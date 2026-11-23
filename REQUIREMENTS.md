# VSC requirements: three main stages

_23 Nov 2026. Repo copy of the working doc in Claude Docs; edit there first, then re-export._

## Scope

VSC turns phone video of a real space into something you can poke, in three stages taken strictly in order: **1 Renderer → 2 Simulator → 3 Actors**. Each stage has to pass its acceptance checks before the next one starts. Stage 1 is the work right now: P1 is done and P2 is in progress.

1. **Renderer**: an accurate, visual-first 3D scene from video. Camera pose comes from a VGGT-class model, used as a frozen tool.
2. **Simulator**: live, low-latency physics on that scene that gets the structure right, for both rigid and deformable objects. This is the crux of the project.
3. **Actors**: embodied agents (framed as a POMDP, with a self-designed VLA as the dream result) and non-individual ones such as environmental processes, crowds and flows.

**How to read the tables.** A *functional* requirement (FR) says what the system does. A *non-functional* requirement (NFR) says how well it has to do it: accuracy, speed, memory, cost, reproducibility. Every row has a check that settles it with a number. A row marked *proposed* has a target that hasn't been decided yet. A row marked *provisional* belongs to a later stage, and its details stay open until the stage before it is done.

**One trained artifact per stage, each consumed by the next one:** the object completion model (1) makes partial objects whole, the material model (2) gives them physics, and the embodied actor (3) is trained in the worlds that result. The scene models, completion and materials, are the centrepiece. The simulated scene is the main result.

**Sources:** `agent.md`, the checkpoint track and *What VSC trains* (claude.ai project docs, as of 23 Nov), the P1 write-up and experiment notes in `report_notes/`, and the Notion Decision log, Skill roadmap and Research reading list (probes P1–P8). Not yet synced with `claude/development-plan.md`.

## Stage 1: Renderer

Stage 1 is done when a phone video becomes **one metric 3D scene** whose objects are whole and ready to simulate: every frame has a camera pose, there's one surface instead of stacked layers, and each object has closed geometry that Stage 2 can step. P1 showed that per-frame depth stacked with ICP can't get there: even with perfect poses, frames disagree by 30.5 mm at 30–60 cm from the board. Those numbers are the baseline. The **object completion model** is this stage's trained artifact. It fills the gap the frozen tools leave, because existing completion models aim to look right rather than to be usable in physics.

### Functional requirements

| ID | The system must | Acceptance check | Probe |
| --- | --- | --- | --- |
| FR1.1 | Capture video of a space with an iPhone 14 and save it unchanged to `captures/` | A recorded video plays back at its full frame count, with no Continuity re-crops (scans use Camera-app video) | done |
| FR1.2 | Calibrate the camera (K and distortion) from a checkerboard video | `capture/camera_calibration.json` written; reprojection RMS under 0.5 px (calibration C: 0.436 px) | done |
| FR1.3 | Estimate a camera pose for every frame using a VGGT-class model, run as a frozen tool (correct only up to an overall scale) | A pose for each of the 56 desk-video frames, written in the OpenCV convention | P2 |
| FR1.4 | Produce reference poses with classic SfM (COLMAP) to compare against | COLMAP registers at least 90% of the frames *(proposed)*; sparse cloud saved | P2 |
| FR1.5 | Put the scene in metres. Physics needs real size: at 2× scale, things fall √2× too slowly and weigh 8× too much | Scale taken from the board's 15.5 mm squares by a Sim(3) (Umeyama) fit; board corners land within the stated error | P2 |
| FR1.6 | Fuse all frames into one surface, not a stack of per-frame layers | Layering test from P1 row C, run on each method's own depth and poses, reported for the 0–10, 10–30 and 30–60 cm bands | P2 |
| FR1.7 | Build a Gaussian-splat scene and render views the camera never took | 3DGS trained with gsplat on our own capture; held-out frames rendered and scored against the real ones | P3 |
| FR1.8 | Compare starting from the static scene with tracking while mapping (SLAM) | The same capture run through MonoGS or SplaTAM, scored with the same metrics | P3 |
| FR1.9 ⭐ | Turn each partial object the camera saw into a whole, simulation-ready one (closed surface, sensible mass distribution) using VSC's **own trained** completion model | Trained on synthetic whole shapes cut down to what a camera would see. On held-out shapes: completion error vs the true shape, and the share of outputs that are watertight and manifold, both compared against Reverse2Complete | not yet a probe |
| FR1.10 | Show the scene in a hosted viewer | A public link opens the splat scene in a browser | P3 |
| FR1.11 | Hand Stage 2 collision geometry for each object alongside the splats (splats render; meshes or particles collide) | Every object has a closed mesh or a particle set, in the same metric frame as the splats | P4 |

### Non-functional requirements

| ID | Quality | Target | How it's measured |
| --- | --- | --- | --- |
| NFR1.1 | Layering accuracy | Under P1 row C at every band: < 2.4 mm (0–10 cm), < 11.5 mm (10–30 cm), < 30.5 mm (30–60 cm) | P1 layering script on the desk video |
| NFR1.2 | Pose accuracy | ATE and RPE reported after Sim(3) alignment; worst board error under row B's 270 mm by a wide margin *(target value not set)* | evo, `--align --correct_scale`, against checkerboard PnP poses |
| NFR1.3 | Repeatability | Mean ± spread over 3 separate captures, not just one video | P2 results table, built in pandas |
| NFR1.4 | Memory and frame count | VGGT memory and error recorded from 10 to 160 frames; maximum frame count stated for each machine (all-pairs attention makes memory grow with frame count) | Frame-count ablation on the M1 (16 GB) and the RTX 4080 Super (16 GB VRAM) |
| NFR1.5 | Hardware and cost | Runs on the M1 and the 4080; any rented GPU is logged against the £450 initial budget | Compute ledger |
| NFR1.6 | Conventions | OpenCV camera frame (x right, y down, z forward), metres, rotations via the exp and log maps | Code review |
| NFR1.7 | Viewer responsiveness | A latency number is published; target not set *(proposed: under 100 ms per frame)* | Timed in the hosted viewer |
| NFR1.8 | Physics-usable completion | Completed objects are watertight, have consistent normals and have a volume Stage 2 can assign mass to *(pass rate target not set)* | Mesh checks on every completed object |
| NFR1.9 | Not mix-and-match | The completion model is trained by VSC; VGGT is only ever a frozen tool; COLMAP and PnP are algorithms and fine to use | Write-up says what was trained and what was run |

## Stage 2: Simulator *(provisional)*

Stage 2 is done when you can push something in the reconstructed scene and it moves the way the real object would, live, for both rigid and deformable things, and the world is shown to be reliable rather than assumed to be. There are two hard parts. The first is the **handoff point**, where splats become something a solver can step and what gets lost there: PhysX can't simulate Gaussians, so the route into Isaac needs collision meshes. The second is that **materials can't be seen**: a static capture carries no information about mass, stiffness or friction. That's the gap VSC's **material model** fills, and the gap that sets VSC apart from Real-to-Sim-to-Real.

### Functional requirements

| ID | The system must | Acceptance check | Probe |
| --- | --- | --- | --- |
| FR2.1 | Hand the Stage 1 scene to a physics solver at a chosen handoff point | Two routes built and compared: MPM directly on the Gaussians (PhysGaussian) and collision meshes paired with the splats (the Isaac Sim NuRec pattern). What each route loses is written down | P4 |
| FR2.2 | Split the scene into separate bodies, with the room fixed and the objects free to move | Each object can be selected and moved on its own; the static scene stays put | P4 |
| FR2.3 ⭐ | Give each object a **distribution** of mass, stiffness and friction from VSC's **own trained** material model: a category prior from retail data (start from Amazon Berkeley Objects; engineering tables for stiffness and friction), sharpened per object by what the video shows, then sampled into the solver | On ABO-500, mass error beats NeRF2Physics. The posterior narrows when the object moves in the video and stays at the prior when it doesn't | P6 |
| FR2.4 | Simulate rigid bodies and deformable bodies in the same scene | One rigid case and one deformable case, each run in a captured scene | P4 / P6 |
| FR2.5 | Let the user poke the scene by applying a force or moving an object | The scene responds to the input in the viewer | P4 |
| FR2.6 | Render the simulated state back as splats so it still looks like the real space | The moved objects render without holes at their old positions | P4 |
| FR2.7 | Carry the work to both export targets: Blender (mesh, optional export) and Isaac Lab or an equivalent. Both are results of the work, not the end goal | Both imports open; whatever each one refuses is written down | P5 |
| FR2.8 | *(Optional)* A learned simulator that predicts the next physics state quickly. Built only if solver speed turns out to be what holds the actor back | Trained on our own solver's runs; its speed-up and error against the solver are reported | only if needed |

### Non-functional requirements

| ID | Quality | Target | How it's measured |
| --- | --- | --- | --- |
| NFR2.1 | Live, low latency | Frame rate and input-to-response latency published *(proposed: at least 15 fps, the rate Atlas runs live)* | Timed on the RTX 4080 Super |
| NFR2.2 | World reliability: likely the headline result | Open-loop replay: the same actions in the simulation and in reality, with the error between them reported in mm *(target not set; it depends on the actor's first task)* | Film a poke, simulate the same poke, compare tracked points |
| NFR2.3 | Stability | No blow-ups (energy doesn't grow without an input) over a 60 s run *(proposed)* | Energy logged per step |
| NFR2.4 | Memory | Fits in 16 GB VRAM for a desk-sized scene | Peak memory logged |
| NFR2.5 | Ablation | The material model beats fixed default values **and** plain domain randomisation on the replay test (the Phys2Real fork). The randomisation width is the posterior's own uncertainty | Same test with each option |
| NFR2.6 | Honest data | Retail weights and sizes are cleaned (packaging, box dimensions, units); hollow objects use true volumes from the ABO 3D models | Cleaning steps listed in the write-up |
| NFR2.7 | Portability | Shape and material numbers move between engines unchanged; Isaac runs on the 4080 (Linux or Windows with an RTX card), not the M1 | Same scene loaded in both targets |
| NFR2.8 | Not mix-and-match | Solvers are algorithms and allowed; the material model is trained by VSC | Write-up |

## Stage 3: Actors *(provisional)*

Stage 3 is done when actors are introduced into the simulated scene and the physics responds to them. One kind is a **full-scale embodied VLA** ("do it right", no cut-down version) trained in the worlds Stages 1–2 build. The other kind is non-individual: environmental processes, crowds and flows. On purpose, this section only pins down the interfaces. The actor's body and its first task stay open until Stage 2 is done (`agent.md`: don't settle checkpoint-3 details early). VSC's own contribution lies in the action representation, the action expert, the data and the training recipe, not in the backbone.

### Functional requirements

| ID | The system must | Acceptance check | Probe |
| --- | --- | --- | --- |
| FR3.1 | Run an observe → act loop: the actor sees rendered views of the scene and sends actions to the simulator | One full episode runs from start to finish in a captured scene | P7 |
| FR3.2 | Write the embodied actor's problem down as a POMDP (states, actions, observations, transitions, reward) once its first task is picked. The policy sees only what its camera sees | The specification is written; the true state is never passed to the policy | P7 |
| FR3.3 ⭐ | Drive the actor with a VLA designed by VSC: an open pretrained vision-language backbone (e.g. Molmo) trained end to end on VSC's data, plus **our own action expert** trained from scratch | The trained policy beats the untrained backbone at the first task | P7 |
| FR3.4 | Output movement as DCT motion chunks (FAST-style trajectory tokens, not geometry compression) | Trajectories rebuilt from the chunks within a stated error; compression ratio reported | P8 |
| FR3.5 | Add non-individual actors: environmental processes modelled as fields that spread over the scene (fluid, heat, wear), and crowds and flows modelled as many simple movers or as a flowing density | One process and one crowd or flow each change the scene through the simulator | provisional |
| FR3.6 | Train the policy inside the reconstructed worlds, with many simulations running in parallel on the GPU (Isaac Lab or an equivalent) | Training runs without real-robot data; the learning curve and the number of parallel environments are logged | provisional |

### Non-functional requirements

| ID | Quality | Target | How it's measured |
| --- | --- | --- | --- |
| NFR3.1 | Task success | Success rate over at least 50 episodes, with its spread *(proposed)* | Fixed task, fixed seeds |
| NFR3.2 | Closed-loop agreement | Policies rank the same in the simulation as on the real setup, and fail in the same places (the Real-to-Sim-to-Real check) | Several policy checkpoints scored both ways |
| NFR3.3 | Not redundant | Each new part is compared against the strongest existing version of that part: FAST's tokenizer for the motion chunks, π₀'s flow-matching head for the action expert. Both comparisons run on a standard benchmark and on our own scenes | Benchmark table |
| NFR3.4 | Control rate | The policy and the simulator together keep up with Stage 2's live frame rate *(target not set)* | Timed loop |
| NFR3.5 | Compute | Development on the 4080 (smaller backbones, LoRA, debugging the training file); full training runs on rented 80 GB-class GPUs, logged against the budget | Compute ledger, W&B |
| NFR3.6 | Honest claims | Running a pretrained model is never written up as building it; never fine-tune someone else's robot policy and call it ours | Write-up |
| NFR3.7 | Positioning | The write-up says what Real-to-Sim-to-Real already ships (manipulation tasks captured with a robot) and what VSC adds: arbitrary static captures, where no motion is observed | Write-up |

## All stages

Every stage follows the same rules for how code gets built, written and published.

| ID | Requirement | How it's checked |
| --- | --- | --- |
| NFR0.1 | **Order:** a stage starts only after the one before it passes its checks (1 → 2 → 3) | Probe status in the checkpoint track |
| NFR0.2 | **From scratch first:** a plain NumPy version first, then the library, then a comparison of the two (the P2 two-view SfM did this) | Both versions committed |
| NFR0.3 | **Readable code:** each file opens with what it computes; comments say *why*; small functions; no unused code or speculative options | Code review against `agent.md` |
| NFR0.4 | **Done means published:** the question and its answer, one figure or table with real numbers, how to reproduce it (commands, seed, hardware), and the caveats | Public write-up in `report_notes/` |
| NFR0.5 | **Reproducible:** every number traces back to a script, a capture and a commit | Experiment note per run |
| NFR0.6 | **Trained models are VSC's own:** pretrained models are frozen tools or starting points, never the thing claimed | Each write-up says what was trained and what was run |
| NFR0.7 | **Each trained artifact earns its place:** it's built only if the next stage consumes it; three models means three training pipelines | The consuming stage is named before training starts |
| NFR0.8 | **Private data stays private:** captures are gitignored; no personal details go out to external services | `.gitignore`; review before each push |

### Open questions

- [ ] **P2's measure:** on 23 Nov Marv chose layering only. The 15 Nov Platinum design also asks for ATE/RPE, 3 captures and a 10–160 frame ablation. Which one counts as "P2 done"?
- [ ] Pose accuracy target (NFR1.2) and viewer latency target (NFR1.7).
- [ ] Stage 2's live frame rate and structural-accuracy targets (NFR2.1, NFR2.2).
- [ ] The handoff point (FR2.1): where the splats become solver input, and what is lost there. To be decided after the rendering reading.
- [ ] The actor's first concrete task. It blocks the POMDP specification (FR3.2) **and** the material model's accuracy bar (NFR2.2): the same question seen from both ends.
- [ ] The actor's body (arm, mobile manipulator or humanoid). To be settled when Stage 3 is reached.
- [ ] The stand-in-CAD pose route: a rough pose first, rotate into the canonical frame, complete, then track with keypoints and PnP. Should it become a Stage 1 probe? It isn't a requirement yet.
- [ ] The entry point: start from the static scene or from SLAM? Deferred until the foundational reading; FR1.8 compares both.
- [ ] Sync these requirements against `claude/development-plan.md`.
