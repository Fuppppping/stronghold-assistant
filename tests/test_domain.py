from pathlib import Path
import unittest

from stronghold.domain import Hit, MatchState, Reading, Season, alerts


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

    def test_strategy_recommendation_can_precede_lineup_selection(self):
        hit = Hit("策略", "变形同构", (10, 10, 50, 50), .98)
        states = {"伊比利亚": True, "叙拉古": False, "卡西米尔": False}
        guide = self.season.strategy_guide(self.season.rank(states), states, [hit])
        self.assertEqual(guide["id"], "iberia")
        reading = Reading(scene="策略轮选", hits=[hit])
        self.assertEqual(alerts(reading, None, set(), set(), states, self.season, strategy_guide=guide),
                         [(hit, "推荐策略 · 顺位 1")])

    def test_visible_shop_card_outweighs_an_inferred_ban(self):
        hit = Hit("干员", "深靛", (100, 200, 160, 225), .98)
        reading = Reading(scene="调度中心", hits=[hit])
        bans = {"伊比利亚": False}
        match = MatchState(auto=bans)
        match.observe(reading)
        self.assertIn("深靛", self.season.grouped(bans, seen=match.seen)["伊比利亚"])
        self.assertIn(hit, [item for item, _ in alerts(
            reading, self.season.lineups["iberia"], set(), set(), bans, self.season)])

    def test_example_guide_uses_current_catalogue(self):
        sample = Path(__file__).resolve().parent.parent / "guide.example.json"
        guide = self.season.add_guide(sample)
        self.assertEqual(guide["id"], "my-egir-guide")
        with self.assertRaises(ValueError):
            self.season.add_guide(sample)


class MatchStateTests(unittest.TestCase):
    def test_initial_panel_commits_before_the_next_frame(self):
        match = MatchState()
        match.observe(Reading(scene="盟约选择", verified_panel=True, setup=True,
                              groups=[{"炎", "伊比利亚"}, {"乌萨斯", "谢拉格"}], selected_group=0,
                              pacts={"精准": True}))
        self.assertEqual(match.states, {"炎": True, "伊比利亚": True, "乌萨斯": False,
                                        "谢拉格": False, "精准": True})

    def test_reopened_or_scrolled_panel_keeps_current_match(self):
        match = MatchState(auto={"炎": True}, manual={"助力": True}, excluded={"断罪者"}, played=True,
                           seen={"深靛"})
        match.observe(Reading(scene="盟约选择", verified_panel=True, pacts={"奥术": False}))
        self.assertEqual(match.states, {"炎": True, "助力": True, "奥术": False})
        self.assertEqual(match.excluded, {"断罪者"})
        self.assertEqual(match.seen, {"深靛"})

    def test_new_setup_clears_previous_match_only_when_verified(self):
        match = MatchState(auto={"炎": True}, manual={"助力": True}, played=True, seen={"深靛"})
        new = Reading(scene="盟约选择", setup=True, pacts={"乌萨斯": True})
        match.observe(new)
        self.assertIn("炎", match.states)
        match.observe(new)
        self.assertEqual(match.states, {"乌萨斯": True})
        self.assertEqual(match.seen, set())


if __name__ == "__main__":
    unittest.main()
