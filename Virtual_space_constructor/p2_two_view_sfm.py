# p2_two_view_sfm.py — P2 warm-up: structure-from-motion from two frames, written from scratch.
#
# What it computes: from two photos alone (no board, no depth model), how the camera turned and which
# direction it moved between them, then the 3D position of every matched point (where its two rays cross).
# Photos can't tell a small room from a big one, so the camera's movement comes out with length 1:
# the shape is right, the size is unknown. COLMAP does this same thing over many frames, plus bundle adjustment.
#
# Steps (NumPy unless noted):
#   1 match points between the frames (SIFT, OpenCV — finding features isn't what P2 is about)
#   2 essential matrix E: the one 3x3 matrix every true match obeys (x_b^T E x_a = 0), by the 8-point method + RANSAC
#   3 split E into rotation R and direction of travel t (4 candidates; keep the one with points in front of both cameras),
#     then polish R and t directly against every agreeing match (scipy least_squares)
#   4 triangulate every match
#   5 grade against the board (used only here): R and t vs the board's poses, and the triangulated board corners
#     vs the real board once the size is fixed. OpenCV's findEssentialMat + recoverPose runs alongside as a check.
#
# Run from this folder:   live3d_env/bin/python p2_two_view_sfm.py ../captures/videos/<video>.mp4 [frame_a frame_b]

import json
import os
import sys

import cv2
import numpy as np
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation

CALIBRATION_FILE = os.path.join(os.path.dirname(__file__), "..", "capture", "camera_calibration.json")
CAMERA_NAME = "iphone14_continuity_1080p"
FRAME_A, FRAME_B = 0, 80          # video frames; 0 -> 80 is ~24 cm of camera movement in the 28 Oct desk video
RATIO = 0.75                      # Lowe's ratio test: keep a match only if it's clearly better than the runner-up
RANSAC_PIXELS = 1.0               # a match fits E if it's within 1 px of where E says it should be
RANSAC_ROUNDS = 2000


# ── setup ───────────────────────────────────────────────────────────────────

def load_calibration():
    with open(CALIBRATION_FILE) as f:
        calibration = json.load(f)
    camera = calibration["cameras"][CAMERA_NAME]
    cols, rows = calibration["board"]["inner_corners"]
    board = np.zeros((cols * rows, 3), np.float32)
    board[:, :2] = np.mgrid[0:cols, 0:rows].T.reshape(-1, 2) * calibration["board"]["square_size_m"]
    return np.array(camera["K"]), np.array(camera["dist_coeffs"]), (cols, rows), board


def read_frame(video_path, n, K, dist):
    video = cv2.VideoCapture(video_path)
    video.set(cv2.CAP_PROP_POS_FRAMES, n)
    ok, frame = video.read()
    video.release()
    if not ok:
        sys.exit(f"Couldn't read frame {n}")
    return cv2.undistort(frame, K, dist)      # undistort once, so everything after is a plain pinhole camera


def find_board(frame, K, corners_shape, board):
    # grading only: the board's corners in the image, and the 4x4 pose taking camera points into the board's frame
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    found, corners = cv2.findChessboardCorners(gray, corners_shape)
    if not found:
        sys.exit("Board not found in one of the frames — pick frames where it's fully visible")
    corners = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1),
                               (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001))
    _, rvec, tvec = cv2.solvePnP(board, corners, K, None)
    R, _ = cv2.Rodrigues(rvec)
    camera_to_board = np.eye(4)
    camera_to_board[:3, :3] = R.T
    camera_to_board[:3, 3] = (-R.T @ tvec).ravel()
    return corners.reshape(-1, 2), camera_to_board


# ── step 1: matches ─────────────────────────────────────────────────────────

def match_points(frame_a, frame_b):
    sift = cv2.SIFT_create()
    keys_a, desc_a = sift.detectAndCompute(cv2.cvtColor(frame_a, cv2.COLOR_BGR2GRAY), None)
    keys_b, desc_b = sift.detectAndCompute(cv2.cvtColor(frame_b, cv2.COLOR_BGR2GRAY), None)
    pairs = cv2.BFMatcher().knnMatch(desc_a, desc_b, k=2)
    good = [m for m, second in pairs if m.distance < RATIO * second.distance]
    pixels_a = np.array([keys_a[m.queryIdx].pt for m in good])
    pixels_b = np.array([keys_b[m.trainIdx].pt for m in good])
    return pixels_a, pixels_b


def to_rays(pixels, K):
    # pixel -> direction from the camera centre (x, y, 1). E works on these, so K drops out of the maths.
    return np.c_[pixels, np.ones(len(pixels))] @ np.linalg.inv(K).T


# ── step 2: essential matrix ────────────────────────────────────────────────

def centre_and_scale(rays):
    # Hartley normalisation: shift the points to be centred on 0 and scale them to average length sqrt(2).
    # Without it the 8-point equations are badly balanced (x, y ~0.2 next to a 1), and on this mostly-flat
    # desk the fit falls apart: 122 of OpenCV's 177 agreeing matches without it.
    centre = rays[:, :2].mean(axis=0)
    s = np.sqrt(2) / np.linalg.norm(rays[:, :2] - centre, axis=1).mean()
    return np.array([[s, 0, -s * centre[0]], [0, s, -s * centre[1]], [0, 0, 1]])


def eight_point(rays_a, rays_b):
    # Each match gives one linear equation in E's 9 numbers (x_b^T E x_a = 0). With 8+ matches, the best fit is
    # the direction the equations squeeze least: the last singular vector. Every match lies on a line through
    # the other camera's centre, so the matrix must have rank 2: zero its smallest singular value.
    T_a, T_b = centre_and_scale(rays_a), centre_and_scale(rays_b)
    A = np.einsum("ni,nj->nij", rays_b @ T_b.T, rays_a @ T_a.T).reshape(-1, 9)
    F = np.linalg.svd(A)[2][-1].reshape(3, 3)
    U, S, Vt = np.linalg.svd(F)
    F = U @ np.diag([S[0], S[1], 0]) @ Vt
    return T_b.T @ F @ T_a                                       # undo the centring and scaling


def snap_to_essential(F):
    # A true E has singular values (s, s, 0): it's "cross with t, after rotating by R". Snap to the nearest one.
    # Only once, on the final fit: on 8 noisy points the snap moves them 50-130 px (seen on the desk video),
    # so snapping every RANSAC guess would score good guesses as bad.
    U, _, Vt = np.linalg.svd(F)
    return U @ np.diag([1, 1, 0]) @ Vt


def sampson_error(E, rays_a, rays_b):
    # how far (in ray units, ~pixels / focal length) each match is from obeying E, to first order
    Ea = rays_a @ E.T
    Eb = rays_b @ E
    residual = np.sum(rays_b * Ea, axis=1)
    return np.abs(residual) / np.sqrt(Ea[:, 0]**2 + Ea[:, 1]**2 + Eb[:, 0]**2 + Eb[:, 1]**2)


def ransac_essential(rays_a, rays_b, threshold):
    # Some matches are wrong. Fit E to 8 random matches many times; keep the E most matches agree with,
    # then refit it on all of those.
    rng = np.random.default_rng(0)
    best = np.zeros(len(rays_a), bool)
    for _ in range(RANSAC_ROUNDS):
        sample = rng.choice(len(rays_a), 8, replace=False)
        with np.errstate(all="ignore"):     # SIFT can report one pixel twice; a sample of copies has no answer
            inliers = sampson_error(eight_point(rays_a[sample], rays_b[sample]), rays_a, rays_b) < threshold
        if inliers.sum() > best.sum():
            best = inliers
    return snap_to_essential(eight_point(rays_a[best], rays_b[best])), best


# ── steps 3-4: rotation, direction of travel, 3D points ─────────────────────

def triangulate(rays_a, rays_b, R, t):
    # Camera A sits at the origin, camera B maps points by x_b = R x_a + t. Each camera's ray gives two linear
    # equations for the point X; solve all four together (DLT) by SVD, one point at a time (vectorised).
    P_a = np.c_[np.eye(3), np.zeros(3)]
    P_b = np.c_[R, t]
    A = np.stack([rays_a[:, :1] * P_a[2] - P_a[0], rays_a[:, 1:2] * P_a[2] - P_a[1],
                  rays_b[:, :1] * P_b[2] - P_b[0], rays_b[:, 1:2] * P_b[2] - P_b[1]], axis=1)
    X = np.linalg.svd(A)[2][:, -1]
    return X[:, :3] / X[:, 3:]


def split_essential(E, rays_a, rays_b):
    # E fixes R and t only up to 4 mirror-image choices. Only the right one puts the points in front of both cameras.
    U, _, Vt = np.linalg.svd(E)
    if np.linalg.det(U) < 0: U = -U
    if np.linalg.det(Vt) < 0: Vt = -Vt
    W = np.array([[0, -1, 0], [1, 0, 0], [0, 0, 1]])
    best = None
    for R in (U @ W @ Vt, U @ W.T @ Vt):
        for t in (U[:, 2], -U[:, 2]):
            X = triangulate(rays_a, rays_b, R, t)
            in_front = np.sum((X[:, 2] > 0) & ((X @ R.T + t)[:, 2] > 0))
            if best is None or in_front > best[0]:
                best = (in_front, R, t)
    return best[1], best[2]


def essential_from(rotation_vector, t):
    # E = [t]x R: "rotate, then cross with the direction of travel". t is kept at length 1 (size is unknown).
    t = t / np.linalg.norm(t)
    t_cross = np.array([[0, -t[2], t[1]], [t[2], 0, -t[0]], [-t[1], t[0], 0]])
    return t_cross @ Rotation.from_rotvec(rotation_vector).as_matrix()


def polish(R, t, rays_a, rays_b, threshold):
    # The snap to a true E is the nearest matrix, not the best camera motion: on its own it left only 9 of
    # ~160 matches within 1 px. So adjust R and t directly to shrink every match's error (two-view bundle
    # adjustment, minus the points). Rotation as a rotation vector (exp map), never raw matrix entries.
    # Huber loss: errors past ~1 px count linearly, so the few wrong matches can't drag the answer.
    start = np.r_[Rotation.from_matrix(R).as_rotvec(), t]
    fit = least_squares(lambda x: sampson_error(essential_from(x[:3], x[3:]), rays_a, rays_b), start,
                        loss="huber", f_scale=threshold)
    return Rotation.from_rotvec(fit.x[:3]).as_matrix(), fit.x[3:] / np.linalg.norm(fit.x[3:])


# ── step 5: grading (the board, plus OpenCV as a cross-check) ───────────────

def angle_deg(R):
    return np.degrees(np.arccos(np.clip((np.trace(R) - 1) / 2, -1, 1)))


def direction_error_deg(t, t_true):
    return np.degrees(np.arccos(np.clip(t @ t_true / np.linalg.norm(t) / np.linalg.norm(t_true), -1, 1)))


def board_shape_error(R, t, corners_a, corners_b, K, board, pose_a):
    # Triangulate the board corners with this R, t (camera movement of length 1), fix the size with the one thing
    # photos can't give, the real square size, then compare with the real corners in camera A's frame.
    X = triangulate(to_rays(corners_a, K), to_rays(corners_b, K), R, t)
    true = (np.c_[board, np.ones(len(board))] @ np.linalg.inv(pose_a).T)[:, :3]
    neighbours = np.arange(len(board) - 1)[np.diff(board[:, 0]) > 0]        # corner and the next one along its row
    scale = np.median(np.linalg.norm(true[neighbours + 1] - true[neighbours], axis=1)
                      / np.linalg.norm(X[neighbours + 1] - X[neighbours], axis=1))
    return np.linalg.norm(scale * X - true, axis=1).mean(), scale


def main():
    video_path = sys.argv[1]
    frame_a_n, frame_b_n = (int(sys.argv[2]), int(sys.argv[3])) if len(sys.argv) > 3 else (FRAME_A, FRAME_B)
    K, dist, corners_shape, board = load_calibration()
    frame_a, frame_b = read_frame(video_path, frame_a_n, K, dist), read_frame(video_path, frame_b_n, K, dist)

    corners_a, pose_a = find_board(frame_a, K, corners_shape, board)
    corners_b, pose_b = find_board(frame_b, K, corners_shape, board)
    a_to_b = np.linalg.inv(pose_b) @ pose_a                  # true x_b = R x_a + t, from the board
    R_true, t_true = a_to_b[:3, :3], a_to_b[:3, 3]
    print(f"Frames {frame_a_n} -> {frame_b_n}: board says the camera turned {angle_deg(R_true):.1f} deg "
          f"and moved {np.linalg.norm(t_true)*100:.1f} cm")

    pixels_a, pixels_b = match_points(frame_a, frame_b)
    rays_a, rays_b = to_rays(pixels_a, K), to_rays(pixels_b, K)
    threshold = RANSAC_PIXELS / K[0, 0]
    E, inliers = ransac_essential(rays_a, rays_b, threshold)
    R, t = split_essential(E, rays_a[inliers], rays_b[inliers])
    R, t = polish(R, t, rays_a[inliers], rays_b[inliers], threshold)
    inliers = sampson_error(essential_from(Rotation.from_matrix(R).as_rotvec(), t), rays_a, rays_b) < threshold
    X = triangulate(rays_a[inliers], rays_b[inliers], R, t)
    shape_error, scale = board_shape_error(R, t, corners_a, corners_b, K, board, pose_a)
    print(f"{len(pixels_a)} matches, {inliers.sum()} fit one E ({inliers.mean()*100:.0f}%)")

    E_cv, mask = cv2.findEssentialMat(pixels_a, pixels_b, K, cv2.RANSAC, 0.999, RANSAC_PIXELS)
    _, R_cv, t_cv, _ = cv2.recoverPose(E_cv, pixels_a, pixels_b, K, mask=mask)
    shape_error_cv, _ = board_shape_error(R_cv, t_cv.ravel(), corners_a, corners_b, K, board, pose_a)

    print("\n                          from scratch | OpenCV")
    print(f"  matches agreeing        {inliers.sum():12d} | {int(mask.sum()):6d}")
    print(f"  rotation error (deg)    {angle_deg(R_true.T @ R):12.2f} | {angle_deg(R_true.T @ R_cv):6.2f}")
    print(f"  travel direction (deg)  {direction_error_deg(t, t_true):12.2f} | {direction_error_deg(t_cv.ravel(), t_true):6.2f}")
    print(f"  board corners (mm)      {shape_error*1000:12.2f} | {shape_error_cv*1000:6.2f}   (after fixing the size)")
    print(f"\nSize from the board's squares: camera moved {scale*100:.1f} cm (board says {np.linalg.norm(t_true)*100:.1f} cm)")
    depth = X[:, 2] * scale
    print(f"Triangulated {len(X)} points, depth {np.percentile(depth, 5):.2f}-{np.percentile(depth, 95):.2f} m (5th-95th percentile)")


if __name__ == "__main__":
    main()
