import json
from pathlib import Path
import tempfile
import unittest

from stronghold.domain import Hit, MatchState, Reading, Season, alerts
from stronghold.stock import Holding, StockLedger
from stronghold.vision import Line, Recognizer


class EvidenceTests(unittest.TestCase):
    def test_first_pact_frame_provides_named_bans(self):
        season, match = Season(), MatchState()
        match.observe(Reading(scene="盟约选择", setup=True, verified_panel=True,
                              pacts={"伊比利亚": False, "乌萨斯": True}))
        banned = season.banned(match.states)
        self.assertEqual(banned["深靛"], "盟约推算")
        self.assertNotIn("塔露拉", banned)
        match.observe(Reading(scene="盟约选择", verified_panel=True, excluded={"塔露拉"}))
        self.assertEqual(season.banned(match.states, match.excluded)["塔露拉"], "名单识别")
        self.assertIn("深靛", season.banned(match.states, match.excluded))

    def test_restart_after_strategy_resets_all_match_evidence(self):
        match = MatchState(auto={"炎": True}, manual={"助力": False}, excluded={"矩"}, seen={"塔露拉"})
        match.stock.observe("队友1", [Holding("棘刺", elite=1)])
        match.observe(Reading(scene="策略轮选"))
        match.observe(Reading(scene="盟约选择", setup=True, verified_panel=True, pacts={"阿戈尔": True}))
        self.assertEqual(match.states, {"阿戈尔": True})
        self.assertEqual(match.excluded, set())
        self.assertEqual(match.seen, set())
        self.assertEqual(match.stock.players, {})
        match.manual["精准"] = True
        match.observe(Reading(scene="盟约选择", setup=True, verified_panel=True, pacts={"奥术": False}))
        self.assertTrue(match.states["精准"])

    def test_menu_boundary_needs_two_frames_and_resets_once(self):
        match = MatchState(auto={"炎": True})
        menu = Reading(reset_hint=True)
        match.observe(menu)
        self.assertIn("炎", match.states)
        match.observe(menu)
        epoch = match.epoch
        self.assertEqual(match.states, {})
        match.observe(menu)
        self.assertEqual(match.epoch, epoch)

    def test_stock_replaces_each_player_and_never_counts_shop_offers(self):
        match = MatchState()
        match.observe(Reading(scene="队友阵容", roster_slot="队友1", holdings=[Holding("棘刺", elite=1)]))
        match.observe(Reading(scene="队友阵容", roster_slot="队友1", holdings=[Holding("棘刺", elite=1)]))
        match.stock.observe("自己", [Holding("棘刺", normal=2)])
        match.observe(Reading(scene="调度中心", hits=[Hit("干员", "棘刺", (0, 0, 10, 10), .99)]))
        self.assertEqual(match.stock.occupied("棘刺"), 5)
        self.assertEqual(match.stock.estimate("棘刺", 10), "估算余量 0–5 · 自设总池 10")
        self.assertIn("总池待核实", match.stock.estimate("棘刺"))
        self.assertIn("记录冲突", match.stock.estimate("棘刺", 3))
        match.observe(Reading(scene="队友阵容", roster_slot="队友1", holdings=[]))
        self.assertEqual(match.stock.occupied("棘刺"), 5)

    def test_star_special_merge_and_unclear_elite_is_lower_bound(self):
        ledger = StockLedger()
        ledger.observe("队友1", [Holding("星极", normal=1, elite=1), Holding("塔露拉", uncertain=2)])
        self.assertEqual(ledger.occupied("星极"), 3)
        self.assertEqual(ledger.occupied("塔露拉"), 2)
        self.assertTrue(ledger.uncertain("塔露拉"))

    def test_manual_rank_correction_survives_head_only_refresh_and_reset(self):
        match = MatchState()
        match.stock.observe("面板1", [Holding("棘刺", uncertain=1)])
        match.stock.correct("面板1", Holding("棘刺", elite=1))
        match.stock.observe("面板1", [Holding("棘刺", uncertain=1)])
        self.assertEqual(match.stock.occupied("棘刺"), 3)
        match.clear()
        self.assertEqual(match.stock.manual, {})

    def test_all_built_in_guides_pass_the_import_contract(self):
        season = Season()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'guide.json'
            for guide in list(season.lineups.values()):
                imported = dict(guide, id='copy-'+guide['id'])
                path.write_text(json.dumps(imported, ensure_ascii=False), encoding='utf8')
                self.assertEqual(season.add_guide(path)['id'], imported['id'])

    def test_roster_ocr_tracks_individual_duplicates_with_nearby_rank(self):
        recognizer = object.__new__(Recognizer)
        recognizer.roster_names = {"棘刺": "棘刺", "星极": "星极"}
        lines = [Line("棘刺", (400, 100, 450, 120), .99), Line("精锐", (400, 125, 450, 140), .99),
                 Line("棘刺", (600, 100, 650, 120), .99), Line("星极", (800, 100, 850, 120), .7)]
        hits, holdings = recognizer.read_holdings(lines)
        self.assertEqual(len(hits), 2)
        self.assertEqual(holdings, [Holding("棘刺", elite=1, uncertain=1)])

    def test_stack_alert_roles_and_extended_guide_validation(self):
        season = Season()
        guide = season.lineups["iberia"]
        reading = Reading(scene="调度中心", hits=[Hit("干员", name, (i*100, 200, i*100+50, 230), .99)
                                                  for i, name in enumerate(("旅骨", "深靛"))])
        notes = {hit.name: note for hit, note in alerts(reading, guide, set(), set(), {}, season)}
        self.assertTrue(notes["旅骨"].startswith("核心叠层"))
        self.assertTrue(notes["深靛"].startswith("可用叠层"))
        sample = json.loads((Path(__file__).resolve().parent.parent/'guide.example.json').read_text(encoding='utf8'))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'guide.json'
            sample['stacking'][0]['operator'] = []
            path.write_text(json.dumps(sample), encoding='utf8')
            with self.assertRaisesRegex(ValueError, 'stacking'):
                season.add_guide(path)


if __name__ == '__main__':
    unittest.main()
