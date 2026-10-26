# Virtual Space Constructor — Media Pipeline Methods Summary

**Project**: `/Users/yin/Documents/projects/Programming/BAYMAX/archive/Virtual_space_constructor/`
**Status**: Archived pre-BAYMAX pivot (Nov 2025). Foundation for future [open3d_world_recon_and_action_sim](../../future_work/open3d_world_recon_and_action_sim.md).
**Purpose of this file**: Reference summary of the encoding, compression, format-conversion, and playback methods used in the pipeline. Written for portfolio / interview review and for reuse when picking this back up as future flagship work.

**Honest scope note**: this is a live 3D reconstruction pipeline, NOT a media-streaming project. Traditional streaming concepts (network protocols, codecs, adaptive bitrate, playback buffering) mostly don't apply here — the pipeline is fully in-process on a single machine. Sections below note where each category applies vs where the project has no equivalent.

---

## 1. Overall pipeline

```
   ┌─────────────────┐
   │  Webcam         │  OpenCV VideoCapture (default backend, ~30fps)
   │  (cv2)          │  BGR uint8 frame, native camera resolution
   └────────┬────────┘
            │
            ▼
   ┌──────────────────────────────────────┐
   │ Color-space conversion               │  BGR → RGB via cv2.cvtColor
   │ Type promotion                       │  uint8 → float32 for MiDaS
   └────────┬─────────────────────────────┘
            │
            ▼
   ┌──────────────────────────────────────┐
   │ MiDaS transform pipeline             │  dpt_transform: resize, normalize
   │ (torch.hub / intel-isl/MiDaS)        │  numpy → torch.Tensor on MPS/CPU
   └────────┬─────────────────────────────┘
            │
            ▼
   ┌──────────────────────────────────────┐
   │ MiDaS DPT_Large depth prediction     │  Vision Transformer depth head
   │ (torch inference, no_grad)           │  Output: relative depth tensor
   └────────┬─────────────────────────────┘
            │
            ▼
   ┌──────────────────────────────────────┐
   │ Bicubic interpolation                │  Resize depth map to camera res
   │ (torch.nn.functional.interpolate)    │  (4D squeeze/unsqueeze dance)
   └────────┬─────────────────────────────┘
            │
            ▼
   ┌──────────────────────────────────────┐
   │ Depth-to-point-cloud unprojection    │  Pinhole camera model:
   │ (numpy)                              │  X = (u - cx) * Z / fx
   │                                      │  Y = (v - cy) * Z / fy
   │                                      │  Z from depth map
   └────────┬─────────────────────────────┘
            │
            ▼
   ┌──────────────────────────────────────┐
   │ Depth-range filtering                │  Mask depths outside [0.5, 10]
   │ (numpy boolean mask)                 │  Removes noisy near/far outliers
   └────────┬─────────────────────────────┘
            │
            ▼
   ┌──────────────────────────────────────┐
   │ Statistical outlier removal          │  20 neighbors, 2.0 std ratio
   │ (open3d)                             │  Removes scattered noise points
   └────────┬─────────────────────────────┘
            │
            ▼
   ┌──────────────────────────────────────┐
   │ ICP registration                     │  Iterative Closest Point:
   │ (open3d.pipelines.registration)      │  point-to-point align new cloud
   │                                      │  to accumulated scene
   │                                      │  threshold 0.02, max 50 iter
   └────────┬─────────────────────────────┘
            │
            ▼
   ┌──────────────────────────────────────┐
   │ Voxel downsampling                   │  voxel_size = 0.02
   │ (open3d)                             │  Spatial compression by binning
   └────────┬─────────────────────────────┘
            │
            ▼
   ┌──────────────────────────────────────┐
   │ Two live visualization windows       │  cv2.imshow depth map (colored)
   │ (cv2 + open3d)                       │  o3d.Visualizer 3D scene view
   └────────┬─────────────────────────────┘
            │
            ▼
   ┌──────────────────────────────────────┐
   │ .ply serialization on ESC            │  Polygon File Format (ASCII/binary)
   │ (open3d.io.write_point_cloud)        │  Persists final scene to disk
   └──────────────────────────────────────┘
```

---

## 2. Encoding methods used

Encoding here means the transformations that make data consumable by the next stage — not video codecs. This project has several format transitions each with encoding semantics:

| Stage | From format | To format | Purpose |
|---|---|---|---|
| Camera capture | Analog sensor | BGR uint8 numpy array | OpenCV default |
| Color-space convert | BGR uint8 | RGB float32 | MiDaS expects RGB and float |
| Normalization (MiDaS transform) | RGB [0,255] float32 | RGB [0,1] normalized tensor | Model input convention |
| Device transfer | CPU tensor | MPS (or CPU) tensor | Apple Silicon GPU acceleration |
| Depth output | Model logits (variable shape) | uint8 [0,255] via cv2.NORM_MINMAX | For colormap visualization |
| Depth visualization | Grayscale uint8 | BGR uint8 via cv2.COLORMAP_MAGMA | Human-readable false-color depth |
| Color for point cloud | uint8 [0,255] | float64 [0,1] | Open3D convention |
| Point cloud → disk | In-memory geometry | .ply binary/ASCII | Persistence |

No traditional video encoding (no MP4, no H.264/HEVC/AV1). No audio pipeline at all.

---

## 3. Compression methods

Three distinct compression techniques applied for different reasons:

### 3.1 Voxel downsampling — LOSSY spatial compression
- `open3d.geometry.PointCloud.voxel_down_sample(voxel_size=0.02)`
- Bins points into a 3D grid of 2cm cubes, keeps one representative per occupied voxel
- Reduces million-point clouds to manageable sizes without losing overall structure
- Called after every capture merge — bounds memory growth

### 3.2 Statistical outlier removal — LOSSY noise compression
- `remove_statistical_outlier(nb_neighbors=20, std_ratio=2.0)`
- For each point, computes mean distance to 20 nearest neighbors; drops points > 2σ from the batch mean
- Removes scattered noise points that would inflate .ply file size without adding structure

### 3.3 Depth-range filtering — LOSSY value-range compression
- Boolean mask on depth map: `(depth > 0.5) & (depth < 10)`
- Discards depth values MiDaS predicted with low confidence at the extremes
- Effectively caps the point cloud's Z-axis range, removing degenerate outliers before they hit ICP

### Compression NOT used
- No RGB/depth image compression (frames processed live in-memory)
- No .ply compression (Open3D can write compressed binary but default here appears to use uncompressed)
- No transform coding (DCT/DWT), no entropy coding, no quantization beyond what's implicit in dtype conversions

---

## 4. Streaming and network protocols

**None.** The pipeline is entirely single-process, single-machine:
- No client-server split
- No serialization to network
- No RTP/RTSP/HLS/DASH/WebRTC
- No socket I/O
- All frames flow through in-process Python function calls

Camera capture is technically a "stream" in the sense of continuous ~30 FPS delivery from `cv2.VideoCapture(0)`, but there's no network layer — it's a device-driver stream to local memory only.

---

## 5. Codecs

**None directly configured.**
- OpenCV's `VideoCapture` internally uses whatever codec the camera driver + OpenCV backend negotiate (typically YUYV or MJPEG on webcams via AVFoundation on macOS). No explicit codec settings in the code.
- No video file input/output. No `cv2.VideoWriter`. No FFMPEG calls.
- MiDaS operates on decoded raw frames only.

If reused for the future open3d project, video-file input and video-file output would need codec selection (H.264 via cv2.VideoWriter + FourCC, or PyAV, or FFMPEG subprocess). None of that is implemented here.

---

## 6. Adaptive bitrate

**Not present.**

There's ONE commented-out line hinting at manual resolution downscaling for compute-limited machines:
```python
# camera.set(cv2.CAP_PROP_FRAME_WIDTH,640)
# camera.set(cv2.CAP_PROP_FRAME_HEIGHT,360)
```
This would statically drop capture resolution to 360p — NOT adaptive. And it's commented out (not active).

No runtime measurement of processing latency, no dynamic quality adjustment, no ABR ladder. The suggested Readme workaround for compute limits is:
> "have a static render that recaptures say every 10 seconds"
i.e., temporal subsampling as a manual quality/compute trade-off, not adaptive bitrate.

---

## 7. Playback pipelines

Two simultaneous visualization outputs, both in-process:

### 7.1 Live depth-map preview (OpenCV)
- `cv2.imshow("Depth Map", depth_color)` in a window
- `cv2.waitKey(1)` for 1ms per frame poll
- Refresh cadence tied to the manual-capture loop (only shows a new depth map when SPACEBAR is pressed)
- Depth visualized via cv2.COLORMAP_MAGMA false-color

### 7.2 Live 3D scene view (Open3D)
- `o3d.visualization.Visualizer` with GPU-accelerated rendering (Metal on macOS)
- Full 6-DoF orbital camera control via mouse
- Updates after each SPACEBAR capture:
  - `visualizer.clear_geometries()`
  - `visualizer.add_geometry(scene_points)`
  - `visualizer.reset_view_point(True)`
- Continuous non-blocking event loop via `visualizer.poll_events()` + `visualizer.update_renderer()`

### 7.3 Final scan view
- After ESC, `o3d.visualization.draw_geometries([scene_points])` opens a blocking full-scan viewer for inspection before termination.

No playback buffering, no frame-drop logic, no jitter buffer — the manual-capture pattern means capture and playback are gated by user input, so real-time streaming concerns don't arise.

---

## 8. Registration / alignment (not a media category but load-bearing)

Worth noting since it's the technical core of the reconstruction:

- **ICP (Iterative Closest Point) — point-to-point variant**
- `o3d.pipelines.registration.registration_icp` with:
  - `TransformationEstimationPointToPoint()`
  - Threshold: 0.02 (max distance for correspondence match)
  - Convergence: max 50 iterations
  - Initial transformation: 4x4 identity matrix (no prior pose estimate)
- Aligns each new capture into the accumulated scene coordinate frame
- Point-to-point ICP is the simplest ICP variant; point-to-plane would be more accurate with normals but not implemented

Known limitation: without robust initial pose estimation (SLAM tracking or IMU), ICP can fail to converge on large viewpoint changes between captures. Manual-capture mode mitigates by encouraging user to make small viewpoint moves between SPACEBAR presses.

---

## 9. Format catalogue

Complete list of formats present at some pipeline stage:

| Format | Where |
|---|---|
| BGR uint8 numpy | Camera output, OpenCV default |
| RGB float32 numpy | MiDaS input pre-transform |
| RGB [0,1] normalized torch tensor | MiDaS post-transform |
| Depth prediction tensor (variable dtype) | MiDaS raw output |
| Depth float32 numpy | Post-interpolation, pre-3D-conversion |
| uint8 [0,255] grayscale | Depth visualization intermediate |
| BGR uint8 (colormap) | Depth false-color visualization |
| 3D point array float64 (Nx3) | Unprojected point cloud |
| 3D color array float64 [0,1] (Nx3) | Point cloud colors |
| Open3D PointCloud object | Accumulated scene representation |
| .ply (Polygon File Format) | Final on-disk output |

---

## 10. What's NOT here (for future reuse)

If picked up for the future open3d project (video-to-3D reconstruction phase 1), these gaps need filling:

- **Video file input** — currently webcam-only; needs `cv2.VideoCapture(filepath)` or PyAV for arbitrary video sources
- **Codec-explicit video output** — no cv2.VideoWriter with FourCC; needed if the pipeline exports comparison videos
- **Camera intrinsic calibration** — hardcoded `focal_length=500` is a guess; proper calibration via cv2.calibrateCamera would improve reconstruction quality
- **Automatic capture cadence** — currently manual SPACEBAR; needs frame-rate-throttled auto capture
- **Global bundle adjustment** — ICP is greedy pairwise; drift accumulates. A global bundle adjustment (e.g., via g2o or Ceres) would fix drift for longer sequences
- **Mesh reconstruction** — output is point cloud only; no Poisson surface reconstruction, marching cubes, or TSDF fusion (would produce watertight meshes better suited for animation/Blender export)
- **Gaussian splatting** — the modern replacement for point-cloud reconstruction (better visual fidelity, differentiable rendering). Should evaluate switching from point-cloud-only to GS backbone if reactivating this project
- **PhysGaussian integration** — physics-aware Gaussians would bridge to the future project's Phase 2 (agent action simulation in reconstructed scenes)
- **True streaming** — if the future project needs network delivery of reconstructions, need actual streaming layer (WebRTC, WebSocket data channels, or dedicated streaming protocols). None here.

---

## 11. References

- **MiDaS**: [intel-isl/MiDaS](https://github.com/isl-org/MiDaS) — monocular depth estimation via Vision Transformer
- **DPT_Large**: Dense Prediction Transformer variant used in this project (larger, more accurate than DPT_Hybrid or MiDaS_small)
- **ICP**: Point-to-point variant; see Open3D registration pipeline docs
- **PLY format**: Polygon File Format spec — ASCII header + binary/ASCII body for 3D geometry
- **Future project brief**: [future_work/open3d_world_recon_and_action_sim.md](../../future_work/open3d_world_recon_and_action_sim.md)

---

**Written**: 2026-08-20 as reference summary for the archived Virtual_space_constructor project.
