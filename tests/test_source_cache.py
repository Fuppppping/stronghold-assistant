from types import SimpleNamespace
import unittest
from unittest.mock import patch

from PIL import Image

from stronghold.domain import Reading, Hit, Season
from stronghold import vision
from stronghold.vision import Recognizer, Line, ShopControls


class CountingRecognizer(Recognizer):
    def __init__(self,scene='调度中心'):
        self.last_scene=scene
        self.ban_continuation=False
        self.calls=0
        self.reset_cache()

    def read(self,frame,forced='',roi=None):
        self.calls+=1
        return Reading(scene=forced or self.last_scene,hits=[Hit('干员','深靛',(100,650,160,680),.99)])


class SourceCacheTests(unittest.TestCase):
    def test_unchanged_4k_source_skips_normalization_and_is_defensive(self):
        image=Image.new('RGB',(3840,2160),(40,50,60))
        r=CountingRecognizer()
        with patch('stronghold.vision.normalize_frame',wraps=vision.normalize_frame) as normalize:
            first=r.inspect(image)
            first.excluded.add('外部修改')
            cached=r.inspect(image)
            self.assertEqual(normalize.call_count,1)
        self.assertTrue(cached.reused)
        self.assertFalse(cached.excluded)
        self.assertEqual(cached.hits[0].box,(300,1950,480,2040))
        self.assertEqual(r.calls,1)

    def test_filtered_roi_halo_changes_invalidate_before_resize(self):
        image=Image.new('RGB',(3840,2160),(40,50,60))
        r=CountingRecognizer()
        with patch('stronghold.vision.normalize_frame',wraps=vision.normalize_frame) as normalize:
            r.inspect(image)
            changed=image.copy()
            changed.paste((255,255,255),(267,2035,270,2045))
            reading=r.inspect(changed)
            self.assertEqual(normalize.call_count,2)
        self.assertFalse(reading.reused)
        self.assertEqual(r.calls,2)

    def test_geometry_forcing_roi_and_reset_all_invalidate_source_cache(self):
        r=CountingRecognizer()
        image=Image.new('RGB',(1280,720),(40,50,60))
        with patch('stronghold.vision.normalize_frame',wraps=vision.normalize_frame) as normalize:
            r.inspect(image)
            doubled=r.inspect(image.resize((2560,1440)))
            self.assertTrue(doubled.reused)
            self.assertEqual(doubled.hits[0].box,(200,1300,320,1360))
            r.inspect(image,forced='盟约选择')
            r.inspect(image,forced='盟约选择',roi=[350,85,900,600])
            r.reset_cache()
            r.inspect(image,forced='盟约选择',roi=[350,85,900,600])
            self.assertEqual(normalize.call_count,5)

    def test_letterbox_and_ignored_board_changes_keep_correct_coordinates(self):
        image=Image.new('RGB',(1440,900),(40,50,60))
        region=(40,30,1320,750)
        r=CountingRecognizer()
        with patch('stronghold.vision.game_region',return_value=region), \
             patch('stronghold.vision.normalize_frame',wraps=vision.normalize_frame) as normalize:
            r.inspect(image)
            changed=image.copy()
            changed.paste((150,130,120),(400,300,450,350))
            reading=r.inspect(changed)
            self.assertEqual(normalize.call_count,1)
        self.assertTrue(reading.reused)
        self.assertEqual(reading.hits[0].box,(140,680,200,710))

    def test_palette_changes_do_not_reuse_raw_indices_as_rgb_pixels(self):
        image=Image.new('P',(1280,720),0)
        image.putpalette([40,50,60]+[0,0,0]*255)
        r=CountingRecognizer()
        with patch('stronghold.vision.normalize_frame',wraps=vision.normalize_frame) as normalize:
            r.inspect(image)
            changed=image.copy()
            changed.putpalette([180,150,130]+[0,0,0]*255)
            reading=r.inspect(changed)
            self.assertEqual(normalize.call_count,2)
        self.assertFalse(reading.reused)

    def test_source_guard_covers_normalized_changes_at_filter_edges_and_scales(self):
        changed_count=0
        for size in ((640,360),(1981,1117),(3840,2160)):
            image=Image.new('RGB',size,(40,50,60))
            region=(0,0,*size)
            original=Recognizer.scene_key(vision.normalize_frame(image,region),'调度中心','',None)
            source=Recognizer.source_key(image,region,'调度中心','',None)
            for x,y in ((89.5,680),(899.5,300),(700,100.5),(1149.5,680)):
                sx,sy=size[0]/1280,size[1]/720
                px,py=round(x*sx),round(y*sy)
                changed=image.copy()
                changed.paste((255,255,255),(max(0,px-2),max(0,py-2),px+3,py+3))
                key=Recognizer.scene_key(vision.normalize_frame(changed,region),'调度中心','',None)
                if key!=original:
                    changed_count+=1
                    self.assertNotEqual(Recognizer.source_key(changed,region,'调度中心','',None),source)
        self.assertGreaterEqual(changed_count,9)


class ControlCacheTests(unittest.TestCase):
    def setUp(self):
        self.frame=Image.new('RGB',(1280,720),(40,50,60))
        self.frame.paste((90,110,120),(0,0,300,720))
        self.labels=[Line('冻结',(1000,450,1050,470),.99),Line('刷新',(1190,450,1240,470),.99)]

    def test_only_verified_word_pixels_must_stay_unchanged(self):
        controls=ShopControls()
        controls.remember(self.frame,self.labels)
        changed=self.frame.copy()
        changed.paste((220,150,90),(985,380,1000,395))
        self.assertTrue(controls.matches(changed))
        changed.putpixel((1005,455),(255,255,255))
        self.assertFalse(controls.matches(changed))

    def test_low_confidence_partial_duplicate_and_out_of_place_words_do_not_cache(self):
        for labels in ([self.labels[0],Line('刷新',self.labels[1].box,.89)],
                       [self.labels[0],Line('刷',self.labels[1].box,.99)],
                       [self.labels[0],self.labels[1],self.labels[1]],
                       [self.labels[0],Line('刷新',(400,200,450,220),.99)]):
            controls=ShopControls()
            controls.remember(self.frame,labels)
            self.assertFalse(controls.matches(self.frame))

    def test_confirmed_collapse_word_can_pair_with_refresh(self):
        controls=ShopControls()
        controls.remember(self.frame,[self.labels[1],Line('收起',(1170,665,1210,690),.99)])
        self.assertTrue(controls.matches(self.frame))

    def reader(self):
        r=CountingRecognizer()
        r.season=Season()
        r.portraits=SimpleNamespace(cards=lambda _:[],team=lambda *args:([],{}))
        r.ocr_calls=[]
        def ocr(frame,rect,zoom=1):
            r.ocr_calls.append(rect)
            if rect==(980,375,1280,560):
                return self.labels
            if rect==(90,655,1150,710):
                return [Line('深靛',(1000,660,1070,690),.99)]
            return []
        r.ocr=ocr
        r.read_strategies=lambda *args:[]
        return r

    def test_same_controls_skip_button_ocr_but_changed_glyphs_use_original_path(self):
        r=self.reader()
        r.shop_controls.remember(self.frame,self.labels)
        reading=Recognizer.read(r,self.frame)
        self.assertEqual(reading.scene,'调度中心')
        self.assertNotIn((980,375,1280,560),r.ocr_calls)
        changed=self.frame.copy()
        changed.putpixel((1005,455),(255,255,255))
        r.ocr_calls.clear()
        reading=Recognizer.read(r,changed)
        self.assertEqual(reading.scene,'调度中心')
        self.assertIn((980,375,1280,560),r.ocr_calls)

    def test_team_overlay_is_checked_before_cached_shop_controls(self):
        r=self.reader()
        r.shop_controls.remember(self.frame,self.labels)
        r.portraits.team=lambda *args:([],{'面板1':[]})
        with patch.object(r.shop_controls,'matches',side_effect=AssertionError('must detect team first')):
            reading=Recognizer.read(r,self.frame)
        self.assertEqual(reading.scene,'队友阵容')
        self.assertEqual(r.ocr_calls,[])

    def test_forced_other_scene_ignores_shop_controls(self):
        r=self.reader()
        r.shop_controls.remember(self.frame,self.labels)
        with patch.object(r.shop_controls,'matches',side_effect=AssertionError('forced scene must win')):
            reading=Recognizer.read(r,self.frame,forced='策略轮选')
        self.assertEqual(reading.scene,'策略轮选')
