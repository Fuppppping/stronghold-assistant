import json
from pathlib import Path
import tempfile
import tkinter as tk
import unittest
from unittest.mock import patch

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
