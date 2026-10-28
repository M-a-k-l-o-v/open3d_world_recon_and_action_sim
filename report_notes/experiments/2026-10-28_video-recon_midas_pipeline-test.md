# Video-recon (MiDaS): pipeline test — 28 Oct 2026

**Goal:** check `video_reconstruction.py` runs end to end before recording a real desk video.
**How it works:** every 10th frame (3/s) with the whole board → board pose + scale fit + MiDaS depth → points in the board frame, stacked. **No ICP**, so any doubling in the result is MiDaS disagreeing between frames, not ICP smearing.

## Test run (calibration video, every 30th frame)
| | |
| --- | --- |
| Frames checked / used / skipped | 48 / **4** / 44 (board only visible in the first 4.8 s) |
| Points | 32,389 |
| Time | 37 s (≈5 s per used frame) |

## The real experiment
Done the same day: [desk video 1](2026-10-28_video-recon_midas_desk-video-1.md).
