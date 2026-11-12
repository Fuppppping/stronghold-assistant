import time
import unittest
from unittest.mock import patch

from stronghold.domain import Hit, MatchState, Reading, Season
from stronghold.recommendation import pivot_advice
from stronghold.stock import Holding, StockLedger


def lineup(identifier, core, support=(), minimum=1):
    return dict(id=identifier,name=identifier,targets={'乌萨斯':3},
                stages=[dict(name='成型',core=core,operators=list(support))],
                requirements=[dict(name='输出',operators=core,minimum=minimum)],
                strategies=[],equipment={},stacking=[],sources=[])


class OwnershipTests(unittest.TestCase):
    def setUp(self):
        self.season = Season()
        self.states = dict.fromkeys(self.season.pacts, True)

    def test_teammates_and_shop_offers_are_not_implicitly_mine(self):
        match = MatchState()
        match.stock.observe('面板1',[Holding('冻河',elite=1)])
        match.stock.observe('面板2',[Holding('塔露拉',normal=1)])
        self.assertIsNone(match.stock.own_names())
        match.stock.own_slot = '面板1'
        match.observe(Reading(scene='调度中心',hits=[Hit('干员','棘刺',(1,650,50,680),.99)]))
        self.assertEqual(match.stock.own_names(),frozenset({'冻河'}))

    def test_selected_player_replacement_correction_and_expiry(self):
        ledger = StockLedger(own_slot='面板1')
        self.assertIsNone(ledger.own_names())
        ledger.observe('面板1',[Holding('冻河',uncertain=1)])
        ledger.correct('面板1',Holding('冻河',normal=0))
        self.assertEqual(ledger.own_names(),frozenset())
        ledger.observe('面板1',[Holding('冻河',normal=1),Holding('塔露拉',normal=1)])
        self.assertEqual(ledger.own_names(),frozenset({'塔露拉'}))
        with patch('stronghold.stock.time.time',return_value=ledger.players['面板1'].updated+31):
            ledger.observe('面板2',[Holding('棘刺',normal=1)])
            self.assertIsNone(ledger.own_names())
            self.assertIn('过期',ledger.own_status())

    def test_new_match_or_forgetting_my_panel_removes_binding(self):
        match = MatchState()
        match.stock.own_slot = '面板2'
        match.stock.observe('面板2',[Holding('冻河',normal=1)])
        match.stock.forget('面板2')
        self.assertEqual(match.stock.own_slot,'')
        match.stock.own_slot = '面板1'
        match.clear()
        self.assertIsNone(match.stock.own_names())
        self.assertEqual(match.stock.own_slot,'')

    def test_owned_core_beats_shop_tiebreaker_without_changing_ban_score(self):
        a,b = lineup('a',['塔露拉']),lineup('b',['冻河'])
        self.season.lineups = dict(a=a,b=b)
        baseline = self.season.evaluate(self.states,current=['塔露拉'])[1]
        ranked,fits = self.season.evaluate(self.states,current=['塔露拉'],owned={'冻河'})
        self.assertEqual(ranked[0]['id'],'b')
        self.assertEqual(fits['a'].score,baseline['a'].score)
        self.assertEqual(fits['b'].score,baseline['b'].score)
        self.assertEqual(fits['b'].ownership.bonus,6)
        self.assertEqual(fits['b'].ownership.core,['冻河'])
        with patch.object(self.season,'status',wraps=self.season.status) as status:
            self.season.evaluate(self.states,owned={'冻河'})
            self.assertEqual(status.call_count,len(self.season.operators))

    def test_owned_banned_core_cannot_override_unavailable_roles(self):
        a,b = lineup('a',['塔露拉']),lineup('b',['冻河'])
        self.season.lineups = dict(a=a,b=b)
        ranked,fits = self.season.evaluate(self.states,{'塔露拉'},owned={'塔露拉'})
        self.assertEqual(ranked[0]['id'],'b')
        self.assertFalse(fits['a'].viable)
        self.assertEqual(fits['a'].ownership.bonus,0)
        self.assertEqual(fits['a'].ownership.conflicts,['塔露拉'])
        self.assertIn('冲突待核对',fits['a'].ownership.reason)

    def test_unique_owned_names_and_bounded_support_do_not_fake_role_completion(self):
        g = lineup('two',['塔露拉','冻河'],support=list(self.season.operators),minimum=2)
        fit = self.season.assess(g,self.states,owned=['塔露拉']*20)
        self.assertEqual(fit.ownership.bonus,6)
        self.assertEqual(fit.ownership.unrecorded_roles,['输出'])
        many = self.season.assess(g,self.states,owned=set(self.season.operators))
        self.assertLessEqual(many.ownership.bonus,20)
        self.assertEqual(many.ownership.ready_roles,['输出'])

    def test_unknown_availability_and_unknown_catalog_names_are_not_unbanned(self):
        g = lineup('a',['塔露拉'])
        fit = self.season.assess(g,{},owned={'塔露拉','不在固定池'})
        self.assertEqual(fit.unknown_core,['塔露拉'])
        self.assertIn('待确认',fit.label)
        self.assertEqual(fit.ownership.core,['塔露拉'])

    def test_pivot_only_proposes_viable_candidates_and_uses_partial_record_language(self):
        a,b,c = lineup('a',['塔露拉']),lineup('b',['冻河','折桠']),lineup('c',['塔露拉'],['冻河'])
        self.season.lineups = dict(a=a,b=b,c=c)
        ranked,fits = self.season.evaluate(self.states,{'塔露拉'},owned={'冻河'})
        text = pivot_advice('a',ranked,fits,{'冻河'})
        self.assertIn('受 BAN 限制',text)
        self.assertIn('b：沿用 冻河',text)
        self.assertNotIn('c：',text)
        self.assertEqual(fits['b'].ownership.unrecorded_core,['折桠'])

    def test_no_ownership_record_keeps_original_ranking_and_neutral_pivot(self):
        plain,original = self.season.evaluate(self.states)
        ranked,fits = self.season.evaluate(self.states,owned=None)
        self.assertEqual([g['id'] for g in ranked],[g['id'] for g in plain])
        self.assertTrue(all(f.ownership is None for f in fits.values()))
        self.assertIn('指定我方来源',pivot_advice('iberia',ranked,fits,None))
        self.assertIn('尚未记录',pivot_advice('iberia',ranked,fits,set()))

    def test_own_snapshot_never_double_counts_shared_pool(self):
        ledger = StockLedger()
        ledger.observe('面板1',[Holding('冻河',elite=1)])
        before = ledger.occupied('冻河')
        ledger.own_slot = '面板1'
        self.assertEqual(ledger.own_names(),frozenset({'冻河'}))
        self.assertEqual(ledger.occupied('冻河'),before)

    def test_single_generic_filler_is_not_enough_to_suggest_a_pivot(self):
        a,b = lineup('a',['塔露拉'],['阿米娅']),lineup('b',['冻河'],['阿米娅'])
        self.season.lineups = dict(a=a,b=b)
        ranked,fits = self.season.evaluate(self.states,owned={'阿米娅'})
        text = pivot_advice('a',ranked,fits,{'阿米娅'})
        self.assertIn('暂未找到有足够沿用基础',text)
        self.assertNotIn('b：沿用',text)
