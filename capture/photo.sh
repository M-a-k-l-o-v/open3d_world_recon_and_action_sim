#!/bin/bash
# photo.sh — take one photo with the iPhone camera and save it to captures/photos/.
#
# How it works: macOS Continuity Camera makes the iPhone show up as a webcam.
# ffmpeg finds the camera with "iPhone" in its name, waits 3 seconds so the camera connects, exposure
# and focus settle, then saves a single frame as a JPEG.
#
# Run from the project folder:   bash capture/photo.sh
# Needs once:  brew install ffmpeg   (and allow Terminal to use the camera when asked)

set -e
cd "$(dirname "$0")/.."            # work from the project folder, wherever this is run from

if ! command -v ffmpeg >/dev/null; then
  echo "ffmpeg is not installed. Run:  brew install ffmpeg"
  exit 1
fi

# Find the iPhone's number in ffmpeg's camera list (skip the "Desk View" camera).
CAMERA=$(ffmpeg -hide_banner -f avfoundation -list_devices true -i "" 2>&1 \
  | sed -n '/video devices/,/audio devices/p' | grep -i iphone | grep -vi "desk view" \
  | head -n 1 | sed -E 's/.*\] \[([0-9]+)\] .*/\1/')
if [ -z "$CAMERA" ]; then
  echo "No iPhone camera found. Is the iPhone nearby, locked, and on the same Apple ID?"
  exit 1
fi

mkdir -p captures/photos
OUT="captures/photos/$(date +%Y-%m-%d_%H%M%S).jpg"

# -ss 3 after the input drops the first 3 seconds of frames (connect + exposure warm-up).
ffmpeg -hide_banner -loglevel error -f avfoundation -framerate 30 -video_size 1920x1080 -pixel_format nv12 \
  -i "$CAMERA:none" -ss 3 -frames:v 1 -q:v 2 "$OUT"

echo "Saved $OUT"
