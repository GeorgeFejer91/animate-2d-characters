# More samples between approved poses

Extra frames are useful when they reduce visible jumps without changing identity,
anatomy, timing or ground speed. A denser sequence does not establish a better
gait, accurate foot planting, or a valid transition between different actions.

## Choose the source of inbetweens

- **Continuous rig or deformation:** evaluate the same source at additional
  phases. Do not morph its already rendered frames. Keep the source, registration,
  amplitude, layering, feet and prop constraints fixed. For an N-sample cycle,
  render phase `i/N`, `i=0..N-1`; doubling N retains the original keys at even
  indices. Check adaptive per-frame fallbacks: a changing deformation strength
  can cause a discontinuity that more frames merely reveal.
- **Discrete compatible keys:** author corresponding anatomical/contour points
  and one shared topology, then warp each pair into the interpolated geometry
  before blending linear-light premultiplied colour. Use
  [morphing](morphing.md) and `scripts/morph_sequence.py`. Start with the hardest
  adjacent pair and its halfway pose before expanding a whole sequence.
- **Changed visibility, crossing limbs, different facing or prop ownership:**
  obtain a bridge key or corresponding separated layers with explicit depth
  order. A flat mesh cannot recover paint hidden behind a moving arm. Stop a
  failed interpolation experiment; retain accepted art while recording why.

Always evaluate an inbetween from the approved source or endpoints. Recursive
interpolation of previous outputs accumulates blur and drift. Do not use a
runtime whole-character crossfade to disguise invalid correspondence.

## Timing and consumer contract

For a loop lasting T milliseconds with N samples, each sample lasts T/N. For a
distance-driven gait with D ground units per cycle, derive normalized phase from
actual collision-resolved distance divided by D, then choose `floor(phase*N)`.
Changing N must not change D, root speed, action-boundary timing, or the period.
Do not multiply the simulation clock simply because the atlas has more frames.
Keep existing pause/turn/stop ownership and inspect the last-to-first interval.

The sequence helper accepts one positive duration and sample count per interval.
It emits each shared anchor once. A cycle includes the final-to-first interval
without appending another copy of frame zero. A one-shot has a separate terminal
snapshot, not a zero-duration playback frame. The consumer holds that endpoint or
enters its next state when the total duration expires.

Ship explicit frame counts, state offsets, atlas columns/rows, cell sizes and
timing, direction, loop/one-shot intent and ground pivot. For each shipped atlas
variant, compare its encoded export/hash and clip mapping with what the consumer
actually loads; a small existing build report or manifest is enough. Runtime
indexing must work for the dense atlas, fallback and close-up variants. Preserve
the same normalized phase when switching resolution. Verify
the first, every intermediate, last and wraparound sample in the actual renderer,
including load failure and mobile variants.

## Run a bounded trial

1. Save approved sources/keys, prior export hashes and the consumer's cadence.
   Choose one or two representative characters and all affected directions.
2. Render an equal-duration comparison, initially 8 versus 16 or 32 samples.
   Count distinct decoded images, not container frames. Preserve source pixels at
   key phases before encoding; after lossy encoding check alpha/registration and
   inspect codec differences rather than claiming identical RGB.
3. Decode the final shipped atlases. Compare adjacent visible-colour/alpha changes
   and the closing seam in the sparse and dense versions. These are diagnostics:
   shrinking the motion, freezing frames or blurring the art can improve a number
   while making the result worse. Inspect every exact output as required by
   [final frame analysis](final-frame-analysis.md).
   `scripts/audit_sequence.py` reports whole-canvas change and change over pixels
   visible in either frame (alpha > 0), using premultiplied RGBA in encoded sRGB.
   It also reports duration-normalized change for the
   outgoing frame, exact visible hashes (ignoring RGB at zero alpha), distinct
   frames and repeated endpoints. Compare only equal duration, scale, registration
   and phase; inspect its largest reported steps, including a cyclic seam. These
   are uncalibrated ranking signals, not perceptual scores or pass thresholds:
   lossy encoding can make near-identical poses hash differently, and intentional
   contact/hold timing can make a large change correct.
4. Pack to a measured texture budget. Estimate decoded RGBA memory as width ×
   height × 4; compressed file size alone is misleading. Keep source detail when
   choosing count/layout, select close-up variants from projected size and DPR,
   and load only the needed direction. Verify gutters after final encoding. Do not bake a huge multi-axis
   matrix when the runtime traverses just a few short one-dimensional sequences.
5. Exercise normal-speed movement, loop closure, starts/stops, direction changes,
   near/far texture switching and the existing gameplay tests. Report exactly
   which characters/states improved and what remains untested. Only promote a
   method after visual and consumer checks pass; retain failed cases as limits.

## Lessons from the face-atlas and office trials

The [Affect Tracker dense atlas builder](https://github.com/GeorgeFejer91/affect-tracker-playground/blob/2023af03a4ca3231fe2968f4f3ddd523d25c5c98/scripts/build-dense-photo-atlas.py)
used common facial landmarks, fixed canvas anchors and a shared triangle mesh
to align neighboring source faces before blending. Its 21 × 21 atlas was baked
offline; dense samples then supported small runtime blends. The transferable
parts are correspondence, shared registration, offline baking and exact-output
validation. A face's largely stable visibility does not establish that flat
whole-body morphs can handle crossing arms or alternating leg occlusion.

In the Bürgeramt trial, Aktenkurier and Archivbotin already had a continuous
source-pixel walking field. The first 16-phase bake retained the original eight
keys but revealed inherited shoe inflation and pinching. Native close-up source
comparison also caught compression hidden by smaller front/rear previews.
A fixed lower whole-cycle amplitude was required before reviewing
the denser loop; its repaired keys intentionally differ from the faulty old ones.
Preserve approved keys, not previously unreviewed defects. Compare 8 versus 16
samples of the **same repaired field** to isolate the benefit of sample density.
Packing 64 walking plus 32 existing action cells into a 12 × 8
atlas retained 320 × 416 desktop cells and stayed within 4096 pixels per side.
Close walking used a 4 × 4 grid with 640 × 832 desktop/high-DPR mobile or
320 × 416 low-DPR mobile cells. Clean original-size alpha masters removed
observed backdrop spill before resampling while protecting authored red props.
These are project-specific budget choices, not universal required dimensions.

A separate Aktenkurier work→gesture experiment failed. An average-pose Delaunay
mesh first folded between head, wrist and elbow. Repairing its topology allowed
rendering but still produced a translucent patch above the head, smeared collar
and face, and ghosted arm/coat material. Exact endpoints, valid triangles and
correct timing did not make those intermediates acceptable. The reusable rule is
to treat mesh validity and visual/anatomical acceptance as separate gates, and
to require layers or another approved action key for this kind of occlusion.
