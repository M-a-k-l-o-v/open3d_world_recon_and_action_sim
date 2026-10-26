> **Status: not the working agreement.** This was the first draft of agent.md (26 Oct 2026). Marv asked for something lighter and fun, with heavier method kept out of his way. It now serves as Claude's private method notes for its own experiments and for any future report. The real file is `../agent.md`.

# agent.md — How we approach the Virtual Space Constructor (VSC)

**Version:** 1.0 · **Drafted:** 2026-10-26 · **Owner:** Marv
**Applies to:** Marv, and every AI assistant working on VSC (Cowork, Claude Code, claude.ai chats, any other tool).
**Modelled on:** BAYMAX's `docs/METHODOLOGY.md` (AI-ingested policy, Aug 2026), `docs/PROJECT.md` (is / isn't framing), `docs/OWNERSHIP.md` (who builds what, AI-use rules) and `docs/decisions/0000-template.md` (ADRs) — adapted, not copied. Where VSC deliberately differs from BAYMAX, this file says so.

> **If you are an AI assistant:** read this file at the start of every working session, before touching code or docs. Apply it when you write code, design or run a probe, analyse results, or update project docs. Flag violations of it even when nobody asked you to review methodology. If this file and a project doc disagree, this file governs *how* we work; `CHECKPOINT_TRACK.md` governs *what is decided*. If either disagrees with a newer, dated decision by Marv, Marv's decision wins — record it and fix the stale doc.

---

## 0. Where the truth lives (read order)

| What | Where | Holds |
|---|---|---|
| **How we work** | `agent.md` (this file, project root) | Method, rules, conventions |
| **What is decided / open** | `claude/CHECKPOINT_TRACK.md` (project doc) | Decisions table, open questions, tensions, reading order |
| **History + background** | `claude/HANDOVER.md` (project doc) | Prototype history, the inverse-depth audit, architecture lanes |
| **Live design surface** | `Artifacts/Reconstructor free sketch.pdf` | Checkpoint diagram + Marv's paper notes. Re-read it; it may be ahead of the docs |
| **Reading status** | Notion → Tasklist → *Research reading list* | The authoritative reading checklist |
| **Cross-project decisions** | Notion → Tasklist → Decision log | Dated decisions, newest first |
| **Time** | Google Calendar (reading block, "Deep work — reconstructor model", VSC build sessions) | When work happens |
| **Foundations gate** | `claude/ml_pytorch_foundations_nerf_reminder.md` | The PyTorch / backprop boxes and the NeRF reminder rule |
| **Original brief** | `BAYMAX/future_work/open3d_world_recon_and_action_sim.md` | The idea as first written (Aug 2026), incl. the original thesis |

Conflict rule: **newest dated decision by Marv wins.** A session's *reading* of a whiteboard or doc is not a decision until Marv confirms it (the 30 Sep "Isaac is the endgame" misreading is the cautionary example).

---

## 1. The working agreement (non-negotiable)

- **No rescoping, parking, deferring, or "come back after X ships" framing.** The hard version gets executed. *This is where VSC differs most from BAYMAX:* BAYMAX was locked as a stepping-stone with a `DEFERRED.md` of not-planned work. VSC has **no deferred list** — it has an **open-questions register** (in `CHECKPOINT_TRACK.md`). Nothing gets filed as "not happening."
- **Marv owns all scope and sequencing decisions.** Assistants surface trade-offs and difficulty; they do not decide ordering, cut scope, or close a "Marv's call" question.
- **Straight technical truth about difficulty.** Say plainly when something is lab-scale, when a claim doesn't hold, when an idea is already published. No sycophancy — the Marble-1 brief exists precisely because an LLM once told Marv he'd "reverse-engineered the cutting edge." Don't do that.
- **Re-questioning is welcome.** Marv likes re-opening tool and method decisions when new information arrives. Do it with the evidence, dated.
- **Build alongside reading** (since 18 Oct 2026). Reading alone drains the fun; small probes that test open questions run in parallel with the reading block, and every probe feeds a written report.

---

## 2. What VSC is — and isn't

### VSC is
- **A research direction with three checkpoints**, not a completable sequence:
  1. **Renderer** — a visual-first, accurate scene reconstructor (pose, splats, SLAM live here).
  2. **Simulator** — *"the real crux"*: a live, low-latency, high-fidelity **structural** reconstructor with rigid **and** deformable physics.
  3. **Planner** — an actor under a POMDP that models the simulator's effect; stated result: **a self-designed VLA**.
  Arrows: Renderer → Simulator → Blender scene; Simulator → Planner; Blender scene → Planner. Isaac (or equivalent) and Blender export are **both consequences** of the work at different stages — not "the endgame." The open question is whether the work is **transmittable to both** (Marv, 13 Oct).
- **A learning project.** Marv wants to genuinely understand the stack, and to be challenged. Working code that Marv can't explain is a failure, not a success.
- **A flagship candidate.** Checkpoint 1 done properly is already a portfolio artifact.

### VSC is not
- **Not a demo.** A pretty render with wrong geometry doesn't count (see the photometric-vs-structural rule, §5).
- **Not "another Cosmos / Genie / Real-to-Sim-to-Real."** Those are lab-scale, funded efforts. Re-implementing them is learning, not contribution — say which one you are doing.
- **Not a stepping-stone** in the BAYMAX sense. There is no ship-and-move-on date.

### The thesis (what could make VSC a contribution)
From the original brief, and re-confirmed by Marv on 26 Oct 2026:

> **DCT-based compression lives in checkpoint 3, as a candidate method for modelling actor movement in the reconstructed scene** — compact, tokenizable motion chunks for the planner (the FAST idea, applied to actors in reconstructed space).

Standing technical cautions, from Marv's own Marble-1 brief — apply them every time DCT comes up:
1. **An orthonormal DCT is a rotation.** It preserves energy; on its own it buys nothing a linear layer couldn't. **Any real benefit comes from truncation** (keeping the top-K coefficients) — a dimensionality-reduction claim, which is testable.
2. **Pick the transform by where the redundancy lives.** DCT suits signals whose redundancy is temporal (a 7-DoF arm). A many-joint actor or a dense surface is also correlated *across space*; there, spatial bases (PCA, graph-Laplacian) are serious competitors.
3. **Receding-horizon spectral leakage.** Sliding the window changes every coefficient. "Low-frequency tokens stay stable" is false.
4. **Discrete vs continuous.** If diffusing, diffuse over continuous coefficients, not BPE'd tokens.

A second candidate gap (from Marv's 26 Oct reading of R2S2R): **material properties for arbitrary static captures, where no dynamics are observed.** R2S2R captures tasks being performed; VSC captures static rooms. Whether VSC's contribution is the DCT-actor thesis, this gap, both, or "build it to learn it" is **open and Marv's call.**

**Novelty watch:** before claiming either thesis, check whether a major lab has published it (the original brief named NVIDIA, DeepMind, Google, Meta, Physical Intelligence; World Labs/AMD now belongs on that list). Finding prior art re-states the contribution; it does not end the project.

---

## 3. How we work: probes

A **probe** is a small, controlled experiment that answers one open question and **can fail**. Probes are how VSC moves from reading to building.

### Probe card (every probe gets one, in `docs/probes/`, before it runs)
```
# Probe <ID> — <plain-language name>
Open question it serves:   <name from CHECKPOINT_TRACK>
Hypothesis:                <one falsifiable sentence>
Failure criterion:         <written BEFORE running: what result means "no">
Design:                    <synthetic / benchmark dataset / own capture; what is varied; what is held fixed>
Baselines & controls:      <what it is compared against, incl. a deliberately naive baseline>
Metrics:                   <with units; geometric and photometric reported separately>
Sample size & seeds:       <how many scenes / captures / trials; seeds fixed>
Compute & cost:            <local (M1 / 4080) or rented; £ estimate against the £450 budget>
Result:                    <numbers, with sample size>
Verdict:                   supported | refuted | inconclusive (+ why)
What this changes:         <which decision / open question moves, and how>
Next probe:                <the question this result raises>
```
Rules:
- **Pre-register the failure criterion.** BAYMAX dropped pre-registration as "publication overhead" for its stepping-stone scope. **VSC brings it back** — this is a research direction, and post-hoc rationalisation is the main way a solo researcher fools himself.
- **Negative results are results.** "Refuted" is a complete, useful outcome. Write it up the same way.
- **Synthetic first when you need ground truth, then real data.** A synthetic result is a *hypothesis about real data*, not a conclusion about it. Every synthetic probe names the real-data probe that would confirm it.
- **Never change the test after seeing the result without logging it** (what changed, why, and the original result).

### The probe queue (from 18 Oct 2026; status lives in `CHECKPOINT_TRACK.md`)
| ID | Plain name | Open question |
|---|---|---|
| P1 | Pose drift | How fast pose error accumulates over a capture, and what fixes it |
| P2 | VGGT frame limit | How many frames a VGGT-class model handles on the RTX 4080 Super (16 GB) before running out of memory |
| P3 | Where to start | Static-scene-first vs SLAM-first entry point |
| P4 | Physics handoff | Where the pipeline crosses from splats to what the solver needs, and what is lost |
| P5 | Two exports | Does the work transmit to both Blender (mesh) and Isaac (or equivalent)? |
| P6 | Material properties | What a camera can and can't tell you about mass, stiffness, friction |
| P7 | The actor's task | One concrete POMDP task — blocks P6's accuracy bar too |
| P8 | Actor-motion compression | DCT / FAST for actor motion chunks (checkpoint 3) |
| P9 | Stand-in CAD pose route | completion → stand-in CAD → keypoints → PnP, and the reordered version (proposed 26 Oct) |

Cloud-runnable synthetic probes (no GPU) are written in `vsc_lab/` and attach to the probe they serve; GPU probes run on the 4080 or rented compute.

---

## 4. Decision records (ADRs)

Any decision that crosses checkpoints, fixes a representation, or picks a substrate gets an ADR in `docs/decisions/NNNN-title.md`, using BAYMAX's template unchanged: **Context → Decision → Reasoning → Alternatives considered → Consequences → Open questions → References**, with Status (Proposed / Accepted / Superseded by ADR-NNNN), date and author.
- Decisions already made that should be back-filled as ADRs: pose from a VGGT-class model (3 Sep); DCT placed in checkpoint 3 for actor movement; physics framed as a handoff-point question (30 Sep / 13 Oct); Isaac and Blender as consequences, not endgame (13 Oct).
- **Supersede, never delete.** A wrong decision stays on record with a pointer to the one that replaced it.
- The "Reasoning" section is the one that gets quoted under interview drilling. Make it defensible.

---

## 5. Methodology rules

### 5.1 The VSC failure modes
Every methodology concern should name which of these it guards against:

| Failure mode | What it looks like | Standard guard |
|---|---|---|
| **Unit / frame error** | Numbers in the wrong units or frame silently flow downstream. *The prototype's defining bug:* MiDaS outputs inverse relative depth; the code used it as metric Z, so the room bent and every 2 cm threshold was meaningless | Every array has documented units and frame; assert them at module boundaries; synthetic checks with known ground truth |
| **Photometric ≠ structural** | A render looks right, the geometry is wrong (3DGS optimises pixels, physics needs surfaces) | Report geometric metrics (Chamfer, normals, planarity, scale) **separately** from photometric ones (PSNR, SSIM, LPIPS). Never cite one as evidence for the other |
| **Single-scene overfitting** | It works on one room | Name the number of scenes/captures with every claim; hold out captures |
| **Test-set tuning** | Thresholds tuned on the capture you report | Tuning captures and evaluation captures are separate, and labelled |
| **Synthetic-to-real gap** | A clean synthetic win stated as a real one | Synthetic results are labelled synthetic, with the real-data follow-up named |
| **Benchmark ≠ robustness** | Strong benchmark scores, collapse in the wild (Marv's MonoDiff9D note: Wild6D 10°10cm = 11.1%) | Include an in-the-wild or shifted tier wherever one exists, reported separately |

### 5.2 Reporting honesty
- **Sample size with every number.** Seeds fixed and recorded.
- **Say what kind of number it is.** A pass rate is not an average error (9.6% 3D50 means 9.6% of predictions pass, not mean IoU 9.6%). Report medians and tails (p90), not just means.
- **Defensible comparisons only:** against your own baseline or ablation; against a published number on the *same* benchmark and protocol; cost-normalised. **Never** "VSC beats World Labs / NVIDIA."
- **Big jumps against your own weakened variants are not wins against the field** (Marv's 6D-Diff note: 49.2 → 79.6 is against their own ablations; +2.1 / +2.4 against other methods).

### 5.3 Conventions that prevent the prototype's bug from coming back
- **Units:** metres, radians internally; degrees only in reports.
- **Camera:** OpenCV pinhole — +x right, +y down, +z forward; `x_pix ~ K [R | t] X_world` with (R, t) mapping world → camera. Name transforms `T_<to>_<from>`.
- **Depth:** every depth source declares which of these it is — *metric depth*, *relative depth (unknown scale)*, *affine-invariant inverse depth (unknown scale and shift)*. MiDaS/DPT is the third. VGGT-class pointmaps are the second.
- **Rotations:** never gradient-descend raw matrix entries; optimise in the tangent space (exp/log maps). Average rotations with a chordal or geodesic mean, never by averaging Euler angles.
- **Intrinsics:** calibrated or read from the device, never guessed (the prototype's `focal_length=500`).

### 5.4 Data and captures
- **Capture protocol** for own data (iPhone 14 video): record device, resolution, frame rate, lens, lock exposure/focus where possible, and the intrinsics source. Raw captures live in `captures/` (git-ignored, backed up separately).
- **Public datasets** are version-pinned and cited (e.g. Mip-NeRF 360, Tanks & Temples, ScanNet, Wild6D, REAL275).
- Every capture is labelled **tuning** or **evaluation**, never both.

### 5.5 Results registry (adapted from BAYMAX's model-registry policy)
- **Run IDs are immutable.** A re-run creates a new ID; old results stay on record.
- Results live in `results/` with the config (and its hash), code version, seed and date. Results are never stored inside code or docs — docs link to them.
- Figures are regenerated from results files, never hand-edited.

### 5.6 Compute ledger
- Hardware: **M1 MacBook Pro 2021 (16 GB)**, desktop **RTX 4080 Super (16 GB VRAM) with 32 GB RAM**, **iPhone 14**. Rented-compute budget: **£450** (set 18 Oct 2026).
- Every probe that uses rented compute logs provider, GPU, hours and £ against the budget in `results/compute_ledger.csv`. Hardware limits are not a reason to rule a lane out — they're a cost to log.

---

## 6. Ownership and AI use — *proposed, Marv to confirm*

VSC is solo. The BAYMAX author-split (Marv vs Ronin) doesn't apply; the **CV ownership rule** does: *"AI is fine for boilerplate, glue, docs digestion — not for architecture, algorithms, data models"* and *"if you cannot rewrite the critical part yourself, AI is currently weakening you."*

| Work | Who writes it |
|---|---|
| Core VSC pipeline — pose, reconstruction, simulator, planner, the DCT actor-motion codec | **Marv designs and builds.** AI may explain, review, and suggest; any AI-written line in these modules is disclosed and must be explainable by Marv line by line |
| Probe harnesses, synthetic scenes, measurement tools, plotting, visual explainers | AI may build, **labelled AI-built**; Marv reviews the design and the failure criterion |
| Docs reconciliation, reading summaries, research search | AI, with sources |
| **The learning boxes** — PyTorch training loop from a blank file, the 2D coordinate-network warm-up, backprop by hand | **Marv only. Never done by AI**, not even "as an example" |

- Commits say "I wrote this" or "AI-assisted with: <scope>" (BAYMAX PR rule 5).
- **Monthly self-honesty audit:** 200 words — what Marv built vs what AI built, and could he rewrite the critical part alone?

---

## 7. Teaching and communication style (for every assistant)

- **Define every term the first time it appears.** Marv is not in industry yet.
- **Plain descriptive names**, never opaque codes. (The old "O-1 / T-3" labels are retired in favour of names like "where the DCT goes" and "material properties from a camera.") Probe IDs P1–P9 are fine *alongside* their plain names.
- **Visual first** (Marv, 26 Oct): lead with a diagram, labelled figure, or spatial analogy where the concept allows. For research and teaching answers: **interactive explainers** — live sliders, numbers computed live, step-by-step visuals, and a **check-yourself** section at the end.
- **Analogy before mechanics.**
- **NeRF trigger:** in any chat about the NeRF paper, give the foundations reminder from `ml_pytorch_foundations_nerf_reminder.md` first, name every unchecked box, then teach. Marv decides whether to read on.
- Two questions to ask of every paper: **how it handles scale**, and **how it represents camera pose.**

---

## 8. Repository conventions (target layout)

```
open3d_world_recon_and_action_sim/
├── agent.md                  ← this file
├── README.md                 ← what VSC is, how to run things (to write)
├── Artifacts/                ← sketch board and other design surfaces
├── docs/
│   ├── decisions/            ← ADRs (BAYMAX template)
│   └── probes/               ← one probe card per probe
├── vsc_lab/                  ← cloud-runnable synthetic probes (AI-built, labelled)
├── src/vsc/                  ← Marv's core pipeline code
├── tests/
├── results/                  ← immutable run outputs + compute_ledger.csv
├── captures/                 ← raw video (git-ignored)
└── Virtual_space_constructor/← the archived prototype (reference only)
```
- **Tooling, same as BAYMAX:** `uv` for environments and a frozen lockfile; `ruff` (lint + format, line length 100); `pyright` (basic mode, strict per module as it matures); `pytest`. CI runs all four when the repo is on GitHub.
- **.gitignore** from day one: `**/live3d_env/`, `.venv/`, `captures/`, `*.ply` over a few MB, model weights, `__pycache__/`, `.DS_Store`.
- **Git is not initialised yet.** Initialise when Marv says so; `main` protected once on GitHub; no force-push to `main`, ever.

---

## 9. Flag vs don't flag; ask vs proceed

**Flag these:**
- Any number without units, frame, or sample size
- A photometric metric offered as evidence of good geometry
- A claim from one scene or one capture
- A synthetic result stated as if it were real
- Tuning on an evaluation capture
- AI-written core-pipeline code without disclosure; any AI attempt to do a learning box
- A session re-deciding something Marv already decided, or treating its own reading as a decision
- Any rescoping / parking / "do this later" framing
- A DCT benefit claimed from the rotation rather than from truncation

**Don't flag these** (normal here):
- Negative or inconclusive probe results
- Ambitious, lab-scale scope
- Slow progress through the reading
- Marv re-opening a decision because of new evidence
- Hardware limits (log the cost instead)

**Ask Marv before:**
- Changing the status of an open question, or deciding anything marked "Marv's call"
- Spending rented compute
- An architecture choice that crosses checkpoints
- Anything that would change the thesis or contribution claim
- Initialising git, renaming, or reorganising his folders

**Proceed without asking:**
- Building or running a probe Marv has agreed to, within its card
- Fixing stale docs against newer dated decisions (and saying what changed)
- Tests, typos, plotting, explanations

---

## 10. Before you report a probe result — checklist

- [ ] Failure criterion was written before the run, and the verdict is judged against it
- [ ] Every number has units, frame (where relevant) and sample size
- [ ] Geometric and photometric metrics are reported separately
- [ ] Synthetic vs real is labelled; the real-data follow-up is named
- [ ] Tuning and evaluation data were separate
- [ ] Medians and tails, not just means; pass rates labelled as pass rates
- [ ] The comparison is a defensible one (§5.2)
- [ ] Results file has a run ID, config hash, seed, date; figures regenerate from it
- [ ] Rented compute (if any) is in the ledger
- [ ] `CHECKPOINT_TRACK.md` updated: which decision or open question moved

---

## 11. Maintaining this file

- Versioned in git alongside the code (once git exists). Changes are Marv's; an assistant may propose a change, dated, in a clearly marked block.
- Every change is dated and logged below. Assistants re-read this file at the start of every session — version drift between what an assistant last read and the current file is a real risk (the same warning BAYMAX's methodology carried).
- Superseded rules stay visible in the changelog.

### Changelog
- **2026-10-26 — v1.0.** First version, drafted in the anchor Cowork chat from BAYMAX's METHODOLOGY / PROJECT / OWNERSHIP / ADR template, the VSC project docs, the Notion decision log and reading list, the sketch board and the original `future_work` brief. Incorporates Marv's 26 Oct clarification that DCT sits in checkpoint 3 as a candidate method for modelling actor movement. §6 (ownership and AI use) and the pre-registration rule in §3 are **proposed** pending Marv's confirmation. If an earlier `vsc-agent.md` (18 Oct, written in another project) exists, merge it here — this file has not seen it.
