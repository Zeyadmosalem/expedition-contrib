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


TIES = make_cal({(0, 1): 2, (0, 5): 2, (1, 2): 3, (1, 6): 3, (3, 0): 1}, weeks=4)


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

    def test_empty_calendar_hops_the_floor(self):
        tl = RT.plan(make_cal({}, weeks=3))
        self.assertEqual([(h.weekday, h.level) for h in tl.hops], [(3, 0)] * 3)
        self.assertEqual(tl.flag_day, (2, 3, 0))

    def test_partial_week_floor_hop_uses_an_existing_weekday(self):
        tl = RT.plan(make_cal({}, weeks=1, weekdays=range(4, 7)))
        self.assertEqual(tl.hops[0].weekday, 4)

    def test_no_days_is_an_error(self):
        with self.assertRaisesRegex(ValueError, 'no days'):
            RT.plan(Calendar('t', 0, ()))

    def test_fixture_year(self):
        cal = contributions.parse(json.loads(FIXTURE.read_text(encoding='utf-8')), 'tester')
        tl = RT.plan(cal)
        self.assertEqual(len(tl.hops), cal.weeks)
        for h in tl.hops:
            week = [d for d in cal.active if d.week == h.week]
            if week:
                self.assertEqual(h.level, max(d.level for d in week))
                self.assertIn((h.weekday, h.level), {(d.weekday, d.level) for d in week})
            else:
                self.assertEqual(h.level, 0)
        self.assertGreater(tl.period, 15)
        self.assertLess(tl.period, 35)


if __name__ == '__main__':
    unittest.main()
