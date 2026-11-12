#!/bin/bash
# Start the LCARS display now, and every time the Pi boots.
# ./disable_service.sh turns it off again.

# Only one program can use the screen, so stop a copy started by hand (python3 lcars.py) first
pkill -f "python3? .*lcars\.py" && echo "Stopped lcars.py that was run by hand" && sleep 1

sudo systemctl enable --now lcars || exit 1

echo "LCARS started, and will start at boot"
