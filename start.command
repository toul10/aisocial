#!/bin/sh
# macOS: double-click this file to start AI Social.
cd "$(dirname "$0")" || exit 1
./start.sh
status=$?
if [ "$status" -ne 0 ]; then
  echo ""
  echo "Press Enter to close this window."
  read -r _
fi
exit "$status"
