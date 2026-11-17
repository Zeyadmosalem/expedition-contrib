"""Tests for the Expedition contribution Block Hopper (standard library unittest).

Run with:  python -m unittest discover -s tests -v
"""
from __future__ import annotations

import copy
import json
import re
import tempfile
import unittest
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest import mock

from contrib_hopper import contributions, render as R
from contrib_hopper.contributions import Calendar, Day
from contrib_hopper.route import LANE_D, START_W, Nap, Slide, ground
from contrib_hopper.__main__ import OUTPUTS, main

FIXTURE = Path(__file__).parent / 'fixtures' / 'calendar.json'
SVG = '{http://www.w3.org/2000/svg}'


def fixture_payload() -> dict:
    return json.loads(FIXTURE.read_text(encoding='utf-8'))


def with_days(payload: dict, fn) -> dict:
    """Copy of payload with fn(day) applied to every contribution day."""
    p = copy.deepcopy(payload)
    for week in p['data']['user']['contributionsCollection']['contributionCalendar']['weeks']:
        for day in week['contributionDays']:
            fn(day)
    return p


def gappy() -> Calendar:
    """Blocks in weeks 0, 2, 6, 7; empty weeks 1, 3-5 (a nap) and 8-9."""
    levels = {(0, 2): 2, (2, 3): 1, (6, 1): 4, (7, 1): 1}
    days = [Day(f'2026-w{w:02d}-{d}', levels.get((w, d), 0) * 3, levels.get((w, d), 0), w, d)
            for w in range(10) for d in range(7)]
    return Calendar('gappy', sum(x.count for x in days), tuple(days))


def pose_track(frames: str) -> list:
    """[(percent, opacity)] from step-timed opacity keyframes."""
    return sorted((float(p), int(o)) for p, o in re.findall(r'([\d.]+)%\{opacity:([01])\}', frames))


class ParseTests(unittest.TestCase):
    def setUp(self):
        self.cal = contributions.parse(fixture_payload(), 'tester')

    def test_fixture_shape(self):
        self.assertEqual(self.cal.weeks, 53)
        self.assertEqual(len(self.cal.days), 367)            # 2025-11-16 .. 2026-11-17
        self.assertEqual(self.cal.days[0].weekday, 0)        # calendar weeks start on Sunday
        self.assertEqual(self.cal.total, sum(d.count for d in self.cal.days))
        self.assertTrue(all(0 <= d.weekday <= 6 for d in self.cal.days))

    def test_active_days_have_a_level(self):
        for d in self.cal.days:
            self.assertEqual(d.level > 0, d.count > 0, d)

    def test_partial_first_week_keeps_weekday_rows(self):
        payload = fixture_payload()
        weeks = payload['data']['user']['contributionsCollection']['contributionCalendar']['weeks']
        weeks[0]['contributionDays'] = weeks[0]['contributionDays'][3:]   # starts on a Wednesday
        cal = contributions.parse(payload)
        self.assertEqual(cal.days[0].weekday, 3)
        self.assertEqual(cal.days[0].week, 0)

    def test_levels_derived_when_missing(self):
        cal = contributions.parse(with_days(fixture_payload(), lambda d: d.pop('contributionLevel')))
        self.assertTrue(all((d.level > 0) == (d.count > 0) for d in cal.days))
        self.assertEqual({d.level for d in cal.active}, {1, 2, 3, 4})

    def test_api_errors_are_reported(self):
        with self.assertRaisesRegex(ValueError, 'Bad credentials'):
            contributions.parse({'errors': [{'message': 'Bad credentials'}]})
        with self.assertRaisesRegex(ValueError, 'not found'):
            contributions.parse({'data': {'user': None}}, 'ghost')


class FetchTests(unittest.TestCase):
    def test_token_only_in_authorization_header(self):
        seen = {}

        class Resp:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def read(self): return json.dumps(fixture_payload()).encode()

        def fake_urlopen(req, timeout):
            seen['req'] = req
            return Resp()

        with mock.patch.object(urllib.request, 'urlopen', fake_urlopen):
            payload = contributions.fetch('octocat', 'secret-token-123')
        req = seen['req']
        self.assertEqual(req.get_header('Authorization'), 'bearer secret-token-123')
        self.assertNotIn('secret-token-123', req.full_url)
        self.assertNotIn(b'secret-token-123', req.data)
        self.assertEqual(json.loads(req.data)['variables'], {'login': 'octocat'})
        self.assertIn('contributionCalendar', json.loads(req.data)['query'])
        self.assertIn('data', payload)

    def test_missing_token(self):
        with self.assertRaises(ValueError):
            contributions.fetch('octocat', '')


class RenderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cal = contributions.parse(fixture_payload(), 'tester')
        cls.plan = R.plan(cls.cal)
        cls.landed = [h for h in cls.plan.hops if h.level > 0]
        cls.svgs = {theme: R.render(cls.cal, theme) for theme in R.THEMES}
        cls.roots = {theme: ET.fromstring(svg) for theme, svg in cls.svgs.items()}

    def pct(self, t):
        return f'{t / self.plan.period * 100:.3f}'.rstrip('0').rstrip('.')

    def blocks(self, theme):
        return self.roots[theme].find(f"{SVG}g[@id='blocks']").findall(f'{SVG}g')

    def lit(self, theme):
        return [u for g in self.blocks(theme) for u in g.findall(f'{SVG}use') if u.get('class') == 'lt']

    def keyframes(self, svg, name):
        return re.search(r'@keyframes %s\{(.*?\})\}' % name, svg).group(1)

    def test_both_themes_are_well_formed_svg(self):
        self.assertEqual(set(self.svgs), {'light', 'dark'})
        for theme, root in self.roots.items():
            self.assertEqual(root.tag, f'{SVG}svg', theme)
            self.assertEqual(len(root.get('viewBox').split()), 4)
            self.assertIn('tester', root.find(f'{SVG}title').text)
        self.assertNotEqual(self.svgs['light'], self.svgs['dark'])

    def test_no_javascript(self):
        for svg in self.svgs.values():
            self.assertNotIn('<script', svg)
            self.assertNotRegex(svg, r'\son[a-z]+=')

    def test_no_blaster_leftovers(self):
        for svg in self.svgs.values():
            self.assertNotIn('bolt', svg)
            self.assertNotIn('SECTOR CLEAR', svg)
            self.assertIn('LEVEL CLEAR', svg)
            self.assertLess(len(svg), 200_000)

    def test_every_active_day_gets_one_block(self):
        active = self.cal.active
        self.assertGreater(len(active), 100)
        for theme in self.svgs:
            groups = self.blocks(theme)
            self.assertEqual(len(groups), len(active))
            refs = sorted(g.find(f'{SVG}use').get('href') for g in groups)
            self.assertEqual(refs, sorted(f'#b{d.level}' for d in active))

    def test_landed_blocks_squash_and_the_rest_bounce(self):
        svg = self.svgs['dark']
        moves = [self.keyframes(svg, re.fullmatch(r'animation-name:(k\d+)', g.get('style')).group(1))
                 for g in self.blocks('dark')]
        self.assertEqual(sum('scale(' in m for m in moves), len(self.landed))
        self.assertEqual(sum('translateY(-2px)' in m for m in moves), len(self.cal.active) - len(self.landed))
        self.assertTrue(all(m.endswith('to{transform:none}') for m in moves))

    def test_landed_blocks_light_up_at_landing_and_reset(self):
        svg = self.svgs['dark']
        self.assertEqual(len(self.lit('dark')), len(self.landed))
        on = sorted(re.findall(r'@keyframes t\d+\{0%,([\d.]+)%\{opacity:0\}', svg), key=float)
        self.assertEqual(on, sorted((self.pct(h.land) for h in self.landed), key=float))
        for u in self.lit('dark'):
            frames = self.keyframes(svg, re.fullmatch(r'animation-name:(t\d+)', u.get('style')).group(1))
            self.assertIn('opacity:1', frames)
            self.assertTrue(frames.endswith('to{opacity:0}'))

    def test_one_coin_per_block_landing(self):
        for theme in self.svgs:
            coins = self.roots[theme].find(f"{SVG}g[@id='fx']").findall(f".//{SVG}g[@class='x cn']")
            delays = sorted(float(re.search(r'--t:([\d.]+)s', g.get('style')).group(1)) for g in coins)
            self.assertEqual(delays, sorted(round(h.land, 3) for h in self.landed))

    def test_flag_on_busiest_day(self):
        best = max(self.cal.active, key=lambda d: (d.count, d.date))
        self.assertEqual(self.plan.flag_day, (best.week, best.weekday, best.level))
        flags = self.roots['dark'].find(f"{SVG}g[@id='fx']").findall(f"{SVG}use[@class='fg']")
        self.assertEqual(len(flags), 1)
        self.assertAlmostEqual(float(flags[0].get('x')), ground(best.week, best.weekday)[0] - 1, places=2)

    def test_hero_reaches_every_apex_and_landing(self):
        svg = self.svgs['dark']
        hy = self.keyframes(svg, 'hy')
        for h in (*self.plan.hops, self.plan.victory):
            self.assertIn(f'translateY(-{h.apex}px)', hy)
            self.assertIn(f'{self.pct(h.land)}%', hy)
        self.assertEqual(self.keyframes(svg, 'ps').count('opacity:0'), len(self.plan.moves) + 1)

    def test_empty_days_get_floor_only(self):
        floor = self.roots['dark'].find(f"{SVG}g[@id='floor']").findall(f"{SVG}use[@href='#f']")
        self.assertEqual(len(floor), len(self.cal.days))

    def test_busier_days_are_taller_and_brighter(self):
        self.assertEqual(list(R.HEIGHTS), sorted(set(R.HEIGHTS)))
        lum = [sum(c) for c in R.THEMES['dark']['levels']]
        self.assertEqual(lum, sorted(lum))                      # brighter on the dark page
        ink = [sum(c) for c in R.THEMES['light']['levels']]
        self.assertEqual(ink, sorted(ink, reverse=True))        # stronger on the light page

    def test_empty_calendar_still_renders(self):
        cal = contributions.parse(with_days(fixture_payload(), lambda d: d.update(
            contributionCount=0, contributionLevel='NONE')))
        svg = R.render(cal, 'dark')
        root = ET.fromstring(svg)
        self.assertEqual(root.find(f"{SVG}g[@id='blocks']").findall(f'{SVG}g'), [])
        self.assertEqual(len(root.find(f"{SVG}g[@id='fx']").findall(f"{SVG}use[@class='fg']")), 1)
        self.assertIn('LEVEL CLEAR', svg)

    def test_hero_uses_the_skull_and_red_chest_light(self):
        hero = self.roots['dark'].find(f"{SVG}g[@id='hero']")
        fills = {p.get('fill') for p in hero.iter(f'{SVG}path')}
        self.assertIn('#eeeee6', fills)       # skull white
        self.assertIn('#de3442', fills)       # chest light
        self.assertIn('#120e1a', fills)       # INK outline
        self.assertNotIn('#787e92', fills)    # no gun
        classes = {g.get('class') for g in hero.findall(f".//{SVG}g[@class]")}
        self.assertEqual(classes, {'hv', 'hx', 'hy', 'ps', 'pj', 'pl', 'pz'})

    def test_reduced_motion_gets_a_still_frame(self):
        for svg in self.svgs.values():
            self.assertIn('@media (prefers-reduced-motion:reduce){*{animation:none!important}', svg)


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


class CliTests(unittest.TestCase):
    def test_writes_light_and_dark_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch('sys.stdout'):
                self.assertEqual(main(['--user', 'tester', '--input', str(FIXTURE), '--out', tmp]), 0)
            for name in OUTPUTS.values():
                root = ET.parse(Path(tmp) / name).getroot()
                self.assertEqual(root.tag, f'{SVG}svg')


if __name__ == '__main__':
    unittest.main()
