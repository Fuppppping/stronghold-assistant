import unittest
from stronghold.cadence import ScanCadence
from stronghold.domain import Reading


class CadenceTests(unittest.TestCase):
    def test_static_capture_slows_but_new_content_restores_fast_sampling(self):
        cadence = ScanCadence()
        self.assertEqual(cadence.interval(True),.25)
        for _ in range(3):
            cadence.observe(Reading(reused=True))
        self.assertEqual(cadence.interval(True,'调度中心'),.5)
        cadence.observe(Reading(reused=False))
        self.assertEqual(cadence.interval(True,'调度中心'),.25)

    def test_opening_and_strategy_priority_even_when_cached(self):
        cadence = ScanCadence(reused=8)
        for scene in ('盟约选择','策略轮选'):
            self.assertEqual(cadence.interval(True,scene),.25)
        self.assertEqual(cadence.interval(True,reset_hint=True),.25)

    def test_background_saving_can_be_disabled(self):
        cadence = ScanCadence(reused=8)
        self.assertEqual(cadence.interval(False,'调度中心'),1.5)
        self.assertEqual(cadence.interval(False,'调度中心',enabled=False),.25)

    def test_failure_backoff_is_bounded_and_reset_on_recovery(self):
        cadence = ScanCadence()
        for expected in (1,2,4,4):
            cadence.failed()
            self.assertEqual(cadence.interval(True),expected)
        cadence.observe(Reading())
        self.assertEqual(cadence.interval(True),.25)
        cadence.failed()
        cadence.reset()
        self.assertEqual((cadence.errors,cadence.reused),(0,0))
