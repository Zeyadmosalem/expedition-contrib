"""Turn a contribution calendar into an animated Expedition-style SVG.

Layout: every day of the last year is an isometric floor tile; active days are
raised blocks (busier = taller and brighter). Weeks run down-right, weekdays
run up-right. The skull hero walks the catwalk along the front edge, and when
lined up with a week fires a bolt up that column; each block it crosses bursts
into particles. After the last week the grid rebuilds and the loop repeats.

Animation is pure CSS (no JavaScript): per-block keyframes for the block's
death and rebuild, and shared keyframes started with `animation-delay` for
bolts, flashes and particles.
"""
from __future__ import annotations

from dataclasses import dataclass
from xml.sax.saxutils import escape

from . import pixels as px
from .character import Character
from .contributions import Calendar

HEIGHTS = (2, 4, 7, 10, 14)      # block height per level 0..4 (level 0 = floor slab)
STEP = 0.2                       # seconds per week while there is something to shoot
DASH = 0.07                      # seconds per week through empty weeks
TRAVEL = 0.22                    # seconds for a bolt to cross a whole column
INTRO, OUTRO = 0.5, 0.5          # warp in / warp out around the walk
REBUILD, DROP, HOLD = 1.6, 0.35, 1.2
BURST = 0.55                     # particle flight time
LANE_D = -1.5                    # hero walks between catwalk rows d=-1 and d=-2
START_U = -3                     # hero starts three weeks before the first column
BOLT_END_D = 7                   # bolts fly one row past the last weekday

THEMES = {
    'dark': {
        'floor': (24, 28, 46), 'walk': (40, 44, 66), 'lamp': (90, 200, 220),
        'levels': [(38, 64, 96), (40, 108, 140), (48, 164, 190), (118, 236, 240)],
        'trim': (90, 200, 220), 'text': (150, 226, 236), 'sub': (104, 124, 158),
        'bolt': ((255, 244, 190), (255, 170, 60)),
    },
    'light': {
        'floor': (222, 228, 238), 'walk': (196, 202, 218), 'lamp': (40, 150, 190),
        'levels': [(160, 212, 230), (92, 182, 212), (40, 140, 182), (20, 92, 150)],
        'trim': (150, 236, 255), 'text': (24, 44, 78), 'sub': (96, 108, 136),
        'bolt': ((255, 236, 150), (236, 120, 30)),
    },
}


def tile_xy(w: float, d: float) -> tuple[float, float]:
    """Top-left corner of the ground diamond for week w, weekday d."""
    return (w + d) * 8, (w - d) * 4


def ground(w: float, d: float) -> tuple[float, float]:
    """Ground point at the centre of (w, d); fractional values allowed."""
    x, y = tile_xy(w, d)
    return x + 8, y + 4


@dataclass(frozen=True)
class Shot:
    week: int
    weekday: int
    level: int
    date: str
    kill: float          # seconds into the loop when the bolt reaches the block
    drop: float          # seconds into the loop when the block starts to fall back in


@dataclass(frozen=True)
class Timeline:
    period: float
    walk_start: float
    walk_end: float
    rebuild_start: float
    end_u: int
    align: float         # hero is lined up with week w when u = w - align
    bolt_start_d: float
    bolt_height: int
    fire: dict           # week -> seconds
    shots: tuple         # Shot per active day
    stops: tuple         # (u, seconds) at every whole step of the hero's walk


def plan(cal: Calendar, character: Character | None = None) -> Timeline:
    character = character or Character()
    hero = px.hero_frames(character.colors(), character.head_raster())[0]
    gun = px.gun(character.colors())
    tip_dx = 2 + gun.w                       # gun drawn 2 px right of the feet
    tip_dy = (-hero.h + 1) + (hero.h - 10) + 1
    align = tip_dx / 16                      # see docs: tip lies on column u + align
    bolt_start_d = LANE_D + align
    end_u = max(cal.weeks, 1) + 1
    busy = {d.week for d in cal.active}
    # The hero fires at week w while crossing u in [w-1, w]; walk slowly there,
    # dash through empty weeks.
    stops, t = [(START_U, INTRO)], INTRO
    for u in range(START_U, end_u):
        t += STEP if u + 1 in busy else DASH
        stops.append((u + 1, t))
    at = dict(stops)
    walk_start, walk_end = INTRO, t
    rebuild_start = walk_end + OUTRO
    period = rebuild_start + REBUILD + DROP + HOLD
    fire = {w: at[w - 1] + (1 - align) * (at[w] - at[w - 1]) for w in range(cal.weeks)}
    span = BOLT_END_D - bolt_start_d
    last = max(cal.weeks - 1, 1)
    shots = []
    for day in cal.active:
        kill = fire[day.week] + TRAVEL * (day.weekday - bolt_start_d) / span
        drop = rebuild_start + REBUILD * day.week / last + 0.03 * (6 - day.weekday)
        shots.append(Shot(day.week, day.weekday, day.level, day.date, kill, drop))
    return Timeline(period, walk_start, walk_end, rebuild_start, end_u, align,
                    bolt_start_d, -tip_dy, fire, tuple(shots), tuple(stops))


def _num(v: float) -> str:
    s = f'{v:.2f}'.rstrip('0').rstrip('.')
    return '0' if s in ('-0', '') else s


def render(cal: Calendar, theme: str = 'dark', character: Character | None = None) -> str:
    th = THEMES[theme]
    character = character or Character()
    tl = plan(cal, character)
    T = tl.period

    def pct(t: float) -> str:
        return f'{min(max(t / T * 100, 0), 100):.3f}'.rstrip('0').rstrip('.')

    # ---------- sprites -------------------------------------------------
    defs = []
    floor = px.iso_block(HEIGHTS[0], th['floor'], px.shade(th['floor'], .62),
                         px.shade(th['floor'], .46), outline=False)
    walk = px.iso_block(HEIGHTS[0], th['walk'], px.shade(th['walk'], .62),
                        px.shade(th['walk'], .46), outline=False)
    lamp = px.iso_block(HEIGHTS[0], th['walk'], px.shade(th['walk'], .62),
                        px.shade(th['walk'], .46), outline=False)
    for x, y in ((8, 4), (9, 4), (8, 5), (9, 5)):          # a lit floor light every few tiles
        lamp.set(x, y, th['lamp'])
    defs.append(f'<g id="f">{floor.paths()}</g><g id="c">{walk.paths()}</g><g id="cl">{lamp.paths()}</g>')
    for level in range(1, 5):
        top = th['levels'][level - 1]
        block = px.iso_block(HEIGHTS[level], top, px.shade(top, .68), px.shade(top, .5),
                             trim=th['trim'] if level >= 3 else None)
        defs.append(f'<g id="b{level}">{block.paths()}</g>')

    bounds = [1e9, 1e9, -1e9, -1e9]

    def grow(x0, y0, x1, y1):
        bounds[0] = min(bounds[0], x0); bounds[1] = min(bounds[1], y0)
        bounds[2] = max(bounds[2], x1); bounds[3] = max(bounds[3], y1)

    # ---------- floor and catwalk (static) ---------------------------------
    tiles = [(d.week, d.weekday, 'f') for d in cal.days]
    for u in range(START_U, tl.end_u + 1):
        tiles.append((u, -1, 'cl' if u % 4 == 0 else 'c'))
        tiles.append((u, -2, 'c'))
    floor_svg = []
    for w, d, ref in sorted(tiles, key=lambda t: (t[0] - t[1], t[0])):
        x, y = tile_xy(w, d)
        h = HEIGHTS[0]
        floor_svg.append(f'<use href="#{ref}" x="{_num(x - 1)}" y="{_num(y - h - 1)}"/>')
        grow(x - 1, y - h - 1, x + 17, y + 11)

    # ---------- blocks: per-block death + rebuild keyframes ----------------
    css = []
    blocks_svg = []
    order = sorted(tl.shots, key=lambda s: (s.week - s.weekday, s.week))
    for i, s in enumerate(order):
        h = HEIGHTS[s.level]
        x, y = tile_xy(s.week, s.weekday)
        blocks_svg.append(f'<use class="b" href="#b{s.level}" x="{_num(x - 1)}" y="{_num(y - h - 1)}" '
                          f'style="animation-name:k{i}"/>')
        grow(x - 1, y - h - 25, x + 17, y + 11)
        # vanish the instant the bolt arrives, then fall back in solid with gravity
        css.append(f'@keyframes k{i}{{0%,{pct(s.kill)}%{{opacity:1;transform:none}}'
                   f'{pct(s.kill + .002)}%,{pct(s.drop)}%{{opacity:0;transform:translateY(-28px)}}'
                   f'{pct(s.drop + .002)}%{{opacity:1;transform:translateY(-28px);'
                   f'animation-timing-function:cubic-bezier(.55,0,1,.45)}}'
                   f'{pct(s.drop + DROP)}%,to{{opacity:1;transform:none}}}}')

    # ---------- bursts (shared keyframes, started by --t) --------------------
    fx_svg = []
    for s in order:
        h = HEIGHTS[s.level]
        cx, cy = ground(s.week, s.weekday)
        color = px.hex_color(px.lift(th['levels'][s.level - 1], 30))
        fx_svg.append(f'<g transform="translate({_num(cx)} {_num(cy - h)})" fill="{color}" '
                      f'style="--t:{s.kill:.3f}s"><rect class="x f" x="-3" y="-2" width="6" height="4"/>'
                      f'<rect class="x p1" x="-1" y="-1" width="2" height="2"/>'
                      f'<rect class="x p2" x="-1" y="-1" width="2" height="2"/>'
                      f'<rect class="x p3" x="-1" y="-1" width="2" height="2"/>'
                      f'<rect class="x p4" x="-1" y="-1" width="2" height="2"/></g>')

    # ---------- bolts: one per week that has something to shoot ---------------
    core, glow = th['bolt']
    streak = px.Raster(9, 6)
    for i, (x, y) in enumerate(((0, 4), (1, 4), (2, 3), (3, 3), (4, 2), (5, 2), (6, 1), (7, 1))):
        streak.set(x, y + 1, glow)
        streak.set(x, y, core)
    defs.append(f'<g id="bolt" transform="translate(-8 -2)">{streak.paths()}</g>')
    dx = (BOLT_END_D - tl.bolt_start_d) * 8
    dy = -(BOLT_END_D - tl.bolt_start_d) * 4
    fired = sorted({s.week for s in tl.shots})
    for w in fired:
        bx, by = ground(w, tl.bolt_start_d)
        by -= tl.bolt_height
        fx_svg.append(f'<g transform="translate({_num(bx)} {_num(by)})" style="--t:{tl.fire[w]:.3f}s">'
                      f'<g class="x bo"><use href="#bolt"/></g>'
                      f'<rect class="x mz" x="-2" y="-2" width="4" height="3" fill="{px.hex_color(core)}"/></g>')

    # ---------- hero ---------------------------------------------------------
    frames = px.hero_frames(character.colors(), character.head_raster())
    gun = px.gun(character.colors())
    fw, fh = frames[0].w, frames[0].h
    gx, gy = 2, -fh + 1 + fh - 10                # relative to the feet
    frames_svg = ''.join(f'<g class="l l{k}">{f.paths()}</g>' for k, f in enumerate(frames))
    gun_svg = f'<g transform="translate({gx} {gy})">{gun.paths()}</g>'
    sx, sy = ground(START_U, LANE_D)
    ex, ey = ground(tl.end_u, LANE_D)
    grow(sx - fw, sy - fh - 2, ex + gx + gun.w + 2, ey + 4)
    hero_svg = (f'<g transform="translate({_num(sx)} {_num(sy)})"><g class="hv"><g class="hm">'
                f'<g transform="translate({-(fw // 2)} {-fh + 1})">{frames_svg}</g>{gun_svg}</g></g></g>')

    # ---------- HUD ----------------------------------------------------------
    minx, miny, maxx, maxy = (b for b in bounds)
    minx, miny, maxx, maxy = minx - 6, miny - 6, maxx + 6, maxy + 6
    width, height = maxx - minx, maxy - miny
    total = f'{cal.total:,}'
    who = escape(cal.login or 'github')
    font = "font-family=\"ui-monospace,'Cascadia Mono','SFMono-Regular',Consolas,'Courier New',monospace\" font-weight=\"700\""
    hud = (f'<g {font}>'
           f'<text x="{_num(minx + 10)}" y="{_num(maxy - 22)}" font-size="18" fill="{px.hex_color(th["text"])}">{total}</text>'
           f'<text x="{_num(minx + 10)}" y="{_num(maxy - 10)}" font-size="8" fill="{px.hex_color(th["sub"])}">'
           f'CONTRIBUTIONS IN THE LAST YEAR</text>'
           f'<text x="{_num(maxx - 10)}" y="{_num(miny + 16)}" font-size="8" text-anchor="end" '
           f'fill="{px.hex_color(th["sub"])}">EXPEDITION // @{who}</text>'
           f'<text class="sc" x="{_num(maxx - 10)}" y="{_num(miny + 30)}" font-size="11" text-anchor="end" '
           f'fill="{px.hex_color(th["text"])}">SECTOR CLEAR</text></g>')

    # ---------- shared CSS ----------------------------------------------------
    b = BURST
    shared = [
        f'.b{{animation-duration:{T:.3f}s;animation-iteration-count:infinite;animation-timing-function:linear}}',
        f'.x{{opacity:0;animation-duration:{T:.3f}s;animation-iteration-count:infinite;'
        'animation-timing-function:linear;animation-delay:var(--t)}',
        '.f{animation-name:fl;fill:#fff}.p1{animation-name:p1}.p2{animation-name:p2}'
        '.p3{animation-name:p3}.p4{animation-name:p4;fill:#fff}.bo{animation-name:bo}.mz{animation-name:fl}',
        f'@keyframes fl{{0%,{pct(.07)}%{{opacity:1}}{pct(.08)}%,to{{opacity:0}}}}',
        f'@keyframes bo{{0%{{opacity:1;transform:none}}{pct(TRAVEL)}%{{opacity:1;transform:translate({_num(dx)}px,{_num(dy)}px)}}'
        f'{pct(TRAVEL + .01)}%,to{{opacity:0;transform:translate({_num(dx)}px,{_num(dy)}px)}}}}',
    ]
    for name, (mx, my), (ex2, ey2) in (('p1', (-4, -8), (-9, -1)), ('p2', (4, -9), (9, -2)),
                                       ('p3', (-2, -5), (-5, 5)), ('p4', (2, -11), (5, 3))):
        shared.append(f'@keyframes {name}{{0%{{opacity:1;transform:none}}'
                      f'{pct(b / 2)}%{{opacity:1;transform:translate({mx}px,{my}px)}}'
                      f'{pct(b)}%{{opacity:1;transform:translate({ex2}px,{ey2}px)}}'
                      f'{pct(b + .01)}%,to{{opacity:0;transform:translate({ex2}px,{ey2}px)}}}}')
    def at_u(u: int) -> str:
        n = u - START_U
        return 'none' if n == 0 else f'translate({n * 8}px,{n * 4}px)'

    runs = []                                       # merge whole steps of equal speed
    for (u0, t0), (u1, t1) in zip(tl.stops, tl.stops[1:]):
        if runs and abs((t1 - t0) - runs[-1][4]) < 1e-9:
            runs[-1][2:4] = [u1, t1]
        else:
            runs.append([u0, t0, u1, t1, t1 - t0])
    walk_kf = ['0%{transform:none}']
    for u0, t0, u1, _t1, _dur in runs:              # 2 px x 1 px snaps, like a pixel game
        walk_kf.append(f'{pct(t0)}%{{transform:{at_u(u0)};animation-timing-function:steps({(u1 - u0) * 4},end)}}')
    walk_kf.append(f'{pct(tl.walk_end)}%,to{{transform:{at_u(tl.end_u)}}}')
    shared += [
        f'.hm{{animation:hm {T:.3f}s infinite}}',
        f'@keyframes hm{{{"".join(walk_kf)}}}',
        f'.hv{{animation:hv {T:.3f}s steps(1,end) infinite}}',
        f'@keyframes hv{{0%{{opacity:0}}{pct(INTRO * .4)}%{{opacity:1}}{pct(INTRO * .55)}%{{opacity:0}}'
        f'{pct(INTRO * .7)}%,{pct(tl.walk_end + .1)}%{{opacity:1}}{pct(tl.walk_end + .2)}%{{opacity:0}}'
        f'{pct(tl.walk_end + .28)}%{{opacity:1}}{pct(tl.walk_end + .36)}%,to{{opacity:0}}}}',
        '.l{opacity:0;animation:lg .4s steps(1,end) infinite}.l1{animation-delay:.1s}'
        '.l2{animation-delay:.2s}.l3{animation-delay:.3s}',
        '@keyframes lg{0%{opacity:1}25%,to{opacity:0}}',
        f'.sc{{opacity:0;animation:sc {T:.3f}s steps(1,end) infinite}}',
        f'@keyframes sc{{0%,{pct(tl.walk_end)}%{{opacity:0}}{pct(tl.walk_end + .01)}%,'
        f'{pct(tl.rebuild_start + REBUILD + DROP)}%{{opacity:1}}'
        f'{pct(tl.rebuild_start + REBUILD + DROP + .01)}%,to{{opacity:0}}}}',
        '@media (prefers-reduced-motion:reduce){*{animation:none!important}.l0,.sc{opacity:1!important}}',
    ]

    title = f'{who}: {total} contributions in the last year, blasted by the Expedition skull hero'
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{_num(minx)} {_num(miny)} {_num(width)} {_num(height)}" '
        f'width="{_num(width * 2)}" height="{_num(height * 2)}" shape-rendering="crispEdges" '
        f'role="img" aria-labelledby="title">'
        f'<title id="title">{title}</title>'
        f'<style>{"".join(shared)}{"".join(css)}</style>'
        f'<defs>{"".join(defs)}</defs>'
        f'<g id="floor">{"".join(floor_svg)}</g>'
        f'<g id="blocks">{"".join(blocks_svg)}</g>'
        f'<g id="fx">{"".join(fx_svg)}</g>'
        f'<g id="hero">{hero_svg}</g>'
        f'{hud}</svg>\n'
    )
