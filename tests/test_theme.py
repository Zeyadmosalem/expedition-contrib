"""Tests for scene colours: presets and theme.toml (contrib_hopper.theme)."""
from __future__ import annotations

import os
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest import mock

from contrib_hopper import contributions, render as R
from contrib_hopper import theme as TH
from contrib_hopper.__main__ import OUTPUTS, main

REPO = Path(__file__).resolve().parent.parent
FIXTURE = Path(__file__).parent / 'fixtures' / 'calendar.json'


def rgb(h: str) -> tuple:
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


class PresetTests(unittest.TestCase):
    def test_default_preset_is_crimson_like_the_profile(self):
        self.assertEqual(TH.DEFAULT_PRESET, 'crimson')
        dark = TH.palettes()['dark']
        self.assertEqual(dark['levels'], [rgb('#5a1422'), rgb('#961a2a'), rgb('#d12a3c'), rgb('#ef4e5c')])
        self.assertEqual(dark['text'], rgb('#ef4e5c'))
        light = TH.palettes()['light']
        self.assertEqual(light['levels'], [rgb('#f4a7ae'), rgb('#ef4e5c'), rgb('#d12a3c'), rgb('#961a2a')])
        self.assertEqual(light['text'], rgb('#400e18'))

    def test_cyan_preset_is_the_original_look(self):
        cyan = TH.palettes('cyan')
        self.assertEqual(cyan['dark']['floor'], (24, 28, 46))
        self.assertEqual(cyan['dark']['levels'][3], (118, 236, 240))
        self.assertEqual(cyan['light']['floor'], (222, 228, 238))
        self.assertEqual(cyan['light']['catwalk'], (196, 202, 218))

    def test_every_preset_is_complete_and_ordered(self):
        for name in TH.PRESETS:
            pal = TH.palettes(name)
            self.assertEqual(list(pal), ['dark', 'light'])
            for theme in TH.THEMES:
                self.assertEqual(set(pal[theme]), set(TH.KEYS), (name, theme))
                self.assertEqual(len(pal[theme]['levels']), 4)
            dark = [sum(c) for c in pal['dark']['levels']]
            light = [sum(c) for c in pal['light']['levels']]
            self.assertEqual(dark, sorted(dark), name)                   # brighter when busier
            self.assertEqual(light, sorted(light, reverse=True), name)   # darker when busier

    def test_palettes_are_copies(self):
        pal = TH.palettes()
        pal['dark']['levels'][0] = (0, 0, 0)
        pal['dark']['floor'] = (1, 2, 3)
        self.assertEqual(TH.palettes()['dark']['levels'][0], rgb('#5a1422'))
        self.assertEqual(TH.palettes()['dark']['floor'], rgb('#160c10'))


class FileTests(unittest.TestCase):
    def test_empty_settings_mean_the_default_preset(self):
        self.assertEqual(TH.from_dict({}), TH.palettes())

    def test_repo_theme_toml_loads(self):
        pal = TH.load(REPO / 'theme.toml')          # the user's file: any valid customization passes
        self.assertEqual(list(pal), ['dark', 'light'])
        for theme in TH.THEMES:
            self.assertEqual(set(pal[theme]), set(TH.KEYS))

    def test_overrides_merge_on_top_of_the_preset(self):
        pal = TH.from_dict({'preset': 'cyan', 'dark': {
            'text': '#ffffff', 'levels': ['#010101', '#020202', '030303', '#040404']}})
        cyan = TH.palettes('cyan')
        self.assertEqual(pal['dark']['text'], (255, 255, 255))
        self.assertEqual(pal['dark']['levels'], [(1, 1, 1), (2, 2, 2), (3, 3, 3), (4, 4, 4)])
        self.assertEqual(pal['dark']['floor'], cyan['dark']['floor'])
        self.assertEqual(pal['light'], cyan['light'])

    def test_bad_settings_are_rejected(self):
        bad = [
            ({'colour': 'red'}, 'unknown theme setting'),
            ({'preset': 'neon'}, 'unknown theme preset'),
            ({'preset': 3}, 'preset'),
            ({'dark': 'red'}, r'\[dark\] must be a table'),
            ({'dark': {'sky': '#000000'}}, r'unknown colour\(s\) in \[dark\]'),
            ({'light': {'text': 'blue'}}, 'hex'),
            ({'light': {'text': '#12345'}}, 'hex'),
            ({'dark': {'levels': ['#000000'] * 3}}, 'four colours'),
            ({'dark': {'levels': '#000000'}}, 'four colours'),
        ]
        for data, message in bad:
            with self.subTest(data=data):
                with self.assertRaisesRegex(ValueError, message):
                    TH.from_dict(data)


class RenderThemeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cal = contributions.load(str(FIXTURE), 'tester')

    def test_default_render_is_crimson(self):
        self.assertEqual(R.THEMES, TH.palettes())
        self.assertIn('#ef4e5c', R.render(self.cal, 'dark'))

    def test_render_uses_the_given_palette(self):
        svg = R.render(self.cal, 'dark', palette=TH.palettes('cyan')['dark'])
        self.assertIn('#76ecf0', svg)          # cyan busiest level
        self.assertNotIn('#ef4e5c', svg)       # no crimson

    def test_cli_reads_a_theme_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / 'colours.toml'
            cfg.write_text('preset = "cyan"\n', encoding='utf-8')
            with mock.patch('sys.stdout'):
                main(['--user', 'tester', '--input', str(FIXTURE), '--out', tmp, '--theme', str(cfg)])
            dark = (Path(tmp) / OUTPUTS['dark']).read_text(encoding='utf-8')
            self.assertIn('#76ecf0', dark)
            ET.fromstring(dark)

    def test_cli_uses_theme_toml_in_the_working_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, 'theme.toml').write_text(
                '[dark]\nlevels = ["#111111", "#222222", "#333333", "#123456"]\n', encoding='utf-8')
            cwd = os.getcwd()
            try:
                os.chdir(tmp)
                with mock.patch('sys.stdout'):
                    main(['--user', 'tester', '--input', str(FIXTURE), '--out', 'out'])
                dark = Path(tmp, 'out', OUTPUTS['dark']).read_text(encoding='utf-8')
                light = Path(tmp, 'out', OUTPUTS['light']).read_text(encoding='utf-8')
            finally:
                os.chdir(cwd)
            self.assertIn('#123456', dark)
            self.assertNotIn('#123456', light)

    def test_cli_rejects_a_bad_theme_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / 'bad.toml'
            cfg.write_text('preset = "neon"\n', encoding='utf-8')
            with mock.patch('sys.stdout'), self.assertRaisesRegex(ValueError, 'unknown theme preset'):
                main(['--user', 'tester', '--input', str(FIXTURE), '--out', tmp, '--theme', str(cfg)])


if __name__ == '__main__':
    unittest.main()
