# Calibration: iPhone 14 via Continuity Camera, attempt B — 28 Oct 2026

**Goal:** real intrinsics (K, distortion) for the 1920×1080 Continuity stream.
**Data:** `captures/videos/iphone 14 Calibration video.mp4` — 47.7 s, 1432 frames, hand-held over the printed board on a table.
**Board:** 9×6 inner corners, **15.5 mm squares** (measured by Marv; matches a ruler photo: ≈305 px/cm, square ≈467 px). First run used 1 mm by mistake — that only affects metre scale, not K.

## Result (saved to `capture/camera_calibration.json`)
| | Value | Should be |
| --- | --- | --- |
| RMS error | **1.66 px** | < 0.5 px |
| fx / fy | 2011.6 / 1990.7 | within a few px (square pixels) |
| cx / cy | 968.2 / 544.0 | — |
| k1, k2, p1, p2, k3 | −0.046, 0.286, −0.002, 0.016, −0.702 | small; k3 this big is suspicious |

## Why it's weak
| Check | Result |
| --- | --- |
| Frames with the whole board | 25 (every 5th checked) / 123 (every frame) — **all within 0.0–4.8 s** |
| Board tilt vs camera | **2–3°** (flat-on) |
| Where the board appears | x 18–692 of 1920 (**left third only**), y 22–926 |
| Board size in image | 422–545 px wide |
| Per-frame error | median 1.50 px, worst 2.25; 12 frames > 2 px |
| Refits on the same data | fx = **2008** (all frames, full model) vs **1807** (simple model, 111 frames) → fx not pinned down |
| Sharpness (Laplacian variance) | median 339, min 141 |

Plus **Continuity auto-rotation**: the stream starts turned 90°, and jumps several degrees between consecutive frames at 31.1 s and 45.0–45.7 s (frame difference 52–56 vs a typical 9.6). Each rotation re-crops the sensor, so the frames don't share one K.

## Learned
- A flat-on board can't separate "longer focal length" from "farther away" — tilt is what pins down fx.
- Continuity Camera is a webcam: it keeps the picture upright by rotating and cropping. For calibration, **keep the phone still in landscape and move the board**.

## Next
Redo on the tripod: phone still in landscape, board 30–60 cm away, tilted ~30° in different directions, swept through all four corners of the frame. Target < 0.5 px with fx ≈ fy.
