# Empty-week slide & nap, and themeable colours — design

Date: 2026-11-17
Status: approved in brainstorming, awaiting spec review
Builds on: `2026-11-17-block-hopper-design.md` (merged)

Two changes to Block Hopper:

1. The hero no longer hops tile to tile across weeks with no contributions. It hops down,
   slides along the floor, naps in the middle of long gaps, and hops back up.
2. Scene colours come from a `theme.toml` with presets. The default preset, `crimson`,
   matches the profile README (`#EF4E5C`, `#D12A3C`, `#961A2A`, `#400E18` on `#0A0407`);
   `cyan` is the original look. Any colour can be overridden per GitHub theme.

## 1. Empty weeks: hop down, slide, nap, hop up

### Behaviour

A **gap** is a maximal run of consecutive weeks `a..b` with no contributions (k = b − a + 1
weeks).

- **Hop down** onto the floor of week `a`, at the weekday nearest the previous landing's
  weekday among the weekdays that exist in week `a` (same rule as today's floor hop).
- **Slide** (only if k ≥ 2) along the floor from week `a` to week `b`, at the weekday nearest
  the current weekday that exists in week `b`. Constant speed, `SLIDE_PER_WEEK` = 0.12 s per
  week. Slide pose: wide, low surf stance, feet on the floor. A dust puff appears at each
  week tile the hero reaches during the slide.
- **Nap** (only if k ≥ `NAP_MIN` = 3): the slide is split at the middle week
  `m = (a + b) // 2`: slide `a → m`, nap at `m` for `NAP` = 1.2 s, slide `m → b`. Sleep pose:
  the stand pose rotated 90° (lying on the floor). Three pixel "Z"s float up and fade,
  0.35 s apart.
- The next non-empty week is a normal **hop up** onto its tallest block.
- A one-week gap is just hop down + hop up (no slide, no nap).
- Gap at the **start** of the year: the hop down is from the catwalk (`FLOOR_HOP` timing).
  Gap at the **end**: slide (and nap) to the last week; the victory hop happens on the floor.
- An all-empty calendar: hop down from the catwalk to week 0, slide, nap in the middle,
  slide to the last week, victory hop. Flag rule unchanged (last week, weekday nearest 3).

After this change there are no floor-to-floor hops: every hop either lands on a block or is
the single hop down into a gap.

### Timing

Every move is followed by the existing `PAUSE` (0.06 s). Hop durations and apex formula are
unchanged. The hop down from the catwalk keeps `FLOOR_HOP` (0.18 s).

### Route model (`route.py`)

- `Hop(week, weekday, level, takeoff, land, apex)` — unchanged.
- New `Slide(from_week, from_weekday, week, weekday, start, end)`.
- New `Nap(week, weekday, start, end)`.
- `Timeline` gains `moves: tuple[Hop | Slide | Nap, ...]` (the full sequence in time order,
  excluding the victory hop). `Timeline.hops` stays: every `Hop` in `moves`, in order.
  `victory`, `flag_day`, `hop_end`, `reset_start`, `period` keep their meaning; `hop_end` is
  the end time of the last move.
- New constants `SLIDE_PER_WEEK = 0.12`, `NAP = 1.2`, `NAP_MIN = 3`.

### Rendering (`render.py`, `pixels.py`)

- `pixels.hero_poses(colors, head)` returns a `Poses(stand, jump, slide, sleep)` named
  tuple. `stand`, `jump`, `slide` are the same size; `sleep` is `stand` rotated 90° clockwise.
  New `pixels.rotate_cw(raster)`, `pixels.zee(color)` (4×4 "Z", outlined) and
  `pixels.puff(color)` (4×3 dust puff, no outline).
- Hero groups: `hx` (ground motion) and `hy` (arc) as today. A slide moves `hx` linearly from
  the start tile's ground point to the end tile's and keeps `hy` at 0. A nap holds both.
- Poses: four groups `ps` (stand), `pj` (jump), `pl` (slide), `pz` (sleep), each with
  step-timed opacity keyframes. Exactly one is visible at any time: jump during a hop, slide
  during a slide, sleep during a nap, stand otherwise. `pz` has its own transform so the
  lying sprite rests on the floor centred on the ground point.
- Dust puffs and Zs use the shared `--t` / `animation-delay` trick (like coins) in the `fx`
  layer. Puff: rises 3 px and fades over 0.4 s. Z: rises 12 px, drifts 4 px right, fades over
  0.9 s.
- Reduced motion: unchanged (hero standing on the catwalk; puffs and Zs hidden like coins).

## 2. Colours: `theme.toml`

### File

`theme.toml` in the repo root (shipped with `preset = "crimson"` and commented examples):

```toml
preset = "crimson"   # "crimson" (matches the profile) or "cyan" (the original look)

[dark]               # optional overrides for GitHub's dark theme
# levels = ["#5a1422", "#961a2a", "#d12a3c", "#ef4e5c"]   # quiet -> busiest
[light]              # optional overrides for GitHub's light theme
# text = "#400e18"
```

Colour keys (per theme): `floor`, `catwalk`, `lamp`, `levels` (exactly four, quiet →
busiest), `trim`, `text`, `sub`, `lit`, `flag`. Values are hex codes (`#rrggbb` or `rrggbb`).
Unknown top-level keys, unknown colour keys, unknown presets, bad hex codes and a `levels`
list that is not four colours are rejected with a clear `ValueError`. Missing keys come from
the preset; a missing file means the `crimson` preset.

### Presets

| key | crimson dark | crimson light |
|---|---|---|
| floor | `#160c10` | `#f2e4e7` |
| catwalk | `#2c161e` | `#e2ced4` |
| lamp | `#ef4e5c` | `#d12a3c` |
| levels | `#5a1422 #961a2a #d12a3c #ef4e5c` | `#f4a7ae #ef4e5c #d12a3c #961a2a` |
| trim | `#ff8a94` | `#ffd0d4` |
| text | `#ef4e5c` | `#400e18` |
| sub | `#9a6a72` | `#8a5a62` |
| lit | `#ffd166` | `#ffb703` |
| flag | `#ffe3e6` | `#400e18` |

`cyan` = today's `render.THEMES` values exactly (`walk` renamed `catwalk`; `flag` and `lit`
as today).

On the dark page busier levels are brighter; on the light page busier levels are darker
(the existing test keeps holding for both presets).

### Code

- New `contrib_hopper/theme.py`: `PRESETS`, `DEFAULT_PRESET = 'crimson'`, `KEYS`,
  `from_dict(data) -> dict[str, dict]` (returns `{'dark': {...}, 'light': {...}}` with RGB
  tuples and `levels` as a list of four tuples), `load(path)`, `palettes(preset)`.
- `render.render(cal, theme='dark', character=None, palette=None)`: `palette` is one theme's
  colour dict; `None` means the default preset's colours for `theme`. `render.THEMES` stays
  as the default preset's palettes (so `for theme in THEMES` still lists `light`, `dark`).
- CLI: `--theme FILE`; without it, `theme.toml` in the working folder if it exists, else the
  default preset.
- Workflow: `theme.toml` added to the push `paths:` filter.
- README: new "Customize the colours" section; the hero section is unchanged.

## Testing

- Route: every `Hop` lands on a block or is the first move into a gap; each gap of k weeks is
  exactly: hop down, then (k ≥ 2) slide(s) ending at week `b`, with a nap iff k ≥ 3 at
  `(a + b) // 2`; one block landing per non-empty week; moves are contiguous in time (each
  starts `PAUSE` after the previous ends); start/end/all-empty gaps; partial-week weekdays.
- Render: exactly one pose visible per keyframe time; one puff per week slid over; three Zs
  per nap; every landing still lights a top and pops a coin.
- Theme: presets load; overrides merge; every invalid input rejected; CLI reads `--theme`
  and the working-folder `theme.toml`; repo `theme.toml` equals the default preset.
- Visual: browser check of a long gap (slide, nap with Zs, hop up) in both themes and both
  presets.

## Out of scope

- Crying (option offered, not chosen).
- Colour settings for the hero (stay in `character.toml`).
- Changing the profile README repo (separate one-line follow-up).
