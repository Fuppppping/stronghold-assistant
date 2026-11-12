import unittest
from unittest.mock import patch

from stronghold.stock import Holding, StockLedger


class StockFreshnessTests(unittest.TestCase):
    def setUp(self):
        self.now = 100.0
        self.clock = patch('stronghold.stock.time.time',side_effect=lambda:self.now)
        self.clock.start()
        self.addCleanup(self.clock.stop)
        self.ledger = StockLedger(own_slot='面板1')

    def test_correcting_one_card_does_not_renew_old_cards_or_pool_estimates(self):
        self.ledger.observe('面板1',[Holding('旅骨',normal=1),Holding('深靛',normal=1)])
        self.now = 131
        self.ledger.correct('面板1',Holding('旅骨',elite=1))
        self.assertEqual(self.ledger.players['面板1'].updated,100)
        self.assertEqual(self.ledger.own_names(),frozenset({'旅骨'}))
        view = self.ledger.view()
        self.assertEqual(view.amount('深靛'),'1（含旧记录）')
        self.assertIn('已过期',view.note('深靛'))
        self.assertIn('过期',view.estimate('深靛',10))

    def test_automatic_frame_does_not_renew_manual_rank_override(self):
        self.ledger.correct('面板1',Holding('棘刺',elite=1))
        self.now = 125
        self.ledger.observe('面板1',[Holding('棘刺',uncertain=1)])
        self.assertEqual(self.ledger.occupied('棘刺'),3)
        self.assertEqual(self.ledger.manual_times['面板1']['棘刺'],100)
        self.now = 131
        self.assertEqual(self.ledger.occupied('棘刺'),1)
        self.assertEqual(self.ledger.own_names(),frozenset({'棘刺'}))
        view = self.ledger.view()
        self.assertIn('旧校正已停用',view.note('棘刺'))
        self.assertIn('（3份）',view.note('棘刺'))
        self.assertEqual(view.estimate('棘刺',10),'估算余量 0–9 · 自设总池 10')

    def test_reading_other_cards_does_not_keep_absent_manual_card_fresh(self):
        self.ledger.correct('面板1',Holding('旅骨',elite=1))
        for now in (115,125,131):
            self.now = now
            self.ledger.observe('面板1',[Holding('深靛',normal=1)])
        self.assertEqual(self.ledger.own_names(),frozenset({'深靛'}))
        self.assertIn('旅骨',self.ledger.view().stale_names)
        self.assertIn('另有1条旧记录',self.ledger.own_status())

    def test_zero_override_expires_and_recent_real_card_can_return(self):
        self.ledger.observe('面板1',[Holding('旅骨',normal=1)])
        self.now = 101
        self.ledger.correct('面板1',Holding('旅骨'))
        self.now = 125
        self.ledger.observe('面板1',[Holding('旅骨',normal=1)])
        self.assertEqual(self.ledger.own_names(),frozenset())
        self.assertEqual(self.ledger.occupied('旅骨'),0)
        self.now = 132
        self.assertEqual(self.ledger.own_names(),frozenset({'旅骨'}))
        self.assertEqual(self.ledger.occupied('旅骨'),1)

    def test_undo_restores_original_frame_without_changing_its_timestamp(self):
        self.ledger.observe('面板1',[Holding('星极',uncertain=1)])
        self.now = 101
        self.ledger.correct('面板1',Holding('星极',elite=1))
        self.assertEqual(self.ledger.occupied('星极'),2)
        self.ledger.clear_correction('面板1','星极')
        self.assertEqual(self.ledger.occupied('星极'),1)
        self.assertEqual(self.ledger.players['面板1'].updated,100)
        self.assertNotIn('面板1',self.ledger.manual)
        self.assertNotIn('面板1',self.ledger.manual_times)
        self.now = 131
        self.assertIsNone(self.ledger.own_names())

    def test_undo_without_recent_frame_does_not_create_a_zero_or_fresh_record(self):
        self.ledger.correct('面板1',Holding('旅骨',elite=1))
        self.ledger.clear_correction('面板1','旅骨')
        self.assertIsNone(self.ledger.own_names())
        self.assertEqual(self.ledger.view().records,{})
        self.assertIn('等待读取',self.ledger.own_status())

    def test_manual_only_record_expires_but_is_kept_as_history(self):
        self.ledger.correct('面板1',Holding('旅骨',normal=2))
        self.assertEqual(self.ledger.own_names(),frozenset({'旅骨'}))
        self.now = 131
        self.assertIsNone(self.ledger.own_names())
        view = self.ledger.view()
        self.assertEqual(view.occupied('旅骨'),2)
        self.assertIn('含旧记录',view.amount('旅骨'))
        self.assertIn('手动校正',view.note('旅骨'))
        self.assertIn('已过期',view.note('旅骨'))
        self.assertIn('过期',view.estimate('旅骨',10))

    def test_forgetting_player_clears_manual_timestamps_and_binding(self):
        self.ledger.correct('面板1',Holding('旅骨',normal=1))
        self.ledger.forget('面板1')
        self.assertEqual(self.ledger.manual_times,{})
        self.assertEqual(self.ledger.own_slot,'')

    def test_view_reads_one_clock_and_uses_special_merge_for_all_players(self):
        self.ledger.observe('面板1',[Holding('星极',elite=1)])
        self.ledger.observe('面板2',[Holding('星极',normal=1)])
        with patch('stronghold.stock.time.time',side_effect=[130,131]) as clock:
            view = self.ledger.view()
        self.assertEqual(clock.call_count,1)
        self.assertEqual(view.occupied('星极'),3)
        self.assertEqual(view.stale_names,set())
        self.assertEqual(view.estimate('星极',10),'估算余量 0–7 · 自设总池 10')

    def test_frame_with_missing_names_replaces_visible_part_without_claiming_sold(self):
        self.ledger.observe('面板1',[Holding('旅骨',normal=1),Holding('深靛',normal=1)])
        self.now = 110
        self.ledger.observe('面板1',[Holding('深靛',normal=1)])
        self.assertEqual(self.ledger.own_names(),frozenset({'深靛'}))
        self.assertEqual(self.ledger.view().note('旅骨'),'尚无此卡记录')

    def test_future_timestamps_are_not_treated_as_fresh(self):
        self.ledger.observe('面板1',[Holding('旅骨',normal=1)])
        self.now = 90
        self.assertIsNone(self.ledger.own_names())
        self.assertIn('时间待确认',self.ledger.view().note('旅骨'))
        self.assertIn('过期',self.ledger.estimate('旅骨',10))
