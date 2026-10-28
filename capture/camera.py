"""camera.py — one live view of the iPhone camera on the Mac; keys trigger photos and recording.

    SPACE  take a photo            -> captures/photos/
    R      start / stop recording  -> captures/videos/
    Q/ESC  quit (finishes any recording first)

How it works: macOS Continuity Camera makes the iPhone show up as a webcam. OpenCV reads its
1920x1080 frames and shows them in a window. While recording, each frame is also piped into
ffmpeg, which encodes it to H.264; stopping closes that pipe, so ffmpeg always finishes the
file cleanly. If the iPhone isn't there yet, or drops out mid-session, the window says so,
any recording is saved, and it reconnects on its own when the phone comes back.

Run from the project folder:   bash capture/camera.sh
"""

import datetime
import os
import shutil
import subprocess
import sys
import time

import cv2
import numpy as np

WIDTH, HEIGHT, FPS = 1920, 1080, 30
PREVIEW_SCALE = 0.5            # preview at 960x540 so it fits next to the terminal
WINDOW = "iPhone camera"
PROJECT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
WHITE, RED, ORANGE = (255, 255, 255), (0, 0, 255), (0, 165, 255)


def iphone_listed():
    # Ask macOS (through ffmpeg) whether an iPhone camera exists, without opening any camera —
    # so waiting for the phone doesn't keep flicking the FaceTime camera's light on and off.
    devices = subprocess.run(["ffmpeg", "-hide_banner", "-f", "avfoundation", "-list_devices", "true", "-i", ""],
                             capture_output=True, text=True).stderr
    return "iPhone Camera" in devices


def open_iphone():
    # OpenCV doesn't give camera names (and numbers them differently from ffmpeg), so pick the
    # camera that delivers 1920x1080: on this Mac that's the iPhone (FaceTime tops out at 720p).
    for index in range(3):
        camera = cv2.VideoCapture(index)
        camera.set(cv2.CAP_PROP_FRAME_WIDTH, WIDTH)
        camera.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)
        ok, frame = camera.read()
        if ok and frame.shape[:2] == (HEIGHT, WIDTH):
            return camera
        camera.release()
    return None


# Naming convention for everything saved in captures/ — <what>_<method>_<date_time>[_<detail>]:
#   photo_2026-10-28_160701.jpg                     camera.sh photo
#   video_2026-10-28_160701.mp4                     camera.sh video
#   image-recon_midas_2026-10-28_160701.ply         Main.py point cloud (frames: ..._capture01.jpg)
#   video-recon_midas_2026-10-28_160701_from-<video>.ply   video_reconstruction.py point cloud
def timestamp():
    return datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")


def capture_path(folder, filename):
    folder = os.path.join(PROJECT, "captures", folder)
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, filename)


def show(frame, text, colour=WHITE):
    # draw on a small copy only — saved photos and video stay clean
    preview = cv2.resize(frame, None, fx=PREVIEW_SCALE, fy=PREVIEW_SCALE)
    cv2.putText(preview, text, (15, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 4)
    cv2.putText(preview, text, (15, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.8, colour, 2)
    cv2.imshow(WINDOW, preview)
    key = cv2.waitKey(1) & 0xFF
    window_closed = cv2.getWindowProperty(WINDOW, cv2.WND_PROP_VISIBLE) < 1
    return key, window_closed


def save_photo(frame, filename):
    path = capture_path("photos", filename)
    cv2.imwrite(path, frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
    print(f"Saved {os.path.relpath(path, PROJECT)}")
    return os.path.basename(path)


class Recording:
    """One video file. Frames go to ffmpeg over a pipe; stop() closes the pipe so ffmpeg finishes the file."""

    def __init__(self):
        self.path = capture_path("videos", f"video_{timestamp()}.mp4")
        self.frames = 0
        # raw BGR frames in on stdin -> H.264 out. crf 18 = visually near-lossless (artefacts hurt
        # reconstruction); veryfast keeps 1080p30 encoding real-time on the M1.
        self.encoder = subprocess.Popen(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgr24",
             "-s", f"{WIDTH}x{HEIGHT}", "-r", str(FPS), "-i", "-",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", self.path],
            stdin=subprocess.PIPE)
        print(f"Recording to {os.path.relpath(self.path, PROJECT)}")

    def write(self, frame):
        self.encoder.stdin.write(frame.tobytes())
        self.frames += 1

    def elapsed(self):
        seconds = self.frames // FPS
        return f"{seconds // 60:02d}:{seconds % 60:02d}"

    def stop(self):
        self.encoder.stdin.close()      # end of input: ffmpeg finishes writing and closes the file
        self.encoder.wait()
        print(f"Saved {os.path.relpath(self.path, PROJECT)} ({self.frames} frames, {self.frames / FPS:.1f} s)")


def main():
    if shutil.which("ffmpeg") is None:
        sys.exit("ffmpeg is not installed. Run:  brew install ffmpeg")

    waiting_frame = np.zeros((HEIGHT, WIDTH, 3), np.uint8)
    camera, recording = None, None
    notice, notice_until = "", 0.0        # short message after a photo, e.g. "Saved ..."
    last_attempt = 0.0
    cv2.namedWindow(WINDOW)

    while True:
        # Not connected: show a waiting screen and look for the phone every 2 s.
        if camera is None:
            key, window_closed = show(waiting_frame, "Waiting for the iPhone (nearby, locked, same Apple ID)", ORANGE)
            if key in (ord("q"), 27) or window_closed:
                break
            if time.time() - last_attempt > 2:
                last_attempt = time.time()
                if iphone_listed():
                    camera = open_iphone()
                    if camera is not None:
                        print("Connected to the iPhone")
            continue

        ok, frame = camera.read()
        if not ok:
            print("Lost the iPhone stream — saving any recording and reconnecting")
            if recording:
                recording.stop()
                recording = None
            camera.release()
            camera = None
            continue

        if recording:
            recording.write(frame)

        hint = notice if time.time() < notice_until else None     # REC stays visible even then
        if recording:
            text, colour = f"REC {recording.elapsed()}    " + (hint or "R = stop    SPACE = photo"), RED
        else:
            text, colour = hint or "SPACE = photo    R = record    Q = quit", WHITE
        key, window_closed = show(frame, text, colour)

        if key in (ord("q"), 27) or window_closed:
            break
        if key == ord(" "):
            notice, notice_until = f"Saved {save_photo(frame, f'photo_{timestamp()}.jpg')}", time.time() + 1.5
        if key == ord("r"):
            if recording:
                recording.stop()
                recording = None
            else:
                recording = Recording()

    if recording:
        recording.stop()
    if camera is not None:
        camera.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
