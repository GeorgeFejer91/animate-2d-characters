# Germany Simulator lessons

The observed loader used archived `crowd-towel-man.png` and `crowd-towel-woman.png`, 32×3 cells with front view in row1. Recheck loaded assets next time: experimental references initially supplied the wrong view.

Man: straw hat, sunglasses/moustache, blue polo, khaki shorts, white socks over toes, brown sandals, blue towel/yellow band. Woman: grey curls/visor, coral jacket, white shirt, khaki shorts, white socks over toes, dark sandals, red/white towel. Towels stay under the anatomical right arm. The user approved local storage and source-pixel/manual alternatives for this session; those are not standing workflow exceptions.

| Observed failure | Correction |
| --- | --- |
| Wrong view or changed identity | Inspect actual assets and approved other states first |
| Same foot led in generated poses | Prove opposite contacts early; change strategy after repeated failure |
| Static thighs or detached thighs | Move full thigh/shorts hems from connected hips; remove duplicate static skin |
| Long/thin legs, small shoes, too much skin | Lock visible proportions against approved idle art, not inferred bone lengths |
| Gaps, pointed roots, cuff/skin slivers | Inspect all final joins on light/dark; assign pixels once and hide roots under clothing |
| Smooth tubes against a painted body | Preserve intact knee/skin paint; smoothing invented surfaces did not solve congruence |
| Fuzzy chroma edges | Clean alpha and use one local final despill; inspect actual export and solid-background preview |
| Jump/scale popping | Shared registration preserves source displacement |
| Qualified passes despite visible defects | One source-bound all-frame visual gate; unresolved findings fail |
| Front/back feet alternate but barely read as walking | Check native motion; increase projected stride/lift with connected thigh/hem and body weight transfer |
| Abrupt walking-to-turn feet or baseline | Ease actual source-pixel gait fields into the same planted source baseline, then turn and ease the new walk in |
| Numerically ordered angles turned the wrong way | Derive whole-body views from adjacent accepted anchors; inspect actual pixels for monotonic facing in every forward/reverse path |
| Repeated direction input restarted gait | Coalesce the latest request; finish the current loop/core before a new stop→turn→start path |
| Stale reviews/service status | Review exact encoded/stored pixels and preserve stable IDs/activation |

Earlier tube/ribbon repairs failed for long legs, lost knee paint, changed sock/shoe proportions and remnants. Strict review rejected all32 saved walking frames despite30 passing validator fixtures. Those fixtures verify software behavior, not artistic quality; rejected renderers are not default recipes.

The accepted repair generates matching neutral directional sources from the approved base and deforms intact painted limbs beneath one connected source garment. Knee paint, socks and sandals stay in the original limb pixels. A straight column split through a shoe initially left a dangling sole sliver; following the real transparent gap removed it. A source with excessive exposed skin needs correction and renewed comparison before animation. All32 lateral walking frames passed actual source/light/dark/ordered-frame analysis; both Pets were updated under their original IDs and fetched stored RGBA pixels matched the approved exports. Viewer-right stays foreground in both facings because the user requested that order.

The reusable `painted_walk.py` reproduces those32 approved frames exactly in a regression check. Initial vertical projection was too small at native size; increasing stride/lift with coupled thigh/hem/pelvis/torso motion addressed that failure. Four accepted body sources preserve the short original limbs; rear/up shows heels and towel on viewer-right. Stop/start fields ease into the exact planted turn anchor, sharing the sole pivot. The planner supports all12 direction pairs with runtime core separate from demo loops. Absolute angle requests produced wrong facing: adjacent accepted anchors and actual forward/reverse pixel inspection proved more useful. Details live in [painted walking](painted-walking.md). These are separate game exports, not extra unsupported Pets rows; every revised frame still needs the single final image gate.

Morphing is optional and has not been demonstrated as a repair here. Keep character-specific ratios, masks and pivots out of generic defaults.

The featured-character extension exposed different failures: spread side-contact poses split boots at a fixed column, a broad bucket mask captured trouser corners, and a raised-bucket front pose left a slit under the jacket in opposite gait phases. Measured cloth seams and complete-foot centres, precise protected prop polygons, and original garment overlap above the knees repaired those defects. A bucket hiding the whole calf needed new visible leg paint before rigging. Merz's side action retained approved side trousers; his front action used an intact matching front body because replacing its legs with the bucket-occluded walking source restored missing paint. Water is a separate intended effect, never an excuse to relax body connectivity checks. Details and optional helper inputs are in [painted walking](painted-walking.md).

Merz uses eight bucket-action keys crossed with eight distance-driven gait phases per front/side action. Action endpoints use exact walking cells. Left side action frames mirror the accepted middle action; endpoints use the actual left-facing walk. The final export review covers all key/phase cells, native and light/dark composites, and the ordered action/turn paths. A review-sheet canvas reuse bug briefly displayed a duplicate character in the mirrored preview; rebuilding the sheet confirmed the atlas itself had one figure. Always inspect exact final consumer pixels and rebuild stale evidence after repairs.
