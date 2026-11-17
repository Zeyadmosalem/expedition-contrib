"""Tests for hero customization (character.toml, colours, picture heads)."""
from __future__ import annotations

import os
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest import mock

from contrib_hopper import character as C, contributions, pixels as px, render as R
from contrib_hopper.__main__ import OUTPUTS, main

FIXTURE = Path(__file__).parent / 'fixtures' / 'calendar.json'
SVG = '{http://www.w3.org/2000/svg}'
REPO = Path(__file__).resolve().parent.parent

try:
    from PIL import Image
except ImportError:          # picture heads are optional; colour tests still run
    Image = None


def hero_fills(svg: str) -> set:
    hero = ET.fromstring(svg).find(f"{SVG}g[@id='hero']")
    return {p.get('fill') for p in hero.iter(f'{SVG}path')}


def make_photo(path: Path, size=(40, 30)) -> None:
    """A tiny synthetic 'photo': warm face on a blue background, dark eyes."""
    im = Image.new('RGB', size, (40, 90, 200))
    w, h = size
    for y in range(h):
        for x in range(w):
            if (x - w / 2) ** 2 + (y - h / 2) ** 2 < (h / 2.4) ** 2:
                im.putpixel((x, y), (235, 190, 150))
    for ex in (w / 2 - 4, w / 2 + 4):
        for dx in (0, 1):
            for dy in (0, 1):
                im.putpixel((int(ex) + dx, int(h / 2 - 2) + dy), (20, 20, 20))
    im.save(path)


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.cal = contributions.load(str(FIXTURE), 'tester')

    def test_repo_character_toml_loads_and_renders(self):
        hero = C.load(REPO / 'character.toml')      # the user's file: any valid customization passes
        root = ET.fromstring(R.render(self.cal, 'dark', hero))
        self.assertEqual(root.tag, f'{SVG}svg')

    def test_suit_and_light_colours(self):
        hero = C.from_dict({'suit': '#961a2a', 'light': 'FFD060'})
        fills = hero_fills(R.render(self.cal, 'dark', hero))
        for new in ('#961a2a', '#ffd060'):
            self.assertIn(new, fills)
        for old in ('#24263e', '#de3442'):                    # Expedition defaults are gone
            self.assertNotIn(old, fills)
        self.assertIn('#eeeee6', fills)                       # the skull head is unchanged

    def test_optional_character_table(self):
        self.assertEqual(C.from_dict({'character': {'light': '#00ff00'}}).light, (0, 255, 0))

    def test_old_gun_setting_is_ignored(self):
        self.assertEqual(C.from_dict({'gun': '#3a3f55'}), C.Character())
        self.assertFalse(hasattr(C.Character(), 'gun'))
        with self.assertRaisesRegex(ValueError, r'expected head, light, suit\)'):
            C.from_dict({'hat': 'yes'})

    def test_bad_settings_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'hex colour'):
            C.from_dict({'suit': 'red'})
        with self.assertRaisesRegex(ValueError, 'unknown character setting'):
            C.from_dict({'hat': 'yes'})
        with self.assertRaisesRegex(ValueError, 'not found'):
            C.from_dict({'head': 'missing.png'}, Path(tempfile.gettempdir()))

    def test_cli_reads_character_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / 'hero.toml'
            cfg.write_text('suit = "#961a2a"\n', encoding='utf-8')
            with mock.patch('sys.stdout'):
                main(['--user', 'tester', '--input', str(FIXTURE), '--out', tmp, '--character', str(cfg)])
            for name in OUTPUTS.values():
                self.assertIn('#961a2a', hero_fills((Path(tmp) / name).read_text(encoding='utf-8')))

    def test_cli_uses_character_toml_in_the_working_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, 'character.toml').write_text('light = "#00ff00"\n', encoding='utf-8')
            cwd = os.getcwd()
            try:
                os.chdir(tmp)
                with mock.patch('sys.stdout'):
                    main(['--user', 'tester', '--input', str(FIXTURE), '--out', 'out'])
                svg = Path(tmp, 'out', OUTPUTS['dark']).read_text(encoding='utf-8')
            finally:
                os.chdir(cwd)
            self.assertIn('#00ff00', hero_fills(svg))


@unittest.skipIf(Image is None, 'Pillow is not installed')
class PictureHeadTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        make_photo(self.dir / 'photo.png')
        self.cal = contributions.load(str(FIXTURE), 'tester')

    def tearDown(self):
        self.tmp.cleanup()

    def test_head_is_round_posterized_and_outlined(self):
        head = C.head_from_image(self.dir / 'photo.png')
        self.assertEqual((head.w, head.h), (18, 18))
        for corner in ((1, 1), (16, 1), (1, 16), (16, 16)):
            self.assertNotIn(corner, head.px)                 # round: corners stay clear
        levels = {32, 96, 160, 224}
        for c in head.px.values():
            self.assertTrue(c == px.INK or set(c) <= levels, c)
        self.assertIn(px.INK, head.px.values())

    def test_picture_head_in_the_animation(self):
        hero = C.from_dict({'head': 'photo.png'}, self.dir)
        svg = R.render(self.cal, 'dark', hero)
        fills = hero_fills(svg)
        self.assertNotIn('#eeeee6', fills)                    # no skull white
        self.assertIn('#e0a0a0', fills)                       # posterized face colour
        landed = {h.week for h in R.plan(self.cal).hops if h.level > 0}
        self.assertEqual(landed, {d.week for d in self.cal.active})       # still lands on every busy week

    def test_saved_pixel_head_round_trips(self):
        out = self.dir / 'character.png'
        with mock.patch('sys.stdout'):
            self.assertEqual(C.main([str(self.dir / 'photo.png'), str(out)]), 0)
        with Image.open(out) as im:
            self.assertEqual(im.size, (18, 18))
        self.assertEqual(C.head_from_image(out).px, C.head_from_image(self.dir / 'photo.png').px)

    def test_unreadable_picture(self):
        bad = self.dir / 'not-a-picture.png'
        bad.write_text('hello', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'not a picture'):
            C.head_from_image(bad)


if __name__ == '__main__':
    unittest.main()
