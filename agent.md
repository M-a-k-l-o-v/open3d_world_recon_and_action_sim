# agent.md — how we're approaching VSC

_Last updated 26 Oct 2026. Short on purpose. BAYMAX is a reference for how Marv likes to organise things, not a template — VSC is a solo, for-fun learning project and isn't aiming at a publication._

**For any AI assistant on this project:** read this first, every session. It's how Marv wants to work, not a rulebook.

---

## What VSC is

Turn video of a real space into something you can poke: a 3D reconstruction, then a physics simulation of it, then an actor that acts inside it.

1. **Renderer** — accurate, visual-first scene reconstruction from video. Pose comes from a VGGT-class model (decided 3 Sep).
2. **Simulator** — *the real crux*: live, low-latency, structurally accurate, rigid **and** deformable physics.
3. **Actors** — the introduction of actors into the simulated scene: embodied ones (POMDP framing; the dream result is a self-designed VLA) and non-individual ones (environmental processes, crowds and flows).

**Scene-first.** The priority is the scene — reconstruct it (1), then simulate it (2); actors come in later (3). **The checkpoints are the order of progression: 1 → 2 → 3.** Don't settle checkpoint-3 details (like the actor's body) while checkpoint 1 is the work.

Isaac (or equivalent) and a Blender export both come *out of* the work at different stages — neither is "the endgame". The DCT idea lives in **checkpoint 3**, as a candidate way to model **actor movement in the scene** (compact motion chunks, FAST-style).

**What it isn't:** a demo, a stepping-stone with a ship date, or an attempt to out-build World Labs. It's Marv learning the whole stack by building it, and seeing where his own ideas take it.

## The deal

- **The hard version, no rescoping.** No "park it", "do it later", "after X ships". Marv owns scope and order.
- **Straight talk.** Say when something is lab-scale, already published, or doesn't hold up. No flattery.
- **Changing our minds is fine.** New information → re-open the decision, note the date.
- **Sundays off.** Skip a session without guilt; if something clicks fast, move faster.

## How we build

- **Build alongside reading.** Small experiments ("probes") that poke an open question. Try it, see what breaks, write down what we learned. A result that says "nope" is a good result.
- **From scratch first, then the library.** A plain NumPy version first so the mechanism is visible, then the real library, then compare. (Marv's own pattern from his ML prep.)
- **One or two sentences on "what is this actually computing?"** for anything worth understanding.
- **Open questions live in `CHECKPOINT_TRACK.md`.** Status, decisions and the probe list live there, not here.

Probe list right now: pose drift · VGGT frame limit on the 4080 · where to start (static scene vs SLAM) · the physics handoff (splats → solver) · exporting to both Blender and Isaac · material properties from a camera · the actor's first task · actor-motion compression (DCT/FAST) · the stand-in-CAD pose route.

## Who does what

- **Marv designs.** Architecture, what gets trained and why, how the pieces connect, what an experiment should show. He doesn't write the code.
- **Claude writes the code** to Marv's design, and explains it.
- **Marv debugs and edits the training file** when he wants to — so the training file in particular has to be easy to find your way around.
- **Not a mix-and-match project.** VSC trains **its own models** — each stage aims for its own trained artifact where it earns its place — **the scene models are the centrepiece** (object completion and the material model; details in `TRAINED_ARTIFACTS.md`). Pretrained models appear only as **frozen tools** (VGGT for pose) or as a **starting point** that we then train end to end (the actor's vision-language backbone) — never as the thing we claim. Algorithms (geometry, solvers) are fine. Details: `TRAINED_ARTIFACTS.md` (project doc).
- **The learning boxes** in the foundations list stay Marv's own coding exercises, outside VSC. Claude doesn't do them.

## How code gets written

1. **Readable first.** Written so Marv can follow it:
   - each file opens with a few lines on what it does and what it computes;
   - comments say *why*, not what the next line obviously does;
   - small functions with plain names, one job each, top-to-bottom order where possible;
   - no clever one-liners where three clear lines would do.
2. **Minimal changes. No bloat.**
   - each change is the smallest edit that does the job;
   - no speculative options, config knobs, abstractions or "just in case" handling;
   - no unused functions, no reformatting code that wasn't touched;
   - if something isn't used yet, it isn't written yet.

## Gotchas we've already hit (so we don't again)

- **Know what kind of depth you have.** MiDaS gives *inverse* depth with unknown scale and shift — the old prototype used it as real depth, which bent the room and made every "2 cm" threshold meaningless. VGGT-style output is only off by one overall scale.
- **Don't guess the focal length.** Calibrate or read it from the phone.
- **Rotations:** don't gradient-descend raw matrices or average Euler angles — use the exp/log maps.
- **A nice render isn't nice geometry.** Splats are tuned for pixels; physics needs surfaces.
- **Same camera convention everywhere:** OpenCV (x right, y down, z forward), metres.

## How to talk to Marv

- **Visual first** — diagram, picture, or physical analogy before the formal version. For bigger explanations: an interactive explainer with sliders and a quick check-yourself at the end.
- **Define every term** the first time. Plain names, not codes.
- **For any NeRF chat:** give the foundations reminder in `claude/ml_pytorch_foundations_nerf_reminder.md` first, then teach.
- Two questions worth asking of every paper: *how does it handle scale?* and *how does it represent camera pose?*

## Where things live

- **This folder** — the project: `Artifacts/` (the sketch board — re-read it, it's often ahead of the docs), `Virtual_space_constructor/` (the old prototype), `capture/` (iPhone photo/record scripts — output goes to `captures/`; `calibrate.py` + checkerboard write the camera intrinsics to `capture/camera_calibration.json`), and code as it gets built.
- **Project docs (Cowork/claude.ai):** `CHECKPOINT_TRACK.md` (decided / open / probes), `TRAINED_ARTIFACTS.md` (what VSC trains), `HANDOVER.md` (history and the prototype audit), the ML foundations reminder.
- **Notion:** the *Research reading list* (what's read) and the Tasklist decision log.
- **Calendar:** the morning reading block, "Deep work — reconstructor model", Thursday VSC build sessions.
- **`report_notes/`** — Claude's own notebook (method notes, where each result came from) for if and when Marv wants to write a report. Not rules for Marv; he can ignore it.

## Kit

M1 MacBook Pro (16 GB) · desktop RTX 4080 Super (16 GB VRAM, 32 GB RAM) · iPhone 14 · rented compute when a probe needs more — **£450 is the initial budget**, expected to grow over the long roadmap.

---
_Changelog_ — 26 Oct 2026: scene models are the centrepiece; checkpoint 3 = introduction of actors. Scene-first priority. Checkpoints = order of progression. Pretrained-model rule confirmed (frozen tool or starting point). £450 marked as an initial budget, expected to grow. Marv designs, Claude writes code; readable + minimal-change rules added; "train our own model, not mix-and-match" added. Earlier the same day: first version. Lightweight by Marv's request; the heavier draft moved to `report_notes/`. If there's an older `vsc-agent.md` from 18 Oct in another project, paste it in and we'll merge.
