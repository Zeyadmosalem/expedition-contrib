# Block Hopper — design

Date: 2026-11-17
Status: approved in brainstorming, awaiting spec review

## Goal

Replace the "skull hero blasts the contribution grid" animation with a platformer: the hero
hops across the year, one hop per week, landing on each week's tallest block. Same isometric
pixel-art style, same hero (skull or picture head, suit and chest-light colours), same
CSS-only animated SVG that plays inside GitHub's `<img>` sandbox. Nothing is destroyed; the
hero lights up the route it plays through.

The blaster is removed, not kept as a mode.

## What the viewer sees

1. **Warp in.** The hero flickers in on the front catwalk (the existing `hv` flicker) at
   `START_U`, then hops onto week 0.
2. **One hop per week, weeks 0 … N-1.**
   - Target = the week's tallest block (highest level). Ties go to the weekday nearest the
     previous landing's weekday; if still tied, the lower weekday.
   - A week with no active days → hop onto the floor tile at the previous landing's weekday
     (weekday 3 if there is no previous landing).
3. **Landing.**
   - The landed block squashes for an instant (scaleY ~0.8 anchored at its base, ~0.12 s) and
     recovers.
   - A pixel coin pops out above the block, rises ~12 px while spinning (2-frame flip), and
     fades (~0.6 s).
   - The block's top face switches to a glowing "lit" colour and stays lit until the finale
     reset.
   - Every other active block in the same week does a 2 px sympathy bounce at the same moment.
   - Floor landings: no squash, no coin, no light.
4. **Finale.** After the last week the hero does one victory hop in place, then warps out
   (existing flicker). A pixel flag pops up on the busiest day of the year (highest
   contribution count; ties → the latest date). "LEVEL CLEAR" (replaces "SECTOR CLEAR") shows
   from the last landing until the lights reset. Lit tops fade back to normal over ~0.4 s
   before the loop restarts.
5. **Hero pose.** Airborne uses a new jump pose (legs tucked). On the ground it uses the stand
   pose (`LEGS[0]`). No gun.
6. **Reduced motion:** a still frame: hero standing on the catwalk, all blocks unlit, flag
   and "LEVEL CLEAR" shown.

Accepted trade-off: the hero is always drawn above the blocks. CSS cannot re-sort SVG depth
during an animation, so a tall block in front of the hero does not hide its feet.

## Timing

| Item | Value |
|---|---|
| Intro (warp in) | 0.5 s |
| Hop onto a block | 0.30 s + 0.04 s × abs(level difference to previous landing) |
| Floor → floor hop | 0.18 s |
| Ground pause after each landing | 0.06 s |
| Victory hop + outro | 0.5 s + 0.5 s |
| Hold with lights on | 1.2 s |
| Lights fade | 0.4 s |

Typical year: ~53 hops → ~18–20 s of hopping, ~23 s per loop. Floor and catwalk count as
level 0 for the level difference.

## Motion (approach A: nested X/Y groups)

The hero is wrapped in two nested groups with separate keyframes:

- **Outer `hx`** moves the ground point: at each hop it travels from the takeoff tile's
  ground point to the landing tile's ground point with `linear` timing, then holds through the
  ground pause.
- **Inner `hy`** is the vertical arc relative to that ground line. Each hop is two segments:
  takeoff → apex with `cubic-bezier(.33,.66,.66,1)` (ease-out), apex → landing with
  `cubic-bezier(.33,0,.66,.33)` (ease-in). Apex lift = 10 px above the higher of the two
  tiles' top surfaces, + 2 px per level climbed.
  The standing height on a tile = that tile's block height (`HEIGHTS[level]`), so the inner
  offset at takeoff/landing is `-HEIGHTS[level]`.
- **Pose** switching (stand vs jump) uses `steps(1,end)` opacity keyframes on the two pose
  groups, toggled at each takeoff and landing.

About 3 keyframes per hop per group, so a few KB of CSS for a full year.

## Code changes

Rename the package `contrib_blaster/` → `contrib_hopper/`. Update `__main__`, the workflow
(`paths:` and `python -m` lines), README commands/layout table, and test imports.
**Output filenames do not change** (`expedition-contrib.svg`, `expedition-contrib-dark.svg`),
so existing profile README image URLs keep working.

| File | Change |
|---|---|
| `contributions.py` | None. |
| `character.py` | Remove the `gun` field and its colour mapping. A `gun` key in a toml is accepted and ignored (kept in an `IGNORED` set so `from_dict` does not reject old files). |
| `pixels.py` | Remove `GUN` / `gun()`. Add `JUMP_LEGS` and `hero_poses(colors, head) -> (stand, jump)`. Add `coin(frame)` (2 frames, gold + highlight, outlined), `flag()` (pole + pennant in the theme accent), and `lit_top(color)` (top-diamond-only raster to overlay on a block). Keep `iso_block`, `Raster`, palette, skull. |
| `render.py` | Rewrite `plan()` and `render()`. `Timeline` holds `hops: tuple[Hop]`, `period`, `hop_end`, `flag_day`, `reset_start`. `Hop(week, weekday, level, takeoff, land, apex)` — `level` 0 = floor. Remove bolts, muzzle flash, bursts, `Shot`. Keep floor/catwalk drawing, `THEMES` (add `lit` and `coin` colours per theme), HUD, viewBox/bounds logic, reduced-motion rule. |
| `character.toml` | Drop the `gun` line. |
| `README.md` | New description, alt text, regenerated preview, layout table, customisation section without gun. |

Per-block CSS: each active block is a `<g>` holding the block `<use>` and, for landed blocks,
its lit-top overlay `<use>`. The `<g>` carries one keyframe animation (squash for the landed
block, sympathy bounce for the others in that week) so the overlay always moves with its
block; the overlay has its own on/off opacity keyframes. Coins reuse one
shared keyframe started with the existing `--t` / `animation-delay` trick.

## Edge cases

- **Empty calendar:** every hop is a floor hop; flag goes on the last week's middle tile
  (weekday 3); "LEVEL CLEAR" still shows.
- **Partial first/last week:** use the weeks/weekdays the calendar actually has; a floor hop
  in a partial week lands on a weekday that exists in that week (nearest to the previous one).
- **Picture head:** same as today; pose rasters are built from `character.head_raster()`.

## Testing

Replace blaster-specific tests in `tests/test_blaster.py` (rename to `tests/test_hopper.py`):

- exactly one hop per calendar week, in week order
- each hop lands on that week's tallest block; tie-break rules hold; empty weeks are floor hops
- takeoff < land, landing times strictly increase, last landing < period
- every landed block has a lit overlay that turns on at its landing time and is off again
  before the period ends
- one coin per non-empty week; no coins for floor hops
- flag sits on the busiest day
- SVG for both themes is well-formed XML; no `<script>`; no bolt/burst elements
- empty calendar renders
- hero uses the skull and red chest light by default; no gun pixels

Keep the parsing, token-handling, character and picture-head tests, updating `gun`
references (old `gun` key accepted and ignored).

Manual check: render `preview/` from `tests/fixtures/calendar.json` and step through it in a
browser in both themes before calling the work done.

## Out of scope

- A coin counter in the HUD.
- Depth-correct occlusion of the hero by blocks in front of it.
- Keeping the blaster as a selectable mode.
