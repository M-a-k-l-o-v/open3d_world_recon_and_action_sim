# Open questions

Design questions that came up and aren't settled yet. Each has: the question, current thinking, and how a probe would settle it. Newest last.

---

## Is object categorisation needed for mesh completion (Reverse2Complete route)? — 23 Nov

**Short answer:** it helps, but completion doesn't strictly need it. It **is** needed on the stand-in-CAD route (completion → stand-in CAD → keypoints → PnP), because keypoints are defined per category or per instance.
*General reasoning only. Not yet checked against what the Reverse2Complete paper actually does.*

**Why it helps**
- Completion has to guess the hidden side, and that guess comes from a shape prior. A label like "chair" narrows the prior: you get a back and four legs, not a blob.
- It matters most under heavy occlusion, where many completions fit the visible half and the category picks the right family.

**Why it isn't strictly needed**
- Category-free completion models exist. They learn priors from many object types without labels and work from the partial geometry alone.
- A hard category step is a single point of failure. A wrong label gives a confidently wrong shape, and real rooms contain objects outside any fixed category list.

### The middle path: category as soft conditioning
Feed the category in as a hint, not a switch (top-k classes, or a vision-language embedding).

| Benefits | Disadvantages |
| --- | --- |
| **Fails softly:** a wrong or unsure label nudges the shape instead of forcing the wrong family | **More to build and tune:** how to inject the hint and how much weight it gets is real design work before any results |
| **Handles unknown objects:** an embedding still says something about objects outside any list | **The model can learn to ignore it** unless training forces it to use the hint (e.g. sometimes dropping the label) |
| **One model, not one per category:** less to train, and VSC trains its own completion model | **No help for the stand-in-CAD route:** keypoints + PnP still need a definite category or a retrieved model |
| **Easy to test:** hint off, true label or wrong label (the probe below) | **Harder to debug:** when a shape comes out wrong, it's unclear whether the label or the geometry caused it |

**Verdict:** don't build the middle path yet. Run the cheap probe first. Only add soft conditioning if the true category clearly helps and a wrong one clearly hurts.

### Probe to settle it
Complete the same partial objects three ways:
1. no category
2. the correct category
3. a deliberately wrong category

Measure shape error (e.g. Chamfer distance against the full shape) at increasing occlusion levels.
- If (2) beats (1) only at high occlusion, and (3) is much worse than (1): categorisation helps, but it must be soft.
- If (2) ≈ (1): skip categorisation for completion, and decide it only where the stand-in-CAD route needs it.
