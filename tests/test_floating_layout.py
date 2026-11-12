import unittest

from stronghold.floating_layout import Placement, HEADER, fit, snap, follow


class FloatingLayoutTests(unittest.TestCase):
    def test_follow_preserves_offset_and_docked_edges_during_resize(self):
        p = Placement(x=10,y=100,width=400,height=500)
        moved = follow(p,(0,0,1280,720),(80,40,1360,760))
        self.assertEqual((moved.x,moved.y),(90,140))
        p = Placement(x=864,y=162,width=400,height=500)
        moved = follow(p,(0,0,1280,720),(80,40,1680,940))
        self.assertEqual((moved.x,moved.y),(1264,382))

    def test_snap_does_not_pull_distant_panels_and_supports_outside_docking(self):
        bounds = (100,100,1380,820)
        self.assertEqual(snap(Placement(x=108,y=107),bounds).x,100)
        self.assertEqual(snap(Placement(x=108,y=107),bounds).y,100)
        self.assertEqual(snap(Placement(x=-294,y=180),bounds).x,-300)
        self.assertEqual(snap(Placement(x=400,y=400),bounds).x,400)

    def test_behavior_preferences_keep_backward_compatible_defaults(self):
        p = Placement.load({'x':24,'y':180})
        self.assertTrue(p.follow_game and p.auto_compact and p.snap_edges)
        p = Placement.load({'follow_game':False,'auto_compact':False,'snap_edges':False})
        self.assertFalse(p.follow_game or p.auto_compact or p.snap_edges)
        self.assertEqual(Placement.load(p.dump()),p)

    def test_unplugged_monitor_recovers_whole_panel_to_work_area(self):
        p = fit(Placement(x=9000,y=-2000,width=500,height=700),[(0,0,1920,1040)])
        self.assertGreaterEqual(p.x,0)
        self.assertGreaterEqual(p.y,0)
        self.assertLessEqual(p.x+p.width,1920)
        self.assertLessEqual(p.y+HEADER+p.height,1040)

    def test_negative_monitor_is_preserved_and_desktop_gaps_are_avoided(self):
        areas = [(-1920,-400,0,640),(0,0,1920,1040)]
        p = fit(Placement(x=-1800,y=-300,width=400,height=500),areas)
        self.assertEqual((p.x,p.y),(-1800,-300))
        p = fit(Placement(x=-700,y=900),areas)
        self.assertGreaterEqual(p.y,-400)
        self.assertLessEqual(p.y+HEADER+p.height,640)

    def test_bad_saved_preferences_are_ignored_and_size_is_bounded(self):
        p = Placement.load({'x':'offscreen','width':True,'height':99999,'locked':'yes','opacity':float('nan')})
        self.assertEqual(p,Placement())
        p = fit(Placement(width=9999,height=9999),[(0,0,1280,680)])
        self.assertEqual(p.width,640)
        self.assertLessEqual(p.y+HEADER+p.height,680)
        self.assertEqual(Placement.load(p.dump()),p)

    def test_collapsed_header_stays_recoverable_after_expand(self):
        p = fit(Placement(y=1000,collapsed=True),[(0,0,1920,1040)])
        self.assertLessEqual(p.y+HEADER,1040)
        p.collapsed = False
        p = fit(p,[(0,0,1920,1040)])
        self.assertLessEqual(p.y+HEADER+p.height,1040)
