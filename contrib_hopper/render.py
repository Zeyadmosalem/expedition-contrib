"""Turn a contribution calendar into an animated Block Hopper SVG.

Layout: every day of the last year is an isometric floor tile; active days are
raised blocks (busier = taller and brighter). Weeks run down-right, weekdays
run up-right. The skull hero hops across the year, one hop per week onto the
week's tallest block (route.py works out where and when). A landed block
squashes, pops a coin and lights up, and the rest of its week bounces. After
the last week a flag pops up on the busiest day, the hero does a victory hop
and warps out, the lights fade and the loop restarts.

Animation is pure CSS (no JavaScript). The hero is two nested groups: `hx`
moves its ground point linearly, `hy` lifts it along an eased arc per hop.
Per-block keyframes drive the squash/bounce and the lit tops; coins share one
keyframe started with `animation-delay`.
"""
from __future__ import annotations

from xml.sax.saxutils import escape

from . import pixels as px
from .character import Character
from .contributions import Calendar
from .route import HEIGHTS, INTRO, LANE_D, START_W, ground, lift, plan, tile_xy
from .theme import palettes

__all__ = ['THEMES', 'HEIGHTS', 'ground', 'plan', 'render', 'tile_xy']

CATWALK_FROM = -3                # catwalk strip starts three weeks before the first column
SQUASH = 0.12                    # landed block: squash and recover, seconds
BOUNCE = 0.14                    # the rest of the week: 2 px bounce, seconds
COIN, COIN_RISE = 0.6, 16        # coin flight time (s) and height (px)
COIN_LIFT = 36                  # coin starts this far above the block top: clear of the hero's head
EASE_OUT = 'cubic-bezier(.33,.66,.66,1)'     # take-off -> apex
EASE_IN = 'cubic-bezier(.33,0,.66,.33)'      # apex -> landing

THEMES = palettes()              # default preset's {'dark': ..., 'light': ...}; see theme.py


def _num(v: float) -> str:
    s = f'{v:.2f}'.rstrip('0').rstrip('.')
    return '0' if s in ('-0', '') else s


def render(cal: Calendar, theme: str = 'dark', character: Character | None = None,
           palette: dict | None = None) -> str:
    """palette: one theme's colours (see theme.py); None = the default preset's `theme`."""
    th = palette if palette is not None else THEMES[theme]
    character = character or Character()
    tl = plan(cal)
    T = tl.period

    def pct(t: float) -> str:
        return f'{min(max(t / T * 100, 0), 100):.3f}'.rstrip('0').rstrip('.')

    bounds = [1e9, 1e9, -1e9, -1e9]

    def grow(x0, y0, x1, y1):
        bounds[0] = min(bounds[0], x0); bounds[1] = min(bounds[1], y0)
        bounds[2] = max(bounds[2], x1); bounds[3] = max(bounds[3], y1)

    # ---------- sprites -------------------------------------------------
    defs = []
    floor = px.iso_block(HEIGHTS[0], th['floor'], px.shade(th['floor'], .62),
                         px.shade(th['floor'], .46), outline=False)
    walk = px.iso_block(HEIGHTS[0], th['catwalk'], px.shade(th['catwalk'], .62),
                        px.shade(th['catwalk'], .46), outline=False)
    lamp = px.iso_block(HEIGHTS[0], th['catwalk'], px.shade(th['catwalk'], .62),
                        px.shade(th['catwalk'], .46), outline=False)
    for x, y in ((8, 4), (9, 4), (8, 5), (9, 5)):          # a lit floor light every few tiles
        lamp.set(x, y, th['lamp'])
    defs.append(f'<g id="f">{floor.paths()}</g><g id="c">{walk.paths()}</g><g id="cl">{lamp.paths()}</g>')
    for level in range(1, 5):
        top = th['levels'][level - 1]
        block = px.iso_block(HEIGHTS[level], top, px.shade(top, .68), px.shade(top, .5),
                             trim=th['trim'] if level >= 3 else None)
        defs.append(f'<g id="b{level}">{block.paths()}</g>')
    defs.append(f'<g id="lt">{px.lit_top(th["lit"]).paths()}</g>')
    defs.append(f'<g id="n0">{px.coin(0).paths()}</g><g id="n1">{px.coin(1).paths()}</g>')
    flag = px.flag(th['flag'])
    defs.append(f'<g id="flag">{flag.paths()}</g>')

    # ---------- floor and catwalk (static) ---------------------------------
    tiles = [(d.week, d.weekday, 'f') for d in cal.days]
    for u in range(CATWALK_FROM, cal.weeks + 2):
        tiles.append((u, -1, 'cl' if u % 4 == 0 else 'c'))
        tiles.append((u, -2, 'c'))
    floor_svg = []
    for w, d, ref in sorted(tiles, key=lambda t: (t[0] - t[1], t[0])):
        x, y = tile_xy(w, d)
        h = HEIGHTS[0]
        floor_svg.append(f'<use href="#{ref}" x="{_num(x - 1)}" y="{_num(y - h - 1)}"/>')
        grow(x - 1, y - h - 1, x + 17, y + 11)

    # ---------- blocks: squash / bounce, and the lit top of landed blocks ------
    landed = {(h.week, h.weekday) for h in tl.hops if h.level > 0}
    land_at = {h.week: h.land for h in tl.hops if h.level > 0}
    css, blocks_svg = [], []
    order = sorted(cal.active, key=lambda d: (d.week - d.weekday, d.week))
    for i, day in enumerate(order):
        h = HEIGHTS[day.level]
        x, y = tile_xy(day.week, day.weekday)
        bx, by = _num(x - 1), _num(y - h - 1)
        t = land_at[day.week]
        inner = f'<use href="#b{day.level}" x="{bx}" y="{by}"/>'
        if (day.week, day.weekday) in landed:
            inner += f'<use class="lt" href="#lt" x="{bx}" y="{by}" style="animation-name:t{i}"/>'
            css.append(f'@keyframes t{i}{{0%,{pct(t)}%{{opacity:0}}'
                       f'{pct(t + .02)}%,{pct(tl.reset_start)}%{{opacity:1}}to{{opacity:0}}}}')
            pose, dur = 'scale(1.08,.8)', SQUASH
        else:
            pose, dur = 'translateY(-2px)', BOUNCE
        css.append(f'@keyframes k{i}{{0%,{pct(t)}%{{transform:none}}{pct(t + dur / 2)}%{{transform:{pose}}}'
                   f'{pct(t + dur)}%,to{{transform:none}}}}')
        blocks_svg.append(f'<g class="b" style="animation-name:k{i}">{inner}</g>')
        grow(x - 1, y - h - 1, x + 17, y + 11)

    # ---------- coins (shared keyframes, started by --t) and the flag --------
    fx_svg = []
    for hop in tl.hops:
        if hop.level == 0:
            continue
        cx, cy = ground(hop.week, hop.weekday)
        top = cy - HEIGHTS[hop.level]
        fx_svg.append(f'<g transform="translate({_num(cx - 4)} {_num(top - COIN_LIFT)})">'
                      f'<g class="x cn" style="--t:{hop.land:.3f}s">'
                      f'<use class="cf" href="#n0"/><use class="cf c1" href="#n1"/></g></g>')
        grow(cx - 4, top - COIN_LIFT - COIN_RISE, cx + 4, top)
    fw_, fd, fl = tl.flag_day
    cx, cy = ground(fw_, fd)
    top = cy - HEIGHTS[fl]
    fx_svg.append(f'<use class="fg" href="#flag" x="{_num(cx - 1)}" y="{_num(top - flag.h + 3)}"/>')
    grow(cx - 1, top - flag.h + 3, cx - 1 + flag.w, top + 3)

    # ---------- hero: hx = ground motion, hy = arc, ps/pj = pose ---------------
    stand, jump = px.hero_poses(character.colors(), character.head_raster())
    fw, fh = stand.w, stand.h
    sx, sy = ground(START_W, LANE_D)

    def box(gx, gy, up):
        grow(gx - fw / 2 - 1, gy - up - fh - 1, gx + fw / 2 + 1, gy + 2)

    def move(dx, dy):
        return 'none' if (dx, dy) == (0, 0) else f'translate({_num(dx)}px,{_num(dy)}px)'

    def rise(up):
        return 'none' if up == 0 else f'translateY(-{_num(up)}px)'

    hx, hy = ['0%{transform:none}'], ['0%{transform:none}']
    ps, pj = ['0%{opacity:1}'], ['0%{opacity:0}']
    pos, up = (0.0, 0.0), 0
    box(sx, sy, 0)
    for hop in (*tl.hops, tl.victory):
        gx, gy = ground(hop.week, hop.weekday)
        nxt = (gx - sx, gy - sy)
        mid = (hop.takeoff + hop.land) / 2
        hx.append(f'{pct(hop.takeoff)}%{{transform:{move(*pos)}}}{pct(hop.land)}%{{transform:{move(*nxt)}}}')
        hy.append(f'{pct(hop.takeoff)}%{{transform:{rise(up)};animation-timing-function:{EASE_OUT}}}'
                  f'{pct(mid)}%{{transform:{rise(hop.apex)};animation-timing-function:{EASE_IN}}}'
                  f'{pct(hop.land)}%{{transform:{rise(lift(hop.level))}}}')
        ps.append(f'{pct(hop.takeoff)}%{{opacity:0}}{pct(hop.land)}%{{opacity:1}}')
        pj.append(f'{pct(hop.takeoff)}%{{opacity:1}}{pct(hop.land)}%{{opacity:0}}')
        box(gx, gy, hop.apex)
        pos, up = nxt, lift(hop.level)
    hx.append(f'to{{transform:{move(*pos)}}}')
    hy.append(f'to{{transform:{rise(up)}}}')
    hero_svg = (f'<g transform="translate({_num(sx)} {_num(sy)})"><g class="hv"><g class="hx"><g class="hy">'
                f'<g transform="translate({-(fw // 2)} {-fh + 1})">'
                f'<g class="ps">{stand.paths()}</g><g class="pj">{jump.paths()}</g>'
                f'</g></g></g></g></g>')

    # ---------- HUD ----------------------------------------------------------
    minx, miny, maxx, maxy = bounds
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
           f'fill="{px.hex_color(th["text"])}">LEVEL CLEAR</text></g>')

    # ---------- shared CSS ----------------------------------------------------
    v = tl.victory
    run = f'{T:.3f}s'
    shared = [
        f'.b,.lt{{animation-duration:{run};animation-iteration-count:infinite;animation-timing-function:linear}}',
        '.b{transform-box:fill-box;transform-origin:50% 100%}.lt{opacity:0}',
        f'.x{{opacity:0;animation-duration:{run};animation-iteration-count:infinite;'
        'animation-timing-function:linear;animation-delay:var(--t)}',
        '.cn{animation-name:cn}',
        f'@keyframes cn{{0%{{opacity:1;transform:none}}{pct(COIN * .6)}%{{opacity:1;transform:translateY(-12px)}}'
        f'{pct(COIN)}%,to{{opacity:0;transform:translateY(-{COIN_RISE}px)}}}}',
        '.cf{opacity:0;animation:cf .24s steps(1,end) infinite}.c1{animation-delay:.12s}',
        '@keyframes cf{0%{opacity:1}50%,to{opacity:0}}',
        f'.hx{{animation:hx {run} linear infinite}}@keyframes hx{{{"".join(hx)}}}',
        f'.hy{{animation:hy {run} infinite}}@keyframes hy{{{"".join(hy)}}}',
        f'.ps{{animation:ps {run} steps(1,end) infinite}}@keyframes ps{{{"".join(ps)}}}',
        f'.pj{{opacity:0;animation:pj {run} steps(1,end) infinite}}@keyframes pj{{{"".join(pj)}}}',
        f'.hv{{animation:hv {run} steps(1,end) infinite}}',
        f'@keyframes hv{{0%{{opacity:0}}{pct(INTRO * .4)}%{{opacity:1}}{pct(INTRO * .55)}%{{opacity:0}}'
        f'{pct(INTRO * .7)}%,{pct(v.land + .1)}%{{opacity:1}}{pct(v.land + .2)}%{{opacity:0}}'
        f'{pct(v.land + .28)}%{{opacity:1}}{pct(v.land + .36)}%,to{{opacity:0}}}}',
        f'.sc{{opacity:0;animation:sc {run} steps(1,end) infinite}}',
        f'@keyframes sc{{0%,{pct(tl.hop_end)}%{{opacity:0}}{pct(tl.hop_end + .01)}%,'
        f'{pct(tl.reset_start)}%{{opacity:1}}{pct(tl.reset_start + .01)}%,to{{opacity:0}}}}',
        f'.fg{{opacity:0;animation:fg {run} linear infinite}}',
        f'@keyframes fg{{0%,{pct(tl.hop_end)}%{{opacity:0;transform:translateY(6px)}}'
        f'{pct(tl.hop_end + .15)}%,{pct(tl.reset_start)}%{{opacity:1;transform:none}}'
        f'to{{opacity:0;transform:none}}}}',
        '@media (prefers-reduced-motion:reduce){*{animation:none!important}.sc,.fg{opacity:1!important}}',
    ]

    title = f'{who}: {total} contributions in the last year, hopped across by the Expedition skull hero'
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{_num(minx)} {_num(miny)} {_num(width)} {_num(height)}" '
        f'width="{_num(width * 2)}" height="{_num(height * 2)}" shape-rendering="crispEdges" '
        f'role="img" aria-labelledby="title">'
        f'<title id="title">{title}</title>'
        f'<style>{"".join(shared)}{"".join(css)}</style>'
        f'<defs>{"".join(defs)}</defs>'
        f'<g id="floor">{"".join(floor_svg)}</g>'
        f'<g id="blocks">{"".join(blocks_svg)}</g>'
        f'<g id="hero">{hero_svg}</g>'
        f'<g id="fx">{"".join(fx_svg)}</g>'
        f'{hud}</svg>\n'
    )
