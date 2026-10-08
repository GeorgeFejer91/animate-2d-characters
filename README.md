# Animate 2D characters

A reusable Codex skill for source-faithful painted 2D character animation: four-direction walking, planted corner turns, prop actions and event-driven reactions. Developed through the Germany Simulator walking and bucket-pouring work.

The workflow is character lock → approved source poses → movement → exact final-image analysis. One visual gate covers identity, proportions, rendering style, lighting/color, contours, texture, anatomy/occlusion and ordered motion. Its helper checks evidence completeness and file hashes; an actual image reviewer must decide visual quality.

## Install

Clone this repository into your Codex skills directory under `animate-2d-characters`, then restart Codex or reload skills. Alternatively ask the installed skill-installer to install the skill at this repository's root.

Invoke `$animate-2d-characters` with the actual character artwork, required directions/actions and destination. For example: “Animate this character walking in all four directions, with connected painted limbs and smooth planted corner turns. Analyze every exact final frame.”

## Contents

`SKILL.md` is the short entry point. References disclose painted walking, reaction/event hooks, final image analysis, optional morphing and Pets-specific delivery when needed. Scripts include a source-pixel walk renderer, planted-foot cycle-distance assessment, multi-key/cyclic mesh interpolation with preserved duration, movement/attachment diagnostics, material matching, a small planted-reaction player and hash-bound image-review validation.

Game reactions preserve separate meanings for idle, waving, jumping, failure, waiting, working, review and looking. Existing approved art comes first. Walking uses ground distance; prop actions and reactions use time. Reactions finish turns and preserve landing, routes, prop ownership and accepted walk pixels.

Ordinary game animation works without the Pets plugin. ChatGPT Pets uploads still require the installed Pets skill and its authoritative tools. Do not infer that a successful numerical check certifies visual continuity.

## Offline helpers

The Python image helpers use Pillow, NumPy and SciPy. The browser reaction player has no external dependency and can be loaded as a plain script. Generate missing artwork with the image-generation tool; choose a source-pixel rig when the user requests that method and intact artwork supports it.

Read `references/dense-sampling.md` to choose direct rig resampling versus landmark-guided inbetweens, preserve cadence and budget atlas sizes. Use `scripts/morph_sequence.py` for compatible discrete keys; changing occlusion still needs layers or approved bridge art.

Read `references/resolution-and-upscaling.md` before selecting output sizes. Clean source mattes first, compare source detail with projected display pixels at the intended DPR, and inspect extreme poses at native close-up size. `scripts/assess_resolution.py` checks sampling, aspect, gutters, texture limits and RGBA8 mip memory; run it with `--self-test` to verify the helper.

Run `python scripts/self_test_morph_sequence.py` for endpoint, seam, timing, invalid-mesh and overwrite-protection tests. Run `python scripts/self_test.py` for meaningful geometry/attachment failures, and `python scripts/self_test_final_frame_analysis.py --output-dir <temporary-directory>` for stale/partial evidence rejection. Use `scripts/audit_final_frame_analysis.py --help` and `scripts/painted_walk.py --help` for their contracts.

Character artwork and project-specific evidence stay in the game project. This repository contains the reusable skill, not its desktop companion or game assets.
