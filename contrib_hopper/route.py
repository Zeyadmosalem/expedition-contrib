"""Route and timing for the Block Hopper animation (pure maths, no SVG).

The hero starts on the catwalk in front of week 0 and makes one hop per
calendar week: onto that week's tallest block, or onto the floor when the week
is empty. After the last week it does a victory hop in place. All times are
seconds into one loop of the animation.
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
class Timeline:
    hops: tuple[Hop, ...]         # one Hop per calendar week, in week order
    victory: Hop                  # the hop in place after the last week
    flag_day: tuple[int, int, int]  # (week, weekday, level) the flag pops up on
    hop_end: float                # last weekly landing: flag and LEVEL CLEAR appear
    reset_start: float            # lit tops start fading out
    period: float                 # loop length


def _nearest(weekdays: list[int], target: float) -> int:
    """The weekday closest to target; ties go to the lower weekday."""
    return min(weekdays, key=lambda d: (abs(d - target), d))


def plan(cal: Calendar) -> Timeline:
    if not cal.days:
        raise ValueError('the contribution calendar has no days')
    by_week: dict[int, list[Day]] = {}
    for day in cal.days:
        by_week.setdefault(day.week, []).append(day)

    hops = []
    t, prev_level, prev_d = INTRO, 0, NO_LANDING
    for w in range(cal.weeks):
        days = by_week.get(w, [])
        active = [d for d in days if d.count > 0]
        if active:
            level = max(d.level for d in active)
            weekday = _nearest([d.weekday for d in active if d.level == level], prev_d)
        else:
            level = 0
            weekday = _nearest([d.weekday for d in days] or [prev_d], prev_d)
        if level == 0 and prev_level == 0:
            dur = FLOOR_HOP
        else:
            dur = HOP + HOP_PER_LEVEL * abs(level - prev_level)
        apex = max(lift(prev_level), lift(level)) + APEX + APEX_PER_LEVEL * max(0, level - prev_level)
        hops.append(Hop(w, weekday, level, t, t + dur, apex))
        t += dur + PAUSE
        prev_level, prev_d = level, weekday

    last = hops[-1]
    victory = Hop(last.week, last.weekday, last.level, t, t + VICTORY, lift(last.level) + VICTORY_APEX)
    reset_start = victory.land + OUTRO + HOLD
    if cal.active:
        best = max(cal.active, key=lambda d: (d.count, d.date))
        flag_day = (best.week, best.weekday, best.level)
    else:
        weekdays = [d.weekday for d in by_week.get(last.week, [])] or [NO_LANDING]
        flag_day = (last.week, _nearest(weekdays, NO_LANDING), 0)
    return Timeline(tuple(hops), victory, flag_day, last.land, reset_start, reset_start + FADE)
