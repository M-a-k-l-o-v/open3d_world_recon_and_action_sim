# Image-recon (MiDaS): offline desk frames, flatness — 28 Oct 2026

**Goal:** first run of the fixed pipeline on real frames, before a live session.
**Setup:** two frames (0.5 s, 2.5 s) from the calibration video: board lying on a table, phone overhead. K from attempt B; board 15.5 mm. The real scene is a **flat table**, so every point should land on the board's plane (height 0).

## Numbers
| | Frame 0.5 s | Frame 2.5 s |
| --- | --- | --- |
| Camera to board | 0.38 m | 0.39 m |
| MiDaS (BEiT-L-512) | 4.2 s | 4.4 s |
| Depth fit error on board | 0.4 mm | 0.5 mm |
| Depth range | 0.35–0.37 m | 0.35–0.37 m |
| Height off the table plane | **median 1 mm, 90% within 3 mm** | same |
| Pixels kept by the old 0.5–10 m filter | **0%** | 0% |

**Startup:** a cold start took 574 s; warm it's ~10 s (torch 0.9 s, open3d 1.5 s, BEiT load 6.8 s, move to GPU 0.4 s). A cold open3d import alone was 91 s vs 2 s warm.

## Changed because of it
- Near-depth filter 0.5 m → **0.1 m** (desk scenes sit 0.3–0.4 m away).
- Voxel size 2 cm → **2 mm** (board squares are 15.5 mm).

## Caveat
Best case: the whole frame was at the board's own distance, so nothing was extrapolated. It shows the fix works, not how accurate it is away from the board.
