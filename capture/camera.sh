#!/bin/bash
# camera.sh — open a live view of the iPhone camera on the Mac.
#   SPACE = photo (captures/photos/)   R = start/stop recording (captures/videos/)   Q = quit
#
# Uses macOS Continuity Camera (the iPhone shows up as a webcam). The work is in capture/camera.py.
# Before capturing for reconstruction: Control Center → Video Effects → turn off Center Stage
# and Portrait — they crop and zoom from frame to frame, which corrupts camera pose.
#
# Run from the project folder:   bash capture/camera.sh
# Needs once:  brew install ffmpeg

cd "$(dirname "$0")/.."            # work from the project folder, wherever this is run from
exec Virtual_space_constructor/live3d_env/bin/python capture/camera.py
