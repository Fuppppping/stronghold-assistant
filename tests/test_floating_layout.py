import unittest

from stronghold.floating_layout import Placement, HEADER, fit


class FloatingLayoutTests(unittest.TestCase):
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
