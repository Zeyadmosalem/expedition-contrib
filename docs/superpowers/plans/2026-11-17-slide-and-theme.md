# Slide & Nap + Theme Colours Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Empty weeks become hop down → slide (→ nap on long gaps) → hop up instead of tile-to-tile floor hops, and all scene colours come from a `theme.toml` with a crimson default that matches the profile README.

**Architecture:** `theme.py` (new) owns presets and `theme.toml` parsing; `render.py` takes a palette instead of hard-coded colours. `route.py` emits a sequence of moves (`Hop`, `Slide`, `Nap`) instead of one hop per week; `pixels.py` gains slide/sleep poses, a "Z" and a dust puff; `render.py` animates the new moves.

**Tech Stack:** Python 3.11+ standard library (`tomllib`), `unittest`, hand-written SVG + CSS animation.

**Spec:** `docs/superpowers/specs/2026-11-17-slide-and-theme-design.md`

## Global Constraints

- Generator uses only the Python standard library; Pillow is needed only to read a picture head.
- Animation is CSS only: no `<script>`, no `on*=` attributes (plays inside GitHub's `<img>` sandbox).
- Output filenames stay `expedition-contrib.svg` (light) and `expedition-contrib-dark.svg` (dark).
- Reduced motion (`prefers-reduced-motion: reduce`) gets a still frame: hero standing on the catwalk, blocks unlit, flag and LEVEL CLEAR shown; coins, puffs and Zs hidden.
- Isometric geometry unchanged: `tile_xy(w, d) = ((w + d) * 8, (w - d) * 4)`, `HEIGHTS = (2, 4, 7, 10, 14)`.
- New timing constants (spec): `SLIDE_PER_WEEK = 0.12`, `NAP = 1.2`, `NAP_MIN = 3`; `PAUSE = 0.06` after every move.
- Default preset `crimson` colours exactly as the spec's table; `cyan` = the previous `render.THEMES` values.
- Run tests from the repo root: `python -m unittest discover -s tests -v`.
- Never run `sed` or other bulk rewrites over the repo; never touch `.superpowers/` (except your report), `docs/` or `dist/`.
- End every commit message with the Co-Authored-By line your own harness attribution instructions specify.
- Work happens on branch `slide-and-theme` in `C:\Users\DELL\Desktop\Projects\expedition-contrib` (Git Bash path `/c/Users/DELL/Desktop/Projects/expedition-contrib`).

---

### Task 1: `theme.py` presets and `theme.toml`

**Files:**
- Create: `contrib_hopper/theme.py`, `theme.toml`
- Test: `tests/test_theme.py`

**Interfaces:**
- Produces (used by Task 2):
  - `KEYS = ('floor', 'catwalk', 'lamp', 'levels', 'trim', 'text', 'sub', 'lit', 'flag')`, `THEMES = ('dark', 'light')`, `DEFAULT_PRESET = 'crimson'`, `PRESETS: dict[str, dict[str, dict]]`
  - `palettes(preset: str = DEFAULT_PRESET) -> dict[str, dict]` — fresh copies `{'dark': {...}, 'light': {...}}`; colours are RGB tuples, `levels` a list of four tuples. Raises `ValueError` for an unknown preset.
  - `from_dict(data: dict) -> dict[str, dict]`, `load(path: str | Path) -> dict[str, dict]`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_theme.py`:

```python
"""Tests for scene colours: presets and theme.toml (contrib_hopper.theme)."""
from __future__ import annotations

import unittest
from pathlib import Path

from contrib_hopper import theme as TH

REPO = Path(__file__).resolve().parent.parent


def rgb(h: str) -> tuple:
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


class PresetTests(unittest.TestCase):
    def test_default_preset_is_crimson_like_the_profile(self):
        self.assertEqual(TH.DEFAULT_PRESET, 'crimson')
        dark = TH.palettes()['dark']
        self.assertEqual(dark['levels'], [rgb('#5a1422'), rgb('#961a2a'), rgb('#d12a3c'), rgb('#ef4e5c')])
        self.assertEqual(dark['text'], rgb('#ef4e5c'))
        light = TH.palettes()['light']
        self.assertEqual(light['levels'], [rgb('#f4a7ae'), rgb('#ef4e5c'), rgb('#d12a3c'), rgb('#961a2a')])
        self.assertEqual(light['text'], rgb('#400e18'))

    def test_cyan_preset_is_the_original_look(self):
        cyan = TH.palettes('cyan')
        self.assertEqual(cyan['dark']['floor'], (24, 28, 46))
        self.assertEqual(cyan['dark']['levels'][3], (118, 236, 240))
        self.assertEqual(cyan['light']['floor'], (222, 228, 238))
        self.assertEqual(cyan['light']['catwalk'], (196, 202, 218))

    def test_every_preset_is_complete_and_ordered(self):
        for name in TH.PRESETS:
            pal = TH.palettes(name)
            self.assertEqual(list(pal), ['dark', 'light'])
            for theme in TH.THEMES:
                self.assertEqual(set(pal[theme]), set(TH.KEYS), (name, theme))
                self.assertEqual(len(pal[theme]['levels']), 4)
            dark = [sum(c) for c in pal['dark']['levels']]
            light = [sum(c) for c in pal['light']['levels']]
            self.assertEqual(dark, sorted(dark), name)                   # brighter when busier
            self.assertEqual(light, sorted(light, reverse=True), name)   # darker when busier

    def test_palettes_are_copies(self):
        pal = TH.palettes()
        pal['dark']['levels'][0] = (0, 0, 0)
        pal['dark']['floor'] = (1, 2, 3)
        self.assertEqual(TH.palettes()['dark']['levels'][0], rgb('#5a1422'))
        self.assertEqual(TH.palettes()['dark']['floor'], rgb('#160c10'))


class FileTests(unittest.TestCase):
    def test_empty_settings_mean_the_default_preset(self):
        self.assertEqual(TH.from_dict({}), TH.palettes())

    def test_repo_theme_toml_is_the_default(self):
        self.assertEqual(TH.load(REPO / 'theme.toml'), TH.palettes())

    def test_overrides_merge_on_top_of_the_preset(self):
        pal = TH.from_dict({'preset': 'cyan', 'dark': {
            'text': '#ffffff', 'levels': ['#010101', '#020202', '030303', '#040404']}})
        cyan = TH.palettes('cyan')
        self.assertEqual(pal['dark']['text'], (255, 255, 255))
        self.assertEqual(pal['dark']['levels'], [(1, 1, 1), (2, 2, 2), (3, 3, 3), (4, 4, 4)])
        self.assertEqual(pal['dark']['floor'], cyan['dark']['floor'])
        self.assertEqual(pal['light'], cyan['light'])

    def test_bad_settings_are_rejected(self):
        bad = [
            ({'colour': 'red'}, 'unknown theme setting'),
            ({'preset': 'neon'}, 'unknown theme preset'),
            ({'preset': 3}, 'preset'),
            ({'dark': 'red'}, r'\[dark\] must be a table'),
            ({'dark': {'sky': '#000000'}}, r'unknown colour\(s\) in \[dark\]'),
            ({'light': {'text': 'blue'}}, 'hex'),
            ({'light': {'text': '#12345'}}, 'hex'),
            ({'dark': {'levels': ['#000000'] * 3}}, 'four colours'),
            ({'dark': {'levels': '#000000'}}, 'four colours'),
        ]
        for data, message in bad:
            with self.subTest(data=data):
                with self.assertRaisesRegex(ValueError, message):
                    TH.from_dict(data)


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m unittest tests.test_theme -v`
Expected: ERROR `ImportError: cannot import name 'theme' from 'contrib_hopper'`

- [ ] **Step 3: Write `contrib_hopper/theme.py`**

```python
"""Scene colours for the animation: presets plus theme.toml overrides.

theme.toml (in the repo root) picks a preset and can override any colour for
GitHub's dark or light theme:

    preset = "crimson"          # or "cyan"
    [dark]
    levels = ["#5a1422", "#961a2a", "#d12a3c", "#ef4e5c"]   # quiet -> busiest
    [light]
    text = "#400e18"

Colours are hex codes. Anything left out comes from the preset.
"""
from __future__ import annotations

import re
import tomllib
from pathlib import Path

KEYS = ('floor', 'catwalk', 'lamp', 'levels', 'trim', 'text', 'sub', 'lit', 'flag')
THEMES = ('dark', 'light')
DEFAULT_PRESET = 'crimson'


def _rgb(value: str) -> tuple:
    value = value.strip().lstrip('#')
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def _palette(**colors) -> dict:
    return {k: [_rgb(c) for c in v] if k == 'levels' else _rgb(v) for k, v in colors.items()}


PRESETS = {
    # Matches the profile README: #EF4E5C, #D12A3C, #961A2A, #400E18 on near-black.
    'crimson': {
        'dark': _palette(floor='#160c10', catwalk='#2c161e', lamp='#ef4e5c',
                         levels=['#5a1422', '#961a2a', '#d12a3c', '#ef4e5c'],
                         trim='#ff8a94', text='#ef4e5c', sub='#9a6a72', lit='#ffd166',
                         flag='#ffe3e6'),
        'light': _palette(floor='#f2e4e7', catwalk='#e2ced4', lamp='#d12a3c',
                          levels=['#f4a7ae', '#ef4e5c', '#d12a3c', '#961a2a'],
                          trim='#ffd0d4', text='#400e18', sub='#8a5a62', lit='#ffb703',
                          flag='#400e18'),
    },
    # The original Expedition look.
    'cyan': {
        'dark': {'floor': (24, 28, 46), 'catwalk': (40, 44, 66), 'lamp': (90, 200, 220),
                 'levels': [(38, 64, 96), (40, 108, 140), (48, 164, 190), (118, 236, 240)],
                 'trim': (90, 200, 220), 'text': (150, 226, 236), 'sub': (104, 124, 158),
                 'lit': (255, 214, 92), 'flag': (240, 80, 90)},
        'light': {'floor': (222, 228, 238), 'catwalk': (196, 202, 218), 'lamp': (40, 150, 190),
                  'levels': [(160, 212, 230), (92, 182, 212), (40, 140, 182), (20, 92, 150)],
                  'trim': (150, 236, 255), 'text': (24, 44, 78), 'sub': (96, 108, 136),
                  'lit': (255, 190, 50), 'flag': (222, 52, 66)},
    },
}


def palettes(preset: str = DEFAULT_PRESET) -> dict:
    """Fresh copies of a preset's dark and light palettes."""
    if preset not in PRESETS:
        raise ValueError(f'unknown theme preset {preset!r} (expected {", ".join(sorted(PRESETS))})')
    return {name: {k: list(v) if k == 'levels' else v for k, v in pal.items()}
            for name, pal in PRESETS[preset].items()}


def _color(value, key: str) -> tuple:
    if not isinstance(value, str) or not re.fullmatch(r'#?[0-9a-fA-F]{6}', value.strip()):
        raise ValueError(f'theme colour {key!r} must be a hex code like "#d12a3c", got {value!r}')
    return _rgb(value)


def from_dict(data: dict) -> dict:
    """Palettes for both themes from parsed theme.toml data."""
    unknown = set(data) - {'preset', *THEMES}
    if unknown:
        raise ValueError(f'unknown theme setting(s): {", ".join(sorted(unknown))} '
                         f'(expected preset, dark, light)')
    preset = data.get('preset', DEFAULT_PRESET)
    if not isinstance(preset, str):
        raise ValueError(f'theme "preset" must be a name like "crimson", got {preset!r}')
    result = palettes(preset)
    for name in THEMES:
        table = data.get(name, {})
        if not isinstance(table, dict):
            raise ValueError(f'theme [{name}] must be a table of colours')
        bad = set(table) - set(KEYS)
        if bad:
            raise ValueError(f'unknown colour(s) in [{name}]: {", ".join(sorted(bad))} '
                             f'(expected {", ".join(KEYS)})')
        for key, value in table.items():
            if key == 'levels':
                if not isinstance(value, list) or len(value) != 4:
                    raise ValueError(f'[{name}] levels must be a list of four colours, quietest to busiest')
                result[name][key] = [_color(c, f'{name}.levels') for c in value]
            else:
                result[name][key] = _color(value, f'{name}.{key}')
    return result


def load(path: str | Path) -> dict:
    with open(path, 'rb') as f:
        return from_dict(tomllib.load(f))
```

- [ ] **Step 4: Create `theme.toml` in the repo root**

```toml
# Colours of the contribution animation. Edit, commit, and the next workflow
# run (on push, daily, or "Run workflow" in the Actions tab) redraws it.

# "crimson" matches the profile README; "cyan" is the original Expedition look.
preset = "crimson"

# Optional: override any colour for GitHub's dark or light theme. Anything left
# out comes from the preset. Keys: floor, catwalk, lamp, levels (four colours,
# quietest to busiest), trim, text, sub, lit, flag.
[dark]
# levels = ["#5a1422", "#961a2a", "#d12a3c", "#ef4e5c"]
# floor = "#160c10"

[light]
# text = "#400e18"
```

- [ ] **Step 5: Run the tests**

Run: `python -m unittest tests.test_theme -v` → `Ran 8 tests ... OK`
Run: `python -m unittest discover -s tests -v` → `Ran 56 tests ... OK`

- [ ] **Step 6: Commit**

```bash
git add contrib_hopper/theme.py theme.toml tests/test_theme.py
git commit -m "Add theme presets and theme.toml"   # plus your Co-Authored-By line
```

---

### Task 2: Render from a palette; `--theme` CLI; workflow trigger

**Files:**
- Modify: `contrib_hopper/render.py` (imports, `THEMES`, `render()` signature, the `th['walk']` uses), `contrib_hopper/__main__.py`, `.github/workflows/update.yml`
- Test: `tests/test_theme.py` (new class)

**Interfaces:**
- Consumes: `theme.palettes()`, `theme.load()` (Task 1).
- Produces: `render(cal, theme='dark', character=None, palette=None) -> str`; `render.THEMES == theme.palettes()`; CLI flag `--theme FILE`, `DEFAULT_THEME = 'theme.toml'` in `__main__`.

- [ ] **Step 1: Write the failing tests**

In `tests/test_theme.py` add these imports at the top: `import os`, `import tempfile`, `import xml.etree.ElementTree as ET`, `from unittest import mock`, `from contrib_hopper import contributions, render as R`, `from contrib_hopper.__main__ import OUTPUTS, main`; and add `FIXTURE = Path(__file__).parent / 'fixtures' / 'calendar.json'` next to `REPO`. Then add this class before the `if __name__` block:

```python
class RenderThemeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cal = contributions.load(str(FIXTURE), 'tester')

    def test_default_render_is_crimson(self):
        self.assertEqual(R.THEMES, TH.palettes())
        self.assertIn('#ef4e5c', R.render(self.cal, 'dark'))

    def test_render_uses_the_given_palette(self):
        svg = R.render(self.cal, 'dark', palette=TH.palettes('cyan')['dark'])
        self.assertIn('#76ecf0', svg)          # cyan busiest level
        self.assertNotIn('#ef4e5c', svg)       # no crimson

    def test_cli_reads_a_theme_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / 'colours.toml'
            cfg.write_text('preset = "cyan"\n', encoding='utf-8')
            with mock.patch('sys.stdout'):
                main(['--user', 'tester', '--input', str(FIXTURE), '--out', tmp, '--theme', str(cfg)])
            dark = (Path(tmp) / OUTPUTS['dark']).read_text(encoding='utf-8')
            self.assertIn('#76ecf0', dark)
            ET.fromstring(dark)

    def test_cli_uses_theme_toml_in_the_working_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, 'theme.toml').write_text(
                '[dark]\nlevels = ["#111111", "#222222", "#333333", "#123456"]\n', encoding='utf-8')
            cwd = os.getcwd()
            try:
                os.chdir(tmp)
                with mock.patch('sys.stdout'):
                    main(['--user', 'tester', '--input', str(FIXTURE), '--out', 'out'])
                dark = Path(tmp, 'out', OUTPUTS['dark']).read_text(encoding='utf-8')
                light = Path(tmp, 'out', OUTPUTS['light']).read_text(encoding='utf-8')
            finally:
                os.chdir(cwd)
            self.assertIn('#123456', dark)
            self.assertNotIn('#123456', light)

    def test_cli_rejects_a_bad_theme_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / 'bad.toml'
            cfg.write_text('preset = "neon"\n', encoding='utf-8')
            with mock.patch('sys.stdout'), self.assertRaisesRegex(ValueError, 'unknown theme preset'):
                main(['--user', 'tester', '--input', str(FIXTURE), '--out', tmp, '--theme', str(cfg)])
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python -m unittest tests.test_theme -v`
Expected: failures/errors in `RenderThemeTests` (`R.THEMES` differs; `render() got an unexpected keyword argument 'palette'`; `unrecognized arguments: --theme`).

- [ ] **Step 3: Change `contrib_hopper/render.py`**

Add the import `from .theme import palettes` directly below the `from .route import ...` line.

Replace the whole `THEMES = { ... }` dict with:

```python
THEMES = palettes()              # default preset's {'dark': ..., 'light': ...}; see theme.py
```

Replace

```python
def render(cal: Calendar, theme: str = 'dark', character: Character | None = None) -> str:
    th = THEMES[theme]
```

with

```python
def render(cal: Calendar, theme: str = 'dark', character: Character | None = None,
           palette: dict | None = None) -> str:
    """palette: one theme's colours (see theme.py); None = the default preset's `theme`."""
    th = palette if palette is not None else THEMES[theme]
```

In the sprites section, the `walk` and `lamp` sprites each use `th['walk']` three times; change all six to `th['catwalk']`.

- [ ] **Step 4: Change `contrib_hopper/__main__.py`**

Replace `from . import character, contributions` with `from . import character, contributions, theme as colours`.
Below `DEFAULT_CHARACTER = 'character.toml'` add `DEFAULT_THEME = 'theme.toml'`.
After the `--character` argument add:

```python
    ap.add_argument('--theme', help='colour settings file (default: theme.toml if it exists)')
```

After the block that sets `hero`, add:

```python
    if args.theme:
        palettes = colours.load(args.theme)                 # named explicitly: must exist
    elif Path(DEFAULT_THEME).is_file():
        palettes = colours.load(DEFAULT_THEME)
    else:
        palettes = colours.palettes()
```

Replace `svg = render(cal, theme, hero)` with `svg = render(cal, theme, hero, palettes[theme])`.

- [ ] **Step 5: Add `theme.toml` to the workflow trigger**

In `.github/workflows/update.yml`, under `paths:`, directly after the line `      - "character.toml"` add the line `      - "theme.toml"`.

- [ ] **Step 6: Run the tests**

Run: `python -m unittest discover -s tests -v` → `Ran 61 tests ... OK`

- [ ] **Step 7: Commit**

```bash
git add contrib_hopper/render.py contrib_hopper/__main__.py .github/workflows/update.yml tests/test_theme.py
git commit -m "Render with theme palettes and add --theme"   # plus your Co-Authored-By line
```

---

### Task 3: Route moves — hop down, slide, nap

**Files:**
- Modify: `contrib_hopper/route.py` (docstring, constants, new dataclasses, `Timeline`, `plan`)
- Test: `tests/test_route.py`, `tests/test_character.py` (one assertion)

**Interfaces:**
- Produces (used by Task 5):
  - `SLIDE_PER_WEEK = 0.12`, `NAP = 1.2`, `NAP_MIN = 3`
  - `Slide(from_week: int, from_weekday: int, week: int, weekday: int, start: float, end: float)` (frozen dataclass)
  - `Nap(week: int, weekday: int, start: float, end: float)` (frozen dataclass)
  - `Timeline(moves: tuple, hops: tuple[Hop, ...], victory: Hop, flag_day: tuple[int, int, int], hop_end: float, reset_start: float, period: float)` — `moves` is every `Hop`/`Slide`/`Nap` in time order (victory excluded); `hops` is the `Hop`s of `moves`; `hop_end` is the end of the last move.
  - `Hop` unchanged.

- [ ] **Step 1: Update and add tests**

In `tests/test_route.py`, add this helper below `make_cal`:

```python
def moves_of(tl) -> list:
    """Moves as tuples: ('hop', week, weekday, level), ('slide', from_w, from_d, w, d), ('nap', w, d)."""
    out = []
    for m in tl.moves:
        if isinstance(m, RT.Hop):
            out.append(('hop', m.week, m.weekday, m.level))
        elif isinstance(m, RT.Slide):
            out.append(('slide', m.from_week, m.from_weekday, m.week, m.weekday))
        else:
            out.append(('nap', m.week, m.weekday))
    return out
```

and this constant below `TIES`:

```python
# blocks in weeks 0, 2, 6, 7; gaps: week 1 (k=1), weeks 3-5 (k=3, nap at 4), weeks 8-9 (k=2, at the end)
GAPS = make_cal({(0, 2): 2, (2, 3): 1, (6, 1): 4, (7, 1): 1}, weeks=10)
```

Delete the whole `test_empty_calendar_hops_the_floor` method and the whole `test_fixture_year` method, and add these methods to `RouteTests`:

```python
    def test_gaps_hop_down_slide_nap_and_hop_up(self):
        self.assertEqual(moves_of(RT.plan(GAPS)), [
            ('hop', 0, 2, 2),
            ('hop', 1, 2, 0),                       # one-week gap: hop down ...
            ('hop', 2, 3, 1),                       # ... and straight back up
            ('hop', 3, 3, 0),                       # three-week gap: hop down,
            ('slide', 3, 3, 4, 3),                  # slide to the middle,
            ('nap', 4, 3),                          # nap,
            ('slide', 4, 3, 5, 3),                  # slide to the end,
            ('hop', 6, 1, 4),                       # hop up
            ('hop', 7, 1, 1),
            ('hop', 8, 1, 0),                       # two-week gap at the end: hop down, slide
            ('slide', 8, 1, 9, 1),
        ])
        v = RT.plan(GAPS).victory
        self.assertEqual((v.week, v.weekday, v.level), (9, 1, 0))   # victory hop on the floor

    def test_moves_are_back_to_back(self):
        tl = RT.plan(GAPS)
        start = lambda m: m.takeoff if isinstance(m, RT.Hop) else m.start
        end = lambda m: m.land if isinstance(m, RT.Hop) else m.end
        self.assertAlmostEqual(start(tl.moves[0]), RT.INTRO)
        for a, b in zip(tl.moves, tl.moves[1:]):
            self.assertLess(start(a), end(a))
            self.assertAlmostEqual(start(b), end(a) + RT.PAUSE)
        self.assertAlmostEqual(tl.hop_end, end(tl.moves[-1]))
        self.assertAlmostEqual(tl.victory.takeoff, tl.hop_end + RT.PAUSE)
        self.assertEqual(tl.hops, tuple(m for m in tl.moves if isinstance(m, RT.Hop)))

    def test_slide_and_nap_durations(self):
        for m in RT.plan(GAPS).moves:
            if isinstance(m, RT.Slide):
                self.assertAlmostEqual(m.end - m.start, RT.SLIDE_PER_WEEK * (m.week - m.from_week))
            elif isinstance(m, RT.Nap):
                self.assertAlmostEqual(m.end - m.start, RT.NAP)

    def test_no_floor_to_floor_hops(self):
        for tl in (RT.plan(GAPS), RT.plan(TIES), RT.plan(make_cal({}, weeks=6))):
            prev = None
            for m in tl.moves:
                if isinstance(m, RT.Hop) and m.level == 0:
                    self.assertFalse(isinstance(prev, RT.Hop) and prev.level == 0, moves_of(tl))
                    self.assertNotIsInstance(prev, (RT.Slide, RT.Nap))
                prev = m

    def test_empty_year_slides_and_naps(self):
        tl = RT.plan(make_cal({}, weeks=5))
        self.assertEqual(moves_of(tl), [('hop', 0, 3, 0), ('slide', 0, 3, 2, 3), ('nap', 2, 3),
                                        ('slide', 2, 3, 4, 3)])
        self.assertAlmostEqual(tl.hops[0].land - tl.hops[0].takeoff, RT.FLOOR_HOP)   # off the catwalk
        self.assertEqual(tl.flag_day, (4, 3, 0))

    def test_gap_at_the_start(self):
        tl = RT.plan(make_cal({(2, 5): 1}, weeks=3))
        self.assertEqual(moves_of(tl), [('hop', 0, 3, 0), ('slide', 0, 3, 1, 3), ('hop', 2, 5, 1)])

    def test_slide_ends_on_a_weekday_that_exists(self):
        days = [Day(f'2026-w00-{d}', 0, 0, 0, d) for d in range(7)]
        days += [Day(f'2026-w01-{d}', 0, 0, 1, d) for d in range(2)]     # partial last week: Sun, Mon
        tl = RT.plan(Calendar('t', 0, tuple(days)))
        self.assertEqual(moves_of(tl), [('hop', 0, 3, 0), ('slide', 0, 3, 1, 1)])

    def test_fixture_year(self):
        cal = contributions.parse(json.loads(FIXTURE.read_text(encoding='utf-8')), 'tester')
        tl = RT.plan(cal)
        busy = {d.week for d in cal.active}
        landed = [h for h in tl.hops if h.level > 0]
        self.assertEqual([h.week for h in landed], sorted(busy))       # one block landing per busy week
        for h in landed:
            week = [d for d in cal.active if d.week == h.week]
            self.assertEqual(h.level, max(d.level for d in week))
            self.assertIn((h.weekday, h.level), {(d.weekday, d.level) for d in week})
        visited = set()
        for m in tl.moves:                                              # every week is crossed
            if isinstance(m, RT.Slide):
                visited.update(range(m.from_week, m.week + 1))
            elif isinstance(m, RT.Hop):
                visited.add(m.week)
        self.assertEqual(visited, set(range(cal.weeks)))
        self.assertGreater(tl.period, 10)
        self.assertLess(tl.period, 40)
```

In `tests/test_character.py`, in `test_picture_head_in_the_animation`, replace the line

```python
        self.assertEqual(len(R.plan(self.cal).hops), self.cal.weeks)   # still one hop per week
```

with

```python
        landed = {h.week for h in R.plan(self.cal).hops if h.level > 0}
        self.assertEqual(landed, {d.week for d in self.cal.active})       # still lands on every busy week
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python -m unittest tests.test_route -v`
Expected: errors such as `AttributeError: 'Timeline' object has no attribute 'moves'` / `module 'contrib_hopper.route' has no attribute 'Slide'`.

- [ ] **Step 3: Change `contrib_hopper/route.py`**

Replace the module docstring with:

```python
"""Route and timing for the Block Hopper animation (pure maths, no SVG).

The hero starts on the catwalk in front of week 0 and works through the year:
onto each busy week's tallest block with a hop; into a run of empty weeks with
one hop down, then a slide along the floor (with a nap halfway when the run is
NAP_MIN weeks or longer) and a hop back up. After the last week it does a
victory hop in place. All times are seconds into one loop of the animation.
"""
```

Below the line `APEX, APEX_PER_LEVEL, VICTORY_APEX = 10, 2, 14   # px` add:

```python
SLIDE_PER_WEEK = 0.12             # sliding along the floor, seconds per week
NAP, NAP_MIN = 1.2, 3             # nap length; gaps this many weeks or longer get a nap
```

Below the `Hop` dataclass add:

```python
@dataclass(frozen=True)
class Slide:
    from_week: int
    from_weekday: int
    week: int
    weekday: int
    start: float
    end: float


@dataclass(frozen=True)
class Nap:
    week: int
    weekday: int
    start: float
    end: float
```

Replace the whole `Timeline` dataclass with:

```python
@dataclass(frozen=True)
class Timeline:
    moves: tuple      # every Hop / Slide / Nap in time order (victory hop excluded)
    hops: tuple       # the Hops of `moves`, in order
    victory: Hop      # the hop in place after the last week
    flag_day: tuple   # (week, weekday, level) the flag pops up on
    hop_end: float    # end of the last move: flag and LEVEL CLEAR appear
    reset_start: float  # lit tops start fading out
    period: float     # loop length
```

Replace the whole `plan` function with:

```python
def plan(cal: Calendar) -> Timeline:
    if not cal.days:
        raise ValueError('the contribution calendar has no days')
    by_week: dict[int, list[Day]] = {}
    for day in cal.days:
        by_week.setdefault(day.week, []).append(day)

    def busy(w: int) -> list[Day]:
        return [d for d in by_week.get(w, []) if d.count > 0]

    def weekdays(w: int, fallback: int) -> list[int]:
        return [d.weekday for d in by_week.get(w, [])] or [fallback]

    moves: list = []
    t, level, week, weekday = INTRO, 0, START_W, NO_LANDING

    def hop_to(w: int, d: int, lv: int) -> None:
        nonlocal t, level, week, weekday
        dur = FLOOR_HOP if lv == 0 and level == 0 else HOP + HOP_PER_LEVEL * abs(lv - level)
        apex = max(lift(level), lift(lv)) + APEX + APEX_PER_LEVEL * max(0, lv - level)
        moves.append(Hop(w, d, lv, t, t + dur, apex))
        t += dur + PAUSE
        level, week, weekday = lv, w, d

    def slide_to(w: int) -> None:
        nonlocal t, week, weekday
        d = _nearest(weekdays(w, weekday), weekday)
        dur = SLIDE_PER_WEEK * (w - week)
        moves.append(Slide(week, weekday, w, d, t, t + dur))
        t += dur + PAUSE
        week, weekday = w, d

    def nap() -> None:
        nonlocal t
        moves.append(Nap(week, weekday, t, t + NAP))
        t += NAP + PAUSE

    w = 0
    while w < cal.weeks:
        days = busy(w)
        if days:
            lv = max(d.level for d in days)
            hop_to(w, _nearest([d.weekday for d in days if d.level == lv], weekday), lv)
            w += 1
            continue
        b = w                                   # the gap is weeks w..b
        while b + 1 < cal.weeks and not busy(b + 1):
            b += 1
        hop_to(w, _nearest(weekdays(w, weekday), weekday), 0)
        if b - w + 1 >= NAP_MIN:
            slide_to((w + b) // 2)
            nap()
            slide_to(b)
        elif b > w:
            slide_to(b)
        w = b + 1

    last = moves[-1]
    hop_end = last.land if isinstance(last, Hop) else last.end
    victory = Hop(week, weekday, level, t, t + VICTORY, lift(level) + VICTORY_APEX)
    reset_start = victory.land + OUTRO + HOLD
    if cal.active:
        best = max(cal.active, key=lambda d: (d.count, d.date))
        flag_day = (best.week, best.weekday, best.level)
    else:
        flag_day = (cal.weeks - 1, _nearest(weekdays(cal.weeks - 1, NO_LANDING), NO_LANDING), 0)
    hops = tuple(m for m in moves if isinstance(m, Hop))
    return Timeline(tuple(moves), hops, victory, flag_day, hop_end, reset_start, reset_start + FADE)
```

- [ ] **Step 4: Run the tests**

Run: `python -m unittest tests.test_route -v` → `Ran 16 tests ... OK`
Run: `python -m unittest discover -s tests -v` → `Ran 67 tests ... OK` (the renderer still draws only `tl.hops` until Task 5).

- [ ] **Step 5: Commit**

```bash
git add contrib_hopper/route.py tests/test_route.py tests/test_character.py
git commit -m "Plan empty weeks as hop down, slide and nap"   # plus your Co-Authored-By line
```

---

### Task 4: Slide and sleep poses, Z and dust puff sprites

**Files:**
- Modify: `contrib_hopper/pixels.py`, `contrib_hopper/render.py` (one line: how it reads `hero_poses`)
- Test: `tests/test_pixels.py`

**Interfaces:**
- Produces (used by Task 5):
  - `Poses(NamedTuple)`: `stand, jump, slide, sleep` (all `Raster`); `hero_poses(colors=COLORS, head=None) -> Poses`. `stand`, `jump`, `slide` share a size; `sleep` is `rotate_cw(stand)`.
  - `rotate_cw(r: Raster) -> Raster` — pixel `(x, y)` moves to `(r.h - 1 - y, x)`; size becomes `(r.h, r.w)`.
  - `zee(color) -> Raster` (6×6, outlined "Z"), `puff(color) -> Raster` (4×3, 8 pixels, no outline).

- [ ] **Step 1: Write the failing tests**

In `tests/test_pixels.py`, in `test_stand_and_jump_poses` replace the line

```python
        stand, jump = px.hero_poses()
```

with

```python
        poses = px.hero_poses()
        stand, jump = poses.stand, poses.jump
```

and add these methods to `SpriteTests`:

```python
    def test_slide_pose_is_a_wide_low_stance(self):
        poses = px.hero_poses()
        stand, slide = poses.stand, poses.slide
        self.assertEqual((slide.w, slide.h), (stand.w, stand.h))
        feet = lambda r: [(x, y) for (x, y), c in r.px.items() if c == px.COLORS['b']]
        self.assertEqual(max(y for x, y in feet(slide)), slide.h - 1)            # feet on the floor
        self.assertLess(min(x for x, y in feet(slide)), min(x for x, y in feet(stand)))
        self.assertGreater(max(x for x, y in feet(slide)), max(x for x, y in feet(stand)))

    def test_sleep_pose_is_the_stand_pose_lying_down(self):
        poses = px.hero_poses()
        stand, sleep = poses.stand, poses.sleep
        self.assertEqual((sleep.w, sleep.h), (stand.h, stand.w))
        self.assertEqual(sorted(sleep.px.values()), sorted(stand.px.values()))
        r = stand
        for _ in range(4):
            r = px.rotate_cw(r)
        self.assertEqual(r.px, stand.px)                                         # four turns = start
        self.assertEqual(px.rotate_cw(stand).px, sleep.px)

    def test_zee_and_dust_puff(self):
        c = (240, 220, 230)
        z = px.zee(c)
        self.assertEqual((z.w, z.h), (6, 6))
        self.assertIn(c, z.px.values())
        self.assertIn(px.INK, z.px.values())
        p = px.puff(c)
        self.assertEqual((p.w, p.h), (4, 3))
        self.assertEqual(len(p.px), 8)
        self.assertEqual(set(p.px.values()), {c})
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python -m unittest tests.test_pixels -v`
Expected: errors such as `AttributeError: 'tuple' object has no attribute 'stand'`.

- [ ] **Step 3: Change `contrib_hopper/pixels.py`**

Add `from typing import NamedTuple` below `from __future__ import annotations`.

Directly after the closing `]` of `JUMP_LEGS`, add:

```python
# Sliding along the floor: wide, low surf stance, feet on the bottom row
SLIDE_LEGS = [
    "...kkkk..kkkk...",
    "..kkk......kkk..",
    ".kkk........kkk.",
    "bbb..........bbb",
]
```

Directly after the `FLAG` definition, add:

```python
# Napping: a "Z" floats up; sliding: a puff of dust at each tile
ZEE = ["ZZZZ", "..Z.", ".Z..", "ZZZZ"]
PUFF = [".dd.", "dddd", ".dd."]
```

Replace the whole `hero_poses` function with:

```python
class Poses(NamedTuple):
    stand: Raster
    jump: Raster
    slide: Raster
    sleep: Raster


def rotate_cw(r: Raster) -> Raster:
    """r turned 90 degrees clockwise: pixel (x, y) moves to (r.h - 1 - y, x)."""
    out = Raster(r.h, r.w)
    for (x, y), c in r.px.items():
        out.set(r.h - 1 - y, x, c)
    return out


def hero_poses(colors: dict = COLORS, head: Raster | None = None) -> Poses:
    """stand, jump and slide share one size so they swap in place; sleep is stand lying down."""
    head = head or grid(SKULL, outline=True)
    stand = _hero(colors, head, STAND_LEGS)
    return Poses(stand, _hero(colors, head, JUMP_LEGS), _hero(colors, head, SLIDE_LEGS), rotate_cw(stand))


def zee(color: Color) -> Raster:
    return grid(ZEE, {'Z': tuple(color)}, outline=True)


def puff(color: Color) -> Raster:
    return grid(PUFF, {'d': tuple(color)})
```

- [ ] **Step 4: Keep `render.py` working**

In `contrib_hopper/render.py` replace

```python
    stand, jump = px.hero_poses(character.colors(), character.head_raster())
```

with

```python
    poses = px.hero_poses(character.colors(), character.head_raster())
    stand, jump = poses.stand, poses.jump
```

- [ ] **Step 5: Run the tests**

Run: `python -m unittest discover -s tests -v` → `Ran 70 tests ... OK`

- [ ] **Step 6: Commit**

```bash
git add contrib_hopper/pixels.py contrib_hopper/render.py tests/test_pixels.py
git commit -m "Add slide and sleep poses, Z and dust puff sprites"   # plus your Co-Authored-By line
```

---

### Task 5: Animate slides, naps, dust and Zs

**Files:**
- Modify: `contrib_hopper/render.py`
- Test: `tests/test_hopper.py`

**Interfaces:**
- Consumes: `Hop`, `Slide`, `Nap`, `Timeline.moves` (Task 3); `Poses`, `zee`, `puff` (Task 4); palette keys `text`, `sub` (Task 1).
- Produces: SVG where the hero group has pose classes `ps`, `pj`, `pl`, `pz`; the fx layer has `<use class="x pu" ...>` dust puffs and `<use class="x zq" ...>` Zs, each with `style="--t:S.SSSs"`.

- [ ] **Step 1: Write the failing tests**

In `tests/test_hopper.py`:

Add the import `from contrib_hopper.contributions import Calendar, Day` and change `from contrib_hopper.route import ground` to `from contrib_hopper.route import LANE_D, START_W, Nap, Slide, ground`.

Below the `with_days` helper add:

```python
def gappy() -> Calendar:
    """Blocks in weeks 0, 2, 6, 7; empty weeks 1, 3-5 (a nap) and 8-9."""
    levels = {(0, 2): 2, (2, 3): 1, (6, 1): 4, (7, 1): 1}
    days = [Day(f'2026-w{w:02d}-{d}', levels.get((w, d), 0) * 3, levels.get((w, d), 0), w, d)
            for w in range(10) for d in range(7)]
    return Calendar('gappy', sum(x.count for x in days), tuple(days))


def pose_track(frames: str) -> list:
    """[(percent, opacity)] from step-timed opacity keyframes."""
    return sorted((float(p), int(o)) for p, o in re.findall(r'([\d.]+)%\{opacity:([01])\}', frames))
```

In `RenderTests.test_hero_reaches_every_apex_and_landing` replace the line

```python
        self.assertEqual(self.keyframes(svg, 'ps').count('opacity:0'), len(self.plan.hops) + 1)
```

with

```python
        self.assertEqual(self.keyframes(svg, 'ps').count('opacity:0'), len(self.plan.moves) + 1)
```

and in `test_hero_uses_the_skull_and_red_chest_light` replace `{'hv', 'hx', 'hy', 'ps', 'pj'}` with `{'hv', 'hx', 'hy', 'ps', 'pj', 'pl', 'pz'}`.

Add this class before `class CliTests`:

```python
class EmptyWeekTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cal = gappy()
        cls.plan = R.plan(cls.cal)
        cls.svg = R.render(cls.cal, 'dark')
        cls.root = ET.fromstring(cls.svg)
        cls.slides = [m for m in cls.plan.moves if isinstance(m, Slide)]
        cls.naps = [m for m in cls.plan.moves if isinstance(m, Nap)]

    def pct(self, t):
        return float(f'{t / self.plan.period * 100:.3f}')

    def keyframes(self, name):
        return re.search(r'@keyframes %s\{(.*?\})\}' % name, self.svg).group(1)

    def test_the_gappy_year_has_slides_and_a_nap(self):
        self.assertEqual(len(self.slides), 3)
        self.assertEqual(len(self.naps), 1)

    def test_exactly_one_pose_is_visible_at_all_times(self):
        tracks = {name: pose_track(self.keyframes(name)) for name in ('ps', 'pj', 'pl', 'pz')}
        times = sorted({p for track in tracks.values() for p, _ in track})

        def at(track, p):
            return [o for q, o in track if q <= p][-1]

        for p in times:
            self.assertEqual(sum(at(tracks[n], p) for n in tracks), 1, p)

    def test_slide_and_sleep_poses_show_during_their_moves(self):
        slide_on = [p for p, o in pose_track(self.keyframes('pl')) if o == 1]
        sleep_on = [p for p, o in pose_track(self.keyframes('pz')) if o == 1]
        self.assertEqual(slide_on, [self.pct(s.start) for s in self.slides])
        self.assertEqual(sleep_on, [self.pct(n.start) for n in self.naps])

    def test_hero_slides_to_the_end_of_each_slide(self):
        hx = self.keyframes('hx')
        sx, sy = ground(START_W, LANE_D)
        for s in self.slides:
            gx, gy = ground(s.week, s.weekday)
            self.assertIn(f'translate({R._num(gx - sx)}px,{R._num(gy - sy)}px)', hx)

    def test_one_dust_puff_per_week_slid_over(self):
        puffs = self.root.find(f"{SVG}g[@id='fx']").findall(f".//{SVG}use[@class='x pu']")
        self.assertEqual(len(puffs), sum(s.week - s.from_week for s in self.slides))

    def test_three_zees_per_nap(self):
        zees = self.root.find(f"{SVG}g[@id='fx']").findall(f".//{SVG}use[@class='x zq']")
        self.assertEqual(len(zees), 3 * len(self.naps))
        starts = sorted(float(re.search(r'--t:([\d.]+)s', z.get('style')).group(1)) for z in zees)
        self.assertGreaterEqual(starts[0], self.naps[0].start)
        self.assertLess(starts[-1], self.naps[0].end)

    def test_landings_still_light_up_and_pop_coins(self):
        landed = [h for h in self.plan.hops if h.level > 0]
        coins = self.root.find(f"{SVG}g[@id='fx']").findall(f".//{SVG}g[@class='x cn']")
        self.assertEqual(len(coins), len(landed))
        self.assertEqual(len(re.findall(r'@keyframes t\d+\{', self.svg)), len(landed))

    def test_reduced_motion_hides_the_extra_poses(self):
        self.assertIn('.pj,.pl,.pz{opacity:0}', self.svg)
        self.assertIn('@media (prefers-reduced-motion:reduce){*{animation:none!important}', self.svg)
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python -m unittest tests.test_hopper -v`
Expected: failures in `EmptyWeekTests` (no `pl`/`pz` keyframes → `AttributeError: 'NoneType' object has no attribute 'group'`) and in the two changed `RenderTests`.

- [ ] **Step 3: Change `contrib_hopper/render.py`**

Replace the import line `from .route import HEIGHTS, INTRO, LANE_D, START_W, ground, lift, plan, tile_xy` with:

```python
from .route import HEIGHTS, INTRO, LANE_D, START_W, Hop, Slide, ground, lift, plan, tile_xy
```

Below `EASE_IN = ...` add:

```python
PUFF_TIME = 0.4                          # dust puff: rise 3 px and fade, seconds
ZEE_TIME, ZEE_GAP, ZEES = 0.9, 0.35, 3   # nap: each Z rises and fades; three, this far apart
POSES = ('ps', 'pj', 'pl', 'pz')         # stand, jump, slide, sleep
```

In the sprites section, after the line that appends `<g id="flag">...`, add:

```python
    defs.append(f'<g id="zz">{px.zee(th["text"]).paths()}</g><g id="pf">{px.puff(th["sub"]).paths()}</g>')
```

Replace the whole hero section — from the comment line that starts `# ---------- hero:` up to and including the `hero_svg = (...)` statement — with:

```python
    # ---------- hero: hx = ground motion, hy = arc, ps/pj/pl/pz = pose ----------
    poses = px.hero_poses(character.colors(), character.head_raster())
    fw, fh = poses.stand.w, poses.stand.h
    zw, zh = poses.sleep.w, poses.sleep.h
    sx, sy = ground(START_W, LANE_D)

    def box(gx, gy, up):
        grow(gx - fw / 2 - 1, gy - up - fh - 1, gx + fw / 2 + 1, gy + 2)

    def move(dx, dy):
        return 'none' if (dx, dy) == (0, 0) else f'translate({_num(dx)}px,{_num(dy)}px)'

    def rise(up):
        return 'none' if up == 0 else f'translateY(-{_num(up)}px)'

    hx, hy = ['0%{transform:none}'], ['0%{transform:none}']
    pose_kf = {name: [f'0%{{opacity:{1 if name == "ps" else 0}}}'] for name in POSES}
    current = 'ps'

    def show(t, name):
        nonlocal current
        if name != current:
            pose_kf[current].append(f'{pct(t)}%{{opacity:0}}')
            pose_kf[name].append(f'{pct(t)}%{{opacity:1}}')
            current = name

    pos, up = (0.0, 0.0), 0
    box(sx, sy, 0)
    for m in (*tl.moves, tl.victory):
        if isinstance(m, Hop):
            gx, gy = ground(m.week, m.weekday)
            nxt = (gx - sx, gy - sy)
            mid = (m.takeoff + m.land) / 2
            hx.append(f'{pct(m.takeoff)}%{{transform:{move(*pos)}}}{pct(m.land)}%{{transform:{move(*nxt)}}}')
            hy.append(f'{pct(m.takeoff)}%{{transform:{rise(up)};animation-timing-function:{EASE_OUT}}}'
                      f'{pct(mid)}%{{transform:{rise(m.apex)};animation-timing-function:{EASE_IN}}}'
                      f'{pct(m.land)}%{{transform:{rise(lift(m.level))}}}')
            show(m.takeoff, 'pj')
            show(m.land, 'ps')
            box(gx, gy, m.apex)
            pos, up = nxt, lift(m.level)
        elif isinstance(m, Slide):
            gx, gy = ground(m.week, m.weekday)
            nxt = (gx - sx, gy - sy)
            hx.append(f'{pct(m.start)}%{{transform:{move(*pos)}}}{pct(m.end)}%{{transform:{move(*nxt)}}}')
            show(m.start, 'pl')
            show(m.end, 'ps')
            weeks = m.week - m.from_week
            for i in range(1, weeks + 1):           # a puff of dust at each tile reached
                f = i / weeks
                dx_, dy_ = ground(m.from_week + f * weeks, m.from_weekday + f * (m.weekday - m.from_weekday))
                fx_svg.append(f'<g transform="translate({_num(dx_ - 2)} {_num(dy_ - 3)})">'
                              f'<use class="x pu" href="#pf" style="--t:{m.start + f * (m.end - m.start):.3f}s"/></g>')
                grow(dx_ - 2, dy_ - 6, dx_ + 2, dy_)
            box(gx, gy, 0)
            pos = nxt
        else:                                       # Nap: hold still, lie down, Zs float up
            show(m.start, 'pz')
            show(m.end, 'ps')
            gx, gy = ground(m.week, m.weekday)
            for i in range(ZEES):
                fx_svg.append(f'<g transform="translate({_num(gx + 4)} {_num(gy - zh - 6)})">'
                              f'<use class="x zq" href="#zz" style="--t:{m.start + .2 + i * ZEE_GAP:.3f}s"/></g>')
            grow(gx + 4, gy - zh - 6 - 12, gx + 4 + 6 + 4, gy)
    hx.append(f'to{{transform:{move(*pos)}}}')
    hy.append(f'to{{transform:{rise(up)}}}')
    hero_svg = (f'<g transform="translate({_num(sx)} {_num(sy)})"><g class="hv"><g class="hx"><g class="hy">'
                f'<g transform="translate({-(fw // 2)} {-fh + 1})">'
                f'<g class="ps">{poses.stand.paths()}</g><g class="pj">{poses.jump.paths()}</g>'
                f'<g class="pl">{poses.slide.paths()}</g></g>'
                f'<g class="pz" transform="translate({-(zw // 2)} {-zh + 1})">{poses.sleep.paths()}</g>'
                f'</g></g></g></g>')
```

(`fx_svg` is created in the coins section earlier in `render()`; keep that order.)

In the shared CSS list, replace the two lines

```python
        f'.ps{{animation:ps {run} steps(1,end) infinite}}@keyframes ps{{{"".join(ps)}}}',
        f'.pj{{opacity:0;animation:pj {run} steps(1,end) infinite}}@keyframes pj{{{"".join(pj)}}}',
```

with

```python
        '.pj,.pl,.pz{opacity:0}',
        *(f'.{n}{{animation:{n} {run} steps(1,end) infinite}}@keyframes {n}{{{"".join(pose_kf[n])}}}'
          for n in POSES),
        '.pu{animation-name:pu}.zq{animation-name:zq}',
        f'@keyframes pu{{0%{{opacity:1;transform:none}}{pct(PUFF_TIME)}%,to{{opacity:0;transform:translateY(-3px)}}}}',
        f'@keyframes zq{{0%{{opacity:1;transform:none}}{pct(ZEE_TIME)}%,to{{opacity:0;transform:translate(4px,-12px)}}}}',
```

In the module docstring replace the sentence `The skull hero hops across the year, one hop per week onto the week's tallest block (route.py works out where and when).` with `The skull hero hops onto each busy week's tallest block, and hops down, slides (and naps on long gaps) across empty weeks (route.py works out where and when).`

- [ ] **Step 4: Run the tests**

Run: `python -m unittest discover -s tests -v` → `Ran 78 tests ... OK`
Smoke: `python -m contrib_hopper --user tester --input tests/fixtures/calendar.json --out "$(mktemp -d)"` prints two files under 200 KB.

- [ ] **Step 5: Commit**

```bash
git add contrib_hopper/render.py tests/test_hopper.py
git commit -m "Animate slides, naps, dust puffs and Zs"   # plus your Co-Authored-By line
```

---

### Task 6: README, preview, visual check

**Files:**
- Modify: `README.md`
- Regenerate: `preview/expedition-contrib.svg`, `preview/expedition-contrib-dark.svg`

- [ ] **Step 1: README edits** (Edit tool, one at a time)

1. In the description paragraph replace the sentence `Empty weeks get a quick hop along the floor.` with:
   `When a week (or a run of weeks) has no contributions, the hero hops down and slides along the floor, kicking up dust; on a gap of three weeks or more it stops halfway for a nap, with Zs floating up, then slides on and hops back up onto the next block.`
2. Directly after the paragraph that ends ``pass `--character other.toml`.`` (end of "Customize the hero"), insert this new section:

````markdown
## Customize the colours

Edit [`theme.toml`](theme.toml) and commit it. The default preset, `crimson`, matches the
profile README; `cyan` is the original Expedition look.

```toml
preset = "crimson"   # or "cyan"

[dark]               # optional overrides for GitHub's dark theme
levels = ["#5a1422", "#961a2a", "#d12a3c", "#ef4e5c"]   # quietest -> busiest

[light]              # optional overrides for GitHub's light theme
text = "#400e18"
```

Every colour can be overridden for each theme: `floor`, `catwalk`, `lamp`, `levels` (four
colours, quietest to busiest), `trim`, `text`, `sub`, `lit` (glowing tops of landed blocks)
and `flag`. Anything you leave out comes from the preset. The hero's suit and chest light
stay in `character.toml`. Locally, pass `--theme other.toml` to use a different file.
````

3. In "How the update works" replace ``the generator, `character.toml` or a`` with ``the generator, `character.toml`, `theme.toml` or a``.
4. In the Layout table replace the `route.py` row's description with `The route and timing: hops onto each busy week's tallest block, hop down / slide / nap across empty weeks, flag day, loop length`, and add after the `character.py` row: ``| `contrib_hopper/theme.py` | Colour presets (crimson, cyan) and `theme.toml` overrides |``.

- [ ] **Step 2: Regenerate the preview**

`python -m contrib_hopper --user Zeyadmosalem --input tests/fixtures/calendar.json --out preview`

- [ ] **Step 3: Visual check**

Also render the gappy test calendar (blocks in weeks 0, 2, 6, 7 of 10; see `gappy()` in `tests/test_hopper.py`) in both presets into a temp folder outside the repo, e.g. with a short Python snippet that builds it and calls `render.render(cal, t, palette=theme.palettes(preset)[t])` for `crimson`/`cyan` × `dark`/`light`. Serve the folder (`python -m http.server` in the background), open each SVG in the built-in browser, and pause with `document.getAnimations().forEach(a => { a.pause(); a.currentTime = S * 1000; })` at: mid hop-down into the 3-week gap, mid first slide, mid nap, mid second slide, hop up onto week 6, and near the end. Check: slide pose with feet on the floor and dust behind; lying hero with Zs rising above it; never two poses or none; crimson reads like the profile (coral/red blocks on a near-black floor in dark; pink-to-deep-red in light); cyan looks like before. Also view `preview/expedition-contrib-dark.svg` and `preview/expedition-contrib.svg`. Fix small, obviously-right visual problems in `render.py`/`pixels.py` (with a test if it is logic), re-render, re-check; report anything else. Stop the server when done.

- [ ] **Step 4: Final check and commit**

```bash
python -m unittest discover -s tests -v          # Ran 78 tests ... OK (more if you added tests)
git status --short                                # README.md, preview SVGs (+ any fixes)
git add README.md preview/expedition-contrib.svg preview/expedition-contrib-dark.svg
git commit -m "Document slides, naps and theme.toml; refresh the preview"   # plus your Co-Authored-By line
```
