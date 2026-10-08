# Narrative action rigging

Use this when a character must **do something because an event happened**: approach a player, inspect a document, react to a queue call, speak, glare, recover, and return to ordinary movement. Design the scene and its motion authority together before generating a sheet. The state's purpose determines which poses and transitions need art.

## Event contract

Write one small beat card for each triggered interaction:

| Field | Decision to make |
| --- | --- |
| Trigger and guard | Exact world event, proximity or story stage, one-shot/cooldown, and whether it can interrupt a mission. |
| Owner and priority | Which character owns the beat; which routine actions pause; which higher-priority event can preempt it. |
| Path | Start, approach/turn points, stopping distance, obstacle rule, and return route. The body must travel in world space. |
| Performance | Ordered readable verbs such as walk → settle → look → stamp → speak → hold → recover; duration or completion event for each. |
| Clock and contact | Which clock advances each verb, where a one-shot starts/holds/ends, and which sole or prop contact stays fixed. |
| Props and speech | Which hand keeps the object; speaker, exact visible line, lip/head/gesture cues, voice-start and fallback behavior. |
| Scene cues | Lighting, sound, camera and bounded color-valence target, with independent mix controls where the game has them. |
| Exit | Normal completion, interruption, replay, voice failure, and level close all release pose, sound, camera, and gameplay locks. |

The beat card is an authoring contract, not a new engine framework. Reuse the game's existing entity, route, dialogue, audio, and render state. Keep narrative text in its story authority and route/action state in simulation code. The renderer reads state and owns only its visible interpolation. A Pet-like idle repertoire can provide look, fidget, handle-prop, flinch, and settle actions, but do not import a Pet atlas format or upload flow into another game.

For a camera-sensitive beat, block a few rough or existing-sprite snapshots at the actual game view before creating missing poses: approach, planted contact, line/prop hold and release. This checks placement and sightline without adding a separate animatic pipeline. Mark the physical prop hand and its screen-side position in each facing; the two labels can differ after a turn.

## Movement lanes

- **Root/path:** World position and facing follow the planned path; acceleration, arrival, and obstacle clearance are simulation-owned. A sprite walk row never substitutes for translation.
- **Feet and pelvis:** Advance gait phase by distance traveled, with alternating planted and swing feet and a visible side stride. Hold or settle feet at the destination; do not slide through a paper or speech pose.
- **Torso, hands, props:** Keep a continuous shoulder-to-hand silhouette and the same prop hand. Mark grip/contact, rigid attachments, deforming paint and near/far draw order at action extremes. Separate work, gesture, look, and flinch keys only when their action reads distinctly at game size. Approve the action keys before filling in connected inbetweens.
- **Head, gaze, mouth:** Aim toward the target and return smoothly. While a character owns speech, animate a modest mouth cycle driven by actual speech boundaries where available, or a readable timed fallback. End the mouth cycle when the line ends or is cancelled.
- **Scene response:** Lighting, sound, camera, and subtle paint tint follow the active beat or dialogue owner. Keep the actor inside the actual camera sightline before a spotlight or close-up begins; verify the projected focus in the playable scene. Ease the valence target and restore the source color after ownership ends; avoid per-frame random color changes.

An action can wait for a walk-cycle boundary to stop, but a dramatic approach may need a precise arrival distance. In either case, encode who owns the character until the scene releases it. A route pause, player interaction, or queue call must not replace a higher-priority beat halfway through. Once released, choose a reachable route point and resume without teleporting or trapping the actor in a gesture frame.

## Example: the Bürgeramt Aktenkurier

The player enters the office; the Aktenkurier leaves his paperwork loop, walks up and stops near the player. An in-world spotlight remains on him while the room falls nearly black, an eerie iridescent tone fades in, and the visible German line reads: **“Wer die Finsternis sieht, hat sie selbst gewählt!”** He holds the stare briefly; light and sound fade, then he finds his route and returns to work while the game continues. The beat owns the actor and pauses the queue clock during the blackout. It uses the established subtitle rail, not a new popup. A one-shot guard prevents retriggering on the same visit. Replay and close cancel the tone and clear the beat.

This is a concrete scene example, not a required pattern or line for other characters.

## Production and acceptance

1. Inventory existing source views and props against every verb in the beat card. Generate only missing keys; lock scale, feet baseline, lighting, and prop ownership across the family.
2. Build direction walks plus the needed action rows. Verify opposite contacts, passing, the loop seam, and action transitions in ordered playback at game size. An eight-cell row with repeated holds still has only as many distinct motion samples as its visible poses.
3. Inspect every affected final encoded cell, desktop and mobile, for transparent gutter, attached limbs, source identity, and color/texture continuity. Inspect high-contrast light/dark composites and a playable scene, not only the source PNG.
4. Exercise trigger, arrival, speech/gesture ownership, color easing, sound level, cleanup, replay, and ordinary gameplay after the beat. Include a focused runtime test for the event sequence and a browser playtest for the visual result.

For a team workflow, assign story, character art, animation, color mood, gameplay, soundscape, mix/volume, and QA separate deliverables. Each domain should state its inputs, owned output, and handoff evidence in the same beat card. Review cross-domain timing together before accepting the scene.
