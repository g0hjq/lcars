#!/bin/bash
# Stop the LCARS display and stop it starting when the Pi boots.
# ./enable_service.sh turns it back on.

sudo systemctl disable --now lcars || exit 1

# A copy started by hand (python3 lcars.py) isn't part of the service, so stop that too
pkill -f "python3? .*lcars\.py" && echo "Stopped lcars.py that was run by hand"

echo "LCARS stopped, and won't start at boot"
