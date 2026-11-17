"""Hero customization: head (skull or a picture) and suit colours.

Settings come from a small TOML file (character.toml in the repo root):

    head  = "skull"        # or a picture path, relative to this file
    suit  = "#24263e"      # suit
    light = "#de3442"      # chest light
    gun   = "#787e92"      # gun

A picture becomes the head the way Expedition's CHARACTER option does it:
centred square crop, shrunk to a 16 px round head, posterized to 4 levels per
channel, and given the 1 px dark outline. Reading pictures needs Pillow; the
default skull needs nothing beyond the standard library.

    python -m contrib_blaster.character photo.jpg character.png

saves just that tiny pixel head, so the original photo never has to be
committed to a public repo.
"""
from __future__ import annotations

import re
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from . import pixels as px

HEAD_SIZE = 16
STEP = 64                    # posterize each colour channel to 4 levels (as in Expedition)
DEFAULTS = {'suit': px.COLORS['k'], 'light': px.COLORS['r'], 'gun': px.COLORS['g']}
KEYS = {'head', *DEFAULTS}


@dataclass(frozen=True)
class Character:
    head: str = 'skull'                        # 'skull' or a picture path
    suit: tuple = DEFAULTS['suit']
    light: tuple = DEFAULTS['light']
    gun: tuple = DEFAULTS['gun']
    base: Path = field(default=Path('.'), compare=False)   # folder the head path is relative to

    def colors(self) -> dict:
        """Expedition's hero palette with this character's colours swapped in."""
        c = dict(px.COLORS)
        if self.suit != DEFAULTS['suit']:
            c['k'] = self.suit
            c['K'] = tuple(min(255, round(v * 1.6) + 18) for v in self.suit)   # lit suit edge
        if self.light != DEFAULTS['light']:
            c['r'] = self.light
            c['R'] = px.lift(self.light, 60)
        if self.gun != DEFAULTS['gun']:
            c['g'] = self.gun
            c['G'] = px.lift(self.gun, 90)
        return c

    def head_raster(self) -> px.Raster:
        if self.head == 'skull':
            return px.grid(px.SKULL, outline=True)
        return head_from_image(self.base / self.head)


def parse_color(value, key: str) -> tuple:
    if not isinstance(value, str) or not re.fullmatch(r'#?[0-9a-fA-F]{6}', value.strip()):
        raise ValueError(f'character {key!r} must be a hex colour like "#de3442", got {value!r}')
    v = value.strip().lstrip('#')
    return tuple(int(v[i:i + 2], 16) for i in (0, 2, 4))


def from_dict(data: dict, base: Path = Path('.')) -> Character:
    data = data.get('character', data)          # allow an optional [character] table
    unknown = set(data) - KEYS
    if unknown:
        raise ValueError(f'unknown character setting(s): {", ".join(sorted(unknown))} '
                         f'(expected {", ".join(sorted(KEYS))})')
    head = data.get('head', 'skull')
    if not isinstance(head, str) or not head.strip():
        raise ValueError('character "head" must be "skull" or a picture path')
    head = head.strip()
    if head != 'skull' and not (base / head).is_file():
        raise ValueError(f'character head picture not found: {base / head}')
    colors = {k: parse_color(data[k], k) if k in data else v for k, v in DEFAULTS.items()}
    return Character(head=head, base=base, **colors)


def load(path: str | Path) -> Character:
    path = Path(path)
    with open(path, 'rb') as f:
        return from_dict(tomllib.load(f), path.parent)


def _pillow():
    try:
        from PIL import Image
    except ImportError:
        raise RuntimeError('a picture head needs Pillow: pip install pillow') from None
    return Image


def head_from_image(path: str | Path) -> px.Raster:
    """Picture -> 16 px round, posterized, outlined pixel head (Expedition's photo rule)."""
    Image = _pillow()
    try:
        with Image.open(path) as im:
            im = im.convert('RGBA')
    except (OSError, ValueError) as ex:
        raise ValueError(f'{path} is not a picture that can be read') from ex
    w, h = im.size
    if w < 4 or h < 4:
        raise ValueError(f'{path} is too small for a head')
    if (w, h) == (HEAD_SIZE + 2, HEAD_SIZE + 2):
        return _raster_from_pixels(im)            # already a saved pixel head: use it as is
    side = min(w, h)
    left, top = (w - side) // 2, (h - side) // 2
    small = im.crop((left, top, left + side, top + side)).resize((HEAD_SIZE, HEAD_SIZE), Image.BOX)
    head = px.Raster(HEAD_SIZE + 2, HEAD_SIZE + 2)
    centre = (HEAD_SIZE - 1) / 2
    for y in range(HEAD_SIZE):
        for x in range(HEAD_SIZE):
            if (x - centre) ** 2 + (y - centre) ** 2 > (HEAD_SIZE / 2) ** 2:
                continue                          # round head: leave the corners clear
            r, g, b, a = small.getpixel((x, y))
            if a < 110:
                continue
            head.set(x + 1, y + 1, tuple(min(255, (v // STEP) * STEP + STEP // 2) for v in (r, g, b)))
    return head.outline()


def _raster_from_pixels(im) -> px.Raster:
    r = px.Raster(*im.size)
    for y in range(im.height):
        for x in range(im.width):
            cr, cg, cb, ca = im.getpixel((x, y))
            if ca >= 110:
                r.set(x, y, (cr, cg, cb))
    return r


def save_head(head: px.Raster, out: str | Path) -> None:
    Image = _pillow()
    im = Image.new('RGBA', (head.w, head.h), (0, 0, 0, 0))
    for (x, y), c in head.px.items():
        im.putpixel((x, y), (*c, 255))
    im.save(out)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 2:
        print('usage: python -m contrib_blaster.character PICTURE OUT.png', file=sys.stderr)
        return 2
    save_head(head_from_image(args[0]), args[1])
    print(f'{args[1]}: {HEAD_SIZE + 2}x{HEAD_SIZE + 2} pixel head. Set head = "{Path(args[1]).name}" '
          f'in character.toml.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
