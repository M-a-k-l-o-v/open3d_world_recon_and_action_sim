from image_reconstructor import *

try:
    manual_capture_reconstruction()
except KeyboardInterrupt: # every capture is already saved to captures/ply/ as it's made, so nothing is lost
    print("\nStopped with Ctrl+C — captures so far are saved in captures/ply/")
