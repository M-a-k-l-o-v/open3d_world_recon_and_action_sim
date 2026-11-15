# p1_baseline_experiment.py — P1: is per-frame depth + ICP stacking the wrong approach?
#
# Three pose sources over the SAME per-frame MiDaS clouds:
#   Row A  old ICP — fixed 2 cm search, starts from "no movement", point-to-point (the prototype as built).
#   Row B  best-effort ICP — no board information. Starts from the previous step's movement; search
#          distances come from the data (coarse: motion x median depth; fine: depth noise); coarse-to-fine,
#          point-to-plane.
#   Row C  ceiling — the board's pose in every frame: the best this approach can ever do.
# Scores (the board is the only known geometry, used for grading only):
#   Rows A, B  pose drift: where the true board corners land with the row's poses vs where they really are.
#   Row C      layering: frame pairs' depth disagreement along the line of sight, by distance from the board.
#              PnP pose noise (from every video frame) is reported next to it, since pose noise can fake a gap.
#   Sanity     held-out corners (not used in the depth fit). Secondary: camera path, desk thickness.
#
# Run from this folder:   live3d_env/bin/python p1_baseline_experiment.py ../captures/videos/<video>.mp4
# Add --sweep to rerun row B over a grid of its design calls (k, v, w) instead.
# Step 1 (MiDaS, slow) is cached in captures/cache/; later runs skip it.

import csv
import os
import sys

import cv2
import numpy as np
import open3d as o3d
from scipy.spatial.transform import Rotation

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "capture"))
from camera import PROJECT

FRAME_STEP = 10              # every 10th frame (0.33 s apart), as in video_reconstruction.py
DEPTH_STEP = 4               # keep every 4th pixel of each depth map (480 x 270): ~2 mm apart at 1 m
VOXEL = 0.01                 # 1 cm points for ICP and desk thickness
KEEP_RADIUS = 1.5            # ignore points > 1.5 m from the board: far, extrapolated depth
OLD_ICP_DISTANCE = 0.02      # row A: the old prototype's fixed 2 cm search

# Row B design calls (Marv): safety margin, and the fastest hand-held motion while filming
MARGIN_K = 2.5
MAX_SPEED = 0.5              # m/s
MAX_TURN = np.radians(30)    # rad/s

SWEEP_K = [1.5, 2, 2.5, 3, 4]                                  # --sweep: margins to try
SWEEP_MOTION = [(0.25, 15), (0.5, 30), (1.0, 60)]              # --sweep: (m/s, deg/s), slow / default / fast
BANDS = [(0, .1), (.1, .3), (.3, .6), (.6, .8), (.8, 1.5)]     # distance from the board centre, metres
NEAR_PAIR, FAR_PAIR = 1, 15                                    # neighbours (0.33 s) vs >= 15 steps (~5 s) apart
CACHE_DIR = os.path.join(PROJECT, "captures", "cache")
OUT_DIR = os.path.join(PROJECT, "report_notes", "experiments", "data")


# ── step 1: per-frame depth and board poses (cached) ─────────────────────────

def build_cache(video_path, cache_path):
    # MiDaS loads on import, so only import it when the cache is missing
    from image_reconstructor import K, dist_coeffs, square_size, board_points, find_board_pose, get_inverse_depth

    points_on_board = board_points()
    fit_mask = (np.arange(len(points_on_board)) // 9) % 2 == 0     # FIT = every other row of corners
    board_centre = points_on_board.mean(axis=0)

    video = cv2.VideoCapture(video_path)
    fps = video.get(cv2.CAP_PROP_FPS)
    all_frames, all_poses = [], []                                  # every frame: for PnP noise
    used, poses, depths, keeps, fit_rms, held_rms = [], [], [], [], [], []
    index = 0
    while True:
        ok, frame = video.read()
        if not ok:
            break
        frame = cv2.undistort(frame, K, dist_coeffs)
        pose = find_board_pose(frame)                               # solvePnP with zero distortion (frame is undistorted)
        if pose is not None:
            R, tvec, corners = pose
            board_from_camera = camera_to_board(R, tvec)
            all_frames.append(index); all_poses.append(board_from_camera)

            if index % FRAME_STEP == 0:
                prediction, _ = get_inverse_depth(frame)
                corner_depths = (points_on_board @ R.T + tvec.T)[:, 2]
                s, t, rms_fit, rms_held = fit_inverse_depth(prediction, corners, corner_depths, fit_mask)
                fitted = s * prediction + t
                depth = np.where(fitted > 0, 1 / np.maximum(fitted, 1e-9), 0).astype(np.float32)
                depth = depth[DEPTH_STEP // 2::DEPTH_STEP, DEPTH_STEP // 2::DEPTH_STEP]

                # keep points in front of the camera and within KEEP_RADIUS of the board
                small_K = scale_intrinsics(K)
                in_camera = depth_to_points(depth, np.ones_like(depth, bool), small_K)
                in_board = in_camera @ board_from_camera[:3, :3].T + board_from_camera[:3, 3]
                keep = (depth.ravel() > 0.1) & (np.linalg.norm(in_board - board_centre, axis=1) < KEEP_RADIUS)

                used.append(index); poses.append(board_from_camera); depths.append(depth)
                keeps.append(keep.reshape(depth.shape)); fit_rms.append(rms_fit); held_rms.append(rms_held)
                print(f"[frame {index}] depth fit error: FIT corners {rms_fit*1000:.1f} mm, HELD-OUT {rms_held*1000:.1f} mm")
        index += 1

    os.makedirs(CACHE_DIR, exist_ok=True)
    np.savez_compressed(cache_path, frames=used, poses=poses, depths=depths, keeps=keeps, fit_rms=fit_rms,
                        held_rms=held_rms, all_frames=all_frames, all_poses=all_poses, K=scale_intrinsics(K),
                        board=points_on_board, fps=fps)


def fit_inverse_depth(prediction, corners, corner_depths, fit_mask):
    # 1/Z = s * prediction + t, fitted on the FIT corners only; returns depth error (RMS, m) on FIT and HELD-OUT
    u, v = np.round(corners).astype(int).T
    A = np.stack([prediction[v, u], np.ones(len(u))], axis=1)
    (s, t), *_ = np.linalg.lstsq(A[fit_mask], 1 / corner_depths[fit_mask], rcond=None)
    error = 1 / (A @ [s, t]) - corner_depths
    return s, t, np.sqrt(np.mean(error[fit_mask] ** 2)), np.sqrt(np.mean(error[~fit_mask] ** 2))


def camera_to_board(R, tvec):
    T = np.eye(4)
    T[:3, :3] = R.T
    T[:3, 3] = (-R.T @ tvec).ravel()
    return T


def scale_intrinsics(K):
    # K for the depth map that keeps every DEPTH_STEP-th pixel, starting at DEPTH_STEP // 2
    small = K / DEPTH_STEP
    small[0, 2] = (K[0, 2] - DEPTH_STEP // 2) / DEPTH_STEP
    small[1, 2] = (K[1, 2] - DEPTH_STEP // 2) / DEPTH_STEP
    small[2, 2] = 1
    return small


def depth_to_points(depth, keep, K):
    v, u = np.nonzero(keep)
    Z = depth[v, u]
    return np.stack([(u - K[0, 2]) * Z / K[0, 0], (v - K[1, 2]) * Z / K[1, 1], Z], axis=1)


# ── step 2: three pose sources ──────────────────────────────────────────────

def make_cloud(points):
    cloud = o3d.geometry.PointCloud(o3d.utility.Vector3dVector(points)).voxel_down_sample(VOXEL)
    cloud.estimate_normals(o3d.geometry.KDTreeSearchParamHybrid(radius=3 * VOXEL, max_nn=30))   # for point-to-plane
    return cloud


def row_a_old_icp(clouds, first_pose):
    poses = [first_pose]
    for previous, current in zip(clouds, clouds[1:]):
        reg = o3d.pipelines.registration.registration_icp(
            current, previous, OLD_ICP_DISTANCE, np.eye(4),
            o3d.pipelines.registration.TransformationEstimationPointToPoint(),
            o3d.pipelines.registration.ICPConvergenceCriteria(max_iteration=50))
        poses.append(poses[-1] @ reg.transformation)
    return poses


def row_b_best_icp(clouds, median_depth, depth_noise, step_seconds, first_pose,
                   margin_k=MARGIN_K, max_speed=MAX_SPEED, max_turn=MAX_TURN):
    # step = camera i -> camera i-1. Motion guess = the previous step (constant velocity), identity at first.
    poses, step, log = [first_pose], np.eye(4), []
    for i in range(1, len(clouds)):
        d_fine = max(VOXEL, 3 * depth_noise[i])
        if i == 1:      # no history yet: fastest plausible motion in one step
            d = max_speed * step_seconds[i] + median_depth[i] * max_turn * step_seconds[i]
        else:           # how far points could be from the guess: the previous movement, with a margin
            d = margin_k * (np.linalg.norm(step[:3, 3]) + median_depth[i] * rotation_angle(step))
        d0, d = d, max(d, d_fine)
        stages = 0
        while True:     # coarse-to-fine: each stage starts from the last one's answer
            reg = o3d.pipelines.registration.registration_icp(
                clouds[i], clouds[i - 1], d, step,
                o3d.pipelines.registration.TransformationEstimationPointToPlane(),
                o3d.pipelines.registration.ICPConvergenceCriteria(max_iteration=30))
            step, stages = reg.transformation, stages + 1
            if d <= d_fine:
                break
            d = max(d / 2, d_fine)
        poses.append(poses[-1] @ step)
        log.append((d0, d_fine, stages))
    return poses, log


def rotation_angle(T):
    return np.arccos(np.clip((np.trace(T[:3, :3]) - 1) / 2, -1, 1))


# ── step 3: scores ──────────────────────────────────────────────────────────

def corner_landing_error(row_pose, true_pose, board):
    # true board corners -> this camera (true pose) -> back into the scene with the row's pose
    in_camera = (np.linalg.inv(true_pose) @ np.c_[board, np.ones(len(board))].T)
    landed = (row_pose @ in_camera)[:3].T
    return np.linalg.norm(landed - board, axis=1).mean()


def line_of_sight_gaps(depths, keeps, poses, K, board_centre):
    # Row C: move frame i's points into frame j's camera with the true poses, project to a pixel, and compare
    # their depth with frame j's own depth there (bilinear). With perfect poses, any gap is depth disagreement.
    points = [depth_to_points(d, k, K) for d, k in zip(depths, keeps)]
    distance = [np.linalg.norm(p @ P[:3, :3].T + P[:3, 3] - board_centre, axis=1) for p, P in zip(points, poses)]
    h, w = depths[0].shape
    rows = []
    for i in range(len(points)):
        for j in range(i + 1, len(points)):
            T = np.linalg.inv(poses[j]) @ poses[i]
            p = points[i] @ T[:3, :3].T + T[:3, 3]
            ok = p[:, 2] > 0.1
            u = np.full(len(p), -1.0); v = np.full(len(p), -1.0)
            u[ok] = K[0, 0] * p[ok, 0] / p[ok, 2] + K[0, 2]
            v[ok] = K[1, 1] * p[ok, 1] / p[ok, 2] + K[1, 2]
            ok &= (u >= 0) & (u < w - 1) & (v >= 0) & (v < h - 1)
            u0, v0 = u[ok].astype(int), v[ok].astype(int)
            fu, fv = u[ok] - u0, v[ok] - v0
            corners_valid = keeps[j][v0, u0] & keeps[j][v0, u0 + 1] & keeps[j][v0 + 1, u0] & keeps[j][v0 + 1, u0 + 1]
            d = depths[j]
            seen = ((1 - fu) * (1 - fv) * d[v0, u0] + fu * (1 - fv) * d[v0, u0 + 1]
                    + (1 - fu) * fv * d[v0 + 1, u0] + fu * fv * d[v0 + 1, u0 + 1])
            gap = np.abs(p[ok, 2] - seen)[corners_valid] * 1000
            r = distance[i][ok][corners_valid]
            medians = [np.median(gap[(r >= a) & (r < b)]) if ((r >= a) & (r < b)).sum() >= 200 else np.nan
                       for a, b in BANDS]
            rows.append((i, j, j - i, medians))
    return rows


def pnp_noise(all_frames, all_poses, board_centre):
    # PnP jitter from consecutive frames: smooth motion cancels in the second difference, noise doesn't
    # (var of n[i] - 2n[i+1] + n[i+2] = 6 sigma^2). Real hand jerk at 30 fps adds in too, so this is an upper bound.
    frames = np.array(all_frames)
    triples = [k for k in range(len(frames) - 2) if frames[k + 2] - frames[k] == 2]
    camera_from_board = [np.linalg.inv(P) for P in all_poses]
    orientation = Rotation.from_matrix([T[:3, :3] for T in camera_from_board]).as_rotvec()
    centre = np.array([T[:3, :3] @ board_centre + T[:3, 3] for T in camera_from_board])

    def sigma(x):
        second = np.array([x[k] - 2 * x[k + 1] + x[k + 2] for k in triples])
        robust_std = 1.4826 * np.median(np.abs(second - np.median(second, axis=0)), axis=0)
        return np.sqrt(np.sum(robust_std ** 2)) / np.sqrt(6)

    return sigma(orientation), sigma(centre), len(triples)


def desk_thickness(clouds, poses, board_centre):
    points = np.concatenate([np.asarray(c.points) @ P[:3, :3].T + P[:3, 3] for c, P in zip(clouds, poses)])
    r = np.linalg.norm(points[:, :2] - board_centre[:2], axis=1)
    rows = []
    for a, b in [(0, .1), (.1, .3), (.3, .6), (.6, .8)]:
        z = points[(r >= a) & (r < b) & (np.abs(points[:, 2]) < 0.05), 2]
        rows.append(np.subtract(*np.percentile(z, [75, 25])) * 1000 if len(z) else np.nan)
    return rows


def path_stats(poses):
    centres = np.array([P[:3, 3] for P in poses])
    return np.linalg.norm(np.diff(centres, axis=0), axis=1).sum(), np.ptp(centres[:, 0]), np.ptp(centres[:, 1])


def sweep_row_b(clouds, median_depth, depth_noise, step_seconds, poses_c, board, name):
    # Row B over every (k, v, w) in the grid. Reading off the best one uses the board, so the best row is
    # row B with hindsight it could never have: if even that drifts, the design calls aren't the problem.
    path = os.path.join(OUT_DIR, f"p1_baseline_{name}_rowB_sweep.csv")
    with open(path, "w", newline="") as f:
        out = csv.writer(f)
        out.writerow(["k", "v_m_per_s", "w_deg_per_s", "error_frame10_mm", "error_median_mm", "error_worst_mm",
                      "error_last_mm", "rotation_median_deg", "path_length_m"])
        print("   k |    v |  w | frame 10 | median | worst | last | rotation | path m")
        for k in SWEEP_K:
            for v, w in SWEEP_MOTION:
                poses, _ = row_b_best_icp(clouds, median_depth, depth_noise, step_seconds, poses_c[0],
                                          margin_k=k, max_speed=v, max_turn=np.radians(w))
                e = [corner_landing_error(P, C, board) * 1000 for P, C in zip(poses, poses_c)]
                rot = np.median([np.degrees(rotation_angle(np.linalg.inv(C) @ P)) for P, C in zip(poses, poses_c)])
                row = [k, v, w, e[9], np.median(e), max(e), e[-1], rot, path_stats(poses)[0]]
                out.writerow(np.round(row, 2))
                print(f"{k:4} | {v:4} | {w:2} | {e[9]:8.1f} | {np.median(e):6.1f} | {max(e):5.0f} | {e[-1]:4.0f} | "
                      f"{rot:8.1f} | {row[-1]:.2f}")


# ── main ────────────────────────────────────────────────────────────────────

def main():
    video_path = sys.argv[1]
    name = os.path.splitext(os.path.basename(video_path))[0]
    cache_path = os.path.join(CACHE_DIR, f"p1_{name}_step{FRAME_STEP}.npz")
    if not os.path.exists(cache_path):
        build_cache(video_path, cache_path)
    c = np.load(cache_path)
    K, board, poses_c, depths, keeps = c["K"], c["board"], list(c["poses"]), c["depths"], c["keeps"]
    board_centre = board.mean(axis=0)
    frames = c["frames"]
    print(f"{len(frames)} frames, depth fit error median: FIT {np.median(c['fit_rms'])*1000:.1f} mm, "
          f"HELD-OUT {np.median(c['held_rms'])*1000:.1f} mm")

    # identical clouds for every row
    clouds = [make_cloud(depth_to_points(d, k, K)) for d, k in zip(depths, keeps)]
    median_depth = [np.median(d[k]) for d, k in zip(depths, keeps)]
    step_seconds = np.r_[0, np.diff(frames)] / c["fps"]

    if "--sweep" in sys.argv:
        sweep_row_b(clouds, median_depth, c["fit_rms"], step_seconds, poses_c, board, name)
        return

    poses_a = row_a_old_icp(clouds, poses_c[0])
    poses_b, log_b = row_b_best_icp(clouds, median_depth, c["fit_rms"], step_seconds, poses_c[0])
    d0 = np.array([x[0] for x in log_b]); stages = np.array([x[2] for x in log_b])
    print(f"Row B: coarse search d0 median {np.median(d0)*100:.1f} cm (range {d0.min()*100:.1f}-{d0.max()*100:.1f}), "
          f"fine {log_b[0][1]*100:.1f} cm, {np.median(stages):.0f} stages per step")

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, f"p1_baseline_{name}_poses.csv"), "w", newline="") as f:
        out = csv.writer(f)
        out.writerow(["used_frame", "video_frame", "c_x", "c_y", "c_z", "a_x", "a_y", "a_z", "b_x", "b_y", "b_z",
                      "a_corner_error_mm", "b_corner_error_mm", "a_rotation_error_deg", "b_rotation_error_deg",
                      "fit_rms_mm", "heldout_rms_mm", "median_depth_m", "b_coarse_search_cm"])
        for i, (n, C, A, B) in enumerate(zip(frames, poses_c, poses_a, poses_b)):
            out.writerow([i + 1, n, *np.round(C[:3, 3], 4), *np.round(A[:3, 3], 4), *np.round(B[:3, 3], 4),
                          round(corner_landing_error(A, C, board) * 1000, 1), round(corner_landing_error(B, C, board) * 1000, 1),
                          round(np.degrees(rotation_angle(np.linalg.inv(C) @ A)), 2),
                          round(np.degrees(rotation_angle(np.linalg.inv(C) @ B)), 2),
                          round(c["fit_rms"][i] * 1000, 2), round(c["held_rms"][i] * 1000, 2), round(median_depth[i], 3),
                          round(d0[i - 1] * 100, 1) if i else ""])

    print("\nPose drift — board corners' landing error (mm):   frame | row A | row B")
    errors = {r: [corner_landing_error(P, C, board) * 1000 for P, C in zip(poses, poses_c)]
              for r, poses in [("A", poses_a), ("B", poses_b)]}
    for i in [1, 4, 9, len(frames) - 1]:
        print(f"  {i+1:>3} | {errors['A'][i]:7.1f} | {errors['B'][i]:7.1f}")
    print(f"  worst | {max(errors['A']):7.1f} (frame {np.argmax(errors['A'])+1}) | "
          f"{max(errors['B']):7.1f} (frame {np.argmax(errors['B'])+1})")

    print("\nCamera path: length m | x extent m | y extent m")
    for r, poses in [("A", poses_a), ("B", poses_b), ("C", poses_c)]:
        print(f"  row {r}: " + " | ".join(f"{x:.2f}" for x in path_stats(poses)))

    sigma_rot, sigma_board, n_triples = pnp_noise(c["all_frames"], c["all_poses"], board_centre)
    print(f"\nPnP noise (upper bound, {n_triples} frame triples): rotation {np.degrees(sigma_rot):.3f} deg, "
          f"board position {sigma_board*1000:.2f} mm")

    rows = line_of_sight_gaps(depths, keeps, poses_c, K, board_centre)
    gaps = np.array([r[3] for r in rows]); step_gap = np.array([r[2] for r in rows])
    with open(os.path.join(OUT_DIR, f"p1_baseline_{name}_rowC_gap.csv"), "w", newline="") as f:
        out = csv.writer(f)
        out.writerow(["band_cm", "all_pairs_median_mm", "near_pairs_median_mm", "far_pairs_median_mm",
                      "pairs_with_data", "pnp_noise_bound_mm"])
        print("\nRow C — depth disagreement along the line of sight (median, mm):")
        print("  band cm | all pairs | neighbours | >= 15 apart | pairs | PnP-noise bound")
        for b, (lo, hi) in enumerate(BANDS):
            col = gaps[:, b]
            have = ~np.isnan(col)
            near, far = have & (step_gap == NEAR_PAIR), have & (step_gap >= FAR_PAIR)
            mid = (lo + hi) / 2
            bound = np.sqrt(2) * np.hypot(sigma_board, mid * sigma_rot) * 1000
            vals = [np.median(col[m]) if m.any() else np.nan for m in (have, near, far)]
            label = f"{lo*100:.0f}-{hi*100:.0f}"
            print(f"  {label:>7} | {vals[0]:9.1f} | {vals[1]:10.1f} | {vals[2]:11.1f} | {have.sum():5d} | {bound:5.1f}")
            out.writerow([label, *np.round(vals, 2), int(have.sum()), round(bound, 2)])

    print("\nDesk thickness (IQR of height, mm), rings 0-10/10-30/30-60/60-80 cm:")
    for r, poses in [("A", poses_a), ("B", poses_b), ("C", poses_c)]:
        print(f"  row {r}: " + " | ".join(f"{x:.1f}" for x in desk_thickness(clouds, poses, board_centre)))


if __name__ == "__main__":
    main()
