# Paired Gaussian action arcs

Use this starter when a character has **approved, registered painted keys** for
one bounded action and the host already has Three.js and a locally pinned Spark
runtime. It is an implementation starting point, not a character generator or a
visual acceptance result. Read [Gaussian transitions](gaussian-transitions.md)
for registration, renderer lifetime and handoff, and [narrative action rigging](narrative-action-rigging.md)
for interaction ownership.

The portable files are [`actor.mjs`](../assets/paired-gaussian/actor.mjs),
[`owner.mjs`](../assets/paired-gaussian/owner.mjs),
[`build_paired_gaussian.py`](../scripts/build_paired_gaussian.py) and a
synthetic [specification](../assets/paired-gaussian/fixture/spec.json). Run
`node --test tests/paired-gaussian.test.mjs` from the skill root. The fixture is
a binary/lifecycle test; its cartoon paint is not reference anatomy or a
shipping character. The Python builder uses the skill's existing NumPy,
Pillow and SciPy environment. It adds no JavaScript package or remote runtime.

## Author a state graph before packing paint

Choose main poses that the game can safely hold, such as `work` and `gesture`.
Put approved transition keys between them. Each key uses the **same RGBA canvas,
scale, facing, ground line and pivot**. Assign monotonically increasing `time`
values in seconds to an arc's keys, starting at zero. Those times are the
simulation clock's action duration. Every interval moves continuously; do not
hold or ease to a stop at each intermediate key. An ambient cycle may concatenate
main-to-main arcs without holds. A scripted target change finishes at a safe
main pose, then traverses the next authored arc. A repeated intent must not reset
the active phase. Speech or a phone cue is a separate small overlay signal and
must not restart body motion.

The JSON spec has `id`, `canvas_xy`, `variants` (names to sampling strides),
`states`, and `arcs`. Each state names its PNG and **arbitrary named XY
landmarks**. Adjacent states need common landmark names. Optional `regions`
are named part polygons in image pixels; ordinary overlapping regions use the
last declaration, and the uncovered region is `body`. Draw these polygons around
parts with a stable identity, especially face, hands, clothing panels and props.
For a rigid **held object** that rotates, give its named region `pivot_xy` and
`orientation_landmarks` in both adjacent states. The two landmark names identify
the same directed object axis in each state. The pivot and landmarks use the
registered image-pixel coordinates; the curved polygons must not overlap each
other. For example:

```json
{
  "landmarks": {"grip": [39, 29], "tip": [51, 34]},
  "regions": [{"part": "held_baton", "polygon": [[38, 23], [56, 27], [56, 41], [38, 34]],
               "pivot_xy": [39, 29], "orientation_landmarks": ["grip", "tip"]}]
}
```

The builder derives the shortest signed turn in the Gaussian's upward-Y frame.
At an exact half-turn, direction is ambiguous; add a compatible bridge key to
specify the desired route. Keep the directed axis tied to the **same physical
object points** in every key. If a hand changes grip, defining the axis by
"near hand" and "far edge" can falsely encode a 180° object turn. Use stable
sheet-corner identities and an object-centered pivot, or add a bridge for the
real occlusion and rotation. It refuses one-sided or degenerate controls and
overlapping sampled curved regions. Other regions keep the prior linear path.
There is no universal 16-point human skeleton. Optional `crop_xywh` selects a
registered source cell. Optional `speech_landmarks` lists at most two named
points, with `speech_radius_px` and `speech_amplitude_px`; omit them if no
localized mouth motion is appropriate. The synthetic spec is the exact schema
example.

```sh
python scripts/build_paired_gaussian.py \
  --spec assets/paired-gaussian/fixture/spec.json \
  --output assets/paired-gaussian/fixture/built
```

The builder samples painted RGBA, transports centers using named landmarks,
and solves one-to-one correspondence **within each named part** using a
bidirectional spatial and colour cost. Missing border samples fade in or out;
visible endpoints are drawn from their exact painted keys. The builder projects
synthetic birth/death positions more than one sampling stride beyond the same
named part's visible support to the nearest support sample.
If that part is absent in the opposite key, the synthetic endpoint stays at
its visible counterpart. Exact visible key paint is unchanged. This limits
detached fade trails; it does not establish correct anatomy or approve an
action's rendered appearance. The builder rejects
part assignments over four million pair costs; split a large part into smaller
meaningful regions or increase the sampling stride. It writes deterministic
gzip records, source hashes, counts, durations and a manifest. The record is
24 bytes: start/end XY float32 followed by start/end RGBA8. The output is
bounded to 20,000 slots and 32 segment rows. Neither global matching nor exact
endpoint samples prove texture continuity between keys: inspect the midpoint,
face, cloth, hand and prop at native rendered size on light/dark backgrounds.
If material crosses itself, changes occlusion or lacks a corresponding limb,
author a bridge key or layer ownership instead of tuning the matcher blindly.

The builder groups each owned part into a contiguous slot range and emits
optional `variants.<name>.trajectories` entries with `segment`, exclusive
`start_slot`/`end_slot`, normalized `pivot_start`/`pivot_end`, and
`angle_radians`. Up to eight disjoint entries per segment and 64 per variant
are allowed. The shader rotates only those slots, using pivot translation and
local-frame interpolation so the painted XY endpoints remain exact. The 24-byte
record layout is unchanged. Specs without curved ownership emit no trajectory
metadata and retain linear interpolation. `sampleOwnedTrajectory` is a CPU
reference for endpoint/midpoint checks; `actor.inspect()` exposes the active
segment's entries. The fixture's red baton and direct `swing` arc demonstrate
extent preservation, not valid human anatomy or production-ready motion.

## Host the cloud within the existing render and simulation loops

Host the pinned Spark module and its license with the application. The starter
was written against the local Spark 2.3.1/Three r186 API demonstrated in
[Gaussian transitions](gaussian-transitions.md#integrate-without-an-independent-background-engine);
verify the chosen runtime API when adapting it. Pass the host's `THREE`, scene,
renderer, camera and a loaded Spark module (or an explicit local `moduleURL`).
For a plain browser import map, map both `three` and `three/addons/` to the same pinned Three release; Spark 2.3.1 imports the postprocessing Pass helper. Bundlers can resolve that import through the installed Three package.

Do not fetch an unspecified latest module. Share one owner across actors in the
scene; the owner has one manual update promise and owns the Spark renderer.

```js
import {createGaussianOwner} from './assets/paired-gaussian/owner.mjs';
import {createGaussianActor} from './assets/paired-gaussian/actor.mjs';

const owner = await createGaussianOwner({renderer, scene, sparkModule, signal});
const actor = await createGaussianActor({
  THREE, owner, manifestUrl: '/animation/character.json', variant: 'desktop', signal
});

// In the existing simulation/render pass; never add another RAF or wall clock:
const usable = actor.update(animationState, spriteMesh, {visible: true, reducedMotion});
owner.update(camera, 60);
spriteMesh.visible = !usable; // adapt to the host's own sprite handoff policy

// On exit: detach actor first, then settle the owner and its pending sort.
actor.dispose();
await owner.dispose();
```

`animationState` is simulation-owned `{arc, phase, pose, speaking, mouthFrame}`.
`phase` is normalized 0–1 across the *whole* major arc, not one phase per key.
`arc: null` holds a named main `pose`; `${arcId}-back` reverses an authored
arc, and `${arcId}-roundtrip` goes out and back over one normalized phase.
`sampleArc(manifest, state)` is a pure selector for tests and controllers.
Pause/hidden must freeze the simulation clock without wall-clock catchup.
Returning from a gesture should follow the shortest safe authored route to
the planted main endpoint before walking. Unknown gait art must keep the sprite.

The actor reads the registered source mesh's position, quaternion and original
plane height. Its Gaussian origin is the **source plane floor**; no independent
size fit or collision movement is added. One `SplatMesh` looks up paired XY and
paint textures per slot/segment. Paint interpolates in premultiplied linear
light and is encoded back to sRGB because this Spark path decodes it again.
There is no two-cloud crossfade, midpoint paint swap or unowned animation loop.
Reduced motion suppresses the optional speech deformation.

Keep the approved sprite visible until `actor.update` returns true. Readiness
requires a completed owner sort after the first visible actor update and active
splats. A false return also covers loading, hidden state and failure. Let the
host's existing event receipt and generation token handle cancellation/replay.
Retiring an actor detaches it immediately and defers mesh/texture disposal until
the pending sort settles; dispose actors before disposing their shared owner.
The owner reports failure through `inspect().failure`, hides splats and leaves
the sprite as fallback. Measure actual device frame time and inspect the exact
paint in motion before promotion. The synthetic tests establish deterministic
bytes, seam invariants, bounded decoding and lifetime behavior, not visual
quality or mobile performance.
