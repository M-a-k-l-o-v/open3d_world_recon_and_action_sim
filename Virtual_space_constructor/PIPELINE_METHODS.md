# Virtual Space Constructor — Media Pipeline Methods Summary

**Project**: this repo (`open3d_world_recon_and_action_sim`), folders `capture/` and `Virtual_space_constructor/` (one subfolder per approach: `per_frame_stack_relative_inverse_depth/`, `multi_view_geometry/`).
**Status**: active. Checkpoint 1 (Renderer). P1 (MiDaS pose drift) finished 23 Nov 2026; P2 (multi-view geometry: VGGT vs COLMAP) under way.
**Purpose of this file**: reference summary of the capture, encoding, compression, format-conversion, geometry and playback methods in the pipeline: for portfolio / interview review, and as a map of what each script does.

**Honest scope note**: this is a 3D reconstruction pipeline, NOT a media-streaming project. Traditional streaming concepts (network protocols, adaptive bitrate, playback buffering) mostly don't apply: everything runs in-process on one machine. The one real stream is the iPhone → Mac Continuity Camera link, which macOS handles. Sections below say where each category applies and where it doesn't.

**What changed since the first version (20 Aug 2026)**: webcam → iPhone 14 over Continuity Camera; guessed focal length (500 px) → calibrated camera (fx = 2235.6 px, 0.44 px error); MiDaS output treated as depth → treated as *inverse* depth with scale and shift fitted on a checkerboard; live-only → video recording (H.264) and offline video reconstruction; ICP from "no movement" → board poses, plus P1's measured comparison of ICP settings; new P2 code for structure-from-motion.

---

## 1. Overall pipeline

```
   ┌──────────────────────────────────────┐
   │ iPhone 14 via Continuity Camera      │  macOS shows the phone as a webcam: 1920x1080, 30 fps, BGR uint8
   │ (capture/camera.py)                  │  phone found via ffmpeg's device list; OpenCV picks the 1080p camera
   └────────┬─────────────────────────────┘
            │  live (image_reconstructor.py)      or      recorded .mp4 (camera.sh → R) → video scripts
            ▼
   ┌──────────────────────────────────────┐
   │ Undistort with the calibrated camera │  cv2.undistort(frame, K, dist) — after this the pinhole model
   │ (capture/camera_calibration.json)    │  holds exactly, so everything downstream uses zero distortion
   └────────┬─────────────────────────────┘
            ▼
   ┌──────────────────────────────────────┐
   │ Checkerboard pose                    │  findChessboardCorners (9x6) → cornerSubPix → solvePnP
   │                                      │  → 4x4 camera-to-board transform; frame skipped if board not fully seen
   └────────┬─────────────────────────────┘
            ▼
   ┌──────────────────────────────────────┐
   │ MiDaS DPT_BEiT_L_512 (MiDaS v3.1)    │  torch.hub, beit512 transform, MPS on the M1, no_grad
   │                                      │  output: relative INVERSE depth, upsampled (bicubic) to 1920x1080
   └────────┬─────────────────────────────┘
            ▼
   ┌──────────────────────────────────────┐
   │ Metric depth from the board          │  least squares: 1/Z = s·prediction + t, using the true depth of each
   │                                      │  board corner (from PnP); Z = 1/(s·p + t), invalid where ≤ 0
   └────────┬─────────────────────────────┘
            ▼
   ┌──────────────────────────────────────┐
   │ Unproject with K                     │  X = (u − cx)·Z/fx,  Y = (v − cy)·Z/fy
   └────────┬─────────────────────────────┘
            ▼
   ┌──────────────────────────────────────┐
   │ Clean up                             │  keep 0.1–10 m; statistical outlier removal (20 nbrs, 2σ);
   │                                      │  2 mm voxel downsampling
   └────────┬─────────────────────────────┘
            ▼
   ┌──────────────────────────────────────┐
   │ Place in the board's frame           │  image recon: board pose, then ICP refine (point-to-point, 2 cm)
   │                                      │  video recon: board pose only, no ICP; frames stacked
   └────────┬─────────────────────────────┘
            ▼
   ┌──────────────────────────────────────┐
   │ Save, then show                      │  .ply rewritten after every capture/frame (Ctrl+C safe);
   │                                      │  Open3D viewer
   └──────────────────────────────────────┘
```

Two experiment scripts sit beside this pipeline (sections 8–9): `p1_baseline_experiment.py` (P1: how far per-frame depth + ICP can go) and `p2_two_view_sfm.py` (P2 warm-up: camera motion and 3D points from two photos, no board, no depth model).

| Script | What it does |
| --- | --- |
| `capture/camera.sh` → `camera.py` | Live iPhone view; SPACE = photo, R = record; waits for and reconnects to the phone |
| `capture/calibrate.py` | Camera matrix K and lens distortion from a checkerboard video |
| `per_frame_stack_relative_inverse_depth/Main.py` → `image_reconstructor.py` | Live capture-by-capture point cloud (SPACE per capture) |
| `per_frame_stack_relative_inverse_depth/video_reconstruction.py` | One point cloud from a whole video, board poses only |
| `per_frame_stack_relative_inverse_depth/icp_drift_probe.py` | Chained ICP (old settings) vs board poses |
| `per_frame_stack_relative_inverse_depth/p1_baseline_experiment.py` | P1: three pose sources (old ICP, best-effort ICP, board) + layering test; `--sweep` for row B settings |
| `multi_view_geometry/p2_two_view_sfm.py` | P2 warm-up: two-view structure-from-motion from scratch, checked against the board and OpenCV |
| `multi_view_geometry/vggt_mac_check.py` | VGGT on this Mac: time, memory and pose accuracy vs frame count (NFR1.4) |

---

## 2. Encoding methods used

Encoding here means the transformations that make data consumable by the next stage, plus the one real video encode (recording).

| Stage | From format | To format | Purpose |
|---|---|---|---|
| Camera capture | iPhone sensor (via Continuity) | BGR uint8 1920x1080 numpy | OpenCV default |
| Recording | BGR uint8 frames | H.264 .mp4 (yuv420p) via ffmpeg pipe | Offline reconstruction, repeatable experiments |
| Photo | BGR uint8 | JPEG, quality 95 | Raw frame kept for every capture, even skipped ones |
| Undistortion | Distorted BGR | Undistorted BGR (same size) | Pinhole model holds exactly |
| Colour-space convert | BGR uint8 | RGB float32 | MiDaS expects RGB |
| MiDaS transform | RGB float32 | Normalised tensor, resized for BEiT-512, on MPS | Model input convention |
| Depth output | Relative inverse-depth tensor | float32 numpy 1920x1080 (bicubic) | Back to camera resolution |
| Metric depth | Relative inverse depth | Depth in metres (float32) | Fitted scale and shift from the board |
| Depth visualisation | float32 | uint8 (NORM_MINMAX) → BGR (COLORMAP_MAGMA) | Human-readable preview |
| Colour for point cloud | uint8 [0,255] | float64 [0,1] | Open3D convention |
| Pixels → rays (P2) | Pixel (u, v) | Direction (x, y, 1) = K⁻¹·(u, v, 1) | Camera-independent geometry |
| Point cloud → disk | In-memory geometry | .ply | Persistence |

No audio pipeline at all.

---

## 3. Compression methods

### 3.1 Video compression — LOSSY (recording)
- ffmpeg `libx264`, preset `veryfast`, `crf 18` (visually near-lossless), `yuv420p`
- crf 18 because compression artefacts hurt feature matching and depth; veryfast keeps 1080p30 encoding real-time on the M1

### 3.2 Voxel downsampling — LOSSY spatial compression
- Open3D `voxel_down_sample`: one point per occupied cube
- **2 mm** in the reconstruction scripts (fine enough to see 15.5 mm board squares at desk scale); **1 cm** for ICP in P1
- Video recon thins each frame *before* outlier removal (outlier removal on 2 million raw points is slow), then again after every merge, which bounds memory

### 3.3 Statistical outlier removal — LOSSY noise removal
- `remove_statistical_outlier(nb_neighbors=20, std_ratio=2.0)`: drops points whose mean distance to their 20 nearest neighbours is more than 2σ above average

### 3.4 Depth-range filtering — LOSSY value-range cut
- `0.1 m < depth < 10 m`, in real metres now (the old 0.5–10 cut was applied to unscaled MiDaS values, so it meant nothing). 0.1 m because desk scenes sit 0.3–1.2 m away
- P1 also drops points more than 1.5 m from the board (far, extrapolated depth)

### 3.5 Subsampling — temporal and spatial
- **Every 10th frame** (3 per second at 30 fps) in the video scripts: neighbouring frames add little
- **Every 4th pixel** of each depth map in P1 (480x270, ~2 mm apart at 1 m), with K scaled to match
- P1 caches its slow step (MiDaS per frame) as compressed NumPy (`.npz`, `np.savez_compressed`) in `captures/cache/`

### Compression NOT used
- No .ply compression; no transform or entropy coding of our own (H.264 does its own DCT + entropy coding inside ffmpeg)

---

## 4. Streaming and network protocols

**Only one stream, and macOS owns it.** Continuity Camera sends the iPhone's camera to the Mac wirelessly; our code just reads it as a local camera.
- The stream can drop out (seen 27 Oct: froze at 1:10). `camera.py` and `image_reconstructor.py` detect a failed read, save any recording, and reconnect when the phone reappears (checked every 2 s via ffmpeg's device list, which doesn't open a camera)
- Continuity also **rotates and re-crops** its stream to keep the picture upright (seen 28 Oct), which breaks "one fixed K". Calibrate with the phone still; prefer Camera-app video for scans
- No client-server split, sockets, RTP/RTSP/HLS/DASH/WebRTC

---

## 5. Codecs

- **Encode**: H.264 via ffmpeg (`libx264`), raw BGR frames piped over stdin. Stopping closes the pipe, so ffmpeg always finishes the file cleanly
- **Decode**: OpenCV `VideoCapture(path)` (FFmpeg backend) in every video script
- **Live input**: whatever AVFoundation negotiates for Continuity Camera; no codec settings in our code
- **Photos**: JPEG (`cv2.imwrite`, quality 95)

---

## 6. Adaptive bitrate

**Not present.** Quality/compute trade-offs are fixed, not adaptive:
- preview drawn at 0.5 scale (960x540) so it fits beside the terminal
- every 10th frame, every 4th depth pixel (section 3.5)
- reconstruction is capture-by-capture (SPACE) or offline from a video, never real-time

---

## 7. Playback pipelines

### 7.1 Live camera preview (OpenCV)
- 960x540 copy of each frame with a status line (REC timer, key hints, "Saved …"). Text is drawn on the preview copy only, so saved photos and video stay clean
- `cv2.waitKey(1)` polls keys; closing the window counts as quit

### 7.2 Depth-map preview (OpenCV)
- MiDaS inverse depth shown in false colour (MAGMA) after each capture

### 7.3 3D scene view (Open3D)
- `o3d.visualization.Visualizer`, updated after each capture (clear → add → reset view), non-blocking via `poll_events` / `update_renderer`
- Final `draw_geometries` viewer after ESC / end of video
- The .ply is saved **before** anything renders, so a crash, Ctrl+C or lost phone can't lose work

### 7.4 Experiment outputs
- Figures as PNG and numbers as CSV in `report_notes/experiments/` (`figures/`, `data/`)

---

## 8. Geometry: camera, board, depth, registration

The technical core, and where most of the original bugs were.

### 8.1 Camera calibration (`capture/calibrate.py`)
- Checkerboard video (9x6 inner corners, 15.5 mm squares) → `cv2.calibrateCamera` → K (fx, fy, cx, cy) and distortion
- Frames the first fit misses by more than 1 px (blur, mid-motion) are dropped and the fit redone
- Current: attempt C on a tripod, **0.436 px** RMS error, fx = fy = 2235.6 px, simple lens model (k1, k2 only), 429 frames. Stored per camera name in `camera_calibration.json`; valid only at 1920x1080

### 8.2 Board pose (ground truth)
- `findChessboardCorners` → `cornerSubPix` (11x11 window) → `solvePnP` on the undistorted frame
- Gives the camera's pose in the board's frame and the true depth of every corner. Accurate to ~0.08° rotation / ~1 mm (P1's PnP-noise estimate)
- Used for metric scale and, in experiments, **for grading only**

### 8.3 Inverse depth → metric depth
- MiDaS is trained to ignore scale and shift, so its output is *relative inverse depth*: 1/Z = s·prediction + t with s, t unknown per frame
- s, t by least squares on the board corners' true depths. P1 fits on every other row of corners (FIT) and checks on the rest (HELD-OUT): median 2.3 / 2.7 mm on the desk video
- Pinned only at the board: away from it each frame's error grows, which is why frames disagree (P1)

### 8.4 Registration
- **Image recon**: each capture is moved into the board's frame, then ICP refines it (point-to-point, 2 cm, 50 iterations, from identity)
- **Video recon**: board poses only, no ICP, so any doubling is MiDaS's depth disagreeing between frames
- **P1 rows** (same per-frame clouds, three pose sources):
  - A, old ICP: point-to-point, fixed 2 cm search, starts from "no movement"
  - B, best-effort ICP: starts from the previous step's motion; coarse search = k × (previous movement + median depth × previous turn), fine = max(1 cm, 3 × depth-fit error); halves coarse → fine; point-to-plane
  - C, board poses: the best this approach can ever do
- **P1 result**: with perfect poses (C), frames still disagree 2.4 mm at the board and 30.5 mm 30–60 cm away. Best-effort ICP (B) loses the board by 27–30 cm at every setting in the sweep. Stacking per-frame depth is the wrong approach, not just badly tuned

### 8.5 P1 scores
- **Corner landing error** (rows A, B): put the true board corners through the row's pose; mean distance from where they really are
- **Line-of-sight layering** (row C): move frame i's points into frame j's camera with the true poses, compare their depth with frame j's own depth at that pixel (bilinear), grouped by distance from the board (0–10, 10–30, 30–60 cm)
- **PnP noise bound**: how much pose noise alone could fake a gap

---

## 9. Geometry: structure-from-motion (P2)

### 9.1 Two-view from scratch (`p2_two_view_sfm.py`)
Camera motion and 3D points from two photos alone. Size is unknown (movement comes out with length 1), fixed afterwards from the board's squares for grading.
1. **Matches**: SIFT (OpenCV) + Lowe's ratio test (0.75)
2. **Rays**: pixels → directions with K⁻¹, so K drops out of the maths
3. **Essential matrix** E (every true match obeys x_bᵀ E x_a = 0): 8-point method with Hartley normalisation (centre and scale the points first), rank 2 enforced; RANSAC, 2000 rounds, 1 px Sampson error. Guesses are scored *before* snapping to a true essential matrix (singular values 1, 1, 0), and the snap happens once at the end
4. **Split E** into rotation R and direction of travel t: 4 candidates, keep the one with the points in front of both cameras
5. **Polish**: least squares on R (rotation vector, exp map) and t against every agreeing match, Huber loss
6. **Triangulate**: linear (DLT) per match, by SVD
7. **Grade**: R and t vs the board; triangulated board corners vs the real board; OpenCV's 5-point `findEssentialMat` + `recoverPose` alongside

Result (23 Nov): matches OpenCV when the camera moves 10–30 cm (rotation 0.3–1.1°, direction 2–4°); fails past ~40° of turn, where SIFT can't match the views. One pair can't cover a walk: next is COLMAP (chains of pairs + bundle adjustment) and VGGT (one network over all frames).

### 9.2 Planned (P2)
- **COLMAP** (`pycolmap`): incremental structure-from-motion + bundle adjustment over all 56 frames; dense depth (multi-view stereo) needs CUDA, so on the 4080
- **VGGT**: one forward pass predicts every frame's camera and depth; off by a single overall scale
- **Score**: P1's line-of-sight layering test on each method's own depth and poses

---

## 10. Format catalogue

| Format | Where |
|---|---|
| BGR uint8 numpy 1920x1080 | Camera output, video decode |
| H.264 .mp4 | `captures/videos/` |
| JPEG | `captures/photos/` |
| JSON | `capture/camera_calibration.json` (K, distortion, board, provenance) |
| RGB float32 numpy / normalised torch tensor | MiDaS input |
| Inverse-depth / depth float32 numpy | MiDaS output, metric depth |
| 4x4 float64 transforms | Camera poses (OpenCV convention: x right, y down, z forward; metres) |
| Nx3 float64 points and colours | Unprojected and triangulated points |
| Open3D PointCloud | Scene representation |
| .ply | `captures/ply/` |
| .npz (compressed NumPy) | P1 cache in `captures/cache/` |
| CSV, PNG | Experiment data and figures in `report_notes/experiments/` |

**File names**: `<what>_<method>_<date_time>[_<detail>]`, e.g. `video_2026-10-28_162722.mp4`, `video-recon_midas_<time>_from-<video>.ply` (convention in `capture/camera.py`). `captures/` is gitignored (personal media, large).

---

## 11. What's NOT here yet

Done since 20 Aug: video file input, video recording (H.264), camera calibration, automatic frame cadence (every 10th frame), metric depth.

Still missing:
- **Multi-view-consistent depth and pose**: per-frame MiDaS can't give one surface (P1). P2 compares VGGT and COLMAP
- **Global bundle adjustment**: chained ICP is greedy and drifts (27 cm in P1). COLMAP provides it
- **Fusion into one surface**: TSDF fusion, Poisson or marching cubes for watertight meshes (needed for physics and Blender/Isaac export). Averaging inconsistent layers would only give a smooth surface in the wrong place, so this comes after consistent depth
- **Object completion**: filling the unseen parts of objects (a trained VSC model; see `TRAINED_ARTIFACTS.md`, project doc)
- **Gaussian splatting**: visual-first rendering. A nice render isn't nice geometry: physics needs surfaces
- **True streaming**: none, and none needed so far

---

## 12. References

- Ranftl, R. et al. (2022). Towards Robust Monocular Depth Estimation: Mixing Datasets for Zero-shot Cross-dataset Transfer. *IEEE TPAMI* 44(3). (MiDaS)
- Birkl, R., Wofk, D. and Müller, M. (2023). MiDaS v3.1: A Model Zoo for Robust Monocular Relative Depth Estimation. arXiv:2307.14460. (DPT_BEiT_L_512)
- Zhang, Z. (2000). A Flexible New Technique for Camera Calibration. *IEEE TPAMI* 22(11). (`calibrateCamera`)
- Besl, P. J. and McKay, N. D. (1992). A Method for Registration of 3-D Shapes. *IEEE TPAMI* 14(2). (ICP, point-to-point)
- Chen, Y. and Medioni, G. (1992). Object Modelling by Registration of Multiple Range Images. *Image and Vision Computing* 10(3). (ICP, point-to-plane)
- Lowe, D. G. (2004). Distinctive Image Features from Scale-Invariant Keypoints. *IJCV* 60(2). (SIFT, ratio test)
- Hartley, R. I. (1997). In Defense of the Eight-Point Algorithm. *IEEE TPAMI* 19(6). (normalisation)
- Nistér, D. (2004). An Efficient Solution to the Five-Point Relative Pose Problem. *IEEE TPAMI* 26(6). (OpenCV's `findEssentialMat`)
- Schönberger, J. L. and Frahm, J.-M. (2016). Structure-from-Motion Revisited. *CVPR*. (COLMAP)
- Wang, J. et al. (2025). VGGT: Visual Geometry Grounded Transformer. *CVPR*.
- Open3D registration docs; PLY format spec; FFmpeg `libx264` docs.

---

**Written**: 2026-08-20 as a reference summary for the archived prototype. **Updated**: 2026-11-23 for the current pipeline (iPhone capture, calibration, metric MiDaS depth, video reconstruction, P1, P2 warm-up).
