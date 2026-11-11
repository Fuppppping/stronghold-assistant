import tkinter as tk
import unittest

from stronghold.domain import Hit
from stronghold.overlay import Overlay


class OverlayLayoutTests(unittest.TestCase):
    def test_compact_rail_reserves_top_and_battlefield_at_all_resolutions(self):
        root = tk.Tk()
        root.withdraw()
        overlay = Overlay(root)
        banner = "\n".join(["当前攻略  伊比利亚 · 精奥 / 迅捷", "思路  " + "长攻略" * 100,
                             "核心叠层  棘刺、旅骨、引星棘刺", "可用叠层  深靛、流明、温蒂"])
        hits = [(Hit("干员", "战场干员", (500, 300, 560, 340), .99), "核心叠层"),
                (Hit("干员", "深靛", (900, 600, 1000, 630), .99), "可用叠层 · 详细说明")]
        try:
            for width, height in ((1280, 720), (1920, 1080), (3840, 2160)):
                overlay.draw(width, height, (1280, 720), hits, banner, "调度中心")
                root.update_idletasks()
                plan = overlay.canvas.bbox("plan")
                self.assertGreaterEqual(plan[0], 0)
                self.assertLess(plan[2], width * .16)
                self.assertGreater(plan[1], height * .18)
                self.assertLess(plan[3], height * .46)
                all_items = overlay.canvas.bbox("all")
                self.assertGreaterEqual(all_items[1], height * .18)
                texts = [overlay.canvas.itemcget(item, "text") for item in overlay.canvas.find_all()
                         if overlay.canvas.type(item) == "text"]
                self.assertFalse(any("战场干员" in text for text in texts))
                self.assertTrue(any("深靛" in text for text in texts))
                self.assertLess(all_items[2], width)
                self.assertFalse(any(overlay.canvas.type(item) == "polygon" for item in overlay.canvas.find_all()))
        finally:
            root.destroy()
