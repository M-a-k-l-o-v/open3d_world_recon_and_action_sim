# Calibration: iPhone 14 via Continuity Camera, attempt C (tripod) — 15 Nov 2026

**Goal:** replace attempt B (1.66 px) with a calibration under 0.5 px, fx ≈ fy.
**Data:** `captures/videos/video_2026-11-15_135032_calibration-attempt-C_tripod.mp4` — 74.8 s, 2243 frames. Phone **still on a tripod in landscape**; the board (15.5 mm squares) moved and tilted in front of it.
**Saved to** `capture/camera_calibration.json` (`iphone14_continuity_1080p`), replacing attempt B.

## Result
| | Attempt B | **Attempt C** |
| --- | --- | --- |
| RMS error | 1.66 px | **0.436 px** |
| fx / fy | 2011.6 / 1990.7 | **2235.6 / 2235.6** (fx = fy enforced) |
| cx / cy | 968.2 / 544.0 | 971.0 / 553.7 |
| Distortion k1, k2 (p1, p2, k3) | −0.046, 0.286 (−0.002, 0.016, −0.702) | **−0.015, −0.096** (0, 0, 0) |
| Frames used | 25 | 429 (433 found, 4 over 1 px dropped) |

## Why it's trustworthy this time
| Check | Attempt B | Attempt C |
| --- | --- | --- |
| Board found | 25 frames, all in 0–4.8 s | 434 / 448 checked, **spread over 0.5–73.2 s** (54–60 per 10 s) |
| Rotation jumps (frame-to-frame difference) | 52–56 | max 39, **none > 40** (phone still) |
| Board tilt | 2–3° | **1–64°** (median 5°) |
| fx: full vs simple lens model | 2008 vs 1807 | **2236 vs 2229** — agree |
| Error on held-out frames (fit on half, test on the other half) | — | full model 0.31 px, simple 0.37 px |

## Choices made (and why)
- **Simple lens model** (fx = fy, radial k1, k2 only). The full model fit the centre 0.06 px better on held-out frames, but predicted lopsided distortion in the image corners (7 / 21 / 10 / 25 px) where the board never went. The simple model gives a symmetric 8–9 px.
- **All frames, not 40.** Four different 40-frame subsets gave RMS 0.85–0.89 px and fx 2272–2294. All 433 frames gave 0.511 px; dropping the 4 frames over 1 px gave 0.436 px, fx 2235.6. `calibrate.py` now does this (about 5 min to run).

## Weak spot
The board stayed central: on average 40 of its 54 corners fell in the middle ninth of the frame. Corner coverage reached x 173–1899 and y 61–909 of 1920×1080. Sharpness was lower than in B (median 108 vs 339; the board was farther away). A 30 s top-up sweeping the board into all four image corners would pin the corner distortion down.

## What it changes
fx moved **+11%** (2011.6 → 2235.6). Everything computed with attempt B (the live desk capture, desk video 1) assumed a wider field of view than the lens has, so those clouds are slightly stretched sideways. Rerunning desk video 1 with this K separates calibration error from MiDaS error.
