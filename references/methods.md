# Choose the smallest working method

**Painted source art:** prefer intact limb pixels, including socks/shoes, over reconstruction from coloured tubes. Annotate hips, garment hems, knees, sock starts and ankles. Apply a small continuous deformation or an existing rig while preserving source widths and footwear coverage. Hide roots beneath a connected source garment. Keep shoes rigid where practical. Masks must follow the actual gap between limbs; splitting through a foot can leave dangling sole fragments.

`scripts/painted_walk.py` implements the demonstrated routine; [painted walking](painted-walking.md) documents its measured input and separate game export. It supports lateral and front/back travel without reconstructing skin. Use it for small steps where intact artwork can deform coherently; larger motion needs an articulated rig or approved new key poses.

**Missing views/key poses:** use the image-generation skill/tool, grounded in the canonical base and approved other states. Name failed proportions concretely: short stocky legs, exposed-skin amount, substantial socks/shoes, full moving thighs and a connected waist. Generate one coherent family, not a whole atlas. Check opposite contacts and passing poses first. After two same-foot failures, strengthen pose anchors or use an authorized source-pixel rig.

**Larger articulated movement:** use explicit cutout/mesh pivots or a suitable source rig. `rig_math.py` provides two-bone IK/walk phases; check reach errors as well as lengths. Source anatomy sets widths and coverage; projected lengths can change with foreshortening. Remove stationary thigh silhouettes and duplicated sock shafts. Preserve joint paint, crisp outer contours and consistent near/far occlusion.

Unknown generated spacing requires complete pose extraction, not guessed grid slices. Use one family scale/origin/baseline and preserve airborne displacement and handed props. `audit_sequence.py` is an optional clipping/geometry diagnostic. `harmonize_material.py` matches explicitly masked materials while retaining shading; never recolour clothing as skin.

Use [constrained morphing](morphing.md) only for accepted endpoints with compatible facing, topology and visibility. Prefer direct rig in-betweens when available. Crossfading wrong anatomy does not repair it.
