# Synthetic: calibration + MiDaS inverse-depth fix — 26 Oct 2026

**Goal:** check the new code against made-up data where the true answer is known, before trusting it on real footage.

## 1. Calibration (`capture/calibrate.py`)
**Setup:** rendered the 9×6-corner board through a made-up camera (fx = fy = 1450, cx 965, cy 535, k1 0.08, k2 −0.15) at 25 random poses, 0.35–0.6 m away.

| | True | Recovered |
| --- | --- | --- |
| fx / fy | 1450 / 1450 | 1449.9 / 1449.9 |
| cx / cy | 965 / 535 | 964.9 / 534.4 |
| RMS error | — | 0.095 px (23 frames used) |
| k1, k2, k3 | 0.08, −0.15, 0 | 0.086, −0.192, 0.078 |

k2 and k3 trade off against each other; the total distortion still fits (0.095 px).

## 2. Inverse-depth fix (`image_reconstructor.py`)
**Setup:** tilted board at 0.39–0.52 m, flat wall at 3.00 m behind. Fake "MiDaS output" = true inverse depth scrambled by scale 0.004 and shift −0.15.

| Check | Result |
| --- | --- |
| Board pose from solvePnP | rotation off by 0.039°, position by 0.16 mm |
| Fitted scale / shift | 0.004 / −0.1471 (true −0.15) |
| Depth fit on the board | 0.1 mm error |
| Wall depth (true 3.00 m) | **2.98 m** |
| Board corners in board frame | worst 0.38 mm off |
| Old code (raw output as depth) | board 618 "units", wall 121 → **near board placed behind the wall** |

## 3. Model switch: DPT_Large → DPT_BEiT_L_512 (M1, MPS)
| Model | Input | Time / frame |
| --- | --- | --- |
| DPT_Large (v3) | 384×672 | 0.86 s |
| DPT_BEiT_L_512 (v3.1, largest) | 512×896 | 4.2 s |

BEiT needs **timm 0.6.13**: 1.0.20 fails (checkpoint keys + renamed internals), 0.6.12 won't import on Python 3.11.

## Learned
- Treating MiDaS output as depth doesn't just mis-scale — it **inverts near and far**.
- Even with perfect inputs, 0.1 mm of fit error on the board becomes **2 cm at 6× the board's distance**. The shift is fitted over a narrow depth range and then extrapolated.
