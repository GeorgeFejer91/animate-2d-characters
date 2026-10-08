# Optional landmark-guided finishing

Morph only after accepted keyframes, anatomy, palette, timing, scale, and layering. It interpolates existing pixels; it does not repair missing anatomy. Rendering intermediate rig/mesh poses is usually preferable because it preserves consistent geometry without blending silhouettes.

Morph compatible poses with the same facing, visible limbs, topology, handedness and clothing. A crossfade produces ghost legs and translucent joints. Unconstrained flow can swap similar legs, stretch socks, or drag a towel through the torso. For changed visibility, depth order, or facing, split corresponding layers or add an approved keyframe rather than morphing a flat image.

Track named torso/waist corners, both hips/knees/ankles, heels/toes, shorts hems and prop attachments. Add contour landmarks near joints to preserve thickness. Constrain planted feet and waist in the selected coordinate system. Anchor frame corners. Do not connect independently moving limbs with a single spanning triangle.

## Included mesh helper

`scripts/morph_frames.py` uses explicit common triangles, inverse barycentric mapping, and linear-light premultiplied-alpha blending of warped endpoints. It preserves endpoint pixels, rejects triangles that degenerate/flip anywhere over the interval, and rejects uncovered pixels or overlapping interiors. These establish valid image mapping, not a valid skeleton.

Inputs must share dimensions. Meshes cover the full pixel canvas including background; points refer to pixel centres, with corners `(0,0)`, `(width-1,0)`, `(width-1,height-1)`, `(0,height-1)`. Triangle index triples address corresponding endpoint points. The helper checks coverage/overlap at sampled output pixel centres; inspect topology and contours for subpixel artifacts as well. It does not infer landmarks or topology.

```json
{
  "source":"approved/pose-a.png","target":"approved/pose-b.png",
  "points_source":[[0,0],[191,0],[191,207],[0,207],[96,126]],
  "points_target":[[0,0],[191,0],[191,207],[0,207],[96,125]],
  "triangles":[[0,1,4],[1,2,4],[2,3,4],[3,0,4]]
}
```

This minimal schema mesh is insufficient for articulated anatomy: add real limb, garment and contour landmarks.

```text
python scripts/morph_frames.py transition.json --steps 5 --duration-ms 40 \
  --output-dir transition --report transition-report.json
```

Steps include both endpoints. Do not duplicate shared endpoints when joining pairs. Export more frames only when supported; fixed atlases may require resampling to their prescribed count. Adjust durations to preserve cadence. Inspect final-to-first loop transitions without an extra duplicate first frame creating a pause.

Inspect native-size motion on light/dark/neutral backgrounds, alpha, and material boundaries. Reject knee stretch, thinning thighs, foot sliding, ghost outlines, opacity pulses, material bleed, detachment and left/right swaps. Interpolated joint positions can shorten a bent limb even with a valid mesh; solve joint paths or render the rig when this occurs. Render each in-between directly from approved endpoints rather than repeatedly warping previous output.

Retain raw keyframes and parameters. On failure repair correspondences, split layers or add a keyframe; keep the accepted unmorphed loop. Generative image-to-image finishing is a separate optional experiment, grounded in these anchors and compared against accepted anatomy; a softer surface alone is not grounds to replace a correct sequence.

## Multiple keys and cyclic sequences

Read [dense sampling](dense-sampling.md) first: render additional rig phases
directly when a continuous rig already exists. For actual discrete keys,
`scripts/morph_sequence.py` wraps the same mesh primitive without new dependencies.
All anchors share the same canvas, landmark identities and triangle indices.
Do not re-triangulate independently between pairs.

```json
{
  "anchors": [
    {"file":"a.png", "points":[[0,0],[191,0],[191,207],[0,207],[96,126]]},
    {"file":"b.png", "points":[[0,0],[191,0],[191,207],[0,207],[96,125]]}
  ],
  "triangles": [[0,1,4],[1,2,4],[2,3,4],[3,0,4]],
  "durations_ms": [240,240],
  "samples_per_interval": [4,4],
  "cyclic": true
}
```

The example demonstrates schema, not sufficient anatomical correspondence.

```text
python scripts/morph_sequence.py keys.json --output-dir fresh-sequence
python scripts/self_test_morph_sequence.py
```

There is one duration/count for each adjacent pair, including last→first when
cyclic. A scalar sample count applies to every interval. Each interval samples
`t=0..(n-1)/n`: anchors appear once, with no extra loop endpoint. The original
total duration is retained. `sequence.json` records positive frame durations,
timestamps, source/target indices, t and PNG hashes; one-shot sequences store
their final exact endpoint separately as `terminal.png`/`terminal` metadata.
The Python API `build_sequence(images, points, triangles, durations_ms,
samples_per_interval=4, cyclic=False)` returns images and this metadata. Use
`image_index` to locate each timed sample or separate terminal image.

Export refuses existing output paths and input collisions. Retain the manifest,
source hashes and rejected-mesh diagnostics. Run the helper self-test after
changing sequence logic; it checks endpoints, closing intervals, duration,
determinism, invalid meshes and overwrite protection. It cannot certify
anatomy, occlusion, or the quality of inferred landmarks.
