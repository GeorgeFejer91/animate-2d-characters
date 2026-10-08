# Resolution and appropriate upscaling

Distinguish detail in the original artwork, pixels in an exported cell and
physical pixels on the display. A 4K canvas or larger atlas does not create detail.
Check resolution before expanding frame count or building the complete atlas.

## Preflight at the largest intended size

Record source dimensions and actual figure pixel bounds, export cell/grid,
expected CSS display size, device pixel ratio (DPR), texture limit and resident
RGBA memory. Use an original transparent master or a tight artwork crop: padding
and keyed backdrop do not count as character resolution. Compare matching poses;
a changed pose can legitimately change its bounding box without resizing.

Physical sampling demand is `CSS size × DPR`. Divide this by export cell size to
measure enlargement; preserve the cell aspect ratio. For billboards, measure the
actual projected size at near/ordinary/far distances, camera angles and zoom.
Screen width alone cannot select the correct close-up asset. Check high-DPR
mobile screens and disclose any remaining enlargement. Do not call emulation a
tested physical device.

Verify the actual loaded texture, cell grid and detail state when measuring the
consumer. Atlas height alone is ambiguous: the office trial's compact and close
atlases both had 3328-pixel heights. A dimension-only wait incorrectly measured
the compact fallback as close art. Wait for the selected variant and record its
URL/hash alongside projected size. Even the correct larger variant may still be
enlarged in a very close high-DPR view; report that ratio explicitly.

Before generating hundreds of frames, inspect the original plus contact,
passing, opposite-contact and closure poses at **native intended close-up
resolution** in every direction, enlarged on light/dark backgrounds. Reduced
contact sheets can hide pinched boots, stretched highlights and matte spill.
Crop large boards so the inspection tool cannot downsample away the defect.
Check both extremes, then repeat after final encoding and in the real consumer.

## Choose the enlargement method

Prefer rebaking from higher-resolution originals or evaluating the original rig
at the target resolution. Do not enlarge a previously downsampled/lossy atlas
when better sources exist. Keep one family scale, baseline and pivot; per-frame
fitting causes size pulses.

For a smaller source, report the enlargement factor and limits. Painted art needs
premultiplied-alpha, high-quality resampling and edge/texture/contrast review;
ordinary interpolation cannot restore missing detail. Pixel art needs deliberate
integer/nearest-neighbor scaling, not automatic smoothing. Generative or learned
upscaling is a separate reference-grounded artwork candidate, using the available
image tool when appropriate, and must preserve identity/proportions/materials.
Repair or upscale shared source/key artwork first; independently inventing detail
in each frame causes flicker. Inspect the resulting sequence after encoding.

Clean source mattes before enlargement or deformation. Keep an untouched
reference; distinguish the intentional keyed backdrop from spill in hair edges
or enclosed hand/prop gaps. Sample the actual backdrop, constrain cleanup to
verified regions and protect similarly coloured clothing/props. A transparent
master should remain clean when re-imported. Inspect alpha on light/dark
backgrounds after resizing and encoding, with a gutter around each atlas cell.
Zero matches from one hue threshold do not establish a clean matte: mixed edge
spill can fall outside that threshold. Inspect the original at native scale and
repair the smallest observed region before propagating it into more frames.

## Diagnostic helper

`scripts/assess_resolution.py` measures actual source/export images (optionally
cropped cells), sampling ratios, aspect stretch, transparent gutter and estimated
RGBA8 memory. It never assigns an artistic pass. Supply the consumer's supported
texture limit; the default 4096 is a conservative input, not hardware detection.

```json
{
  "source": {"file":"source-master.png", "crop_xywh":[0,0,384,1024]},
  "export": {"file":"walk.webp", "crop_xywh":[0,0,640,832]},
  "display_css_size_xy": [320,416],
  "device_pixel_ratio": 2,
  "max_texture_size": 4096,
  "mipmaps": false
}
```

Omit the crop for a whole image. Replace these illustrative dimensions with
measured values.

```text
python scripts/assess_resolution.py resolution.json --report resolution-report.json
python scripts/assess_resolution.py --self-test
```

Upscaling warnings prompt source/variant selection and visual review; a modest
intentional enlargement can be appropriate. Repair texture-budget failures,
unintended aspect stretch and contaminated alpha. Recheck mobile close-ups at
their actual DPR and all affected frames under [the final image gate](final-frame-analysis.md).
