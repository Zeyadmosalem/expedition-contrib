"""Tests for the Block Hopper sprites in contrib_hopper.pixels."""
from __future__ import annotations

import unittest

from contrib_hopper import pixels as px


class SpriteTests(unittest.TestCase):
    def test_stand_and_jump_poses(self):
        poses = px.hero_poses()
        stand, jump = poses.stand, poses.jump
        self.assertEqual((stand.w, stand.h), (jump.w, jump.h))
        for pose in (stand, jump):
            colours = set(pose.px.values())
            self.assertIn(px.COLORS['W'], colours)          # skull white
            self.assertIn(px.COLORS['r'], colours)          # chest light
            self.assertNotIn(px.COLORS['g'], colours)       # no gun
        feet = lambda r: max(y for (x, y), c in r.px.items() if c == px.COLORS['b'])
        self.assertEqual(feet(stand), stand.h - 1)          # feet on the bottom row
        self.assertLess(feet(jump), feet(stand))            # feet tucked up in the air

    def test_slide_pose_is_a_wide_low_stance(self):
        poses = px.hero_poses()
        stand, slide = poses.stand, poses.slide
        self.assertEqual((slide.w, slide.h), (stand.w, stand.h))
        feet = lambda r: [(x, y) for (x, y), c in r.px.items() if c == px.COLORS['b']]
        self.assertEqual(max(y for x, y in feet(slide)), slide.h - 1)            # feet on the floor
        self.assertLess(min(x for x, y in feet(slide)), min(x for x, y in feet(stand)))
        self.assertGreater(max(x for x, y in feet(slide)), max(x for x, y in feet(stand)))

    def test_sleep_pose_is_the_stand_pose_lying_down(self):
        poses = px.hero_poses()
        stand, sleep = poses.stand, poses.sleep
        self.assertEqual((sleep.w, sleep.h), (stand.h, stand.w))
        self.assertEqual(sorted(sleep.px.values()), sorted(stand.px.values()))
        r = stand
        for _ in range(4):
            r = px.rotate_cw(r)
        self.assertEqual(r.px, stand.px)                                         # four turns = start
        self.assertEqual(px.rotate_cw(stand).px, sleep.px)

    def test_zee_and_dust_puff(self):
        c = (240, 220, 230)
        z = px.zee(c)
        self.assertEqual((z.w, z.h), (6, 6))
        self.assertIn(c, z.px.values())
        self.assertIn(px.INK, z.px.values())
        p = px.puff(c)
        self.assertEqual((p.w, p.h), (4, 3))
        self.assertEqual(len(p.px), 8)
        self.assertEqual(set(p.px.values()), {c})

    def test_blaster_sprites_are_gone(self):
        for name in ('gun', 'GUN', 'hero_frames', 'LEGS'):
            self.assertFalse(hasattr(px, name), name)

    def test_coin_spins_between_two_frames(self):
        gold = px.COIN_COLORS['y']
        face, edge = px.coin(0), px.coin(1)
        self.assertEqual((face.w, face.h), (8, 9))
        self.assertEqual((edge.w, edge.h), (8, 9))
        width = lambda r: len({x for (x, y), c in r.px.items() if c == gold})
        self.assertGreater(width(face), width(edge))
        self.assertIn(px.INK, face.px.values())

    def test_flag_has_a_pole_and_pennant(self):
        red = (240, 80, 90)
        f = px.flag(red)
        self.assertEqual((f.w, f.h), (7, 14))
        self.assertIn(red, f.px.values())
        for y in range(1, 13):
            self.assertEqual(f.px[(1, y)], px.COLORS['W'])

    def test_lit_top_covers_just_the_top_diamond(self):
        c = (255, 214, 92)
        lit = px.lit_top(c)
        self.assertEqual((lit.w, lit.h), (18, 10))
        self.assertEqual(len(lit.px), 64)                    # 2+6+10+14+14+10+6+2
        block = px.iso_block(7, (1, 1, 1), (2, 2, 2), (3, 3, 3))
        self.assertLessEqual(set(lit.px), set(block.px))     # same frame as a block
        self.assertTrue(all(1 <= y <= 8 for x, y in lit.px))
        self.assertIn(c, lit.px.values())


if __name__ == '__main__':
    unittest.main()
