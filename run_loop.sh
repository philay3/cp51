#!/bin/bash
# Local watched collection loop. Runs a chunk, sleeps, repeats.
# Ctrl-C at any time to stop. Watch the browser and the output.
CHUNK=40
REST=180   # seconds between chunks, gives the portal room
while true; do
  echo "=== chunk start $(date '+%H:%M:%S') ==="
  PYTHONPATH=. .venv/bin/python scripts/collect.py --limit $CHUNK
  code=$?
  if [ $code -ne 0 ]; then
    echo "collector exited non-zero ($code), stopping loop"
    break
  fi
  echo "=== resting ${REST}s, Ctrl-C to stop ==="
  sleep $REST
done
