# Video-recon (SfM): two-view structure-from-motion from scratch — 23 Nov 2026

**Goal (P2 warm-up):** before running COLMAP, build its core by hand: from two photos alone, recover how the camera turned, which way it moved, and the 3D points. Check it against the board and against OpenCV.
**Data:** desk video 1 (`video_2026-10-28_162722.mp4`), undistorted with calibration C (fx = 2235.6 px).
**Code:** `Virtual_space_constructor/multi_view_geometry/p2_two_view_sfm.py <video> [frame_a frame_b]`. SIFT matches (OpenCV); essential matrix by 8-point + RANSAC, split into R and t, polish, triangulation (NumPy + scipy). OpenCV's `findEssentialMat` (5-point) + `recoverPose` alongside. The board is used only for grading.
**Grades:** rotation error and travel-direction error vs the board's poses; board corners triangulated, sized by the real 15.5 mm squares, compared with the real corners (mean, mm).

## Results
| Frames | Camera moved (board) | Rotation error: mine / OpenCV | Direction error | Matches agreeing (1 px) | Board corners |
| --- | --- | --- | --- | --- | --- |
| 0 → 30 | 1.9 cm, 1.5° | 0.24° / 0.21° | 11.9° / 8.0° | 1061 / 4 | 24 / 13 mm |
| 0 → 50 | 10.6 cm, 4.3° | **0.30° / 0.91°** | 1.8° / 2.6° | 640 / 590 | 63 / 106 mm |
| 0 → 80 | 24.2 cm, 10.0° | 1.08° / 0.83° | 3.7° / 2.3° | 163 / 177 | 29 / 10 mm |
| 200 → 280 | 29.1 cm, 15.8° | **0.38° / 0.45°** | 2.1° / 2.1° | 97 / 99 | 14 / 18 mm |
| 400 → 560 | 67.2 cm, 47.7° | 32° / 10° | 98° / 11° | 31 / 35 | 354 / 31 mm |
| 300 → 400 | 69.9 cm, 39.4° | 179° / 133° | 64° / 71° | 5 / 11 | fails |

## Three bugs on the way (each is a known textbook trap)
1. **No centring and scaling (Hartley normalisation).** Rays have x, y of about 0.2 next to z = 1, so the 8-point equations are badly balanced. On OpenCV's 177 good matches it got 122 to agree, and 134 with normalisation.
2. **Snapping every RANSAC guess to a true essential matrix.** With exactly 8 points the linear fit matches all 8 to 0 px, but snapping to singular values (1, 1, 0) moves them 50–130 px, so good guesses scored as bad (9–51 agreeing). Fix: score guesses as rank-2 matrices and snap once at the end.
3. **The snap isn't the best motion.** Even the final snap left only 9 of ~160 matches within 1 px. Fix: polish R (as a rotation vector, the exp map) and t directly against every agreeing match (least squares, Huber loss). Result: 163 agreeing, 1.1° / 3.7°.

A false lead worth recording: I first blamed the flat desk (the 8-point method breaks down when all points lie on one plane). The matched points actually span 1.1–2.3 m in depth and only 2 of OpenCV's good matches were on the board, so the scene wasn't the problem.

## Learned
- **From scratch matches the library** when the camera moves 10–30 cm: rotation within 0.3–1.1°, direction within 2–4°. The 5-point method (OpenCV, COLMAP) mostly wins by being harder to break, not by being more accurate.
- **Too little movement:** at 1.9 cm, rotation is still fine (0.2°) but the direction of travel is poorly fixed (8–12°). Rays from two nearby cameras cross at a shallow angle, so depth and direction are uncertain. (OpenCV's 4 agreeing matches here look like a RANSAC failure on its side.)
- **Too much movement:** past ~40° of turn, SIFT can't match the views (5–35 matches), and both methods fail. **One pair can't cover the walk**: you need chains of overlapping pairs tied together, which is what COLMAP's incremental reconstruction and bundle adjustment do (and what VGGT does in one network pass).
- **Pose isn't shape:** angles within 0.3° can still put the board corners 14–63 mm off, because a small direction error, triangulated at 1.2 m over a 10–30 cm baseline, moves the 3D points a lot.
- **The board isn't pixel-exact ground truth between frames:** E built from the two board poses fits the matches to a median of 5 px (frames 0 → 80). So differences under ~1° here are within the grader's noise.

## Caveats
- One video, six pairs, one RANSAC seed. 1 px threshold for everything.
- The size is fixed from the board's squares; the shape grade includes the board's own pose noise.
