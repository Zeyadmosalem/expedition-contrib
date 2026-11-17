"""Route and timing for the Block Hopper animation (pure maths, no SVG).

The hero starts on the catwalk in front of week 0 and works through the year:
onto each busy week's tallest block with a hop; into a run of empty weeks with
one hop down, then a slide along the floor (with a nap halfway when the run is
NAP_MIN weeks or longer) and a hop back up. After the last week it does a
victory hop in place. All times are seconds into one loop of the animation.
"""
from __future__ import annotations

from dataclasses import dataclass

from .contributions import Calendar, Day

HEIGHTS = (2, 4, 7, 10, 14)       # block height per level 0..4 (level 0 = floor slab)
LANE_D = -1.5                     # catwalk lane, between catwalk rows d=-1 and d=-2
START_W = -1                      # the hero starts on the catwalk one week before week 0
NO_LANDING = 3                    # weekday the tie-break aims at before the first landing

INTRO = 0.5                       # warp in
HOP, HOP_PER_LEVEL = 0.30, 0.04   # hop onto a block: base time + per level of height change
FLOOR_HOP = 0.18                  # floor (or catwalk) to floor
PAUSE = 0.06                      # standing still after each landing
VICTORY, OUTRO, HOLD, FADE = 0.5, 0.5, 1.2, 0.4
APEX, APEX_PER_LEVEL, VICTORY_APEX = 10, 2, 14   # px
SLIDE_PER_WEEK = 0.12             # sliding along the floor, seconds per week
NAP, NAP_MIN = 1.2, 3             # nap length; gaps this many weeks or longer get a nap


def tile_xy(w: float, d: float) -> tuple[float, float]:
    """Top-left corner of the ground diamond for week w, weekday d."""
    return (w + d) * 8, (w - d) * 4


def ground(w: float, d: float) -> tuple[float, float]:
    """Ground point at the centre of (w, d); fractional values allowed."""
    x, y = tile_xy(w, d)
    return x + 8, y + 4


def lift(level: int) -> int:
    """How far the hero's feet sit above the floor when standing on this level."""
    return HEIGHTS[level] - HEIGHTS[0]


@dataclass(frozen=True)
class Hop:
    week: int
    weekday: int
    level: int        # level of the tile it lands on; 0 = floor
    takeoff: float
    land: float
    apex: int         # highest point of the feet above the floor, px


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


@dataclass(frozen=True)
class Timeline:
    moves: tuple      # every Hop / Slide / Nap in time order (victory hop excluded)
    hops: tuple       # the Hops of `moves`, in order
    victory: Hop      # the hop in place after the last week
    flag_day: tuple   # (week, weekday, level) the flag pops up on
    hop_end: float    # end of the last move: flag and LEVEL CLEAR appear
    reset_start: float  # lit tops start fading out
    period: float     # loop length


def _nearest(weekdays: list[int], target: float) -> int:
    """The weekday closest to target; ties go to the lower weekday."""
    return min(weekdays, key=lambda d: (abs(d - target), d))


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
