# Final image-frame analysis

Use this one gate when accepting generated source/key poses, at final export, and after a stored-artwork update. Analyze exact decoded pixels, including every affected frame; bind evidence to the encoded file's SHA-256. Inspect canonical source art and approved other states alongside the result. For source acceptance, a small atlas of candidate poses can use the same schema. Never accept a smooth limb merely because it connects and shares a palette.

## What to inspect

Compare full figures at a shared height, then inspect joints at native size and enlarged over light and dark backgrounds. Preserve the source's intended build, leg-to-torso proportion, exposed-skin length, thigh/calf widths, clothes coverage, face, props and footwear. In poses with foreshortening, compare equivalent views and record that projection; do not impose one universal ratio.

For a new action family or suspected cross-action drift, place comparable neutral, locomotion-contact and action-extreme/return frames for each affected direction on one board at the same canvas scale, ground line and pivot. Compare identity, physical prop hand, hair/head, clothing, texture and contact across actions, not only within a row. If an export looks unstable, compare its source and extracted/packed cell before redrawing art. Preserve the diagnosis and resulting image observations in this same review record.

Analyze rendering style as well as texture continuity: source brush detail, edge treatment, local contrast, highlights, shadow direction and depth order must agree with the body. Blurring a material map can erase painted detail or create glossy cylinders. Smooth centreline bends can round away from the skeleton, distort knees or make thighs appear swollen. Both are appearance failures even with valid bones and connected alpha.

For each final frame, record observations in eight categories: `identity`, `proportions`, `rendering_style`, `lighting_color`, `contour`, `texture`, `anatomy_occlusion`, `motion`. Cite visible features/joins and affected locations, rather than copying an all-pass checklist. Include waist/pants/thigh/knee/sock/ankle checks and both near/far limb occlusions. Review ordered normal/slow playback, or explicit ordered/timestamped frames when playback is unavailable; record what was actually inspected. Do not claim observed live playback from a GIF filename alone.

For a contact or one-shot transition, inspect consecutive exact frames around entry, anticipation, impact/hold, recovery and exit. A contact sheet can reveal pose/colour jumps but cannot establish smoothness, foot skating, temporal flicker or texture crawl; inspect playback at the delivered speed when those matter. An automated critic or pixel-difference metric may locate a suspect interval, but cannot approve the art or replace a source-grounded visual judgment.

A source mismatch, a reported incongruity, an unresolved finding or “pass with qualification” blocks acceptance. Reopen the relevant prior pass instead of arguing that numeric results prove the user's observation wrong. Analyze the smallest failing surface and rebuild its final frames/previews. Preserve unaffected approved rows.

## Provenance helper

Run `audit_final_frame_analysis.py manifest.json --review review.json --report report.json`. It requires Python, Pillow and NumPy. This gate validates current-image evidence and coverage; it cannot independently decide whether a written visual judgment is honest or accurate.

The manifest includes:

- `export: {file, sha256}`, `cell_size_xy: [width, height]` and `movement_rows: [{row, count}]` declaring complete affected atlas rows.
- `references: [{id, file, sha256}]` for canonical identity and appropriate direction/pose images.
- `frames: [{id, file, sha256, row, col, reference_ids}]` covering every declared movement cell exactly once. Frame pixels must equal their final atlas cell.

The review includes a named `reviewer`, `export_sha256`, `reference_sha256` mapping every canonical reference ID to its current hash, strictly boolean `ordered_motion_reviewed: true`, and one entry per frame. Each entry has matching `id`/`sha256`, `reference_ids`, `verdict: pass`, `unresolved_findings: []`, and `analysis` with all eight categories. Each category has `status: pass` and a concrete `observation` from actual image inspection. A failed frame should instead carry its failure and unresolved findings, causing the gate to reject it. Frame/reference IDs must be nonempty strings, required reference lists cannot be empty, and every declared cell must fit entirely within the export; a crop padded by an image library is not valid evidence.

Each frame's `evidence` names actual images with `file`, `sha256`, and roles `source_comparison`, `native`, `enlarged_light`, `enlarged_dark`, `ordered_motion`. A comparison image must also identify its `reference_ids`. Show source and result side by side at usable size; motion evidence can be an ordered strip or a decoded multi-frame animation. Hashed text, wrong dimensions, stale files, changed export cells and incomplete review coverage fail. The comparison evidence and review remain the responsibility of the image analyst; hashes prove provenance, not semantics.

This record includes contour, texture, image continuity, anatomy and colour through its category observations; avoid a second overlapping approval ledger. When saved bytes are re-encoded, compare decoded pixels with the approved export, rebuild stored evidence and analyze actual saved frames; do not require identical encoded hashes from a service that legitimately re-encodes PNGs.
