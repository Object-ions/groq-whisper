#!/usr/bin/env bash
#
# Optional: install groq-dictate as a background LaunchAgent that starts at
# login and runs invisibly. ADVANCED — see the "Run automatically" section of
# the README for the permission steps, which are fiddly on macOS.
#
# Run from inside the repo folder:  bash install_agent.sh
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
AGENT_DIR="$HOME/.groq-dictate"
VENV="$AGENT_DIR/venv"
PY="$VENV/bin/python"
SCRIPT_DST="$AGENT_DIR/groq_dictate.py"
LABEL="com.groqdictate.agent"
PLIST="$HOME/Library/LaunchAgents/${LABEL}.plist"
UID_NUM="$(id -u)"

command -v uv >/dev/null 2>&1 || { echo "!! uv is required. Install: https://docs.astral.sh/uv/"; exit 1; }

echo "==> Creating $AGENT_DIR"
mkdir -p "$AGENT_DIR" "$HOME/Library/LaunchAgents"

# --- API key -> locked file ---
if [ -f "$AGENT_DIR/key" ]; then
  echo "==> Key file already exists; leaving it."
elif [ -n "${GROQ_API_KEY:-}" ]; then
  printf '%s' "$GROQ_API_KEY" > "$AGENT_DIR/key"
  chmod 600 "$AGENT_DIR/key"
  echo "==> Saved API key from \$GROQ_API_KEY to $AGENT_DIR/key (chmod 600)"
else
  echo "!! GROQ_API_KEY not set and no key file present."
  echo "   Run: printf '%s' 'gsk_YOURKEY' > $AGENT_DIR/key && chmod 600 $AGENT_DIR/key"
  exit 1
fi

# --- copy script to a stable path ---
cp "$SCRIPT_DIR/groq_dictate.py" "$SCRIPT_DST"
echo "==> Copied script to $SCRIPT_DST"

# --- permanent venv (fixed path so macOS permissions stick) ---
echo "==> Building venv at $VENV"
uv venv "$VENV" --python 3.12
echo "==> Installing dependencies"
uv pip install --python "$PY" -r "$SCRIPT_DIR/requirements.txt"

# --- LaunchAgent plist ---
echo "==> Writing $PLIST"
cat > "$PLIST" <<PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>${PY}</string>
        <string>${SCRIPT_DST}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>ProcessType</key>
    <string>Interactive</string>
    <key>LimitLoadToSessionType</key>
    <string>Aqua</string>
    <key>StandardOutPath</key>
    <string>${AGENT_DIR}/agent.log</string>
    <key>StandardErrorPath</key>
    <string>${AGENT_DIR}/agent.err</string>
</dict>
</plist>
PLISTEOF

# --- (re)load it ---
echo "==> Loading agent"
launchctl bootout "gui/${UID_NUM}/${LABEL}" 2>/dev/null || true
launchctl bootstrap "gui/${UID_NUM}" "$PLIST"

cat <<DONE

============================================================
 Agent loaded. It will start at every login.

 Now grant permissions to THIS binary:
     $PY

   1. System Settings > Privacy & Security > Input Monitoring
   2. System Settings > Privacy & Security > Accessibility
      (Accessibility is only needed if AUTO_PASTE = True)
   Add the binary above to BOTH lists and toggle it on.
   Tip: run  open $VENV/bin/  and drag 'python' into each list.

 Then restart the agent:
     launchctl kickstart -k gui/${UID_NUM}/${LABEL}

 Watch it:
     tail -f $AGENT_DIR/agent.log $AGENT_DIR/agent.err

 Uninstall:
     launchctl bootout gui/${UID_NUM}/${LABEL}
     rm $PLIST
============================================================
DONE
