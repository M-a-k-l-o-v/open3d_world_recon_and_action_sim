# image_reconstructor.py — point cloud of a room from iPhone frames, using MiDaS depth.
#
# What it computes: MiDaS predicts *relative inverse depth* — bigger means nearer, and it is
# off by an unknown scale s and shift t:  1/Z = s * prediction + t.  With the checkerboard in
# view, solvePnP gives the true distance to every board corner, which pins down s and t.
# Then each pixel gets a real depth Z in metres and is unprojected with the calibrated camera K.
# Each capture is also placed in the board's frame, so captures line up before ICP refines them.

#imports
import cv2
import json
import os
import sys
import time
import torch
import numpy as np
import open3d as o3d
import collections

# iPhone connection and preview window are shared with the capture scripts (capture/camera.py)
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "capture"))
from camera import iphone_listed, open_iphone, show, save_photo, capture_path, timestamp, PROJECT

# camera intrinsics and checkerboard size, made by capture/calibrate.py
CALIBRATION_FILE = os.path.join(os.path.dirname(__file__), "..", "capture", "camera_calibration.json")
CAMERA_NAME = "iphone14_continuity_1080p"

with open(CALIBRATION_FILE) as f:
    calibration = json.load(f)
camera_calibration = calibration["cameras"][CAMERA_NAME]
K = np.array(camera_calibration["K"])
dist_coeffs = np.array(camera_calibration["dist_coeffs"])
board_corners = tuple(calibration["board"]["inner_corners"])
square_size = calibration["board"]["square_size_m"]

#loading image proceesing model midas
device = "mps" if torch.backends.mps.is_available() else "cpu" # tries to use gpu if availiable else uses cpu

depth_model = torch.hub.load("intel-isl/MiDaS", "DPT_BEiT_L_512") # MiDaS v3.1's largest and most accurate model
depth_model.to(device)
depth_model.eval()

transform = torch.hub.load("intel-isl/MiDaS", "transforms").beit512_transform #defines the function to transforms image into a form for MIDAS' depth prediction models(transformation includes file type btw) and moves it to the gpu for inference

def clear_all():
    import torch, gc, cv2
    torch.cuda.empty_cache()
    gc.collect()
    cv2.destroyAllWindows()

def get_inverse_depth(rgb_frame): # MiDaS output is relative *inverse* depth, not depth — see fit_scale_and_shift
    rgb_image = cv2.cvtColor(rgb_frame, cv2.COLOR_BGR2RGB).astype(np.float32) # Convert from BGR(blue - green - red) (OpenCV default) to RGB for midas
    
    # Apply MiDaS transform (returns tensor)
    transformed = transform(rgb_image) # normalised for midas so image/255
    input_tensor = transformed.to(device)

    with torch.no_grad(): # this is an evalution so there is no need to waste processing power on gradient calculation for the weights
        depth_prediction = depth_model(input_tensor) 
    
        depth_prediction = torch.nn.functional.interpolate( #to resize the depth map to the camera resolution 
            depth_prediction.unsqueeze(1), # the depth_prediction is 3D but the interpolation function expects a 4D form we unsqueez
            size=rgb_image.shape[:2],
            mode="bicubic",
            align_corners=False,
        ).squeeze()

        inverse_depth = depth_prediction.squeeze().cpu().numpy() # needs to be renomalised for opencv which is done below

        depth_vis = cv2.normalize(inverse_depth, None, 0, 255, cv2.NORM_MINMAX)
        depth_vis = depth_vis.astype(np.uint8)
        depth_color = cv2.applyColorMap(depth_vis, cv2.COLORMAP_MAGMA)

        cv2.imshow("Depth Map", depth_color)
        cv2.waitKey(1)

    return inverse_depth, rgb_image # Return both!

def board_points():
    # the board's inner corners in its own frame: flat (z = 0), in metres
    cols, rows = board_corners
    points = np.zeros((cols * rows, 3), np.float32)
    points[:, :2] = np.mgrid[0:cols, 0:rows].T.reshape(-1, 2) * square_size
    return points

def find_board_pose(frame):
    # where the camera is relative to the checkerboard (R, tvec), or None if the board isn't fully visible
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    found, corners = cv2.findChessboardCorners(gray, board_corners)
    if not found:
        return None
    corners = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1),
                               (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001))
    _, rvec, tvec = cv2.solvePnP(board_points(), corners, K, None) # frame is already undistorted, so no distortion here
    R, _ = cv2.Rodrigues(rvec)
    return R, tvec, corners.reshape(-1, 2)

def fit_scale_and_shift(inverse_depth, R, tvec, corners):
    # solve 1/Z = s * prediction + t by least squares, using the board corners' true depths.
    # A tilted board covers a wider range of depths and pins the shift t down better. Far from
    # the board's distance this is an extrapolation, so far walls are the least trustworthy part.
    corner_depths = (board_points() @ R.T + tvec.T)[:, 2] # true Z of each corner, metres
    u, v = np.round(corners).astype(int).T
    predictions = inverse_depth[v, u]

    A = np.stack([predictions, np.ones_like(predictions)], axis=1)
    (s, t), *_ = np.linalg.lstsq(A, 1 / corner_depths, rcond=None)

    fit_error_mm = np.sqrt(np.mean((1 / (A @ [s, t]) - corner_depths) ** 2)) * 1000
    print(f"  board at {corner_depths.min():.2f}-{corner_depths.max():.2f} m, depth fit error on board: {fit_error_mm:.1f} mm")
    return s, t

def inverse_depth_to_metric(inverse_depth, s, t):
    # where s * prediction + t <= 0 the depth would be infinite or behind the camera: leave those at 0 (filtered out later)
    fitted_inverse = s * inverse_depth + t
    depth = np.zeros_like(fitted_inverse)
    np.divide(1, fitted_inverse, out=depth, where=fitted_inverse > 0)
    return depth

def camera_to_board(R, tvec):
    # 4x4 transform taking camera-frame points into the board's frame, which every capture shares
    T = np.eye(4)
    T[:3, :3] = R.T
    T[:3, 3] = (-R.T @ tvec).ravel()
    return T

def depth_to_3d_points_with_color(depth_map, rgb_image):
    height, width = depth_map.shape
    fx, fy, cx, cy = K[0, 0], K[1, 1], K[0, 2], K[1, 2] # calibrated, not guessed
    y_indices, x_indices = np.indices((height, width))

    Z = depth_map
    X = (x_indices - cx) * Z / fx
    Y = (y_indices - cy) * Z / fy

    points_3d = np.stack((X, Y, Z), axis=-1).reshape(-1, 3)
    colors  = rgb_image.reshape(-1, 3) / 255.0  # Normalize to 0-1
    return points_3d, colors

def connect_to_iphone():
    # wait for the iPhone instead of quitting — it can take a few seconds to wake up or reconnect
    while True:
        if iphone_listed():
            camera = open_iphone()
            if camera is not None:
                print("Connected to the iPhone")
                return camera
        print("Waiting for the iPhone (nearby, locked, same Apple ID)... Ctrl+C to stop")
        time.sleep(2)

def manual_capture_reconstruction():
    camera = connect_to_iphone()

    scene_points = o3d.geometry.PointCloud()
    session = f"image-recon_midas_{timestamp()}" # names this run's files (convention in capture/camera.py)
    ply_path = capture_path("ply", f"{session}.ply") # one file per session, rewritten after every capture

    voxel_size = 0.002 # 2 mm: fine enough to see 15.5 mm board squares in a desk-scale scene
    capture_count = 0
    visualizer = None

    print("=== Manual Capture Mode ===")
    print("SPACEBAR - Capture frame")
    print("ESC - Finish and save")
    print("\nPosition camera and press SPACEBAR when ready...")


    while True:
        success, frame = camera.read()
        if not success: # the iPhone dropped out: reconnect, keeping the captures so far
            print("Lost the iPhone stream — reconnecting")
            camera.release()
            camera = connect_to_iphone()
            continue

        # Show live preview with instructions (same 960x540 window as capture/camera.sh)
        key, window_closed = show(frame, f"Captures: {capture_count}    SPACE = capture    ESC = done")

        # Spacebar pressed - capture!
        if key == 32:  # Spacebar
            print(f"\n[Capture {capture_count + 1}] Processing...")
            save_photo(frame, f"{session}_capture{capture_count + 1:02d}.jpg") # keep the raw frame, even if this capture gets skipped
                
            if frame.shape[:2] != (camera_calibration["height"], camera_calibration["width"]):
                print(f"  Camera gives {frame.shape[1]}x{frame.shape[0]}, but the calibration is for "
                      f"{camera_calibration['width']}x{camera_calibration['height']} — is camera 0 the iPhone?")
                break

            frame = cv2.undistort(frame, K, dist_coeffs) # straighten the lens distortion so the pinhole model (and K) holds exactly
            pose = find_board_pose(frame)
            if pose is None:
                print("  Checkerboard not fully visible — skipped. Metric depth needs it in view.")
                continue
            R, tvec, corners = pose

            # Depth estimation and conversion: inverse depth -> metres -> 3D points
            inverse_depth, rgb_image = get_inverse_depth(frame)
            s, t = fit_scale_and_shift(inverse_depth, R, tvec, corners)
            depth_map = inverse_depth_to_metric(inverse_depth, s, t)
            new_points, new_colors = depth_to_3d_points_with_color(depth_map, rgb_image)

            # Filter out extreme depth values (common noise) — now real metres
            valid_mask = (depth_map.flatten() > 0.1) & (depth_map.flatten() < 10) # 0.1 m, not 0.5: desk scenes sit ~0.3-0.4 m away
            new_points = new_points[valid_mask]
            new_colors = new_colors[valid_mask]

            # Build Open3D cloud with colour
            new_cloud = o3d.geometry.PointCloud()
            new_cloud.points = o3d.utility.Vector3dVector(new_points)
            new_cloud.colors = o3d.utility.Vector3dVector(new_colors)

            # Statistical outlier removal (reduces noise!)
            new_cloud, _ = new_cloud.remove_statistical_outlier(nb_neighbors=20, std_ratio=2.0)

            # Move into the board's frame: captures from different spots now start already lined up, so ICP only refines
            new_cloud.transform(camera_to_board(R, tvec))

            if len(scene_points.points) == 0:
                # First capture - just add it
                scene_points = new_cloud
            else: # align the new scene with the old one using ICP, which finds the best transformation( using rotation or translation) to align the new and old scenes
                 threshold = 0.02 # distance threshold, the maximum distamce to considered a point   match 
                 intial_transformation = np.identity(4)

                 reg = o3d.pipelines.registration.registration_icp(
                 new_cloud, scene_points, threshold, intial_transformation,
                 o3d.pipelines.registration.TransformationEstimationPointToPoint(),
                 o3d.pipelines.registration.ICPConvergenceCriteria(max_iteration=50)
                )
                 
                 # Apply transformation to align
                 new_cloud.transform(reg.transformation)
                 scene_points += new_cloud

            scene_points = scene_points.voxel_down_sample(voxel_size)

            # Save straight away, before any rendering: a crash, Ctrl+C or lost phone can't lose this capture
            o3d.io.write_point_cloud(ply_path, scene_points)
            print(f"  saved to {os.path.relpath(ply_path, PROJECT)}")

            # Create visualizer after first capture
            if visualizer is None:
                print("Creating 3D visualizer window...")
                visualizer = o3d.visualization.Visualizer()
                visualizer.create_window("3D Scene", width=1000, height=800)
                visualizer.add_geometry(scene_points)
            else:
                visualizer.clear_geometries()
                visualizer.add_geometry(scene_points)
                visualizer.reset_view_point(True)
            
            capture_count += 1
            print(f"✓ Added to scene. Total points: {len(scene_points.points)}")

        # ESC pressed (or preview window closed) - finish
        if key == 27 or window_closed:
            break

        if visualizer is not None:
            visualizer.poll_events()
            visualizer.update_renderer()

    camera.release()
    cv2.destroyAllWindows()
                
    if len(scene_points.points) > 0:
        print(f"\n✓ Scene saved in {os.path.relpath(ply_path, PROJECT)}")
        o3d.visualization.draw_geometries([scene_points], 
                                         window_name="Final 3D Scan",
                                         width=1000, height=800)
    
    return scene_points
    

    
    




