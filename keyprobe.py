# /// script
# requires-python = ">=3.12"
# dependencies = ["pynput"]
# ///
"""
keyprobe — find out how your keyboard reports a given key.

Run with:  uv run keyprobe.py
Then press the key you want to use for push-to-talk. Whatever it prints
(e.g. Key.alt, Key.alt_r, Key.ctrl_r) is the value to set as RECORD_KEY
in groq_dictate.py. Press Esc to quit.
"""

from pynput import keyboard


def on_press(key):
    print(f"PRESS    {key!r}", flush=True)


def on_release(key):
    print(f"RELEASE  {key!r}", flush=True)
    if key == keyboard.Key.esc:
        return False


print("Press the key you want for push-to-talk. Press Esc to quit.")
with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
    listener.join()
