# video_reconstruction.py — one point cloud from a whole video, using the same MiDaS pipeline as Main.py.
#
# What it computes: for every FRAME_STEP-th frame where the whole checkerboard is visible, the board
# gives the camera pose and the metric scale; MiDaS gives (inverse) depth; the frame's points are
# placed in the board's frame and all frames are stacked. No ICP — the board poses alone line frames
# up, so any doubling/thickness you see is MiDaS's depth disagreeing between frames.
#
# Uses the newest video in captures/videos/ (record one with: bash capture/camera.sh, then R).
# Run from this folder:   live3d_env/bin/python video_reconstruction.py

import glob
import os

import cv2
import numpy as np
import open3d as o3d

from image_reconstructor import (K, dist_coeffs, find_board_pose, get_inverse_depth, fit_scale_and_shift,
                                   inverse_depth_to_metric, depth_to_3d_points_with_color, camera_to_board)
from camera import capture_path, timestamp, PROJECT

FRAME_STEP = 10          # every 10th frame = 3 per second at 30 fps; neighbouring frames add little
VOXEL_SIZE = 0.002       # 2 mm, as in Main.py


def newest_video():
    videos = glob.glob(os.path.join(PROJECT, "captures", "videos", "*.mp4"))
    return max(videos, key=os.path.getmtime)


def frame_to_cloud(frame):
    # one frame -> coloured points in the board's frame, or None if the board isn't fully visible
    frame = cv2.undistort(frame, K, dist_coeffs)
    pose = find_board_pose(frame)
    if pose is None:
        return None
    R, tvec, corners = pose
    inverse_depth, rgb_image = get_inverse_depth(frame)
    s, t = fit_scale_and_shift(inverse_depth, R, tvec, corners)
    depth_map = inverse_depth_to_metric(inverse_depth, s, t)
    points, colors = depth_to_3d_points_with_color(depth_map, rgb_image)

    valid = (depth_map.flatten() > 0.1) & (depth_map.flatten() < 10)
    cloud = o3d.geometry.PointCloud()
    cloud.points = o3d.utility.Vector3dVector(points[valid])
    cloud.colors = o3d.utility.Vector3dVector(colors[valid])
    # thin first, then clean: outlier removal on 2 million raw points would be slow
    cloud = cloud.voxel_down_sample(VOXEL_SIZE)
    cloud, _ = cloud.remove_statistical_outlier(nb_neighbors=20, std_ratio=2.0)
    return cloud.transform(camera_to_board(R, tvec))


def main():
    video_path = newest_video()
    video = cv2.VideoCapture(video_path)
    total = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
    print(f"Video: {os.path.relpath(video_path, PROJECT)} ({total} frames), using every {FRAME_STEP}th")

    scene = o3d.geometry.PointCloud()
    video_name = os.path.splitext(os.path.basename(video_path))[0].replace(" ", "-")
    ply_path = capture_path("ply", f"video-recon_midas_{timestamp()}_from-{video_name}.ply")  # rewritten after every frame
    used = skipped = 0
    for index in range(total):
        ok, frame = video.read()
        if not ok:
            break
        if index % FRAME_STEP:
            continue
        print(f"[frame {index}/{total}]")
        cloud = frame_to_cloud(frame)
        if cloud is None:
            print("  board not fully visible — skipped")
            skipped += 1
            continue
        scene = (scene + cloud).voxel_down_sample(VOXEL_SIZE)
        used += 1
        o3d.io.write_point_cloud(ply_path, scene)   # save before anything is rendered

    print(f"\nUsed {used} frames, skipped {skipped}")
    if used == 0:
        return
    print(f"✓ Saved {len(scene.points)} points to {os.path.relpath(ply_path, PROJECT)}")
    o3d.visualization.draw_geometries([scene], window_name="Video reconstruction", width=1000, height=800)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped with Ctrl+C — frames done so far are saved in captures/ply/")
