#!/bin/sh
# AI Social: start on macOS or Linux. Finds Python 3.10+ and runs start.py.
cd "$(dirname "$0")" || exit 1
PATH="$PATH:/opt/homebrew/bin:/usr/local/bin:/Library/Frameworks/Python.framework/Versions/Current/bin"
export PATH

for candidate in python3.14 python3.13 python3.12 python3.11 python3.10 python3 python; do
  path=$(command -v "$candidate" 2>/dev/null) || continue
  # macOS: /usr/bin/python3 is Apple's 3.9 (too old) and may pop up an installer.
  if [ "$(uname)" = "Darwin" ] && [ "$path" = "/usr/bin/python3" ]; then
    continue
  fi
  if "$path" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
    exec "$path" start.py "$@"
  fi
done

echo ""
echo "[AI Social] Δεν βρέθηκε Python 3.10 ή νεότερη."
echo "Κατέβασέ την από https://www.python.org/downloads/ , εγκατάστησέ την και ξαναδοκίμασε."
exit 1
