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
