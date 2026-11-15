# P1: Why my first reconstruction stacked layers instead of one surface

TL;DR (3 lines)
  Question · headline number (6 mm vs 38 mm) · what it changed


1. The question                       ~80 words
   Per frame pose estimation ability of the MIDAS model, how does the relative inverse depth affect pose drift with camera pose change? And why? 

2. Setup                              ~120 words
    I set up a test to see how well the points/frame aligned with each other, it is noted that the pipeline is unable to distiguish what was previously rendered, hence, the points captured are the same scene from a different camera pose ploted in the space. However due to the nature of the test, as a walked handheld arc, with focus on the board on the table, and minimal movemment in other dimentions of rotations and translation, allows us to focus the evaluation around the points closer to the board, as the only item with known scale and position. especially how the pose drift between frames by comparing camera movement to point drift in the cloud.

3. Result                             figure + ~150 words
   [FIGURE: two camera paths on one plot, ICP vs reference,
    drift growing frame by frame]
   Table: error at frame 1 / 10 / N

4. Why it happens                     ~150 words
   MiDaS depth is relative with no scale, and its relative inverse depth calculation uses the closest pixels as the primary informant to the point, so where the camera pose changes, the relative depth of sorrunding objects in the pixel space can be very different resulting in largely differnt pose. hence a drift in pose between frames where camera pose changes.
   - Turning counts as well as walking. At about 1 m away, turning the camera 1° shifts the desk points about 1.7 cm, so a 3° turn alone moves things about 5 cm, past the search distance.
   - The flat desk makes it worse. A flat surface lines up with itself however you slide it along the plane, so ICP has nothing to stop it sliding the wrong way.

5. Proven / claimed / inferred        3 bullets
   What I measured, what I took from papers, what I'm guessing
   - Measured: real steps of 5.7 cm against ICP's 2.4 cm, and 47 of 55 steps over 2 cm.
   - Inferred: "frames too far apart for ICP's 2 cm search is the cause". It fits the data, but we haven't tested it directly.

6. Limitations                        3 bullets
   The experiment was a simple one with only one scene, and camera intrinsics with had a x misalignment which was later adjusted and recalculated to provide a more accurate results table. 
   The camera was handheld so hand movement may include some vibration that affected angle and relative position of the checkerboard which may acount for some of pose drift recorded

7. What it changed                    ~60 words
   Pose comes first, which leads to P2 (VGGT vs COLMAP)
   The next step moves past the use of a model that use relate inverse depth to one that can minimizes pose drift between frames, focusing on models that are more suited to multiview camera geometry (VGGT vs COLMAP)

Appendix: paper notes
   Your Reconstructor sketch notes (MonoDiff9D, R2S2R, WMPO ...),
   tidied and with citations
   - this will be mainly on how the papers discus pose estimation models' sensitivition to camera pose and rotation and scale intrinsics of the capture.