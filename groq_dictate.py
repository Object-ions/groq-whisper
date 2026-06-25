# /// script
# requires-python = ">=3.12"
# dependencies = ["groq", "sounddevice", "numpy", "scipy", "pynput", "pyperclip"]
# ///
"""
groq-dictate — push-to-talk speech-to-text for macOS, powered by Groq Whisper.

Hold the record key, speak, release. The audio is sent to Groq, transcribed,
and pasted straight into whatever text field is focused (browser, editor, chat).

Run with uv (recommended):   uv run groq_dictate.py
Or inside a venv:            python groq_dictate.py
Quit a manual run:          Ctrl-C
"""

import os
import sys
import tempfile
import threading
import time

import numpy as np
import pyperclip
import sounddevice as sd
from scipy.io import wavfile
from pynput import keyboard
from groq import Groq

# ============================ CONFIG ============================
# The push-to-talk key. Key.alt = the Option key (either side).
# If holding it does nothing, run keyprobe.py to see what your key
# reports as, then set it here (e.g. keyboard.Key.alt_r, Key.ctrl_r).
RECORD_KEY = keyboard.Key.alt

# Groq model. "whisper-large-v3-turbo" is fast + multilingual.
# Use "whisper-large-v3" for slightly higher accuracy at lower speed.
MODEL = "whisper-large-v3-turbo"

# Pin a language ("en", "he", "es", ...) for better accuracy/latency,
# or leave None to auto-detect (good for mixed-language use).
LANGUAGE = None

# True  = auto-paste into the focused field (needs Accessibility permission).
# False = copy to clipboard only; you paste manually with Cmd+V.
AUTO_PASTE = True

SAMPLE_RATE = 16000  # Whisper's native rate; leave as-is.
# ===============================================================


def _load_api_key():
    """Prefer the GROQ_API_KEY env var; fall back to ~/.groq-dictate/key."""
    key = os.environ.get("GROQ_API_KEY")
    if key:
        return key.strip()
    keyfile = os.path.expanduser("~/.groq-dictate/key")
    if os.path.exists(keyfile):
        with open(keyfile) as f:
            return f.read().strip()
    return None


API_KEY = _load_api_key()
client = Groq(api_key=API_KEY) if API_KEY else None

_frames = []
_stream = None
_recording = False
_lock = threading.Lock()


def start_recording():
    global _stream, _frames, _recording
    _frames = []
    _recording = True
    _stream = sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="int16",
        callback=lambda indata, *_: _frames.append(indata.copy()),
    )
    _stream.start()
    print("\u25cf recording\u2026", flush=True)


def stop_and_transcribe():
    global _stream, _recording
    _recording = False
    if _stream is not None:
        _stream.stop()
        _stream.close()
        _stream = None

    if not _frames:
        print("(no audio captured \u2014 hold the key a beat longer)", flush=True)
        return

    audio = np.concatenate(_frames, axis=0)

    # Drop stray taps / silence before hitting the API.
    # A quick double-tap of Option captures a sub-second, near-silent clip,
    # and Whisper hallucinates "Thank you." on empty audio - so skip those.
    duration = len(audio) / SAMPLE_RATE
    rms = float(np.sqrt(np.mean(np.square(audio.astype(np.float64)))))
    if duration < 0.4 or rms < 50:
        print(f"(skipped - {duration:.2f}s, level {rms:.0f})", flush=True)
        return

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        path = tmp.name
    wavfile.write(path, SAMPLE_RATE, audio)

    print("\u2026 transcribing", flush=True)
    kwargs = dict(
        file=(os.path.basename(path), open(path, "rb").read()),
        model=MODEL,
        response_format="text",
    )
    if LANGUAGE:
        kwargs["language"] = LANGUAGE

    try:
        text = client.audio.transcriptions.create(**kwargs)
    except Exception as exc:  # noqa: BLE001
        print(f"!! transcription failed: {exc}", flush=True)
        os.remove(path)
        return
    os.remove(path)

    text = (str(text) or "").strip()
    if not text:
        print("(empty transcript)", flush=True)
        return

    pyperclip.copy(text)
    print(f"\u2192 {text}\n", flush=True)

    if AUTO_PASTE:
        time.sleep(0.05)
        kb = keyboard.Controller()
        with kb.pressed(keyboard.Key.cmd):
            kb.press("v")
            kb.release("v")


def on_press(key):
    with _lock:
        if key == RECORD_KEY and not _recording:
            start_recording()


def on_release(key):
    with _lock:
        if key == RECORD_KEY and _recording:
            stop_and_transcribe()


def main():
    if client is None:
        sys.exit(
            "No Groq API key found.\n"
            "Set it with:  export GROQ_API_KEY='gsk_...'\n"
            "or write it to ~/.groq-dictate/key"
        )
    print(
        f"Ready. Hold {RECORD_KEY} to record, release to transcribe. Ctrl-C to quit.",
        flush=True,
    )
    with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
        listener.join()


if __name__ == "__main__":
    main()
