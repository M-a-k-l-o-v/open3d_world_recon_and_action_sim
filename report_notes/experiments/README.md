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
| 28 Oct | [video-recon: desk video 1](2026-10-28_video-recon_midas_desk-video-1.md) | 56 frames; desk thickens 6 mm → 38 mm away from the board; 16.5M points, 58% > 1 m away |
