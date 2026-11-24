# Computer vision and 3D reconstruction: key terms

A companion to the ML training-loop notes (21 Nov). It goes from basics to the terms P2 and the later checkpoints will use.

**Marks**
- ✓ = you've already used this in the project. The note in brackets says where. Read it to check that the definition matches what you did.
- ★ = comes up in P2 (VGGT vs COLMAP). Learn these next.
- ◆ = later checkpoints (renderer output, simulator, planner). It's enough to recognise these for now.
- No mark = basic vocabulary that papers assume you know.

---

## The one chain to keep in your head

Almost everything below is one step in this chain:

```
pixel (u,v) --K⁻¹--> ray in the camera's frame --× depth Z--> 3D point in the camera's frame --pose [R|t]--> point in the world
```

- **Depth** is the missing number. One image only gives you the ray.
- You can get depth from a network (MiDaS, P1), from two views (triangulation, the P2 warm-up), or from many views solved together (SfM + bundle adjustment, P2).
- **Pose** places each camera. You can get it from a known object (board + PnP, P1), from matches between views (essential matrix, the P2 warm-up), or from everything solved jointly (P2).
- P1 found that getting depth and pose **separately per frame** leaves the views disagreeing. P2 tests methods that solve them **together** across frames.

---

## Part A — Basics

### A1. Images

| Term | Meaning |
|---|---|
| Pixel | One sample of the image grid. It's at position (u, v): u = column (x, right), v = row (y, **down**). The origin is top-left. |
| Resolution | Width × height in pixels (yours: 1920×1080). |
| Channels ✓ | The values per pixel: 3 for colour, 1 for grey. **OpenCV stores BGR, not RGB** (you convert before MiDaS). |
| dtype ✓ | uint8 (0–255) for images, float32 for maths. Open3D wants colours as floats in 0–1. |
| Intensity / grayscale | Brightness only. Most feature detectors (e.g. SIFT) work on greyscale. |
| Interpolation ✓ | Estimating values between pixels when resizing: nearest, bilinear, bicubic. You upsample MiDaS output with bicubic. |
| Convolution / kernel / filter | Slide a small weight grid over the image and take weighted sums. Blur, edge detection and every CNN layer work this way. |
| Image gradient / edge | How fast intensity changes. Edges and corners (big change in two directions) are where features come from. |
| Gaussian blur | Smoothing with a bell-shaped kernel. It removes noise and is used to build **scale space** (SIFT). |
| Field of view (FOV) | The angle the camera sees. It's set by focal length and sensor width: FOV = 2·atan(W / 2fx). |
| Motion blur | Smearing while the camera moves during exposure. It kills features, so move slowly when capturing. |
| Rolling shutter | Phones read the sensor row by row, so during fast motion the top and bottom of a frame come from slightly different moments. COLMAP assumes a global shutter (all rows at once). This is another reason to move slowly. |
| Auto-focus / stabilisation | On a phone, focusing slightly changes the focal length. Video stabilisation shifts and crops the frame, which moves cx, cy. Either one breaks "one fixed K". You saw this with Continuity's re-cropping. Lock focus and exposure for scans. |

### A2. Coordinates and transforms

| Term | Meaning |
|---|---|
| Frame (coordinate frame) | An origin plus three axes. Common ones: **world**, **camera**, **image**, **board** ✓ (P1 used the board as the world). |
| OpenCV camera convention ✓ | x right, y down, z forward (into the scene). |
| OpenGL / Blender / many viewers | x right, y **up**, z **backward**. Converting between the two flips y and z. This is the most common bug when exporting to Blender or Isaac ◆. |
| Homogeneous coordinates ✓ | Append a 1: (x, y) → (x, y, 1), (X, Y, Z) → (X, Y, Z, 1). This lets one matrix multiply do rotation and translation together, and lets you treat scale as "divide by the last number". |
| Rotation matrix R ✓ | A 3×3 matrix whose columns are orthonormal and whose det = +1. All of them together form **SO(3)**. A rotation has 3 degrees of freedom. |
| Translation t ✓ | A 3-vector shift. |
| Pose / rigid transform ✓ | R and t together. It's written [R\|t] or as a 4×4 matrix [[R, t], [0 0 0 1]]. All of them form **SE(3)**. 6 DoF. |
| Degrees of freedom (DoF) | How many independent numbers something has. Pose: 6. Pose + scale: 7. Essential matrix: 5. |
| World-to-camera vs camera-to-world ✓ | These are two directions of the same pose. One is the inverse of the other: R⁻¹ = Rᵀ, t' = −Rᵀt. **Always check which one a library gives you.** solvePnP and COLMAP give world-to-camera. You turned the board pose into camera-to-board. |
| Camera centre | Where the camera sits in the world: C = −Rᵀt when [R\|t] is world-to-camera. It's not t itself, which is a classic mistake. |
| Euler angles | Three successive turns (yaw, pitch, roll). They're easy to read but suffer from **gimbal lock**, and the order matters. Avoid them for maths. |
| Axis-angle / rotation vector / Rodrigues ✓ | A 3-vector whose direction is the axis and whose length is the angle. The **exp map** turns it into R. You polished R this way in the P2 warm-up. It's good for optimisation because it has exactly 3 numbers and no constraints. |
| Quaternion ★ | 4 numbers (w, x, y, z) with unit length. It's smooth and compact. **COLMAP stores poses as world-to-camera quaternion + t.** |
| Rotation error (geodesic) ✓ | The angle of R_estᵀ·R_true: θ = arccos((trace − 1)/2). This is how you got "0.30°". |
| Similarity transform, Sim(3) ★ | A pose plus one scale, 7 DoF. You need it to line up an SfM result (arbitrary scale) with the board (metres). |
| Homography H | A 3×3 projective map from one plane to another, or between two views when the camera only rotates. 8 DoF. |

### A3. The camera model

| Term | Meaning |
|---|---|
| Pinhole model ✓ | All rays pass through one point (the optical centre). It's an ideal model that holds once you've undistorted the image. |
| Image plane | The plane at distance f in front of the centre where the image forms. |
| Optical axis | The camera's z-axis, the line straight out of the lens. |
| Focal length fx, fy ✓ | In **pixels**, not mm. Yours: 2235.6 px. fx = fy for square pixels. |
| Principal point cx, cy ✓ | Where the optical axis hits the image. It's near the centre but not exactly. |
| Intrinsics K ✓ | [[fx, 0, cx], [0, fy, cy], [0, 0, 1]]. These describe the camera itself and don't change as it moves (unless you resize, crop or refocus). **Resizing scales K. Cropping shifts cx, cy** ✓ (you scaled K for every 4th pixel). |
| Extrinsics ✓ | The pose [R\|t]: where the camera is. It changes every frame. |
| Projection ✓ | 3D → pixel: x_cam = R·X + t, then u = fx·x/z + cx and v = fy·y/z + cy. Dividing by z is the **perspective division**. It's why far things look small, and why depth is lost. |
| Projection matrix P ★ | P = K[R\|t], 3×4. It does the whole 3D → pixel step in one multiply (homogeneous). |
| Unprojection / back-projection ✓ | Pixel + depth → 3D: X = (u − cx)·Z/fx, Y = (v − cy)·Z/fy. This is what you do to MiDaS depth. |
| Normalised image coordinates / ray ✓ | K⁻¹·(u, v, 1) = (x, y, 1). It's the pixel with the camera removed, a direction in the camera's frame. Essential-matrix maths works on these. |
| Lens distortion ✓ | Real lenses bend straight lines. **Radial** distortion (k1, k2, k3) is barrel or pincushion. **Tangential** distortion (p1, p2) comes from a tilted lens. |
| Undistortion ✓ | Resampling the image so the pinhole model holds. |
| Camera calibration ✓ | Estimating K and the distortion from many views of a known pattern (Zhang's method, the method behind cv2.calibrateCamera). |
| Reprojection error ✓ | The pixel distance between where a feature was seen and where your model projects its 3D point. It's **the** standard error in geometric vision. Your calibration: 0.44 px. |
| Self-calibration / auto-calibration ★ | Estimating K from the images alone, without a pattern. COLMAP and VGGT both do this. P2 can compare their K with your calibrated one. |

### A4. Depth

| Term | Meaning |
|---|---|
| Depth Z ✓ | The distance along the optical axis, not the straight-line distance from the camera (that's **range**). They differ at the image edges. |
| Depth map ✓ | One depth value per pixel. |
| Inverse depth ✓ | 1/Z. Many networks predict it because it's well behaved for far points (→ 0, not ∞). MiDaS outputs this. |
| Disparity ✓ | In stereo, how far a point shifts between left and right images: d = f·B/Z. It's proportional to inverse depth, so the two words are often used loosely for each other. |
| Metric vs relative depth ✓ | Metric depth is in metres. Relative depth is only correct up to an unknown **scale and shift** (MiDaS). Metric models: Depth Pro, Metric3D, UniDepth, ZoeDepth. |
| Scale ambiguity ✓ ★ | One camera can't tell a small, near scene from a large, far one. This affects monocular depth, the essential matrix (t has length 1) and SfM. Something known (board, IMU, metric model) must fix the scale. |
| Affine-invariant / scale-and-shift-invariant ✓ | A training loss that ignores scale and shift (MiDaS). It makes the model robust across datasets but leaves every frame needing its own fit. That's P1's layering cause. |
| Stereo / baseline ✓ | Two cameras a known distance B apart. Depth comes from triangulation. A larger baseline gives better depth but harder matching. You met this as "too little movement → poor direction". |
| Active depth sensors | **Structured light** (projected pattern), **time-of-flight / LiDAR** (light travel time). The iPhone 14 Pro has LiDAR. The plain 14 doesn't. Face ID uses structured light. |
| RGB-D | Colour plus a depth channel per pixel (Kinect, RealSense, iPhone LiDAR). |
| Confidence map ★ | A per-pixel "how sure" score. VGGT outputs one with its depth and points. Use it to drop bad points instead of hand thresholds. |

### A5. 3D data

| Term | Meaning |
|---|---|
| Point cloud ✓ | A set of 3D points, optionally with colours and normals. It has no connectivity. |
| .ply ✓ | A common file format for point clouds and meshes. |
| Normal | The direction perpendicular to the surface at a point. It's estimated from a point's neighbours. Point-to-plane ICP and Poisson meshing need normals. |
| k-nearest neighbours (kNN) ✓ | The k closest points. It's used in outlier removal, normal estimation and ICP. |
| KD-tree | A space-splitting tree that makes nearest-neighbour search fast. Open3D builds one inside ICP. |
| Voxel / voxel downsampling ✓ | A small cube in a 3D grid. Downsampling keeps one point per occupied cube (2 mm, 1 cm). |
| Statistical outlier removal ✓ | Drop points whose mean neighbour distance is unusually large (20 neighbours, 2σ). |
| Mesh ◆ | Vertices plus faces (usually triangles). It has connectivity, so it has a real surface. Physics and Blender need meshes. |
| Watertight / manifold ◆ | A closed surface with no holes, where every edge is shared by exactly two faces. Physics engines need this for collision and volume (mass). |
| Texture / UV map ◆ | An image wrapped onto a mesh. UV coordinates say which pixel goes where. |
| Signed distance function (SDF) ◆ | For every 3D location, the distance to the nearest surface, negative inside. The surface is where SDF = 0. |
| Implicit vs explicit representation ◆ | **Explicit** representations list the geometry (points, meshes, Gaussians). **Implicit** ones are a function you query (SDF, NeRF). |
| Chamfer distance ★ | Compares two point clouds: the average distance from each point to its nearest point in the other cloud, both ways. It's a standard reconstruction metric. |
| Accuracy / completeness ★ | Accuracy: how close your points are to the truth. Completeness: how much of the truth you covered. Together they make up the reconstruction **F-score** at a distance threshold. |
| 3D IoU ✓ | The overlap of two 3D boxes divided by their union. It's MonoDiff9D's 3D50/3D75 (pass rates at IoU ≥ 0.5 / 0.75). |

---

## Part B — Features and matching

| Term | Meaning |
|---|---|
| Feature / keypoint ✓ | A distinctive, repeatable image location, usually a corner or blob. |
| Descriptor ✓ | A vector describing the patch around a keypoint so it can be matched elsewhere. SIFT's descriptor has 128 numbers. |
| SIFT ✓ | Scale-Invariant Feature Transform. It finds blobs across scales and describes them using gradient directions. It's robust to scale, rotation and lighting, and it's COLMAP's default. |
| ORB | A fast binary feature (it's what ORB-SLAM uses). It's quicker than SIFT but less robust. |
| Learned features ★ | Networks that replace SIFT: **SuperPoint** (detect + describe), **SuperGlue / LightGlue** (match), **LoFTR** (detector-free dense matching). They're much better at wide turns, which is where your SIFT failed past ~40°. |
| Correspondence / match ✓ | "This pixel in image A is the same 3D point as that pixel in image B." All multi-view geometry starts here. |
| Lowe's ratio test | Keep a match only if the best candidate is clearly better than the second best (distance ratio < ~0.75–0.8). It removes ambiguous matches before RANSAC. |
| Mutual nearest neighbour | Keep A↔B only if each one is the other's best match. |
| Inlier / outlier ✓ | Matches that agree / don't agree with the model within a threshold (your 1 px). |
| RANSAC ✓ | RANdom SAmple Consensus. Fit a model to a minimal random sample, count inliers, repeat, and keep the best. It handles a large share of wrong matches. |
| Geometric verification ★ | Keep an image pair only if enough matches fit a single E, F or H. COLMAP does this before building its graph. |
| Feature track ★ | One 3D point followed across **many** images: a chain of matches. Longer tracks mean better-constrained points. VGGT predicts tracks directly. |
| Optical flow | The apparent 2D motion of every pixel between consecutive frames (e.g. RAFT). It's dense, unlike features. It's mostly used for video and small motions. |

---

## Part C — Two-view geometry (you built this on 23 Nov)

| Term | Meaning |
|---|---|
| Epipolar geometry ✓ | The geometry of two views. A point seen in image A must lie on one specific line in image B. |
| Epipole | Where camera A's centre appears in image B. All epipolar lines pass through it. |
| Epipolar line | The line in B where A's point must lie: the image of A's ray. |
| Epipolar constraint ✓ | x_bᵀ E x_a = 0 for every true match (normalised coordinates). |
| Essential matrix E ✓ | E = [t]× R. It encodes the relative rotation and the **direction** of travel (not its length). 5 DoF. A valid E has singular values (1, 1, 0) ✓. |
| Fundamental matrix F ★ | The same idea in **pixels**, without knowing K: F = K_b⁻ᵀ E K_a⁻¹. 7 DoF, rank 2. Used when the camera is uncalibrated. |
| 8-point / 5-point algorithm ✓ | Ways to estimate E from 8 or 5 matches. 8-point is linear and simple but needs **Hartley normalisation** ✓. 5-point (Nistér) is minimal, more robust, and copes better with flat scenes. OpenCV and COLMAP use it. |
| Decomposing E / cheirality ✓ | One E gives **four** possible (R, t). Keep the one that puts the triangulated points **in front of both cameras** (positive depth). This is the "cheirality check". recoverPose does it for you. |
| Triangulation ✓ | Intersect two (or more) rays to get a 3D point. Rays never meet exactly, so take the best compromise (DLT or midpoint). |
| Triangulation angle / parallax ✓ | The angle between the two rays at the point. If it's small (short baseline, far point), depth is very uncertain. That's your 1.9 cm case. |
| Sampson error ✓ | A cheap first-order approximation of the reprojection error for a match under E or F. Your RANSAC scored with it. |
| Degenerate configurations ✓ | Setups where the maths can't give a unique answer: **pure rotation** (no baseline, no depth: use a homography), **all points on one plane** (8-point breaks: you checked this and ruled it out), too few matches. COLMAP fits both H and E and picks based on which fits better. |
| Robust loss (Huber, Cauchy) ✓ | A loss that grows slower than squared error for big residuals, so a few remaining outliers can't dominate. You used Huber. Same idea as in ML. |

---

## Part D — Many views: SfM, bundle adjustment, SLAM

| Term | Meaning |
|---|---|
| PnP (Perspective-n-Point) ✓ | Pose from **known 3D points** and their 2D pixels. You used it for the board (solvePnP). **COLMAP uses it to add each new image** to an existing reconstruction. Minimal form: P3P (3 points). |
| Structure from Motion (SfM) ★ | Recover camera poses (motion), 3D points (structure) and often K from an unordered set of images. **Incremental SfM** (COLMAP): pick a good initial pair, triangulate, add the next image by PnP, triangulate new points, bundle adjust, repeat. **Global SfM** (GLOMAP): solve all rotations, then all positions, at once. It's faster and close in accuracy. |
| View graph / scene graph ★ | Images as nodes, verified pairs as edges. Its connectivity decides what SfM can reconstruct. A disconnected graph gives separate models. |
| Registered image ★ | An image COLMAP managed to place. "54 of 56 registered" is a result worth reporting. |
| Bundle adjustment (BA) ★ | Jointly adjust **all** camera poses, **all** 3D points (and optionally K) to minimise the total reprojection error. The "bundles" are the rays. It's the core reason SfM doesn't drift the way your chained ICP did: every observation constrains everything at once. |
| Non-linear least squares ★ | The kind of problem BA is: minimise a sum of squared residuals of a non-linear model. It's solved iteratively with **Gauss–Newton** or **Levenberg–Marquardt** (LM). COLMAP uses the Ceres solver. It's the geometry version of gradient descent: start near the answer and step downhill. |
| Local vs global BA ★ | Local BA refines only recent cameras (fast, used during reconstruction). Global BA refines everything (slow, more accurate). |
| Gauge freedom ★ | An SfM answer is only fixed up to a **similarity** (7 DoF): you can shift, rotate and scale the whole scene and every reprojection error stays the same. So you must **align before comparing** to ground truth. |
| Umeyama / Procrustes alignment ★ | The closed-form best Sim(3) between two sets of matching points (e.g. COLMAP camera centres vs board camera centres). You'll need this to grade P2. |
| Sparse vs dense reconstruction ★ | Sparse: only the triangulated feature points (thousands). Dense: depth for (nearly) every pixel (millions). |
| Multi-view stereo (MVS) ★ | Dense depth from many posed images. COLMAP uses **PatchMatch stereo**, which needs CUDA (your 4080). The poses come from SfM first. |
| Odometry / visual odometry (VO) ✓ | Estimating motion frame to frame by chaining small steps. It always drifts. Your chained ICP was a form of odometry. |
| Drift ✓ | Error that builds up through chaining because nothing corrects it (P1: up to 27 cm). |
| Loop closure ★ | Recognising that you've come back to a place you've seen before and pulling the whole trajectory into agreement. It's the main cure for drift. |
| SLAM ◆ | Simultaneous Localisation And Mapping: SfM done **online, in real time**, frame by frame, with keyframes, local BA and loop closure. Examples: ORB-SLAM3, DROID-SLAM, MASt3R-SLAM. Your sketch's "live, low-latency" simulator is SLAM territory. |
| Keyframe ◆ | A selected frame that SLAM keeps for mapping. The rest are only tracked. Your "every 10th frame" is a crude keyframe rule. |
| Registration ✓ | Aligning two pieces of geometry (clouds or scans) into one frame. |
| ICP ✓ | Iterative Closest Point: pair each point with its nearest neighbour, solve the best rigid move, repeat. It's **local**: it needs a good starting guess, or it pairs the wrong points (P1). |
| Point-to-point vs point-to-plane ICP ✓ | Point-to-point minimises point distances (Besl & McKay). Point-to-plane minimises distance along the target's normal (Chen & Medioni). It converges faster but lets flat surfaces slide, which is P1's desk problem. |
| Global registration | Alignment without a starting guess: match 3D features (e.g. FPFH) + RANSAC, then refine with ICP. |
| Local minimum ✓ | A solution that looks best nearby but isn't the true answer. ICP and BA can both get stuck in one from a bad start. Same idea as in ML. |

### Metrics you'll report in P2 ★

| Metric | Meaning |
|---|---|
| ATE (absolute trajectory error) | Align the estimated camera path to ground truth (Sim(3)), then take the RMSE of the camera positions. It measures global accuracy and drift. |
| RPE (relative pose error) | Error in the motion between frames i and i+k. It measures local accuracy without letting early mistakes dominate. |
| RRA / RTA @ threshold | Relative rotation / translation-direction accuracy: the share of image pairs whose error is under, e.g., 15°. VGGT's papers report this. **AUC@30** is the area under that curve from 0 to 30°. |
| Depth metrics | **AbsRel** = mean of \|Z_est − Z_true\| / Z_true. **δ < 1.25** = the share of pixels within 25%. RMSE. Monocular depth papers use all three. |
| Reprojection error | The mean pixel error after BA. It's low even when the scene is wrong at scale, so it's not proof on its own. |

---

## Part E — Learning-based 3D (links to the ML notes)

| Term | Meaning |
|---|---|
| Monocular depth estimation ✓ | Depth from one image with a network (MiDaS, Depth Anything, Depth Pro). It's per-pixel **regression** (from the ML notes). |
| Zero-shot / cross-dataset ✓ | Used on data from a different source than it was trained on, without retraining (MiDaS's selling point). |
| Distribution shift / OOD ✓ | Test data unlike the training data. It's why MonoDiff9D drops on Wild6D, and why "OOD" in your sketch means held-out cube positions. |
| Backbone / encoder / decoder ✓ | Backbone/encoder: a network turning an image into features (DINOv2, BEiT). Decoder/head: turns features into the output (depth, pose). |
| Vision Transformer (ViT), patches, tokens ✓ | Cut the image into 14×14 or 16×16 **patches**, turn each into a vector (**token**), and let **attention** mix information between tokens. DPT (inside MiDaS) and VGGT are built on this. |
| Attention | Each token computes how much to "look at" every other token and takes a weighted mix. Cross-frame attention is how a network can make views agree. |
| DINOv2 ✓ | A self-supervised ViT (trained without labels) whose features are very good for geometry and matching. VGGT uses it to turn images into tokens. |
| Feed-forward reconstruction ★ | A network that outputs cameras and geometry in **one pass**, with no iterative optimisation: DUSt3R, MASt3R, VGGT. That's the opposite of COLMAP's match → RANSAC → BA pipeline. |
| Pointmap ★ | Per pixel, a 3D point (X, Y, Z) instead of a single depth, all expressed in **one shared frame** (usually the first camera). It's what DUSt3R introduced and VGGT predicts. It avoids per-frame scale fits, which was P1's failure. |
| VGGT ★ | Visual Geometry Grounded Transformer (CVPR 2025). It takes 1 to hundreds of frames and outputs K and pose per frame, depth maps, pointmaps, confidence and tracks. It alternates **frame attention** (within one image) and **global attention** (across all images). The output is in the first camera's frame and is **not metric**, so you still need the board for scale. It can optionally be refined with BA. |
| Camera token ★ | An extra learned token per frame from which VGGT reads that frame's camera parameters. |
| Diffusion ✓ | A generative model trained to remove noise step by step. The timestep t is the noise level, **not** video time (your MonoDiff9D note). |
| 6D / 9D object pose ✓ | 6D = rotation + translation of an object. 9D adds its 3D size. Category-level means it works for any mug, not one specific mug. |
| Detection / segmentation ◆ | Detection gives a box around each object. Segmentation gives a per-pixel mask: **semantic** (class), **instance** (which object), e.g. SAM. You'll need instances to cut objects out of the scene for physics. |
| Benchmark pass rate vs mean error ✓ | "3D50 = 9.6%" means 9.6% of predictions passed. It's not an average error. Keep reading results this way. |

---

## Part F — Turning geometry into a scene (Checkpoint 1 output) ◆

| Term | Meaning |
|---|---|
| Fusion ◆ | Merging many depth maps into one surface. It only helps once the depths **agree**, which is why P2 comes first (your PIPELINE_METHODS §11). |
| TSDF fusion ◆ | A truncated SDF on a voxel grid. Each depth map votes on "distance to surface" near its surface, and the votes are averaged. Classic RGB-D method (KinectFusion). Open3D has it. |
| Marching cubes ◆ | Extracts a triangle mesh from the zero level of an SDF/TSDF grid. |
| Poisson surface reconstruction ◆ | Fits a smooth, watertight surface to a point cloud with oriented normals. Also in Open3D. |
| Rendering / rasterisation / ray tracing ◆ | Turning a 3D scene into an image. Rasterisation projects triangles (fast, used by games and Isaac). Ray tracing follows rays (accurate light). It's the reverse of reconstruction. |
| Novel view synthesis ◆ | Rendering the scene from a viewpoint no camera took. It's how NeRF and 3DGS are judged (PSNR, SSIM, LPIPS). |
| Photometric loss ◆ | Compare a rendered image to the real one pixel by pixel, then use gradients to fix the scene. It's the ML training loop with the scene as the parameters. |
| NeRF ◆ | Neural Radiance Field: an MLP maps (x, y, z, view direction) to colour and density, and an image is formed by **volume rendering** along rays. It's implicit and slow. |
| 3D Gaussian Splatting (3DGS) ◆ | The scene is millions of small coloured 3D Gaussians, rasterised fast. It's the current default for photoreal capture. **It needs SfM poses (usually COLMAP) as input**, so P2's output feeds straight into it. It looks great but isn't a clean surface. Use variants like 2DGS/SuGaR to get meshes. |
| View-dependent colour ◆ | Colour that changes with viewing angle (shine, reflections). NeRF and 3DGS model it. Meshes with plain textures don't. |
| Collision mesh / convex decomposition ◆ | A simplified, usually convex-piece, version of an object's mesh used by the physics engine (V-HACD, CoACD). Visual mesh ≠ collision mesh. |

---

## Part G — Simulation and action (Checkpoints 2–3, from your sketch) ◆

| Term | Meaning |
|---|---|
| Physics engine ◆ | Steps the world forward in time: forces → motion, collisions, contacts (PhysX in Isaac, MuJoCo, Bullet). |
| Rigid vs deformable body ✓ | A rigid body never changes shape (6 DoF). A deformable body bends or stretches (cables, cloth). It needs many more state variables and parameters like **stiffness**. |
| Physical parameters ✓ | Mass, friction, restitution (bounciness), stiffness, damping. A static scan can't see these, which is why your sketch says priors become the main source. |
| System identification ✓ | Fitting physical parameters so the sim matches real recordings (PhysTwin). It's regression with a simulator inside. |
| Real-to-sim / digital twin ✓ | Building a simulation from a real capture. Your whole project is a real-to-sim pipeline. |
| Sim-to-real gap ✓ | The difference that makes a policy work in sim but fail on the robot. |
| Domain randomisation ✓ | Vary sim parameters during training so the real world looks like just another variation. |
| Open-loop vs closed-loop ✓ | Open-loop: replay fixed actions and compare sim vs real (validates the world). Closed-loop: the policy reacts to what it sees (evaluates the policy). |
| Policy ✓ | The function from observation to action. It's what gets trained in sim. |
| POMDP ✓ | Partially Observable Markov Decision Process: hidden **state**, **observations** (your camera frames), **actions**, a **transition** model (the physics engine), a **reward**, and a **belief** (the agent's estimate of the state). Your reconstruction is the observation-to-belief part. |
| World model ✓ | A learned model predicting the next observation or state from the current one and an action. In WMPO it predicts pixels. |
| VLA ✓ | Vision-Language-Action model: images + instruction in, robot actions out. |
| USD / URDF ◆ | Scene and robot description formats. Isaac uses USD. Robots are often described in URDF. Your export target. |

---

## Gotchas that will bite in P2

1. **Pose direction.** COLMAP gives world-to-camera (quaternion + t). The camera centre is −Rᵀt, not t.
2. **Axis convention.** OpenCV (y down, z forward) vs OpenGL/Blender (y up, z back). Flip when exporting.
3. **Scale.** COLMAP and VGGT are only correct up to scale (and a 7-DoF gauge). Align with Umeyama/Sim(3) to the board before computing any error in mm.
4. **K changes** when you resize (VGGT resizes to 518 px wide), crop or refocus. Convert K whenever the image size changes.
5. **Low reprojection error ≠ correct scene.** Always grade against the board too.
6. **Pixel-centre convention.** Some libraries put pixel (0, 0)'s centre at 0.0, others at 0.5. This gives half-pixel offsets, which matter at the 1 px threshold.
7. **Same frames, same grading.** For a fair VGGT vs COLMAP comparison, give both the same 56 frames, the same undistortion and the same metrics.
