"""calibrate.py — work out a camera's intrinsics from a video of the checkerboard.

What it computes: the pinhole camera matrix K (focal lengths fx, fy and the
optical centre cx, cy, all in pixels) and the lens distortion coefficients.
OpenCV finds the board's 9x6 inner corners in many frames; because the board is
known to be flat with equal squares, the only camera that explains where all
those corners land in every frame is the true one, which calibrateCamera solves for.

The result is saved under a name in capture/camera_calibration.json, so each
camera stream (Continuity 1080p now, Camera-app video later) gets its own entry.
A calibration is only valid for the resolution it was made at.

Usage (from the project folder):
    bash capture/record.sh        # ~30 s: move the phone around the board, tilt it, fill the corners of the frame
    Virtual_space_constructor/live3d_env/bin/python capture/calibrate.py captures/videos/<file>.mp4 iphone14_continuity_1080p 25

The last number is the side of one printed/displayed square in millimetres (measure it with a ruler).
"""

import datetime
import json
import os
import sys

import cv2
import numpy as np

INNER_CORNERS = (9, 6)       # matches capture/checkerboard.png (10x7 squares)
MAX_FRAMES = 40              # calibrateCamera gets slow past this and gains little
CALIBRATION_FILE = os.path.join(os.path.dirname(__file__), "camera_calibration.json")


def find_board_in_video(video_path):
    """Return (corner arrays, image size) for frames where the whole board is visible."""
    video = cv2.VideoCapture(video_path)
    found = []
    frame_index = 0
    while True:
        ok, frame = video.read()
        if not ok:
            break
        frame_index += 1
        if frame_index % 5:          # neighbouring frames are near-duplicates
            continue
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        ok, corners = cv2.findChessboardCorners(gray, INNER_CORNERS)
        if ok:
            # Refine to sub-pixel accuracy; a 1-pixel corner error is a lot at 1080p.
            corners = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1),
                                       (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001))
            found.append(corners)
    image_size = (int(video.get(cv2.CAP_PROP_FRAME_WIDTH)), int(video.get(cv2.CAP_PROP_FRAME_HEIGHT)))
    video.release()
    return found, image_size


def board_points(square_size_m):
    """The corners' 3D positions on the flat board (z = 0), in metres."""
    cols, rows = INNER_CORNERS
    points = np.zeros((cols * rows, 3), np.float32)
    points[:, :2] = np.mgrid[0:cols, 0:rows].T.reshape(-1, 2) * square_size_m
    return points


def save(name, entry, square_size_m):
    data = {}
    if os.path.exists(CALIBRATION_FILE):
        with open(CALIBRATION_FILE) as f:
            data = json.load(f)
    data["convention"] = "OpenCV pinhole: x right, y down, z forward; pixels for K, metres for the board"
    data["board"] = {"inner_corners": list(INNER_CORNERS), "square_size_m": square_size_m,
                     "image": "capture/checkerboard.png"}
    data.setdefault("cameras", {})[name] = entry
    with open(CALIBRATION_FILE, "w") as f:
        json.dump(data, f, indent=2)


def main():
    video_path, name, square_mm = sys.argv[1], sys.argv[2], float(sys.argv[3])
    square_size_m = square_mm / 1000

    corners, image_size = find_board_in_video(video_path)
    print(f"Board found in {len(corners)} frames")
    if len(corners) < 10:
        sys.exit("Need at least 10 frames with the whole board visible. Record again, slower.")

    # Spread the chosen frames evenly over the video so all the poses you moved through count.
    keep = np.linspace(0, len(corners) - 1, min(MAX_FRAMES, len(corners))).astype(int)
    corners = [corners[i] for i in keep]
    object_points = [board_points(square_size_m)] * len(corners)

    rms, K, dist, _, _ = cv2.calibrateCamera(object_points, corners, image_size, None, None)

    # RMS reprojection error: how far (in pixels) the solved camera puts each corner
    # from where it was actually seen. Under ~0.5 px is good; over 1 px, recalibrate.
    print(f"RMS reprojection error: {rms:.3f} px")
    print(f"fx={K[0, 0]:.1f}  fy={K[1, 1]:.1f}  cx={K[0, 2]:.1f}  cy={K[1, 2]:.1f}")

    entry = {
        "width": image_size[0],
        "height": image_size[1],
        "fx": K[0, 0], "fy": K[1, 1], "cx": K[0, 2], "cy": K[1, 2],
        "K": K.tolist(),
        "dist_coeffs": dist.ravel().tolist(),     # OpenCV order: k1, k2, p1, p2, k3
        "rms_reprojection_error_px": rms,
        "frames_used": len(corners),
        "source_video": video_path,
        "calibrated_on": datetime.date.today().isoformat(),
    }
    save(name, entry, square_size_m)
    print(f"Saved '{name}' to {CALIBRATION_FILE}")


if __name__ == "__main__":
    main()
