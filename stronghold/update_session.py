"""Short-lived match continuity, bound to the same live game window."""
from dataclasses import asdict
import json
import time

from .domain import MatchState
from .stock import Holding, Snapshot
from .planning import StageProgress
from .update import atomic_json
from .update_install import task_path


def save_session(app, task):
    from . import windows
    from ctypes import byref, wintypes
    task = task_path(task)
    match = asdict(app.match)
    match.pop("last_bans", None)
    for field in ("excluded", "seen", "incomplete"):
        match[field] = sorted(match[field])
    match["groups"] = [sorted(group) for group in match["groups"]]
    pid = wintypes.DWORD()
    if app.window:
        windows.window_pid(app.window.hwnd, byref(pid))
    window = {"hwnd": app.window.hwnd, "process": app.window.process, "pid": pid.value} if app.window else None
    atomic_json(task / "session.json", {"created": time.time(), "window": window, "match": match})


def restore_session(app, plan_file):
    from . import windows
    from ctypes import byref, wintypes
    task = task_path(plan_file.parent)
    data = json.loads((task / "session.json").read_text(encoding="utf-8"))
    window = data.get("window")
    pid = wintypes.DWORD()
    if app.window:
        windows.window_pid(app.window.hwnd, byref(pid))
    if not (0 <= time.time() - data["created"] < 900 and app.window and window
            and app.window.hwnd == window["hwnd"] and app.window.process == window["process"]
            and pid.value == window["pid"]):
        return False
    raw = data["match"]
    match = MatchState()
    for field in ("auto", "manual", "selected", "partial", "played", "in_setup", "epoch"):
        setattr(match, field, raw[field])
    for field in ("excluded", "seen", "incomplete"):
        setattr(match, field, set(raw[field]))
    match.groups = [set(group) for group in raw["groups"]]
    for slot, snap in raw["stock"]["players"].items():
        match.stock.players[slot] = Snapshot([Holding(**item) for item in snap["holdings"]],
                                              snap["updated"], snap["source"])
    match.stock.manual = {slot: {name: Holding(**item) for name, item in items.items()}
                         for slot, items in raw["stock"]["manual"].items()}
    own_slot = raw['stock'].get('own_slot','')
    match.stock.own_slot = own_slot if own_slot in ('面板1','面板2','面板3','面板4') else ''
    progress = raw.get('progress', {})
    if isinstance(progress, dict):
        number, updated, manual = progress.get('round_number'), progress.get('updated', 0), progress.get('manual', {})
        match.progress = StageProgress(
            round_number=number if type(number) is int and 1 <= number <= 99 else None,
            updated=updated if type(updated) in (int,float) else 0,
            manual={name:index for name,index in manual.items() if isinstance(name,str) and type(index) is int and index >= 0}
                   if isinstance(manual,dict) else {})
    app.match = match
    app.update_views()
    return True
