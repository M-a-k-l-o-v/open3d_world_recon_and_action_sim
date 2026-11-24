# vggt_mac_check.py — NFR1.4: does VGGT run on this Mac, how do time and memory grow with frame count,
# and are its camera poses right?
#
# What it computes: VGGT-1B (frozen, from Hugging Face) on N evenly spaced frames of desk video 1, for
# growing N. Per run: wall time and peak GPU memory (MPS, sampled every 50 ms). Accuracy against the
# board poses from the P1 cache, using only scale-free quantities (VGGT is off by one overall scale):
#   rotation error   = angle between VGGT's and the board's relative rotation, frame i -> frame j
#   direction error  = angle between their directions of camera movement, frame i -> frame j
# Memory is capped at the Mac's recommended GPU budget, so a run that doesn't fit fails cleanly
# instead of swapping. Three changes make more frames fit, none of which change what VGGT computes:
#   - only the camera and depth heads (the point head repeats depth + camera; tracking isn't used)
#   - attention in chunks of queries: on the Mac, PyTorch builds the whole frames x frames attention
#     table at once (10 GB at 16 frames); chunking gives the same result a slice at a time
#   - the main network (aggregator) in float16; the two heads stay float32 (the depth head forces float32)
# float16 costs nothing measurable: on 4 frames, all-float32 gave the same errors (0.91° / 1.23° / 0.8°).
# The aggregator is converted on the CPU, before it reaches the GPU: converting it there leaves the
# float32 copy cached.
#
# Needs the P1 cache: run ../per_frame_stack_relative_inverse_depth/p1_baseline_experiment.py on the video first.
# Run from this folder:   ../live3d_env/bin/python vggt_mac_check.py [frame counts, e.g. 40 48]
# Each run in one process leaves cached GPU memory behind, so test the limit in a fresh process.
# Every successful run saves its point cloud to captures/ply/ (video-recon_vggt_<time>_from-<video>_<N>-frames.ply).

import csv
import os
import sys
import threading
import time
import types

import cv2
import numpy as np
import open3d as o3d
import torch
import torch.nn.functional as F
import vggt.layers.attention as vggt_attention
from vggt.models.vggt import VGGT
from vggt.utils.load_fn import load_and_preprocess_images
from vggt.utils.geometry import unproject_depth_map_to_point_map
from vggt.utils.pose_enc import pose_encoding_to_extri_intri

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", "capture"))
from camera import PROJECT, capture_path, timestamp

VIDEO = os.path.join(PROJECT, "captures", "videos", "video_2026-10-28_162722.mp4")
CACHE = os.path.join(PROJECT, "captures", "cache", "p1_video_2026-10-28_162722_step10.npz")
FRAME_DIR = os.path.join(PROJECT, "captures", "frames", "video_2026-10-28_162722_step10")
OUT_CSV = os.path.join(PROJECT, "report_notes", "experiments", "data", "vggt_mac-check_m1-16gb.csv")
CALIBRATION = os.path.join(PROJECT, "capture", "camera_calibration.json")

FRAME_COUNTS = [2, 4, 8, 16, 24, 32, 40, 56]
STOP_AFTER_SECONDS = 600     # don't try bigger N once a run takes this long
ATTENTION_CHUNK_BYTES = 1e9  # largest slice of the attention table held at once
DROP_LEAST_CONFIDENT = 50    # % of points left out of the saved cloud, by VGGT's depth confidence (VGGT's own default)


def chunked_attention(q, k, v, dropout_p=0.0):
    # same as F.scaled_dot_product_attention, one block of queries at a time (each query row is independent)
    rows = max(64, int(ATTENTION_CHUNK_BYTES / (q.shape[0] * q.shape[1] * k.shape[-2] * q.element_size())))
    if q.shape[-2] <= rows:
        return F.scaled_dot_product_attention(q, k, v)
    return torch.cat([F.scaled_dot_product_attention(q[..., i:i + rows, :], k, v)
                      for i in range(0, q.shape[-2], rows)], dim=-2)


# VGGT calls F.scaled_dot_product_attention through its own module: point that one name at the chunked version
vggt_attention.F = types.SimpleNamespace(**{name: getattr(F, name) for name in dir(F) if not name.startswith("_")})
vggt_attention.F.scaled_dot_product_attention = chunked_attention


def save_frames(frame_numbers):
    # the cached frames, undistorted like the board poses were, as PNGs for VGGT's loader
    import json
    camera = json.load(open(CALIBRATION))["cameras"]["iphone14_continuity_1080p"]
    K, dist = np.array(camera["K"]), np.array(camera["dist_coeffs"])
    os.makedirs(FRAME_DIR, exist_ok=True)
    paths = [os.path.join(FRAME_DIR, f"frame_{n:05d}.png") for n in frame_numbers]
    if all(os.path.exists(p) for p in paths):
        return paths
    video, index = cv2.VideoCapture(VIDEO), 0
    wanted = set(frame_numbers)
    while True:
        ok, frame = video.read()
        if not ok:
            break
        if index in wanted:
            cv2.imwrite(os.path.join(FRAME_DIR, f"frame_{index:05d}.png"), cv2.undistort(frame, K, dist))
        index += 1
    return paths


def run_vggt(model, paths, dtype):
    # -> (camera_from_world 4x4 per frame, seconds, peak GPU GB, coloured point cloud)
    images = load_and_preprocess_images(paths).to("mps")
    peak, running = [0], [True]

    def watch():
        while running[0]:
            peak[0] = max(peak[0], torch.mps.driver_allocated_memory())
            time.sleep(0.05)

    watcher = threading.Thread(target=watch); watcher.start()
    start = time.time()
    try:
        with torch.no_grad():
            tokens, patch_start = model.aggregator(images[None].to(dtype))
            pose_enc = model.camera_head([tokens[-1].float()])[-1]         # the camera head reads the last layer
            needed = set(model.depth_head.intermediate_layer_idx)
            tokens = [t.float() if i in needed else None for i, t in enumerate(tokens)]
            depth, confidence = model.depth_head(tokens, images=images[None], patch_start_idx=patch_start)
        torch.mps.synchronize()
    finally:
        running[0] = False; watcher.join()
    seconds = time.time() - start
    assert torch.isfinite(depth).all() and torch.isfinite(pose_enc).all(), "output has NaN/inf"
    extrinsic, intrinsic = pose_encoding_to_extri_intri(pose_enc, images.shape[-2:])
    camera_from_world = np.tile(np.eye(4), (len(paths), 1, 1))
    camera_from_world[:, :3, :] = extrinsic[0].cpu().numpy()
    cloud = depth_to_cloud(depth[0], confidence[0], extrinsic[0], intrinsic[0], images)
    del tokens, pose_enc, depth, confidence, images
    torch.mps.empty_cache()
    return camera_from_world, seconds, peak[0] / 1e9, cloud


def depth_to_cloud(depth, confidence, extrinsic, intrinsic, images):
    # every frame's depth, placed in the world with VGGT's own cameras; the least confident points dropped
    points = unproject_depth_map_to_point_map(depth.float(), extrinsic, intrinsic)       # frames x H x W x 3
    colours = images.permute(0, 2, 3, 1).float().cpu().numpy()
    confidence = confidence.float().cpu().numpy()
    keep = confidence >= np.percentile(confidence, DROP_LEAST_CONFIDENT)
    cloud = o3d.geometry.PointCloud(o3d.utility.Vector3dVector(points[keep].astype(np.float64)))
    cloud.colors = o3d.utility.Vector3dVector(colours[keep].astype(np.float64))
    return cloud


def angle_deg(R):
    return np.degrees(np.arccos(np.clip((np.trace(R) - 1) / 2, -1, 1)))


def pose_errors(vggt_cfw, board_cfw):
    # every pair i < j: relative rotation error, and angle between movement directions (in camera i's frame)
    rot, direction = [], []
    for i in range(len(vggt_cfw)):
        for j in range(i + 1, len(vggt_cfw)):
            rel_v = vggt_cfw[j] @ np.linalg.inv(vggt_cfw[i])         # camera i -> camera j
            rel_b = board_cfw[j] @ np.linalg.inv(board_cfw[i])
            rot.append(angle_deg(rel_v[:3, :3].T @ rel_b[:3, :3]))
            move_v = -rel_v[:3, :3].T @ rel_v[:3, 3]                  # camera j's centre seen from camera i
            move_b = -rel_b[:3, :3].T @ rel_b[:3, 3]
            cos = move_v @ move_b / (np.linalg.norm(move_v) * np.linalg.norm(move_b) + 1e-12)
            direction.append(np.degrees(np.arccos(np.clip(cos, -1, 1))))
    return np.median(rot), np.percentile(rot, 90), np.median(direction)


def main():
    cache = np.load(CACHE)
    frames = cache["frames"]
    board_cfw = np.array([np.linalg.inv(P) for P in cache["poses"]])      # camera_from_board
    paths = save_frames(frames)

    torch.mps.set_per_process_memory_fraction(1.0)       # cap at the recommended budget: fail, don't swap
    print(f"MPS budget {torch.mps.recommended_max_memory()/1e9:.1f} GB")
    start = time.time()
    model = VGGT.from_pretrained("facebook/VGGT-1B")
    model.point_head = model.track_head = None            # P2 needs cameras and depth only
    model.aggregator.half()                               # on the CPU, so no float32 copy reaches the GPU
    model = model.to("mps").eval()
    print(f"model loaded in {time.time()-start:.0f} s, weights {torch.mps.driver_allocated_memory()/1e9:.1f} GB")

    counts = [int(a) for a in sys.argv[1:]] or FRAME_COUNTS
    runs = [(n, torch.float16) for n in counts]
    os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
    with open(OUT_CSV, "a" if sys.argv[1:] else "w", newline="") as f:
        out = csv.writer(f)
        if not sys.argv[1:]: out.writerow(["frames", "precision", "status", "seconds", "peak_gpu_gb", "rotation_error_median_deg",
                      "rotation_error_p90_deg", "direction_error_median_deg"])
        print(" frames | precision | seconds | peak GB | rot err median / p90 | direction err")
        too_slow = False
        for n, dtype in runs:
            if too_slow:
                continue
            pick = np.round(np.linspace(0, len(frames) - 1, n)).astype(int)
            precision = "float16" if dtype == torch.float16 else "float32"
            try:
                cfw, seconds, peak, cloud = run_vggt(model, [paths[k] for k in pick], dtype)
            except (RuntimeError, AssertionError) as error:   # MPS out of memory, or bad output
                print(f" {n:6} | {precision:9} | failed: {str(error).splitlines()[0]}")
                out.writerow([n, precision, str(error).splitlines()[0][:60], "", "", "", "", ""]); f.flush()
                torch.mps.empty_cache()
                continue
            video_name = os.path.splitext(os.path.basename(VIDEO))[0]
            ply_path = capture_path("ply", f"video-recon_vggt_{timestamp()}_from-{video_name}_{n}-frames.ply")
            o3d.io.write_point_cloud(ply_path, cloud)            # saved before anything else can fail
            print(f"  saved {len(cloud.points):,} points to {os.path.relpath(ply_path, PROJECT)}")
            rot, rot90, direction = pose_errors(cfw, board_cfw[pick])
            print(f" {n:6} | {precision:9} | {seconds:7.1f} | {peak:7.2f} | {rot:6.2f}° / {rot90:5.2f}° | {direction:6.1f}°")
            out.writerow([n, precision, "ok", round(seconds, 1), round(peak, 2), round(rot, 3), round(rot90, 3),
                          round(direction, 2)]); f.flush()
            if seconds > STOP_AFTER_SECONDS:
                print("  too slow — stopping the frame-count sweep here")
                too_slow = True
    print(f"\nSaved {os.path.relpath(OUT_CSV, PROJECT)}")


if __name__ == "__main__":
    main()
