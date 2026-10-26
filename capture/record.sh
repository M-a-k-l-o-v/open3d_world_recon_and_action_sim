#!/bin/bash
# record.sh — record video from the iPhone camera to captures/videos/. Press q to stop.
#
# How it works: macOS Continuity Camera makes the iPhone show up as a webcam.
# ffmpeg finds the camera with "iPhone" in its name and records 1080p at 30 fps
# (H.264, high quality) until you press q in this Terminal window.
#
# Run from the project folder:   bash capture/record.sh
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

mkdir -p captures/videos
OUT="captures/videos/$(date +%Y-%m-%d_%H%M%S).mp4"

echo "Recording to $OUT — press q to stop."
# crf 18 = visually near-lossless; small compression artefacts hurt reconstruction.
ffmpeg -hide_banner -loglevel error -stats -f avfoundation -framerate 30 -video_size 1920x1080 -pixel_format nv12 \
  -i "$CAMERA:none" -fps_mode cfr -r 30 -c:v libx264 -crf 18 -pix_fmt yuv420p "$OUT"

echo "Saved $OUT"
