from types import SimpleNamespace
import unittest
from PIL import Image

from stronghold.domain import Hit, Reading
from stronghold.vision import Recognizer


class StubRecognizer(Recognizer):
    def __init__(self, scene='调度中心'):
        self.last_scene = scene
        self.ban_continuation = False
        self.calls = 0
        self.reset_cache()

    def read(self, frame, forced='', roi=None):
        self.calls += 1
        return Reading(scene=forced or self.last_scene,
                       hits=[Hit('干员','深靛',(100,650,160,680),.99)])


class CacheTests(unittest.TestCase):
    def setUp(self):
        self.frame = Image.new('RGB',(1280,720),(40,50,60))

    def test_reuse_is_defensive_and_coordinates_are_not_scaled_twice(self):
        recognizer = StubRecognizer()
        first = recognizer.inspect(self.frame)
        first.excluded.add('私人修改')
        second = recognizer.inspect(self.frame.resize((2560,1440)))
        self.assertTrue(second.reused)
        self.assertEqual(recognizer.calls, 1)
        self.assertFalse(second.excluded)
        self.assertEqual(second.hits[0].box, (200,1300,320,1360))

    def test_card_change_phase_change_and_forced_scene_invalidate(self):
        recognizer = StubRecognizer()
        recognizer.inspect(self.frame)
        changed = self.frame.copy()
        changed.putpixel((120,680),(230,100,90))
        self.assertFalse(recognizer.inspect(changed).reused)
        changed.putpixel((500,30),(230,100,90))
        self.assertFalse(recognizer.inspect(changed).reused)
        self.assertFalse(recognizer.inspect(changed, '盟约选择').reused)
        self.assertEqual(recognizer.calls,4)

    def test_countdown_does_not_recompute_and_right_ban_column_is_tracked(self):
        recognizer = StubRecognizer()
        recognizer.inspect(self.frame)
        changed = self.frame.copy()
        changed.putpixel((1180,30),(230,100,90))
        self.assertTrue(recognizer.inspect(changed).reused)
        bans = StubRecognizer('盟约选择')
        bans.inspect(self.frame)
        changed.putpixel((1200,680),(230,100,90))
        self.assertFalse(bans.inspect(changed).reused)

    def test_ocr_region_changes_only_invalidate_the_changed_region(self):
        recognizer = StubRecognizer()
        calls = []
        recognizer.engine = lambda *a, **kw: calls.append(1) or SimpleNamespace(txts=[],boxes=None,scores=[])
        recognizer.ocr(self.frame, (100,100,200,200))
        changed = self.frame.copy()
        changed.putpixel((1000,500),(250,240,230))
        recognizer.ocr(changed,(100,100,200,200))
        self.assertEqual(len(calls),1)
        changed.putpixel((150,150),(250,240,230))
        recognizer.ocr(changed,(100,100,200,200))
        self.assertEqual(len(calls),2)
