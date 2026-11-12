import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import uuid

from stronghold.domain import MatchState
from stronghold.stock import Holding
from stronghold.update_session import save_session, restore_session


class UpdateSessionTests(unittest.TestCase):
    def test_roundtrip_and_expiry_are_bound_to_window_and_process(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"STRONGHOLD_STATE": directory}):
            task = Path(directory).resolve() / "updates" / uuid.uuid4().hex
            task.mkdir(parents=True)
            match = MatchState(auto={"炎": True}, manual={"精准": False}, excluded={"棘刺"},
                               seen={"阿米娅"}, groups=[{"炎"}, {"乌萨斯"}], selected=0, played=True)
            match.stock.observe("队友1", [Holding("星极", elite=1)])
            match.progress.observe(8,replay=True)
            match.progress.manual['iberia'] = 1
            match.stock.correct("队友2", Holding("阿米娅", normal=2))
            match.stock.own_slot = '面板1'
            app = SimpleNamespace(match=match, window=SimpleNamespace(hwnd=123, process="Arknights.exe"),
                                  update_views=lambda: None)
            def pid(hwnd, pointer):
                pointer._obj.value = 42
            with patch("stronghold.windows.window_pid", side_effect=pid):
                save_session(app, task)
                app.match = MatchState()
                self.assertTrue(restore_session(app, task / "plan.json"))
                self.assertEqual(app.match.auto, {"炎": True})
                self.assertEqual(app.match.stock.own_slot,'面板1')
                self.assertEqual(app.match.progress.round_number,8)
                self.assertEqual(app.match.progress.manual,{'iberia':1})
                self.assertEqual(app.match.excluded, {"棘刺"})
                self.assertEqual(app.match.groups, [{"炎"}, {"乌萨斯"}])
                self.assertEqual(app.match.stock.occupied("星极"), 2)
                self.assertEqual(app.match.stock.occupied("阿米娅"), 2)
                self.assertEqual(app.match.stock.manual["队友2"]["阿米娅"].normal, 2)
                current = json.loads((task/'session.json').read_text(encoding='utf8'))
                old = dict(current,match={k:v for k,v in current['match'].items() if k!='progress'})
                old['match'] = dict(old['match'],stock={k:v for k,v in old['match']['stock'].items() if k!='own_slot'})
                (task/'session.json').write_text(json.dumps(old),encoding='utf8')
                self.assertTrue(restore_session(app,task/'plan.json'))
                self.assertIsNone(app.match.progress.round_number)
                self.assertEqual(app.match.stock.own_slot,'')
                self.assertEqual(app.match.progress.manual,{})
                (task/'session.json').write_text(json.dumps(current),encoding='utf8')
                app.window.hwnd = 124
                self.assertFalse(restore_session(app, task / "plan.json"))
                app.window.hwnd = 123
                raw = json.loads((task / "session.json").read_text(encoding="utf-8"))
                raw["created"] -= 901
                (task / "session.json").write_text(json.dumps(raw), encoding="utf-8")
                self.assertFalse(restore_session(app, task / "plan.json"))
            raw["created"] += 901
            (task / "session.json").write_text(json.dumps(raw), encoding="utf-8")
            with patch("stronghold.windows.window_pid"):
                self.assertFalse(restore_session(app, task / "plan.json"))
