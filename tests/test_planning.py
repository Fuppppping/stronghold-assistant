import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from stronghold.domain import Hit, MatchState, Reading, Season, alerts
from stronghold.planning import StageProgress, choose_stage, round_range
from stronghold.vision import Line, read_round


class PlanningTests(unittest.TestCase):
    def setUp(self):
        self.season = Season()
        self.guide = self.season.lineups['iberia']

    def test_auto_stage_obeys_guide_specific_boundaries(self):
        for number, index in ((1,0),(5,0),(6,1),(9,1),(10,2),(14,2)):
            p = StageProgress()
            p.observe(number,replay=True)
            self.assertIs(choose_stage(self.guide,p).stage,self.guide['stages'][index])
        p = StageProgress()
        p.observe(6,replay=True)
        self.assertIs(choose_stage(self.season.lineups['sargon'],p).stage,
                      self.season.lineups['sargon']['stages'][0])

    def test_unknown_stale_and_level_only_guides_do_not_guess_a_stage(self):
        p = StageProgress()
        self.assertIsNone(choose_stage(self.guide,p).stage)
        p.observe(8,replay=True)
        self.assertIsNone(choose_stage(self.season.lineups['yan'],p).stage)
        with patch('stronghold.planning.time.time',return_value=p.updated+31):
            self.assertIsNone(choose_stage(self.guide,p).stage)
        self.assertIsNone(round_range({'timing':'1–3 本'}))
        self.assertIsNone(round_range({'timing':'R1–R5 或 R8–R9'}))

    def test_manual_stage_is_per_guide_and_overrides_new_ocr(self):
        p = StageProgress(manual={'iberia':1})
        p.observe(1,replay=True)
        self.assertIs(choose_stage(self.guide,p).stage,self.guide['stages'][1])
        self.assertTrue(choose_stage(self.guide,p).caption.startswith('手动'))
        self.assertTrue(choose_stage(self.season.lineups['egir'],p).caption.startswith('自动'))
        p.manual.clear()
        self.assertIs(choose_stage(self.guide,p).stage,self.guide['stages'][0])

    def test_live_round_requires_two_stable_frames_and_does_not_move_backwards(self):
        p = StageProgress()
        p.observe(7)
        p.observe(None)
        p.observe(7)
        self.assertIsNone(p.round_number)
        p.observe(7)
        self.assertEqual(p.round_number,7)
        p.observe(8)
        p.observe(9)
        self.assertEqual(p.round_number,7)
        p.observe(9)
        self.assertEqual(p.round_number,9)
        p.observe(1)
        p.observe(1)
        self.assertEqual(p.round_number,9)

    def test_new_match_resets_round_and_manual_choice(self):
        match = MatchState()
        match.progress.observe(8,replay=True)
        match.progress.manual['iberia'] = 2
        match.observe(Reading(reset_hint=True))
        match.observe(Reading(reset_hint=True))
        self.assertIsNone(match.progress.round_number)
        self.assertEqual(match.progress.manual,{})

    def test_header_round_requires_label_alignment_and_confidence(self):
        label = Line('回合',(426,24,458,43),.99)
        number = Line('12',(477,25,493,40),.99)
        self.assertEqual(read_round([label,number]),12)
        self.assertEqual(read_round([Line('回合8',(426,24,490,43),.99)]),8)
        self.assertIsNone(read_round([Line('回合?3',(426,24,490,43),.99)]))
        self.assertIsNone(read_round([number]))
        for text, box, confidence in [('??',number.box,.99),('I',number.box,.99),
                                       ('12',(477,90,493,105),.99),('12',number.box,.5)]:
            self.assertIsNone(read_round([label,Line(text,box,confidence)]))
        self.assertIsNone(read_round([label,number,Line('3',(498,25,508,40),.99)]))

    def test_phase_emphasis_preserves_global_core_and_stack_alerts(self):
        current = self.guide['stages'][0]
        early = current['core'][0]
        later = next(n for n in self.guide['stages'][-1]['core'] if n not in current['core']+current['operators'])
        reading = Reading(scene='调度中心',hits=[Hit('干员',n,(10+i*100,650,80+i*100,680),.99)
                                               for i,n in enumerate([early,later])])
        notes = {h.name:n for h,n in alerts(reading,self.guide,set(),set(),{},self.season,stage=current)}
        self.assertIn('当前阶段优先',notes[early])
        self.assertTrue(notes[later].startswith('核心'))
        self.assertNotIn('当前阶段优先',notes[later])

    def test_guide_round_ranges_validate_and_reject_overlaps(self):
        sample = json.loads((Path(__file__).resolve().parent.parent/'guide.example.json').read_text(encoding='utf8'))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'guide.json'
            for value in ([True,5],[8,3],[0,5],[1,100],'1–5'):
                sample['stages'][0]['rounds'] = value
                path.write_text(json.dumps(sample),encoding='utf8')
                with self.assertRaisesRegex(ValueError,'rounds'):
                    self.season.add_guide(path)
            sample['stages'][0]['rounds'] = [1,5]
            sample['stages'][1]['rounds'] = [5,9]
            path.write_text(json.dumps(sample),encoding='utf8')
            with self.assertRaisesRegex(ValueError,'重叠'):
                self.season.add_guide(path)
            sample['stages'][1]['rounds'] = [6,14]
            path.write_text(json.dumps(sample),encoding='utf8')
            guide = self.season.add_guide(path)
            p = StageProgress()
            p.observe(6,replay=True)
            self.assertEqual(choose_stage(guide,p).stage['name'],'成型')
