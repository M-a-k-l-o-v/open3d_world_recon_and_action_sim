# icp_drift_probe.py — P1: was pose drift the real problem, or the depth?
#
# What it computes: for every FRAME_STEP-th frame of a video with the whole board visible, MiDaS depth
# (scaled to metres on the board) becomes a point cloud in the camera's frame, and the board gives the
# reference camera pose. Then the frames are chained with ICP the way the old prototype lined up
# captures (point-to-point, 2 cm, starting from "no motion"), and that camera path is compared with
# the board's. Finally the clouds are fused twice — once with the reference poses, once with the ICP
# poses — and the desk's thickness is measured in each. Reference poses isolate the depth error;
# ICP poses add pose drift on top.
#
# Run from this folder:   live3d_env/bin/python icp_drift_probe.py captures/videos/<video>.mp4

import csv
import os
import sys

import cv2
import numpy as np
import open3d as o3d

from image_reconstructor import (K, dist_coeffs, square_size, find_board_pose, get_inverse_depth, fit_scale_and_shift,
                                 inverse_depth_to_metric, depth_to_3d_points_with_color, camera_to_board)
from camera import PROJECT

FRAME_STEP = 10              # same frames as video_reconstruction.py
ICP_VOXEL = 0.01             # 1 cm points for ICP and fusion: fine enough for 2 cm matching, fast
ICP_DISTANCE = 0.02          # old prototype's ICP threshold (2 cm)
KEEP_RADIUS = 1.5            # ignore points > 1.5 m from the board: far, extrapolated depth
OUT_DIR = os.path.join(PROJECT, "report_notes", "experiments", "data")


def frame_to_camera_cloud(frame):
    # one frame -> (cloud in the camera's frame, board_from_camera 4x4), or None without the whole board
    frame = cv2.undistort(frame, K, dist_coeffs)
    pose = find_board_pose(frame)
    if pose is None:
        return None
    R, tvec, corners = pose
    inverse_depth, rgb_image = get_inverse_depth(frame)
    s, t = fit_scale_and_shift(inverse_depth, R, tvec, corners)
    depth_map = inverse_depth_to_metric(inverse_depth, s, t)
    points, _ = depth_to_3d_points_with_color(depth_map, rgb_image)

    board_from_camera = camera_to_board(R, tvec)
    in_board = points @ board_from_camera[:3, :3].T + board_from_camera[:3, 3]
    board_centre = np.array([4 * square_size, 2.5 * square_size, 0])
    keep = (depth_map.flatten() > 0.1) & (np.linalg.norm(in_board - board_centre, axis=1) < KEEP_RADIUS)

    cloud = o3d.geometry.PointCloud(o3d.utility.Vector3dVector(points[keep]))
    return cloud.voxel_down_sample(ICP_VOXEL), board_from_camera


def chain_icp(clouds, first_pose):
    # camera i in the world = camera i-1 in the world x (ICP: camera i -> camera i-1). Errors add up.
    poses = [first_pose]
    for previous, current in zip(clouds, clouds[1:]):
        reg = o3d.pipelines.registration.registration_icp(
            current, previous, ICP_DISTANCE, np.identity(4),
            o3d.pipelines.registration.TransformationEstimationPointToPoint(),
            o3d.pipelines.registration.ICPConvergenceCriteria(max_iteration=50))
        poses.append(poses[-1] @ reg.transformation)
    return poses


def rotation_error_deg(A, B):
    cos = (np.trace(A[:3, :3].T @ B[:3, :3]) - 1) / 2
    return np.degrees(np.arccos(np.clip(cos, -1, 1)))


def desk_thickness(clouds, poses):
    # fuse with the given poses; desk = points within ±5 cm of the board plane; thickness = IQR of height
    points = np.concatenate([np.asarray(c.points) @ P[:3, :3].T + P[:3, 3] for c, P in zip(clouds, poses)])
    r = np.linalg.norm(points[:, :2] - np.array([4 * square_size, 2.5 * square_size]), axis=1)
    rows = []
    for a, b in [(0, .1), (.1, .2), (.2, .3), (.3, .45), (.45, .6), (.6, .8)]:
        z = points[(r >= a) & (r < b) & (np.abs(points[:, 2]) < 0.05), 2]
        q1, q3 = np.percentile(z, [25, 75]) if len(z) else (np.nan, np.nan)
        rows.append((f"{a*100:.0f}-{b*100:.0f} cm", len(z), (q3 - q1) * 1000))
    return rows


def main():
    video_path = sys.argv[1]
    video = cv2.VideoCapture(video_path)
    clouds, reference, frame_numbers = [], [], []
    index = 0
    while True:
        ok, frame = video.read()
        if not ok:
            break
        if index % FRAME_STEP == 0:
            result = frame_to_camera_cloud(frame)
            if result is not None:
                clouds.append(result[0]); reference.append(result[1]); frame_numbers.append(index)
                print(f"[frame {index}] {len(result[0].points)} points")
        index += 1

    icp = chain_icp(clouds, reference[0])
    os.makedirs(OUT_DIR, exist_ok=True)
    name = os.path.splitext(os.path.basename(video_path))[0]
    path_csv = os.path.join(OUT_DIR, f"p1_icp-drift_{name}_poses.csv")
    with open(path_csv, "w", newline="") as f:
        out = csv.writer(f)
        out.writerow(["used_frame", "video_frame", "ref_x", "ref_y", "ref_z", "icp_x", "icp_y", "icp_z",
                      "position_error_mm", "rotation_error_deg"])
        for i, (n, A, B) in enumerate(zip(frame_numbers, reference, icp)):
            error = np.linalg.norm(A[:3, 3] - B[:3, 3]) * 1000
            out.writerow([i + 1, n, *np.round(A[:3, 3], 4), *np.round(B[:3, 3], 4), round(error, 1),
                          round(rotation_error_deg(A, B), 2)])
    print(f"\nSaved camera paths to {os.path.relpath(path_csv, PROJECT)}")

    print("\nDesk thickness (IQR of height, mm):  ring | reference poses | ICP poses")
    for (ring, n_ref, t_ref), (_, n_icp, t_icp) in zip(desk_thickness(clouds, reference), desk_thickness(clouds, icp)):
        print(f"  {ring:>9} | {t_ref:6.1f} ({n_ref:,} pts) | {t_icp:6.1f} ({n_icp:,} pts)")


if __name__ == "__main__":
    main()
