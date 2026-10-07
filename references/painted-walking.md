# Reuse the painted walk routine

This Pets repair became a destination-independent helper: `scripts/painted_walk.py`. It moves intact thigh/shorts, knee, sock and sandal pixels with smooth displacement fields. The original garment overlaps hidden roots; the split follows the actual transparent leg gap. Linear-light premultiplied sampling preserves edges and shading. Feet below the ankle translate rigidly. A fixed foreground limb prevents overlap reversals; choose it from the approved view/user request, never swap it with gait phase.

Use Pillow, NumPy and SciPy in the chosen Python environment. Run:

```text
python scripts/painted_walk.py character.json --output-dir animation
```

The JSON contains `cell_size_xy`, `figure_height`, `baseline_y`, `frame_count` (8 works here), `frame_ms`, and `views`. Each view has a unique `id`, transparent `file` relative to the JSON, `travel_xy` (`[1,0]` right, `[-1,0]` left, `[0,1]` front/down, `[0,-1]` rear/up), and measured `landmarks` in that source's pixels:

```json
{
  "cell_size_xy": [192, 208], "figure_height": 160,
  "baseline_y": 203, "frame_count": 8, "frame_ms": 120,
  "views": [{
    "id": "down", "file": "front.png", "travel_xy": [0, 1],
    "foreground": 1,
    "landmarks": {
      "waist": 795, "hip": 865, "mid": 604,
      "hem": [947, 947], "knee": [992, 992],
      "sock": [1035, 1035], "ankle": [1110, 1110],
      "centres": [490, 690]
    }
  }]
}
```

These numbers illustrate one source, not universal anatomy. Arrays mean viewer-left/right; `foreground: 1` draws viewer-right last. `hip` lies inside clothing, above both hems. Measure every new view rather than carrying coordinates across crops. Sources must already pass proportion/style checks. Correct a faulty source before motion; the helper cannot invent missing paint or limbs. It uses one fixed 512-square working registration and one final family scale, reserves space for vertical foot travel, rejects folded fields/detached substantial regions/clipped export edges, and writes individual transparent frames, an atlas, and `animation.json` with row/timing/pivot/source hashes. It checks all planned outputs against every source/spec before writing; use a separate output directory. These structural checks do not replace visual review.

For four-direction game movement, supply four accepted whole-body sources: front/down, rear/up, right and left, each with measured landmarks. Rear artwork must turn clothing/feet/props together and show heels; head-only look directions are insufficient. Keep the reference's short measured limbs, clothing coverage and prop identity through every view. Register all walks, neutral anchors and turns to one family scale and shared sole pivot. For these Germans on vacation `foreground: 1` stays viewer-right in both lateral facings by user request; that is a case choice, not a rule for every character.

Generate only missing body views from accepted art. Derive intermediate whole-body views from adjacent accepted anchors; requested absolute angles can produce visually wrong facing. Inspect nose, chest, back, feet and prop visibility in the actual ordered pixels for monotonic facing through each path, including its reverse. Holds are acceptable; facing reversals are not. Prove readable steps at native export size: tiny projected foot movement can look stationary even when geometry alternates. Vertical mode couples projected steps/swing lift with moving thigh/garment hems, pelvis sway and torso weight transfer. Inspect full joints after increasing motion; preserve approved lateral cycles while repairing vertical ones.

For turns, use accepted planted body views through front three-quarter, profile, rear three-quarter and rear. Finish the stride, plant feet, turn, then resume the destination cycle; inspect the actual walk→turn→walk sequence. The Python `animate()` function accepts `strength` (0–1) and explicit `phases` for source-pixel stop/start in-betweens. Ease the last stride phase toward strength0, turn through neutral painted poses registered at that same sole baseline, then ease the target phase from0 to1. At strength0 it returns the intact source pixels. Ship these actual bridge frames and review them too; do not snap to a differently registered idle. Do not morph front into back across incompatible visibility or use ghosting crossfades. More turn angles or articulated in-betweens are optional when the game needs them.

`plan_transition(source, target, walks, bridges, turn_cells, anchors, turn_ms=85, with_context=False)` in `painted_walk.py` returns only runtime **stop→whole-body turn→start** cells by default. Supply walk metadata `{row, count, frame_ms}`, bridge metadata `{row, stop_cols, start_cols, frame_ms}`, ordered clockwise turn cells `{row, col}`, and directional anchor indices. It chooses the shortest path (clockwise on an exact tie), supporting all 12 distinct direction pairs, including side↔up/down corners. Stop-neutral must equal the source planted anchor pixel-for-pixel. The target anchor precedes its start bridge. Enter the core **after the last source walk phase** (phase7 in an eight-frame loop), then resume target **phase0**. `with_context=True` adds one source and target loop for a demo; never insert those context loops into the runtime core. Same-direction returns `[]`, or one loop with context.

Keep a single latest-request slot in the runtime. Repeated input does not reset the phase timer, walk phase or active transition. While walking, overwrite the pending direction; at the last phase boundary, discard a request matching the current direction or consume the newest target and play its core once. During a core, coalesce further requests but finish the active core, resume its target phase0, and reconsider the latest request at that walk's next last-phase boundary. This keeps shared planner code stateless and avoids a second animation controller in the skill. Verify all 12 demo lists and reverse paths from actual frames, not turn-index order alone.

Game atlases may use named rows such as down/right/up/left plus a turn row; ship row indices, frame times and shared pivot in a manifest. Preserve the cell's width/height ratio in the game quad instead of stretching rectangular cells into squares. For camera-facing billboards, transform the pixel-pivot offset by the billboard's full orientation and place that pivot at the actor's ground position/elevation; a vertical-only centre offset makes tilted-camera feet float or drift. Verify the actual rendered pivot through camera angles and turns, alongside blocked/paused walking and queued direction changes.

## Calibrate ground speed to planted feet

Distance-driven phase alone does not prove planted feet: the configured ground distance per cycle must match the exported shoe motion at the consumer's actual scale. Keep collision-resolved movement authoritative and tune the walk clock, not the character's route speed.

1. In each side-view row of the **exact exported atlas**, mark the same visible sole point on each foot in at least three frames while that foot is planted. Exclude swing, toe lift, occlusion and turn cells. Follow foot identity; use unwrapped frame numbers across the loop (for example 7, 8, 9). Record `along_pixels` positive in the travel direction, negating x for left-facing art. Measure shoe length in those same exported pixels and record the atlas SHA-256 so stale annotations are detectable.
2. Convert pixels to ground units: for a camera-facing side billboard aligned with travel, `game_units_per_pixel = billboard_height_world / frame_height_pixels / world_units_per_game_unit`. Germany Simulator uses `world_units_per_game_unit = 0.02`; include the exact per-character height passed to `atlasSprite`. For an oblique projection, measure the travel-axis projection in the running game. Do not infer forward distance from raw front/back image y; it mixes depth with foot lift. Use ground-plane projection or authoring foot-root data for those views.
3. Run `python scripts/assess_walk_speed.py measurements.json`. For each planted contact, a fixed ground point obeys `world_root(phase) + foot_relative_root(phase) = constant`. The routine fits cycle distance `D = -cov(phase, foot_ground_offset) / var(phase)` after centering each contact separately. It reports current and best-fit shoe slide in ground units and shoe lengths. Check both feet and both side views. A negative fit, disagreement between feet/views, or visible residual slide indicates wrong marks or art that needs repair; changing the clock cannot correct that.
4. Apply the measured **per-character** distance per complete cycle to the runtime's distance-driven frame progression. Freeze phase on blocked/paused movement and freeze the root through planted turns. Reassess after an art or billboard-scale change, then inspect multiple cycles, wraparound, starts, stops and turns in the real browser at normal speed. The numeric fit is a diagnostic, not visual acceptance.

Example input (numbers are illustrative, not an accepted character calibration):

```json
{
  "character": "example", "view": "right", "atlas_file": "example-atlas.png", "atlas_sha256": "hash-of-exact-export",
  "frames_per_cycle": 8, "game_units_per_pixel": 0.58,
  "current_cycle_distance": 24, "shoe_length_pixels": 22,
  "contacts": [
    {"foot": "left", "samples": [{"frame": 2, "along_pixels": 112}, {"frame": 3, "along_pixels": 105}, {"frame": 4, "along_pixels": 98}]},
    {"foot": "right", "samples": [{"frame": 6, "along_pixels": 110}, {"frame": 7, "along_pixels": 103}, {"frame": 8, "along_pixels": 96}]}
  ]
}
```

Run `python scripts/assess_walk_speed.py --self-test` after editing this subroutine. There is no universal slide threshold; judge the residual against measured shoe size and native-size playback.

Pets retain their supported layout: up/down game cycles belong in separate game assets, not extra Pet rows. The final image-analysis gate covers every delivered walk and turn frame, source comparison and transitions. After a Pets update, fetch stored bytes and compare pixels before claiming success.

For a side source with spread contact feet, measure `foot_centres` and the actual cloth seam as `split_path_xy` (ordered x/y points). The helper follows internal transparency near that seam, keeps the entire shoe below each ankle, and re-centres contacts into the passing pose. Set `step_width` only after native-size inspection. Never choose exterior transparency as the leg gap or split through a boot arch. `auto_hand_mask: false` disables the rough hand heuristic when it catches trousers; provide a precise `rigid_mask` image for hands/props extending below the waist. The mask shares the source canvas and its one registration transform; exclude it from both leg layers and restore it with the upper body. Broad rectangles can capture trouser corners and create floating chips. Missing leg paint behind a prop requires a corrected source, not gap filling.

`root_overlap` extends original garment paint over hidden thigh roots (default 2 working pixels, supported 0–32, always above both knees). Increase it only to repair an observed seam and inspect every opposite gait phase on light/dark backgrounds. It cannot correct a wrong source silhouette or material. Already registered 512-square families can set `registered: true` and `working_baseline_y`; this avoids a second fit changing the family scale. The optional controls preserve previous default output pixels.

For an action during walking, prove the lift/action/return key poses with the character's own prop and hand. Bake each accepted action key across the gait phases when one atlas must serve both clocks. Action time selects the upper-body/prop key; actual ground distance selects the feet. Stationary feet stay stationary while the action continues. Exact walking artwork at action endpoints prevents a state-change pop; enter/exit only in the matching facing and finish any planted turn first. Treat detached water droplets as an explicit effect layer after checking the connected body; do not weaken anatomical checks. Review the effect, hand/handle join, return, mirrored visibility and every delivered key/phase combination. Check the consumer's texture-size limit and keep the same ground pivot if action margins require larger cells.

In the consumer, legacy row selection must run only for legacy assets. Assigning an old row before a zero-distance early return can show a turn/action row while blocked. Apply complete manifest grid metadata, preserving defaults for older manifests, and test paused/blocked walks, real action controllers and missing-asset fallback. Preserve character routes, barks and voice ownership while replacing their animation artwork.
