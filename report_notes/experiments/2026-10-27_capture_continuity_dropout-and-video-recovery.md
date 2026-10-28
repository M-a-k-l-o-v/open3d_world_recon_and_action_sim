# Capture: Continuity Camera dropout + video recovery — 26–27 Oct 2026

**Goal:** get iPhone frames onto the Mac reliably (Continuity Camera + ffmpeg), and record a first calibration video.

## Numbers
| What | Result |
| --- | --- |
| First photo, 1 s warm-up | almost black (17 KB); with 3 s: a real image (55 KB) |
| Raw ffmpeg recording frame rate | reported 1,000,000 fps (variable timestamps) → forced to a constant 30 |
| Calibration recording (27 Oct) | stream **froze at 1:10.5, frame 2117**; ffmpeg ignored `q` and Ctrl+C |
| File left behind | 38.8 MB, no index (moov atom) → unplayable |
| Recovered (rebuilt from raw frames + borrowed encoder settings) | **2081 / 2117 frames, 69.3 s** |
| Frames with the whole board visible | **0 of ~416** checked — phone too close |

## What changed because of it
- Recording moved to Python: OpenCV reads the phone, ffmpeg only encodes. Stopping closes the pipe, so files always finish. → `capture/camera.sh` (live view; SPACE = photo, R = record).
- The view waits for the iPhone and reconnects if it drops.

## Learned
- Continuity Camera drops out (phone picked up, unlocked or out of range). Anything reading it must expect that.
- For calibration the **whole** board must be in frame — close-ups of a few squares are useless.
