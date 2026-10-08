# Reactions and game behavior

Transfer useful Pets mechanics into the game's event model. Ordinary game animation needs no Pets plugin, fixed eleven-row layout, Library upload or desktop companion. Reuse approved states first; generate only missing poses grounded in canonical art. Keep the requested actor scope.

| Meaning | Game event | Visual requirement |
|---|---|---|
| Idle | Resting during a pause | Calm breathing/blink; planted feet |
| Waving | Greeting/conversation | Attached hand; no wave marks |
| Jumping | Success celebration | Actual lift, stable size, same landing baseline |
| Failed | Wrong answer/blockage | Readable body/face reaction; attached limbs |
| Waiting | Awaiting an answer | Expectant pose distinct from idle/checking |
| Working | Thinking before replying | Focused effort, not foot-running |
| Review | Checking an answer/task | Eyes/head/hand inspect; retain existing props |
| Look | Attending to a nearby player | Correct viewer direction and head/neck attachment |

Walking remains distance-driven. Reactions use elapsed time and pause translation at the planted pivot. Each one-shot step has its own elapsed time, reset when that step actually begins after any pending walk/turn or preceding action. Sample its authored cells or dwell durations from that local clock, without wrapping through frame zero; hold its terminal pose or enter the next state at completion. Ambient idle/work phase and gait distance must not choose its entry frame. Freeze its clock when the owning action pauses; on preemption, cancellation or replay, clear the prior action phase and release its locks. This is a host-state rule, not a requirement to replace an existing animation player.

Finish the current step, settle, turn toward the reaction's approved body view, play the state and return through approved turn/start frames. Never use head-look art as rear walking art. Queue a new event until the current turn or airborne jump finishes. Use proximity entry and cooldowns so greetings do not repeat each update; suppress incidental greetings while a reaction or dialogue/answer request is pending so they cannot replace its outcome. The host retains routes, collision decisions and voice ownership.

`scripts/character_interactions.js` is an optional browser/Node reaction player. It consumes `walks`, `bridges`, `transitions` plus `interactions.states[name]={row,durations_ms}` and sixteen ordered `interactions.look.frames`. `request(n,nameOrNames,manifest,{lookIndex})` queues one latest event; `advance(n,dtSeconds,manifest)` returns true while translation must pause. Finish existing turns in the host first. A sequence such as `['review','jumping']` shares a neutral entry/exit. The host owns triggers and cooldowns.

That example player assumes eight walk phases and a down-facing neutral. Adapt its settle indexing and neutral-facing transitions before using a different clip count or facing; do not insert it unchanged into a dense walk or add it beside a host player that already owns those transitions.

Extract imports from the exact approved encoded file and verify source identity. Measure neutral against the game family, then apply one shared scale/pivot transform to every state, preserving airborne displacement. Never fit each frame separately. Uneven source strips need complete pose-group extraction; equal slicing applies only to a verified encoded atlas. Protect props/handedness and preserve accepted walking pixels.

Apply the existing single final-image gate to imported/generated cells and entry/exit frames. Inspect native crops, enlarged light/dark composites, source comparison, ordered loops and gameplay transitions. Verify idle→jump→idle, greeting→waiting→walk and review→success/failure→walk. For a short one-shot, inspect its entry, anticipation, contact, recovery and exit at the actual duration and after several different prior ambient phases; confirm the final action cell is reachable and does not wrap. Check real triggers, dialogue pausing, landing, queues, cooldowns, renderer grid/pivot and saved-file hashes. A scheduler test cannot approve art; valid art cannot prove event hooks.

When a shared size correction would clip the highest jump in a fixed cell, reduce only the measured whole-body airborne excursion with one shared gain. Preserve pose scale and the resting/landing baseline; verify the jump still visibly leaves the ground. Do not clamp head pixels or fit each pose separately.

Pets-specific storage, stable IDs, authoritative validators and upload sessions stay in [Pets integration](pets-integration.md). Do not bundle a private plugin cache or invent equivalents for server validation. The independent game workflow uses these transferable methods and its own asset contract.
