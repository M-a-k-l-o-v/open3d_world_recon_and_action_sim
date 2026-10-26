# open3d_world_recon_and_action_sim (VSC — Virtual Space Constructor)

Turn video of a real space into something you can poke: a 3D reconstruction, then a physics
simulation of it, then actors inside it. Checkpoints in order: **1 reconstruct → 2 simulate → 3 actors**.
How the project is run: [agent.md](agent.md).

## Layout

| Folder | What's in it |
| --- | --- |
| `capture/` | iPhone capture scripts (Continuity Camera + ffmpeg), checkerboard, camera calibration |
| `captures/` | Photos and videos the scripts save (not committed) |
| `Virtual_space_constructor/` | The old MiDaS + Open3D prototype |
| `Artifacts/` | Sketch board and past results (large files via Git LFS) |
| `report_notes/` | Method notes for a possible write-up |

## Setup (macOS, Python 3.11)

```bash
git lfs install                      # once per machine; Artifacts/ uses LFS
brew install ffmpeg
python3.11 -m venv Virtual_space_constructor/live3d_env
Virtual_space_constructor/live3d_env/bin/pip install -r requirements.txt
```

The first run downloads the MiDaS weights (~1.5 GB) into `~/.cache/torch/hub`.

## Capture and calibration

```bash
bash capture/photo.sh         # one photo  -> captures/photos/
bash capture/record.sh        # video, q to stop -> captures/videos/
```

Calibrate once per camera stream: show `capture/checkerboard.png` full-screen or print it, measure one
square in mm, record ~30 s moving the phone around it, then:

```bash
Virtual_space_constructor/live3d_env/bin/python capture/calibrate.py captures/videos/<file>.mp4 iphone14_continuity_1080p <square_mm>
```

This writes `capture/camera_calibration.json` (intrinsics K, distortion, board size), which the
prototype reads.

## Prototype

```bash
cd Virtual_space_constructor && live3d_env/bin/python Main.py
```

Keep the checkerboard in view; SPACE captures, ESC saves `scanned_scene.ply`.
