import json
from pathlib import Path
import tempfile
import tkinter as tk
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from PIL import Image


class FloatingUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from stronghold.app import Dashboard
        cls.directory = tempfile.TemporaryDirectory()
        cls.state = Path(cls.directory.name)
        (cls.state/'settings.json').write_text(json.dumps({'auto_update_check':False,'overlay':False}),encoding='utf8')
        cls.setting = patch('stronghold.app.SETTINGS_DIR',cls.state)
        cls.setting.start()
        cls.root = tk.Tk()
        cls.root.withdraw()
        cls.app = Dashboard(cls.root)
        cls.app.preview = True
        cls.app.running = False

    @classmethod
    def tearDownClass(cls):
        cls.root.destroy()
        cls.setting.stop()
        cls.directory.cleanup()

    def setUp(self):
        from stronghold.floating_layout import Placement
        from stronghold.domain import MatchState, Reading
        self.app.floating.hide()
        self.app.floating.placement = Placement()
        self.app.match = MatchState()
        self.app.reading = Reading()
        self.app.guide_id = 'iberia'
        self.app.enabled.clear()
        self.app.muted.clear()
        self.app.update_views()
        self.app.overlay_font_slider.set(135)
        self.app.enter_floating()
        self.root.update()

    def test_mode_roundtrip_and_saved_preferences_share_one_scanner(self):
        worker = self.app.scanner
        self.assertEqual(self.root.state(),'withdrawn')
        self.assertTrue(self.app.floating.active)
        self.app.floating.placement.x = 90
        self.app.save()
        saved = json.loads((self.state/'settings.json').read_text(encoding='utf8'))
        self.assertTrue(saved['floating_mode'])
        self.assertEqual(saved['floating_layout']['x'],90)
        self.app.leave_floating()
        self.root.update()
        self.assertEqual(self.root.state(),'normal')
        self.assertFalse(self.app.floating.active)
        self.assertIs(self.app.scanner,worker)

    def test_real_win32_styles_keep_recovery_header_interactive(self):
        from stronghold import windows
        dock = self.app.floating
        dock.toggle_lock()
        self.root.update()
        self.assertTrue(windows.get_style(dock.body_hwnd,windows.GWL_EXSTYLE)&0x20)
        self.assertTrue(windows.get_style(dock.body_hwnd,windows.GWL_EXSTYLE)&0x08000000)
        self.assertFalse(windows.get_style(dock.header_hwnd,windows.GWL_EXSTYLE)&0x20)
        dock.toggle_collapse()
        self.root.update()
        self.assertTrue(windows.visible(dock.header_hwnd))
        self.assertFalse(windows.visible(dock.body_hwnd))
        dock.toggle_collapse()
        dock.toggle_lock()
        self.root.update()
        self.assertTrue(windows.visible(dock.body_hwnd))
        self.assertFalse(windows.get_style(dock.body_hwnd,windows.GWL_EXSTYLE)&0x20)

    def test_compact_controls_update_the_same_guide_and_alert_preferences(self):
        from stronghold.domain import Reading, Hit
        dock = self.app.floating
        for page in range(6):
            dock.tabs.select(page)
            self.root.update()
            self.assertTrue(dock.pages[page].winfo_ismapped())
        dock.tabs.select(1)
        self.root.update()
        dock.guide_tree.selection_set('ursus')
        dock.choose_guide()
        self.assertEqual(self.app.guide_id,'ursus')
        dock.tabs.select(4)
        self.root.update()
        dock.gear_tree.selection_set('盟约之币')
        dock.change_gear('enabled')
        self.app.reading = Reading(scene='调度中心',hits=[Hit('装备','盟约之币',(10,600,90,650),.99)])
        self.app.frame = Image.new('RGB',(1280,720))
        self.app.update_views()
        self.assertIn('盟约之币',self.app.enabled)
        self.assertTrue(any(row[2].cget('text')=='盟约之币' for row in dock.alert_rows))
        dock.change_gear('muted')
        self.assertNotIn('盟约之币',self.app.enabled)
        self.assertIn('盟约之币',self.app.muted)
        self.assertEqual(dock.previous_alerts,())

    def test_large_font_narrow_panel_keeps_all_action_buttons_accessible(self):
        dock = self.app.floating
        dock.tabs.select(0)
        dock.placement.width = 320
        dock.apply_geometry()
        dock.set_font(200)
        self.root.update()
        self.assertEqual(dock.action_columns,2)
        for button in dock.action_buttons:
            self.assertGreater(button.winfo_width(),10)
            self.assertLessEqual(button.winfo_x()+button.winfo_width(),dock.action_bar.winfo_width())
            self.assertGreaterEqual(button.winfo_rooty(),dock.body.winfo_rooty())
            self.assertLessEqual(button.winfo_rooty()+button.winfo_height(),dock.body.winfo_rooty()+dock.body.winfo_height())
        from stronghold.stock import Holding
        self.app.match.stock.observe('面板1',[Holding('旅骨',normal=1),Holding('深靛',normal=1)])
        self.app.own_source.set('面板1')
        self.app.change_own_source()
        dock.tabs.select(1)
        self.root.update()
        for button in dock.guide_buttons:
            self.assertLessEqual(button.winfo_x()+button.winfo_width(),dock.guide_bar.winfo_width())
        self.assertGreaterEqual(dock.guide_tree.winfo_height(),90)

    def test_running_panel_recovers_when_monitor_layout_changes(self):
        from stronghold.floating_layout import HEADER
        dock = self.app.floating
        dock.placement.x = 9000
        dock.placement.y = 9000
        dock.last_display_check = 0
        with patch('stronghold.floating.windows.work_areas',return_value=[(0,0,1280,680)]):
            dock.refresh()
        self.assertLessEqual(dock.placement.x+dock.placement.width,1280)
        self.assertLessEqual(dock.placement.y+HEADER+dock.placement.height,680)

    def test_following_client_does_not_accumulate_clamping_drift(self):
        dock = self.app.floating
        previous = self.app.window
        rect = [(0,0,1280,900)]
        self.app.preview = False
        self.app.window = SimpleNamespace(hwnd=123)
        try:
            with patch('stronghold.floating.windows.is_window',return_value=True), \
                 patch('stronghold.floating.windows.bounds',side_effect=lambda _:rect[0]), \
                 patch('stronghold.floating.windows.foreground',return_value=123), \
                 patch('stronghold.floating.windows.owned_window',return_value=False):
                dock.track_client()
                rect[0] = (80,40,1360,940)
                dock.track_client()
                self.assertEqual((dock.placement.x,dock.placement.y),(104,220))
                rect[0] = (9000,40,10280,940)
                dock.track_client()
                rect[0] = (0,0,1280,900)
                dock.track_client()
                self.assertEqual((dock.placement.x,dock.placement.y),(24,180))
        finally:
            self.app.preview = True
            self.app.window = previous

    def test_background_compacts_only_content_and_preserves_manual_collapse(self):
        from stronghold import windows
        dock = self.app.floating
        previous = self.app.window
        self.app.preview = False
        self.app.window = SimpleNamespace(hwnd=123)
        try:
            with patch('stronghold.floating.windows.is_window',return_value=True), \
                 patch('stronghold.floating.windows.bounds',return_value=(0,0,1280,900)), \
                 patch('stronghold.floating.windows.foreground',return_value=999) as foreground, \
                 patch('stronghold.floating.windows.owned_window',return_value=False) as owned:
                dock.track_client()
                self.root.update_idletasks()
                self.assertTrue(dock.auto_compacted)
                self.assertTrue(windows.visible(dock.header_hwnd))
                self.assertFalse(windows.visible(dock.body_hwnd))
                self.assertFalse(dock.placement.collapsed)
                foreground.return_value = dock.header_hwnd
                owned.return_value = True
                dock.track_client()
                self.root.update_idletasks()
                self.assertFalse(dock.auto_compacted)
                self.assertTrue(windows.visible(dock.body_hwnd))
                dock.toggle_collapse()
                foreground.return_value = 123
                owned.return_value = False
                dock.track_client()
                self.assertTrue(dock.placement.collapsed)
                self.assertFalse(windows.visible(dock.body_hwnd))
        finally:
            self.app.preview = True
            self.app.window = previous

    def test_capture_tick_throttles_background_and_resumes_on_game_focus(self):
        previous = self.app.window
        self.app.preview = False
        self.app.running = True
        self.app.window = SimpleNamespace(hwnd=123)
        self.app.last_windows = 100.0
        self.app.last_scan = 100.0
        self.app.last_foreground = 999
        self.app.active_job = None
        self.app.cadence.reset()
        self.app.energy_saving.set(True)
        clock = [100.5]
        submitted = []
        try:
            with patch('stronghold.app.time.monotonic',side_effect=lambda:clock[0]), \
                 patch('stronghold.app.windows.foreground',return_value=999) as foreground, \
                 patch('stronghold.app.windows.bounds',return_value=(0,0,1280,900)), \
                 patch.object(self.app,'submit',side_effect=submitted.append), \
                 patch.object(self.app,'paint_overlay'),patch.object(self.app.floating,'refresh'), \
                 patch.object(self.root,'after'):
                self.app.tick()
                self.assertEqual(submitted,[])
                clock[0] = 101.6
                self.app.tick()
                self.assertEqual(submitted,[123])
                foreground.return_value = 123
                clock[0] = 101.7
                self.app.tick()
                self.assertEqual(submitted,[123,123])
        finally:
            self.app.preview = True
            self.app.running = False
            self.app.window = previous

    def test_unchanged_panel_skips_rendering_but_new_match_data_refreshes(self):
        dock = self.app.floating
        dock.tabs.select(0)
        self.root.update()
        dock.last_render = None
        with patch.object(dock.plan,'configure',wraps=dock.plan.configure) as configure:
            dock.refresh()
            first = configure.call_count
            self.assertGreater(first,0)
            dock.refresh()
            self.assertEqual(configure.call_count,first)
            self.app.update_views()
            self.assertGreater(configure.call_count,first)

    def test_automatic_panel_restore_does_not_steal_keyboard_focus(self):
        from stronghold import windows
        dock = self.app.floating
        for locked in (False,True):
            with self.subTest(locked=locked):
                dock.placement.locked = locked
                dock.body.withdraw()
                self.root.update()
                # Preserve the user's actual foreground, without trying to
                # acquire focus (which Windows may legitimately refuse).
                foreground = windows.foreground()
                self.assertTrue(foreground)
                dock.apply_geometry()
                self.root.update()
                self.assertTrue(windows.visible(dock.body_hwnd))
                self.assertEqual(windows.foreground(),foreground)
                dock.placement.x += 10
                dock.apply_geometry()
                self.root.update()
                self.assertEqual(windows.foreground(),foreground)

    def test_stage_controls_share_manual_choice_and_reset_for_new_match(self):
        from stronghold.domain import Reading
        dock = self.app.floating
        self.app.accept(Reading(scene='调度中心',round_number=1),Image.new('RGB',(1280,720)),None)
        self.assertIn('R1',dock.phase_info.cget('text'))
        self.assertIn('本阶段',dock.plan.cget('text'))
        self.app.phase_choice.set('2 · 中期')
        dock.phase_selector.event_generate('<<ComboboxSelected>>')
        self.root.update()
        self.assertEqual(self.app.phase_selector.get(),'2 · 中期')
        self.assertEqual(self.app.current_plan.stage['name'],'中期')
        self.app.accept(Reading(scene='调度中心',round_number=11),Image.new('RGB',(1280,720)),None)
        self.assertEqual(self.app.current_plan.stage['name'],'中期')
        self.assertEqual(self.app.match.stock.players,{})
        self.app.match.clear()
        self.app.update_views()
        self.assertEqual(dock.phase_selector.get(),'自动')
        self.assertIsNone(self.app.current_plan.stage)

    def test_expired_round_removes_phase_emphasis_without_waiting_for_new_frame(self):
        from stronghold.domain import Reading
        self.app.accept(Reading(scene='调度中心',round_number=8),Image.new('RGB',(1280,720)),None)
        self.assertEqual(self.app.current_plan.stage['name'],'中期')
        self.app.match.progress.updated -= 31
        with patch.object(self.root,'after'):
            self.app.tick()
        self.assertIsNone(self.app.current_plan.stage)
        self.assertIn('回合待确认',self.app.phase_caption.get())

    def test_own_source_is_shared_and_expiry_removes_weight_without_new_frames(self):
        from stronghold.stock import Holding
        self.app.match.stock.observe('面板1',[Holding('旅骨',normal=1)])
        self.assertIsNone(self.app.fits['iberia'].ownership)
        self.app.own_source.set('面板1')
        self.app.floating.own_selector.event_generate('<<ComboboxSelected>>')
        self.root.update()
        self.assertEqual(self.app.owned_names,frozenset({'旅骨'}))
        self.assertGreater(self.app.fits['iberia'].ownership.bonus,0)
        self.assertEqual(self.app.guide_tree.item('iberia','values')[2],'+6')
        self.app.match.stock.players['面板1'].updated -= 31
        with patch.object(self.root,'after'):
            self.app.tick()
        self.assertIsNone(self.app.fits['iberia'].ownership)
        self.assertIn('过期',self.app.own_status.get())
        self.app.match.clear()
        self.app.update_views()
        self.assertEqual(self.app.own_source.get(),'未指定')

    def test_owned_roster_entry_opens_matching_panel_without_switching_guide(self):
        self.app.own_source.set('面板3')
        self.app.change_own_source()
        self.app.show_owned_roster()
        self.assertEqual(self.app.stock_tabs.index('current'),1)
        self.assertEqual(self.app.stock_slot.get(),'面板3')
        self.assertEqual(self.app.guide_id,'iberia')
