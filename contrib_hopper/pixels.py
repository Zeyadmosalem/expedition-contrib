"""Tiny pixel rasters for the SVG renderer (standard library only).

Sprites follow Expedition's pixel_art.py: character grids, a 1 px dark INK
outline, and isometric blocks drawn as a lit top diamond with two shaded side
faces. A Raster is a sparse map of pixels that turns into crisp SVG <path>s
made of 1 px tall horizontal runs, so the output stays sharp at any zoom.
"""
from __future__ import annotations

TILE_W, TILE_H = 16, 8               # isometric diamond, half Expedition's 32x16
INK = (18, 14, 26)                   # outline colour from Expedition

# Expedition's hero palette
COLORS = {
    'W': (238, 238, 230), 'w': (176, 178, 192), 'x': (26, 22, 34),
    'k': (36, 38, 62), 'K': (64, 70, 108), 'r': (222, 52, 66), 'R': (255, 110, 110),
    'h': (172, 176, 190), 'b': (22, 20, 30), 'g': (120, 126, 146), 'G': (210, 214, 226),
}

# The user's flat white skull logo (Expedition/assets/hero_skull.png) reduced
# to 15 px with Expedition's 3-colour rule (white / shade / black). Baked in so
# the generator needs no image library.
SKULL = [
    "......WW....W..",
    "...wxWWWWWWWW..",
    "..WWxWWWWWWWW..",
    ".WWWWWWWWWWWWW.",
    ".WWWwwWWWWWWWWW",
    "WWWxxxwWWWWWWWW",
    "WWwxxxxWWWWwwWW",
    "WWwxxxxWWwxxwWW",
    "WWwxxxxWwxxxwWW",
    "WWWxxxxWwxxxWWW",
    ".WWwxxwWWxxwWW.",
    ".WWWWWWxWWWWWW.",
    ".WWWWWxxxWWWWW.",
    "....WWWWWWW....",
    "....WWwWWW.....",
]

BODY = [
    "....KkkkkkkK....",
    "...KkkkrrkkkK...",
    "..hKkkrrrrkkKh..",
    "..hKkkkrrkkkKh..",
    "...KkkkkkkkkK...",
    "....kkKKKKkk....",
]
STAND_LEGS = [
    "....kkk..kkk....",
    "....kkk..kkk....",
    "....kk....kk....",
    "...bbb....bbb...",
]
# Mid-jump: legs kicked out, feet tucked one row up (same 4-row frame as STAND_LEGS)
JUMP_LEGS = [
    "...kkkk..kkkk...",
    "..kkk......kkk..",
    "..bbb......bbb..",
    "................",
]
# Spinning coin popped by a landing: face-on, then edge-on. Same gold in both themes.
COIN_COLORS = {'y': (250, 196, 60), 'Y': (255, 240, 160), 'o': (196, 124, 28)}
COIN = [
    [".yyyy.",
     "yYYyyo",
     "yYyyyo",
     "yYyyyo",
     "yYyyyo",
     "yyyyoo",
     ".oooo."],
    ["..yo..",
     "..Yo..",
     "..Yo..",
     "..yo..",
     "..yo..",
     "..yo..",
     "..oo.."],
]
# Finish flag on the busiest day: white pole, pennant in the theme's flag colour.
FLAG = [
    "Wppp.",
    "Wpppp",
    "Wppp.",
] + ["W...."] * 9

Color = tuple  # (r, g, b)


def hex_color(c: Color) -> str:
    return '#%02x%02x%02x' % tuple(c)


def shade(c: Color, k: float) -> Color:
    return tuple(max(0, min(255, round(v * k))) for v in c)


def lift(c: Color, amount: int) -> Color:
    return tuple(min(255, v + amount) for v in c)


class Raster:
    """A w x h pixel canvas; unset pixels are transparent."""

    def __init__(self, w: int, h: int):
        self.w, self.h = w, h
        self.px: dict[tuple[int, int], Color] = {}

    def set(self, x: int, y: int, color: Color) -> None:
        if 0 <= x < self.w and 0 <= y < self.h:
            self.px[(x, y)] = tuple(color)

    def blit(self, other: 'Raster', ox: int, oy: int) -> None:
        for (x, y), c in other.px.items():
            self.set(x + ox, y + oy, c)

    def outline(self, color: Color = INK) -> 'Raster':
        """Dark one-pixel rim around every opaque pixel (Expedition's add_outline)."""
        solid = set(self.px)
        for x, y in solid:
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if (nx, ny) not in solid:
                    self.set(nx, ny, color)
        return self

    def paths(self) -> str:
        """SVG paths, one per colour, built from horizontal runs."""
        by_color: dict[Color, list[str]] = {}
        for y in range(self.h):
            x = 0
            while x < self.w:
                c = self.px.get((x, y))
                if c is None:
                    x += 1
                    continue
                start = x
                while x < self.w and self.px.get((x, y)) == c:
                    x += 1
                by_color.setdefault(c, []).append(f'M{start} {y}h{x - start}v1h-{x - start}z')
        return ''.join(f'<path fill="{hex_color(c)}" d="{"".join(runs)}"/>'
                       for c, runs in sorted(by_color.items()))


def grid(rows: list[str], colors: dict = COLORS, outline: bool = False) -> Raster:
    pad = 1 if outline else 0
    r = Raster(len(rows[0]) + 2 * pad, len(rows) + 2 * pad)
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch != '.':
                r.set(x + pad, y + pad, colors[ch])
    return r.outline() if outline else r


def _hero(colors: dict, head: Raster, legs: list[str]) -> Raster:
    """Head on the suit (with the chest light) on the given legs, outlined."""
    body = grid(BODY, colors)
    leg = grid(legs, colors)
    width = max(head.w, 16) + 2
    height = head.h + len(BODY) + len(legs) - 1
    canvas = Raster(width, height)
    canvas.blit(leg, (width - 16) // 2, head.h + len(BODY) - 1)
    canvas.blit(body, (width - 16) // 2, head.h - 1)
    canvas.blit(head, (width - head.w) // 2, 0)
    return canvas.outline()


def hero_poses(colors: dict = COLORS, head: Raster | None = None) -> tuple[Raster, Raster]:
    """(stand, jump): same size, so they can be swapped in place."""
    head = head or grid(SKULL, outline=True)
    return _hero(colors, head, STAND_LEGS), _hero(colors, head, JUMP_LEGS)


def coin(frame: int) -> Raster:
    return grid(COIN[frame], COIN_COLORS, outline=True)


def flag(pennant: Color) -> Raster:
    return grid(FLAG, {'W': COLORS['W'], 'p': tuple(pennant)}, outline=True)


def _diamond_span(y: int) -> tuple[int, int]:
    """x range [a, b) of row y of the top diamond (rows 2, 6, 10, 14, 14, 10, 6, 2 wide)."""
    half = 2 * y + 1 if y < TILE_H // 2 else 2 * (TILE_H - 1 - y) + 1
    return TILE_W // 2 - half, TILE_W // 2 + half


def iso_block(height: int, top: Color, left: Color, right: Color,
              trim: Color | None = None, outline: bool = True) -> Raster:
    """A raised isometric tile: lit top diamond, two shaded faces, INK rim.

    Raster pixel (1, 1) is the tile's top-left corner raised by `height`, so a
    tile whose ground diamond starts at world (X, Y) is drawn at
    (X - 1, Y - height - 1). Diamonds tessellate exactly at offsets (+-8, +-4).
    """
    r = Raster(TILE_W + 2, TILE_H + height + 2)
    bottom = {}                                   # column -> first row below the diamond
    top_row = {}
    for y in range(TILE_H):
        a, b = _diamond_span(y)
        for x in range(a, b):
            r.set(x + 1, y + 1, top)
            bottom[x] = y + 1
            top_row.setdefault(x, y)
    for x, y0 in bottom.items():
        face = left if x < TILE_W // 2 else right
        for y in range(y0, y0 + height):
            r.set(x + 1, y + 1, face)
        if trim is not None and height >= 9:      # lit bulkhead seam halfway down
            r.set(x + 1, y0 + height // 2 + 1, trim)
    edge = lift(top, 34)
    for x, y in top_row.items():                  # bright upper rim, like Expedition
        r.set(x + 1, y + 1, edge)
    return r.outline() if outline else r


def lit_top(top: Color) -> Raster:
    """Only the top diamond (with its bright rim) of an iso_block, in the same frame,
    so it can be laid over any block at the block's own x/y to light it up."""
    return iso_block(0, top, top, top, outline=False)
