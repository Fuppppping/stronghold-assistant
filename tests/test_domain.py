from pathlib import Path
import unittest

from stronghold.domain import Hit, Reading, Season, alerts


class SeasonTests(unittest.TestCase):
    def setUp(self):
        self.season = Season()

    def test_multifaction_and_secondary_only_operators(self):
        self.assertIs(self.season.status("哈洛德", {"维多利亚": True, "谢拉格": False}), True)
        self.assertIs(self.season.status("哈洛德", {"维多利亚": True}, {"哈洛德"}), False)
        self.assertIsNone(self.season.status("摆渡人", {"坚守": False}))
        self.assertIs(self.season.status("摆渡人", {"坚守": False, "不屈": False}), False)
        self.assertIs(self.season.status("摆渡人", {"坚守": False, "不屈": True}), True)

    def test_disabled_lineup_ranks_below_confirmed_open_lineup(self):
        ranked = self.season.rank({"乌萨斯": False, "阿戈尔": True}, current=["塔露拉"])
        self.assertEqual(ranked[0]["id"], "egir")
        self.assertEqual(ranked[-1]["id"], "ursus")

    def test_manual_equipment_and_mute_take_precedence(self):
        item = Hit("装备", "聚合急救箱", (0, 0, 100, 30), .99)
        reading = Reading(scene="调度中心", hits=[item])
        self.assertEqual(alerts(reading, None, {item.name}, set(), {}, self.season),
                         [(item, "关注装备")])
        self.assertEqual(alerts(reading, None, {item.name}, {item.name}, {}, self.season), [])

    def test_example_guide_uses_current_catalogue(self):
        sample = Path(__file__).resolve().parent.parent / "guide.example.json"
        guide = self.season.add_guide(sample)
        self.assertEqual(guide["id"], "my-egir-guide")
        with self.assertRaises(ValueError):
            self.season.add_guide(sample)


if __name__ == "__main__":
    unittest.main()
