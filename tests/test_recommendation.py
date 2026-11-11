from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from stronghold.domain import Season


def guide(identifier, core, candidates=None, minimum=1):
    return {'id':identifier, 'name':identifier, 'targets':{'乌萨斯':3},
            'stages':[{'name':'成型','core':core,'operators':[]}],
            'requirements':[{'name':'输出位','operators':candidates or core,'minimum':minimum}],
            'strategies':[], 'equipment':{}, 'sources':[]}


class RecommendationTests(unittest.TestCase):
    def setUp(self):
        self.season = Season()
        self.states = dict.fromkeys(self.season.pacts, True)

    def test_same_pact_but_banned_core_loses_even_when_visible_card_boosts_it(self):
        broken = guide('broken', ['塔露拉'])
        complete = guide('complete', ['冻河'])
        self.season.lineups = {'broken':broken, 'complete':complete}
        ranked = self.season.rank(self.states, {'塔露拉'}, current=['塔露拉'])
        self.assertEqual(ranked[0]['id'], 'complete')
        fit = self.season.assess(broken, self.states, {'塔露拉'})
        self.assertFalse(fit.viable)
        self.assertEqual(fit.missing_roles, ['输出位'])
        self.assertIn('塔露拉', fit.reason)

    def test_explicit_role_alternative_keeps_lineup_possible_but_explains_loss(self):
        lineup = guide('flexible', ['塔露拉', '冻河'])
        fit = self.season.assess(lineup, self.states, {'塔露拉'})
        self.assertTrue(fit.viable)
        self.assertEqual(fit.blocked_core, ['塔露拉'])
        self.assertIn('输出位：冻河', fit.alternatives)
        self.assertLess(fit.score, self.season.assess(lineup, self.states).score)

    def test_role_minimum_and_early_late_stage_coverage(self):
        lineup = guide('two', ['塔露拉','冻河'], minimum=2)
        self.assertFalse(self.season.assess(lineup, self.states, {'冻河'}).viable)
        old_guide = deepcopy(lineup)
        old_guide.pop('requirements')
        old_guide['stages'].append({'name':'起步','core':['折桠'],'operators':[]})
        fit = self.season.assess(old_guide, self.states, {'折桠'})
        self.assertIn('起步', fit.missing_roles)

    def test_unknown_cards_do_not_become_confirmed_and_seen_cards_restore_fit(self):
        lineup = guide('unknown', ['塔露拉'])
        fit = self.season.assess(lineup, {})
        self.assertTrue(fit.viable)
        self.assertEqual(fit.unknown_core, ['塔露拉'])
        self.assertLess(fit.score, 100)
        restored = self.season.assess(lineup, self.states, {'塔露拉'}, {'塔露拉'})
        self.assertTrue(restored.viable)
        self.assertFalse(restored.blocked_core)

    def test_banned_secondary_card_breaks_role_despite_open_main_pact(self):
        fit = self.season.assess(self.season.lineups['iberia'], self.states | {'奥术':False,'精准':False})
        self.assertIn('霍尔海雅', fit.blocked_core)
        self.assertIn('精奥叠层', fit.missing_roles)
        self.assertFalse(fit.viable)

    def test_large_support_list_cannot_hide_missing_core(self):
        broken = guide('broken', ['塔露拉'])
        broken['stages'][0]['operators'] = list(self.season.operators)
        complete = guide('complete', ['冻河'])
        self.season.lineups = {'broken':broken, 'complete':complete}
        self.assertEqual(self.season.rank(self.states, {'塔露拉'})[0]['id'], 'complete')

    def test_role_only_guide_keeps_uncertainty_and_evaluation_shares_operator_status(self):
        lineup = guide('role-only', [], ['冻河'])
        fit = self.season.assess(lineup, {})
        self.assertIn('待确认', fit.label)
        self.assertEqual(fit.pending_roles, ['输出位'])
        with patch.object(self.season, 'status', wraps=self.season.status) as status:
            self.season.evaluate(self.states)
            self.assertEqual(status.call_count, len(self.season.operators))

    def test_guide_role_validation_rejects_unknown_or_impossible_candidates(self):
        sample = guide('bad-role', ['冻河'])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'guide.json'
            for role in ({'name':'x','operators':['冻河'],'minimum':2},
                         {'name':'x','operators':['不存在']},
                         {'name':'x','operators':['冻河'],'minimum':True}):
                sample['requirements'] = [role]
                path.write_text(json.dumps(sample), encoding='utf8')
                with self.assertRaisesRegex(ValueError, 'requirements'):
                    self.season.add_guide(path)
