"""Tests for the Expedition contribution blaster (standard library unittest).

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
        cls.svgs = {theme: R.render(cls.cal, theme) for theme in R.THEMES}
        cls.roots = {theme: ET.fromstring(svg) for theme, svg in cls.svgs.items()}

    def blocks(self, theme):
        return self.roots[theme].find(f"{SVG}g[@id='blocks']").findall(f'{SVG}use')

    def bursts(self, theme):
        fx = self.roots[theme].find(f"{SVG}g[@id='fx']")
        return [g for g in fx.findall(f'{SVG}g') if g.find(f"{SVG}rect[@class='x f']") is not None]

    def bolts(self, theme):
        fx = self.roots[theme].find(f"{SVG}g[@id='fx']")
        return [g for g in fx.findall(f'{SVG}g') if g.find(f"{SVG}g[@class='x bo']") is not None]

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

    def test_every_active_day_gets_one_block_and_one_burst(self):
        active = self.cal.active
        self.assertGreater(len(active), 100)
        self.assertEqual(len(self.plan.shots), len(active))
        self.assertEqual({(s.week, s.weekday) for s in self.plan.shots},
                         {(d.week, d.weekday) for d in active})
        kills = sorted(round(s.kill, 3) for s in self.plan.shots)
        for theme in self.svgs:
            self.assertEqual(len(self.blocks(theme)), len(active))
            delays = sorted(float(re.search(r'--t:([\d.]+)s', g.get('style')).group(1))
                            for g in self.bursts(theme))
            self.assertEqual(delays, kills)

    def test_every_block_is_shot_and_rebuilt(self):
        svg = self.svgs['dark']
        for use in self.blocks('dark'):
            name = re.fullmatch(r'animation-name:(k\d+)', use.get('style')).group(1)
            frames = re.search(r'@keyframes %s\{(.*?\})\}' % name, svg).group(1)
            self.assertIn('opacity:0', frames)                   # shot down ...
            self.assertTrue(frames.endswith('to{opacity:1;transform:none}'))   # ... and rebuilt

    def test_blocks_are_hit_by_their_weeks_bolt_during_the_walk(self):
        tl = self.plan
        for s in tl.shots:
            self.assertGreaterEqual(s.kill, tl.fire[s.week])
            self.assertLessEqual(s.kill, tl.fire[s.week] + R.TRAVEL)
            self.assertLess(s.kill, tl.walk_end)
            self.assertGreater(s.drop, tl.walk_end)
            self.assertLess(s.drop + R.DROP, tl.period)
        for theme in self.svgs:
            self.assertEqual(len(self.bolts(theme)), len({s.week for s in tl.shots}))

    def test_bolts_fire_in_week_order(self):
        fire = [self.plan.fire[w] for w in range(self.cal.weeks)]
        self.assertEqual(fire, sorted(fire))

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
        root = ET.fromstring(R.render(cal, 'dark'))
        self.assertEqual(root.find(f"{SVG}g[@id='blocks']").findall(f'{SVG}use'), [])

    def test_hero_uses_the_skull_and_red_chest_light(self):
        hero = self.roots['dark'].find(f"{SVG}g[@id='hero']")
        fills = {p.get('fill') for p in hero.iter(f'{SVG}path')}
        self.assertIn('#eeeee6', fills)       # skull white
        self.assertIn('#de3442', fills)       # chest light
        self.assertIn('#120e1a', fills)       # INK outline
        self.assertEqual(len(hero.findall(f".//{SVG}g[@class]")), 2 + 4)   # hv, hm + 4 leg frames


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
