#!/bin/bash
# Double-click from Finder to play Radio Paradise on the Synfonisk.
set -euo pipefail

ROOT="/Users/mark/Documents/Development/_Repositories/Adintegra/sonos-control"
SONOS="$ROOT/.venv/bin/sonos"
CONFIG="$ROOT/stations.yaml"

if [[ ! -x "$SONOS" ]]; then
  osascript -e 'display dialog "sonos CLI is not installed. Run: pip install -e . in the sonos-control repo." buttons {"OK"} default button 1 with icon stop' >/dev/null
  exit 1
fi

if ! "$SONOS" --config "$CONFIG" play rp; then
  osascript -e 'display dialog "Could not start Radio Paradise on the Synfonisk." buttons {"OK"} default button 1 with icon stop' >/dev/null
  exit 1
fi

osascript -e 'display notification "Radio Paradise is playing on Symfonisk" with title "Sonos"' >/dev/null

# Close the Terminal window that macOS opens for .command files.
if [[ "${TERM_PROGRAM:-}" == "Apple_Terminal" ]]; then
  osascript -e 'tell application "Terminal" to close (every window whose name contains "Radio Paradise")' >/dev/null 2>&1 || true
fi
