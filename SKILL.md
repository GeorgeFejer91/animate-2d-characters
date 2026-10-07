---
name: animate-2d-characters
description: Create or repair 2D character movement while preserving reference proportions, painted appearance, connected anatomy and clean transparency. Use for sprite walk cycles, poses and movement exports.
---

# Animate 2D characters

Use one workflow and one visual acceptance record at two checkpoints. Connected pixels and valid files do not prove good animation.

For a game walk, run the [planted-foot speed assessment](references/painted-walking.md#calibrate-ground-speed-to-planted-feet) on the exact exported side-view frames and actual billboard scale before setting the distance per gait cycle. Inspect remaining shoe slide in the running game; a distance-driven clock alone does not prove foot planting.

1. **Lock the character.** Inspect the actual asset and approved other states at native size. Record facing, timing, canvas, baseline and prop hand. Compare views at a shared figure height; lock shorts coverage, exposed skin, limb widths, socks and footwear. Rejected movement frames are not a new design.
2. **Prove the source poses.** Reuse intact artwork or generate only missing views/key poses with the available image-generation tool. Compare them with the locked reference before animation. Reject elongated legs, generic tube shading, smaller shoes, changed clothing or props. For walking, prove opposite contacts and passing poses before expanding the loop.
3. **Build the movement.** Use the simplest method preserving approved pixels; read [methods](references/methods.md). For painted walks, four-direction game sources and side↔up/down stop/turn/start paths, read [painted walking](references/painted-walking.md). Use actual rear/up artwork, accepted whole-body turns and a shared pivot. Move full thighs/garment hems from a connected waist/pelvis, alternate planted/swing feet, and preserve complete knees, socks and ankles. Use one scale and registration per family. Preserve accepted rows during a repair. Smoothing or recolouring cannot replace missing anatomy.
4. **Analyze the exact export.** View every affected encoded frame at native size, enlarged on light/dark backgrounds, alongside the reference, and in ordered motion. Check loop wraparound and relevant state transitions. Apply [the visual acceptance gate](references/final-frame-analysis.md). Repair failures and repeat; unresolved findings and qualified passes block delivery/update. Show motion from these pixels. After an authorized update, fetch and inspect stored frames too.

The single gate covers **contour, texture, image continuity, anatomy and colour**, including identity, source proportions, rendering style, lighting, waist/shorts/thigh/knee/sock/foot joins, and occlusion. Inspect the user's reported defect directly; numerical geometry cannot waive it. Source comparison is required before accepting generated art and after encoding.

Use `scripts/audit_final_frame_analysis.py` to bind real image observations to current reference/frame/export hashes and complete affected-frame coverage. Its test is `scripts/self_test_final_frame_analysis.py --output-dir <temporary-directory>`. Add numerical diagnostics only to investigate a specific defect; avoid duplicate approval ledgers or universal anatomical thresholds. The helper verifies provenance/completeness, not the truth of visual judgments.

For character reactions and their game event hooks, read [interaction states](references/interaction-states.md). For ChatGPT Pets, read [Pets integration](references/pets-integration.md) and the installed Pets skill. Use its actual validators; retain stable IDs, other approved states and activation; show final motion before upload. Existing session approvals apply. For optional interpolation, read [morphing](references/morphing.md) after endpoints pass. For the Germany Simulator vacation-character failures, read [Germany Simulator lessons](references/germany-simulator-lessons.md).

Use premultiplied-alpha filtering; clear hidden RGB at alpha zero. Hidden alpha-zero RGB in a generator preview is not a painted backdrop: composite on real light/dark backgrounds before deciding to chroma-key. Apply one final edge-local chroma cleanup when needed, avoiding cumulative despill or whole-image blur. Solid-background GIFs prevent misleading palette fringes; retain the transparent export. Use fresh preview filenames when clients cache them.

When a new method solves an observed failure, update its short instructions/limitations in the relevant reference, verify helpers changed and refresh the portable package. Keep failed experiments in case notes, not the default workflow.
