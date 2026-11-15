#!/bin/bash
# Restart the LCARS display, so that it picks up changes to the program or its settings.
# The service waits 10 seconds before it starts (see lcars.service), so the screen is blank
# for a little while. ./enable_service.sh starts it if it isn't running at all.

# Only one program can use the screen, so stop a copy started by hand (python3 lcars.py) first
pkill -f "python3? .*lcars\.py" && echo "Stopped lcars.py that was run by hand" && sleep 1

sudo systemctl restart lcars || exit 1

echo "LCARS restarting (it waits 10 seconds before it starts)"
echo "To watch what it prints: journalctl -u lcars -f"
