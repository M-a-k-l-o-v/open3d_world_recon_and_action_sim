# Video-recon (VGGT): does it run on the M1 Mac? — 23 Nov 2026

**Goal (NFR1.4):** does VGGT-1B run on this Mac (Apple M1, 16 GB), how do time and memory grow with frame count, and are its camera poses right?
**Data:** desk video 1, the same 56 cached frames as P1 (undistorted, calibration C). N evenly spaced frames per run.
**Code:** `Virtual_space_constructor/multi_view_geometry/vggt_mac_check.py`. VGGT commit `a288dd0`, weights `facebook/VGGT-1B`, PyTorch 2.9 on MPS, 518 × 294 px input.
**Data file:** `data/vggt_mac-check_m1-16gb.csv`. **Point clouds:** `captures/ply/video-recon_vggt_2026-11-23_*_from-video_2026-10-28_162722_<N>-frames.ply` (one per run; VGGT's own cameras; least-confident 50% of points dropped, VGGT's default)
**Accuracy** is checked against the board poses, using only scale-free measures (VGGT's output is off by one overall scale):
- rotation error: the relative rotation between frames i and j, VGGT vs board
- direction error: the direction the camera moved between frames i and j, VGGT vs board

## Result
| Frames | Time | Peak GPU memory | Rotation error (median / p90) | Direction error (median) |
| --- | --- | --- | --- | --- |
| 2 | 4 s | 4.5 GB | 0.58° / 0.58° | 0.7° |
| 4 | 8 s | 6.7 GB | 0.91° / 1.23° | 0.9° |
| 8 | 19 s | 11.8 GB | 0.66° / 0.98° | 0.7° |
| 16 | 55 s | 11.8 GB | 0.61° / 1.00° | 0.9° |
| 24 | 113 s | 12.9 GB | 0.60° / 0.97° | 0.8° |
| **32** | **188 s** | **13.2 GB** | **0.55° / 0.91°** | **0.7°** |
| 40, 56 | out of memory (40 also in a fresh process) | | | |

Times vary ~25% run to run with whatever else is open (an earlier identical run: 32 s at 8 frames, 240 s at 32); accuracy was identical. **Limit on this Mac: 32 frames per pass** (12.7 GB GPU budget). While it runs, macOS swaps other apps out (8.4 GB swap seen at 32 frames), so the Mac is sluggish. Accuracy holds at ~0.6° as frames are added. Compare best-effort ICP in P1: 6.5° median.

## What it took to get past 4 frames
Out of the box, it ran out of memory at 8 frames. Three changes, none of which change what VGGT computes:

| Change | Why |
| --- | --- |
| Keep only the camera and depth heads | The point head repeats depth + camera; tracking isn't used |
| Attention in chunks of queries | On MPS, PyTorch builds the whole attention table at once: 16 heads × (782 patches × frames)² entries, which is 10 GB in one buffer at 16 frames (that's the allocation that crashed). Chunking gives the same answer a slice at a time |
| Main network (aggregator) in float16, converted on the CPU | Halves the weights (5.4 → 2.9 GB) and the 24 stored layer outputs. Converting on the GPU left the float32 copy cached (+1.6 GB). Heads stay float32: the depth head hard-codes float32 |

float16 costs nothing measurable. On 4 frames, all-float32 gave 0.91° / 1.23° / 0.8°, the same as float16.

## Learned
- **VGGT works on the M1 and its poses are right:** ~0.6° rotation error across 32 frames, in one pass, with no board and no ICP.
- **The whole desk video (56 frames) doesn't fit in one pass.** Options:
  - every other frame (28)
  - smaller input images
  - overlapping chunks of ≤ 32 frames, aligned afterwards
  - the RTX 4080 machine
- **Time grows faster than frame count** (55 s at 16 → 188 s at 32), because every frame attends to every other.

## Caveats
- Accuracy is scale-free only; depth quality isn't scored here (that's P2 proper).
- One video. The board poses are the reference, accurate to ~0.08° (P1's PnP noise).
- Peak memory is the MPS driver's total, sampled every 50 ms, so short spikes may be missed.
