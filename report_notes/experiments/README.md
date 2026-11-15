# Experiments

One note per experiment: goal → setup → numbers → what we learned. Newest last.

**File names:** `<date>_<kind>_<method>_<topic>.md`, where *kind* is one of:
`synthetic` (made-up data with a known answer) · `capture` (phone / recording) · `calibration` ·
`image-recon` (Main.py, single frames) · `video-recon` (video_reconstruction.py, many frames).
Data files in `captures/` follow the same idea (convention in `capture/camera.py`).

| Date | Note | Headline |
| --- | --- | --- |
| 26 Oct | [synthetic: calibration + inverse-depth fix](2026-10-26_synthetic_midas_calibration-and-inverse-depth-fix.md) | Fix recovers a 3.00 m wall as 2.98 m; old code put the near board *behind* the wall |
| 27 Oct | [capture: Continuity dropout + video recovery](2026-10-27_capture_continuity_dropout-and-video-recovery.md) | Stream froze at 1:10; 2081 / 2117 frames recovered; 0 usable for calibration |
| 28 Oct | [calibration: iPhone 14 Continuity, attempt B](2026-10-28_calibration_continuity_iphone14-attempt-B.md) | RMS 1.66 px — board seen from one pose only; Continuity auto-rotates. Redo on tripod |
| 28 Oct | [image-recon: offline desk frames](2026-10-28_image-recon_midas_offline-desk-flatness.md) | Table flat to 1 mm (median) at board distance; old 0.5 m filter kept 0% |
| 28 Oct | [image-recon: live desk at ~1 m](2026-10-28_image-recon_midas_live-desk-1m.md) | 754k points; right from the camera's view, 2.5D shell from others |
| 28 Oct | [video-recon: pipeline test](2026-10-28_video-recon_midas_pipeline-test.md) | Works end to end (4 frames fused) |
| 28 Oct | [video-recon: desk video 1](2026-10-28_video-recon_midas_desk-video-1.md) | 56 frames; desk thickens 6 mm → 38 mm away from the board; stacks layers instead of fusing |
| 15 Nov | [video-recon: chained ICP vs reference poses](2026-11-15_video-recon_midas_icp-drift-vs-reference.md) | ICP drifts 11 cm in 3 s, up to 90 cm / 64°; with perfect poses the desk still stacks 3 → 46 mm. Both failures real |
| 15 Nov | [calibration: attempt C, tripod](2026-11-15_calibration_continuity_iphone14-attempt-C-tripod.md) | **0.436 px**, fx = fy = 2235.6 (B: 1.66 px, fx 2011.6) — simple lens model, all frames |
| 15 Nov | [video-recon: P1 baseline, three pose sources](2026-11-15_video-recon_midas_p1-baseline-three-rows.md) | Perfect poses: frames agree 2.4 mm at the board, 30 mm at 30–60 cm (pose noise ≤ 1.6). Best-effort ICP: 15 vs 92 mm at frame 10, still lost by 27 cm |

## Why the old prototype failed (MiDaS round, closed 29 Oct)
1. **MiDaS output used as depth.** It's inverse depth with unknown scale and shift, so near and far were swapped (synthetic: board 618 vs wall 121 "units").
2. **Focal length guessed** (500 px; calibration says ~1800–2000).
3. **Thresholds in meaningless units.** The 0.5–10 "m" filter and 2 cm ICP / voxel sizes were applied to unscaled values.
4. **ICP from identity** between views with no pose estimate, so captures from different spots couldn't line up. Measured 15 Nov: chained ICP drifts 11 cm within 3 s, up to 90 cm / 64°.
5. **Even with 1–4 fixed, MiDaS is per-frame.** Frames disagree away from the reference (desk 6 → 38 mm thick), and stacking makes layers, not a scene. Next: multi-view-consistent depth/pose (VGGT-class) + real fusion.
