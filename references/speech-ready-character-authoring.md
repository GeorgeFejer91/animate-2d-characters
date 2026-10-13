# Author a new character ready for speech

Use this before producing a new speaking character's views or action sheet. Treat
lip articulation as part of its source contract, so interaction poses arrive with
usable mouths. The detailed deformation and runtime mechanics remain in
[connected lip surfaces](gaussian-transitions.md#deform-a-connected-painted-lip-surface)
and [mouth transport](gaussian-transitions.md#keep-the-mouth-attached-through-transformations).
Use the existing [visual acceptance gate](final-frame-analysis.md) and its record.

## Plan the performance before the art

Use [narrative action rigging](narrative-action-rigging.md) to identify the actions,
views, gestures, props and head changes that can occur while the character owns a
line. Mark which source poses show visible lips and which are rear-facing,
occluded or too small to articulate. A hidden mouth has an explicit no-mouth
registration; audio and body motion can continue without projecting frontal lips
onto that view. Specify normal completion, interruption and voice failure in the
existing interaction contract.

For a partially visible mouth behind paper or another prop, transport a
visible-mouth/occluder mask with the source paint, or use the existing prop depth
and part ownership to protect the occluder. Clip both oral fill and skin transport
so they cannot paint over the paper or reveal lips through it. If the remaining
visible region cannot be safely articulated, suppress speech deformation for
that pose without inventing hidden contours. Inspect the occlusion crossing on
both the outward and return arcs. A partially masked mouth and a fully hidden
no-mouth pose are different authoring cases.

Lock the design, figure scale, face proportions, prop hand, lighting and source
alpha before filling the family. Inspect the planned game projection and native
face detail using [resolution and upscaling](resolution-and-upscaling.md). Where
the design permits, a readable closed rest mouth makes inactive paint and active
closure easier to preserve. Deliberate open source poses still need their real
cavity registered. Do not generate a new family by cloning one generic face or
procedurally redrawing its lips across unrelated poses.

Approve the source extremes and needed bridges first. Changing occlusion, lip
visibility, silhouette or jaw proportions can require missing bridge artwork.
If a transition folds the cheek, duplicates a corner or exposes an unseen side,
repair the art or correspondence before increasing warp strength. A local speech
deformation supplies neither missing views nor a general face rig or full orbit.

## Fit the mouth with each source pose

Keep one compact profile for each distinct source painting with visible lips;
every displayed cell must resolve the profile of its actual source. Generated
samples of one painting can transport that profile through their baked field.
Register it on the exact encoded crop, not on a nearby bridge, an earlier working
sheet or nose/chin interpolation. Its source identity and byte hash, crop,
dimensions, local centre, tangent and normal must travel with its pose. Record a
deliberate null registration for the no-mouth poses.

Fit these controls against enlarged source pixels:

- The true joined corners and a plausible closed lip crease, preserving profile
  width, downturn and asymmetry. A cavity midpoint is not automatically the best
  closure line.
- The complete painted upper and lower cavity boundaries, including teeth, the
  high upper opening and dark side wings. Distinguish a closed black crease,
  lip gloss and a red ridge from a real opening. An owned closed cue must remove
  the whole original cavity, not leave teeth or a corner pocket above the new line.
- Allowed upper/lower opening contours, spreading, rounding, lower-lip contact
  and tooth exposure. Fit their limits to that anatomy and source view; avoid
  sharing another face's maximum aperture or synthetic tooth bar.
- The connected jaw/cheek support and protected eyes, nose, scalp and props.
  Preserve source alpha and transparent cell gutters through the encoded export.

A small set of contour heights, for example five points between measured
corners, is one compact representation. It is not a universal schema. Use enough
controls for the actual curve, with interpolation that cannot overshoot its
bounds and with upper/lower contours meeting at their attached corners. If a
true corner or cavity lies outside a format's allowed coordinates, recenter or
enlarge the local registration and refit it. Truncating the cavity to satisfy
numeric bounds can pass validation while leaving an open mouth at closure.

Keep authored source profiles and compiled manifests consistent. Build checks
should cover finite coordinates, source/cell identity, complete visible-pose
coverage, joined corners, contour ordering and bounded articulation. They do not
certify anatomy; render inactive, owned closed, open, rounded and biting samples
before accepting a profile.

## Carry anatomy through the interaction

Establish semantic lip correspondence between compatible keys: left/right
corners, upper/lower lip and connected jaw paint must remain the same regions.
For paired source transport, apply the same normalized media cue to each
endpoint's own profile **before** transporting and mixing the painted endpoints.
Keep the simulation's body phase and support contacts unchanged.

Carry the centre and both local axes through a baked deformation. Its local
Jacobian maps the tangent and normal, retaining rotation, scale and shear;
transporting only the centre can make the mouth drift or flatten. Include canvas
aspect in pixel/UV conversion and inherit the actor's world transforms. Register
the painting actually loaded during a delayed fallback or representation handoff.
An atlas cell needs its own source profile even when a native endpoint exists.

Inactive speech returns the exact source painting, including a deliberate open
mouth. An owned closed consonant compresses that pose's pre-open boundaries to
one crease. The outside-lip sampling map must retain a positive Jacobian and
avoid folding through both opening and closure. At a protected-face or support
guard, return the sampling map to identity with zero displacement and an identity
Jacobian; a hard return can expose a sampling jump and stretch a bright philtrum column. Bound
width and contact displacement at the same guard. Check original alpha and skin
continuity, not just the oral fill or a derivative test. Follow the detailed
[connected-surface method](gaussian-transitions.md#deform-a-connected-painted-lip-surface)
when implementing this transport.

## Bind speech and fallback during authoring

Let the existing speech owner supply normalized opening, spread, rounding and
contact cues; the current source profile converts them to its own contours and
limits. For recordings, use the actual native media playhead and bind cues to the
recording identity and byte hash. Preserve the recording. Offline recognizer or
grapheme estimates are not verified phoneme alignment; energy alone does not
replace articulation. Reuse the existing update/render pass, without another
speech timer, body timer or background renderer.

Define pause, resume, end, cancellation, replay and owner replacement before
integrating the asset. Pause holds the sampled cue; actual end or cancellation
releases it. An old callback must not move or release the next speaker. Select
and validate the missing-audio behavior during authoring: retain the source mouth
and existing captions, or use a bounded estimated rig only if that fallback has
been visually proved. Missing registration, failed preparation or late readiness
must retain usable source paint without cutting a mouth hole or freezing the
body to an unrelated talk pose. Reuse existing asset admission and teardown.

## Use the existing gate at both checkpoints

At source approval, compare each visible mouth with its locked character at
native detail and game size. Prove inactive fidelity, complete closure of open
paint, distinctive articulation, attached corners and protected facial detail.
Inspect high-contrast light/dark composites and no-mouth views. Repair these
findings before expanding action art.

At final export approval, inspect all affected encoded endpoints, displayed
cells, changing-pose intervals in both directions and the loop seam. Include
multiple interval substeps and ordered playback: endpoint rectangles and a few
midpoints cannot approve correspondence. Compare the original with owned
closure and phonetic extremes, then watch normal-speed rendered interaction
motion at its intended desktop and mobile size. Exercise reduced motion,
pause/resume, end, cancellation, replay, loading failure and fallback handoff.

Use real recorded-media playback with its observed playhead, mouth cue, selected
paint and body phase traced separately. Deliberately held extremes and forced
body arcs diagnose geometry; they do not establish natural speech performance.
Silent capture can establish visual timeline behavior without claiming heard
perceptual synchronization. Label forced fixtures versus natural gameplay,
desktop/mobile emulation versus physical devices, estimated versus verified
alignment, and the actors/poses/recordings actually covered.

Bind observations and rendered motion to current source, profile, export,
runtime, cue and recording hashes in the existing acceptance record. Report
remaining anatomical or motion defects there and repair them; numeric passes or
an older character preview cannot waive them. Measure the change's transfer,
allocation and frame/input cost in the existing game harness before rollout.
