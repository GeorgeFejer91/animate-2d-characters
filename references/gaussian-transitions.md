# Painted sprites and Gaussian transitions

Use this method for an approved painted figure that briefly gains depth, makes a
small turn, dissolves into a volume, or appears inside a volumetric tunnel.
Choose an ordinary sprite or existing rig when it already supplies the motion.
This reference covers source registration, reveal, tunnel construction, runtime
ownership and validation; it is not a multiview reconstruction tutorial.

## Choose the representation

A Gaussian renderer draws oriented, translucent ellipsoids. It does not infer a
back view, establish correspondences between poses, or animate joints by itself.

- An authored relief with a rear shell suits a controlled reveal and a limited
  view range. Record that range and inspect its endpoints before promising an
  orbit. A silhouette extrusion alone does not establish plausible anatomy.
- Independent limb motion needs an approved rig, part ownership or compatible
  authored pose correspondences. Changing occlusion may require bridge art or
  additional views; interpolating all points can smear faces and duplicate hands.
- Use reconstructed geometry or an appropriate dynamic representation when full
  orbit, substantial disocclusion or articulated movement is required. Treat that
  as separate asset work; do not imply a renderer installation solved it.

For a bounded action with approved painted main and transition poses, the
[paired Gaussian action starter](paired-gaussian-actions.md) supplies a reusable
builder, native-image Gaussian texture-patch mesh, fallback Spark cloud,
shared owner and synthetic test. The native patches follow paired correspondences at
simulation-owned phases, without a separate clock or a second visible overlay. Full-resolution source
sampling does not prove endpoint coverage or anatomical correspondence; inspect
the entire arc and repair uncovered or incorrect parts before promotion.
Its bounded spatial phase delay creates liquid transport while returning
exactly to each authored key; owned props share a pivot-derived phase.

## Register the actual displayed pose

Inspect the texture, atlas cell, UVs, billboard dimensions and pivot actually
selected by the running consumer. A working source sheet may have a different
crop or registration from the accepted close-detail export. Match the pose at
the handoff, including its prop, facing, baseline and transparent margins.

For a frame of `W × H` pixels mapped to world width `w` and height `h`, a useful
floor-relative mapping is:

```text
x = ((pixelX + 0.5) / W - 0.5) * w
y = (1 - (pixelY + 0.5) / H) * h
z = authoredDepth(pixelX, pixelY)
```

Preserve the consumer's padding and any explicit pivot offset. These Y values
already measure from the frame bottom: adding the sprite's half-height again
would float the figure. Inspect shoes against the ground, not only a face crop.

Sample front RGB/alpha directly from the accepted pose. Shape the skull, nose,
torso, bent limbs, rigid prop and separate legs with measured part masks or
authored curved surfaces. Preserve gaps between limbs and around the prop. If a
rear shell is needed, register approved rear art and disclose approximations.
Do not silently mirror handed clothing, faces or props onto an unseen side.

Use denser samples for eyes, hair, fingers and paper/text detail; coarse uniform
sampling can blur identity even when the overall silhouette matches. Tune XY
Gaussian extent relative to sample spacing and keep depth extent thin enough
that an oblique view does not smear the paint. Examine both holes from undersized
splats and softness from oversized splats at the intended projected size.
Exact source samples do not imply pixel-identical Gaussian rendering.

Keep a deterministic builder and adjacent source hashes, cell coordinates,
axis/pivot contract, count, scales, bounds and export hash. A common `.splat`
layout uses 32-byte records: XYZ float32, scale XYZ float32, RGBA bytes and WXYZ
quaternion bytes. Verify the selected loader's layout and color conventions;
library-packed GPU data is a different representation.

## Reveal depth while retaining identity

Let the existing scene/event controller supply elapsed time and cancellation.
Separate opacity from depth expansion so the incoming representation can first
align with the flat pose, then acquire volume. One useful construction is:

```text
reveal = smoothstep(0, depthDuration, sceneTime)
opacity = smoothstep(0, fadeDuration, sceneTime)
center.z *= reveal
depthScale *= mix(thinPositiveScale, 1, reveal)
rearOpacity *= smoothstep(rearStart, rearEnd, reveal)
```

Tag the rear explicitly, or document a local front-positive/rear-negative Z
convention before applying deformation. Hide the rear while flattened so it
does not double the silhouette. Match the original actor transform and foot
pivot; bound the turn to the asset's inspected view range.

Apply small, smooth GPU displacements to cloth or a temporary dissolve, with
weights that keep soles planted and protect eyes, face, fingers and rigid props.
Maintain one source of pose state. Avoid inventing a second character controller
or moving the collision body merely to reveal depth. Reduced motion can preserve
a quiet crossfade while removing rotation, ripples and cycling tunnel motion.

Do not hide the accepted sprite merely because loading resolved. Confirm the
Gaussian renderer has produced a usable sorted frame, then crossfade. On failure
or a preparation that misses the chosen handoff, retain the sprite for that
encounter instead of replacing it abruptly mid-line. The existing event receipt
still decides when the scene releases; restore the sprite and its material state.

## Articulate a painted Gaussian mouth from recorded speech

Bind the mouth track to the approved recording's exact identity and byte hash.
Analyze it offline into estimated viseme intervals and a compact energy envelope;
use a recognizer suitable for the spoken language. Keep generated estimates
separate from verified words and phoneme alignment. Ship cue data rather than a
recognizer, reference recording or authoring model. Preserve the original audio.

Read the native media playhead in the existing render/update pass. Blend closure,
vowel opening, spreading, rounding and lower-lip biting across short boundaries;
energy can modulate opening but cannot replace articulation. Select recorded-word
receipt mode before the first word event, so a wall-clock estimate cannot advance
past and reject that receipt. Freeze the pose during pause; close on actual end,
exit and replay. Unowned or failed audio should retain a neutral mouth unless a
separate fallback rig has been validated. Reduced motion can retain these small
semantic movements while removing decorative waves.

Register the lips against the exact source crop and its world-coordinate mapping.
Use a bounded lip/lower-jaw mask that preserves eyes, scalp, props and floor pivot.
A small Gaussian oral cavity may share the same mesh and renderer, with zero alpha
at rest. Inspect actual face relief before choosing its depth: an opening placed
behind one lip edge can appear off-centre despite correct XY registration. Scale
its height with opening rather than leaving a dark oval under every consonant.
Keep the jaw connected and the original painted crease visible at closure.

Inspect normal-speed rendered motion plus native-scale closed, consonant, open
vowel, rounded and biting extremes, comparing the neutral frame to the original.
Do not seek the media for the only synchronization test: some test servers or
media paths reset a seek, making all sampled images the same closed state. Record
real playback and its playhead/pose trace. Include pause/resume, end, replay,
missing audio, splat failure, reduced motion and mobile framing. Measure added
kernels, cue transfer and frame/input cost against the same scene without the rig.
Localized deformation approximates speech; it does not supply a general face rig,
new teeth anatomy or correct views beyond the inspected source angle.

## Build a hollow tunnel with real splats

Create a modest number of Gaussian rings at different depths, with staggered
angular samples and overlapping ellipsoids. In camera-local coordinates, let
positive `d` place a section at `z = -d` and center it on the target sightline:

```text
target = cameraInverse * subjectWorldFocus
centerXY(d) = d * target.xy / -target.z
radiusX(d) = d * tan(verticalFov / 2) * angularWidth(d)
radiusY(d) = d * tan(verticalFov / 2) * angularHeight(d)
```

Guard targets behind or too close to the camera. Different angular widths along
the tube create visible nested depth; small depth-dependent twists and irregular
cloud sizes avoid a flat ring graphic. Account for the current FOV, aspect and
projected subject bounds so portrait framing does not close the central opening.
Keep it transparent through the face and body; inspect both static frames and
motion. Dark splats still need enough tonal separation to show their volume.

Use the same depth-tested splat renderer as the figure where supported. A small
screen vignette may seal outer edges, but it should not be described as the 3D
tunnel. State whether the volume is camera-attached hallucination or a world
object. An authored hallucination need not gain collision, cast realistic shadows
or change the room layout. Test actual opaque occlusion rather than putting the
whole splat layer globally in front of the scene.

## Integrate without an independent background engine

The demonstrated implementation uses locally pinned Spark **2.3.1** with Three.js
**r186**, `SplatMesh` construction, Dyno `objectModifier`, and `SparkRenderer`.
These are recorded versions, not an assertion about the latest release. Inspect
the selected version's API before reusing options. Share the host Three instance,
scene, camera, asset admission queue and render loop; preserve library licenses.

Load only when the scene has an active or approaching consumer. Count transferred
library/WASM bytes as well as the splat file. For a small known file, yielding
bounded record-install chunks may avoid an unnecessary persistent decoder pool;
larger assets may warrant workers. Check actual decode, sort, allocation and
input cost instead of treating either choice as universally faster.

Track a visit/generation token and cancellation signal through preparation.
Dispose stale completions rather than attaching them to a replayed scene. Stop
new work when hidden or inactive, preserve authored committed event timing, and
resume the scene clock without wall-clock catchup.

Own asynchronous GPU readback/sort through teardown. In the demonstrated Spark
path, automatic updates are disabled and the host permits one tracked update
promise at a bounded cadence. Detach immediately on exit; dispose meshes,
renderer buffers and the owned worker after that promise settles. Account for
internally deferred sort timers too: the example uses `minSortIntervalMs: 0`
because the host already throttles updates. This is a lifetime choice for that
version, not a recommendation to sort unboundedly in another runtime. Handle
rejected updates by restoring the sprite; do not introduce an unowned RAF loop.

## Validate the representation and the consumer

Use numeric checks for deterministic bytes, finite centers, positive scales,
source registration, count/bounds and a real depth span. They cannot establish
identity, coherent anatomy or a convincing transition. Inspect the exact shipped
asset in the production renderer at flat, intermediate, expanded and release
states, plus the largest allowed turn. Include a pulled-back foot view when the
normal closeup hides the ground. Keep source art and runtime references together.

Challenge depth with a wall in front, behind and partially across the figure.
Check transparent margins and the tunnel's central hole. Exercise reduced motion,
load failure, delayed readiness, replay during preparation, exit during a sort,
resize and hidden/resume. Confirm restored sprite visibility/materials and no
continued resource growth after warmed repeated visits.

Measure game update/render dispatch rather than monitor RAF cadence: a 144 Hz
monitor can deliver callbacks while a game renders at 60 Hz. Record hardware or
software GPU, viewport/DPR, cold/warm state, transfer, decoded/packed allocation,
input response, frame p50/p95 and teardown. Packed record bytes exclude allocation
padding, GPU targets and sorting overhead. Keep unrelated browser workloads out
of comparable timings; distinguish emulation, forced fixtures, natural gameplay
and physical devices. Numerical, rendered and perceptual evidence have different
scope. Reuse the host's existing checks instead of adding another test platform.

## Demonstrated implementation and limits

The source-pinned [Germany Simulator implementation at `365ab91`](https://github.com/GeorgeFejer91/GermanySimulator/tree/365ab91)
contains the [deterministic asset builder](https://github.com/GeorgeFejer91/GermanySimulator/blob/365ab91/tools/build-omen-splat.py),
[runtime reveal and tunnel](https://github.com/GeorgeFejer91/GermanySimulator/blob/365ab91/buergeramt-splat.js),
[asset contract](https://github.com/GeorgeFejer91/GermanySimulator/blob/365ab91/assets/buergeramt/omen/PROVENANCE.md)
and [silent browser harness](https://github.com/GeorgeFejer91/GermanySimulator/blob/365ab91/tools/playtest-omen-splat.mjs).
It uses 38,938 character splats plus 3,072 procedural tunnel splats, a roughly
half-second crossfade, a 1.45-second depth reveal and a turn under 25 degrees.
Those are one scene's measured design choices, not universal budgets or timings.

The first coarse export softened the face and paperwork; denser local sampling
and thinner depth scales improved the rendered result. An early teardown freed
an in-flight sort target; tracking the update and deferring disposal removed the
failure. The final scene received source/CPU checks, desktop and Android-emulated
rendering, independent depth/foot inspection, and fallback/lifecycle checks.
Physical Android performance and a natural full mission traversal were not
established by that work. Keep its artwork, recordings and project evidence in
the game repository; adapt the method to new approved art rather than treating
this character-specific sculpt as a general human reconstruction helper.
