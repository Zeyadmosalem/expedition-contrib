"""Tests for the Block Hopper route and timing (contrib_hopper.route)."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from contrib_hopper import contributions
from contrib_hopper import route as RT
from contrib_hopper.contributions import Calendar, Day

FIXTURE = Path(__file__).parent / 'fixtures' / 'calendar.json'


def make_cal(levels: dict, weeks: int, weekdays=range(7)) -> Calendar:
    """Synthetic calendar: levels maps (week, weekday) -> level; count = 3 * level."""
    days = []
    for w in range(weeks):
        for d in weekdays:
            lv = levels.get((w, d), 0)
            days.append(Day(f'2026-w{w:02d}-{d}', lv * 3, lv, w, d))
    return Calendar('t', sum(x.count for x in days), tuple(days))


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


TIES = make_cal({(0, 1): 2, (0, 5): 2, (1, 2): 3, (1, 6): 3, (3, 0): 1}, weeks=4)
# blocks in weeks 0, 2, 6, 7; gaps: week 1 (k=1), weeks 3-5 (k=3, nap at 4), weeks 8-9 (k=2, at the end)
GAPS = make_cal({(0, 2): 2, (2, 3): 1, (6, 1): 4, (7, 1): 1}, weeks=10)


class RouteTests(unittest.TestCase):
    def test_one_hop_per_week_in_order(self):
        tl = RT.plan(TIES)
        self.assertEqual([h.week for h in tl.hops], [0, 1, 2, 3])

    def test_targets_and_tie_breaks(self):
        # week 0: level-2 at weekdays 1 and 5, both 2 away from 3 -> lower weekday 1
        # week 1: level-3 at 2 and 6, nearest to 1 -> 2
        # week 2: empty -> floor at the previous weekday 2
        # week 3: only (3, 0) -> weekday 0
        tl = RT.plan(TIES)
        self.assertEqual([(h.week, h.weekday, h.level) for h in tl.hops],
                         [(0, 1, 2), (1, 2, 3), (2, 2, 0), (3, 0, 1)])

    def test_hop_durations(self):
        tl = RT.plan(TIES)
        durations = [h.land - h.takeoff for h in tl.hops]
        expected = [RT.HOP + RT.HOP_PER_LEVEL * n for n in (2, 1, 3, 1)]
        for got, want in zip(durations, expected):
            self.assertAlmostEqual(got, want)
        floor = RT.plan(make_cal({}, weeks=3))
        for h in floor.hops:
            self.assertAlmostEqual(h.land - h.takeoff, RT.FLOOR_HOP)

    def test_apex_clears_both_ends(self):
        tl = RT.plan(TIES)
        self.assertEqual(tl.hops[0].apex, 19)      # floor -> level 2: lift 5 + 10 + 2 per level climbed
        self.assertEqual(tl.hops[2].apex, 18)      # level 3 -> floor: lift 8 + 10, no climb bonus
        prev = 0
        for h in tl.hops:
            self.assertGreater(h.apex, max(RT.lift(prev), RT.lift(h.level)))
            prev = h.level

    def test_timeline_is_ordered(self):
        tl = RT.plan(TIES)
        self.assertAlmostEqual(tl.hops[0].takeoff, RT.INTRO)
        for a, b in zip(tl.hops, tl.hops[1:]):
            self.assertLess(a.takeoff, a.land)
            self.assertAlmostEqual(b.takeoff, a.land + RT.PAUSE)
        v = tl.victory
        self.assertEqual((v.week, v.weekday, v.level), (3, 0, 1))
        self.assertAlmostEqual(v.takeoff, tl.hops[-1].land + RT.PAUSE)
        self.assertAlmostEqual(v.land, v.takeoff + RT.VICTORY)
        self.assertEqual(v.apex, RT.lift(1) + RT.VICTORY_APEX)
        self.assertEqual(tl.hop_end, tl.hops[-1].land)
        self.assertAlmostEqual(tl.reset_start, v.land + RT.OUTRO + RT.HOLD)
        self.assertAlmostEqual(tl.period, tl.reset_start + RT.FADE)

    def test_flag_on_busiest_day_latest_date_wins_ties(self):
        # (1, 2) and (1, 6) both have the top count 9; '2026-w01-6' is the later date
        self.assertEqual(RT.plan(TIES).flag_day, (1, 6, 3))

    def test_partial_week_floor_hop_uses_an_existing_weekday(self):
        tl = RT.plan(make_cal({}, weeks=1, weekdays=range(4, 7)))
        self.assertEqual(tl.hops[0].weekday, 4)

    def test_no_days_is_an_error(self):
        with self.assertRaisesRegex(ValueError, 'no days'):
            RT.plan(Calendar('t', 0, ()))

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


if __name__ == '__main__':
    unittest.main()
