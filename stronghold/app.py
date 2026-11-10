"""Desktop dashboard and live capture loop."""
import json
import logging
import os
from pathlib import Path
from queue import Empty, Queue
from threading import Thread
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import webbrowser

from PIL import Image, ImageTk

from . import windows
from .domain import Reading, Season, alerts, key
from .overlay import Overlay
from .vision import Recognizer

BG = "#0e1720"
PANEL = "#162330"
ALT = "#1e3040"
FG = "#e6edf5"
SECONDARY = "#a6bacb"
TEAL = "#5ce2ce"
GOLD = "#ffcf86"
RED = "#ff9a9d"
FONT = ("Microsoft YaHei UI", 10)
SCENES = ("自动识别", "调度中心", "盟约选择", "策略轮选", "自选编队", "装备选择")
SETTINGS_DIR = Path(os.environ.get("STRONGHOLD_STATE") or
                    Path(os.environ.get("LOCALAPPDATA", ".")) / "StrongholdAssistant")


def settings_load():
    try:
        data = json.loads((SETTINGS_DIR / "settings.json").read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


class Scanner(Thread):
    def __init__(self, season):
        super().__init__(daemon=True)
        self.season = season
        self.requests = Queue()
        self.responses = Queue()

    def run(self):
        recognizer = None
        while True:
            generation, source, scene = self.requests.get()
            try:
                if isinstance(source, Path):
                    with Image.open(source) as image:
                        frame = image.convert("RGB")
                elif isinstance(source, tuple):
                    frame = windows.adb_capture(*source)
                else:
                    frame = windows.capture(source)
                if recognizer is None:
                    recognizer = Recognizer(self.season)
                reading = recognizer.inspect(frame, scene)
                self.responses.put((generation, reading, frame, None))
            except Exception as exc:
                logging.exception("Capture or OCR failed")
                self.responses.put((generation, None, None, str(exc)))


class Dashboard:
    def __init__(self, root):
        self.root = root
        root.title("卫戍协议助手")
        root.geometry("1040x735")
        root.minsize(850, 650)
        root.configure(bg=BG)
        root.option_add("*Font", FONT)
        self.season = Season()
        settings = settings_load()
        for path in sorted((SETTINGS_DIR / "guides").glob("*.json")):
            try:
                self.season.add_guide(path)
            except (OSError, ValueError) as exc:
                logging.warning("Cannot load guide %s: %s", path, exc)
        self.guide_id = settings.get("guide", "")
        if self.guide_id not in self.season.lineups:
            self.guide_id = ""
        self.enabled = set(settings.get("enabled", [])) & self.season.equipment.keys()
        self.muted = set(settings.get("muted", [])) & self.season.equipment.keys()
        self.show_overlay = tk.BooleanVar(value=settings.get("overlay", True))
        self.scene = tk.StringVar(value=SCENES[0])
        self.adb = tk.StringVar(value=settings.get("adb") or windows.find_adb())
        self.serial = tk.StringVar(value=settings.get("serial", ""))
        self.use_adb = tk.BooleanVar(value=settings.get("use_adb", False))
        self.win_name = tk.StringVar()
        self.status = tk.StringVar(value="正在寻找客户端")
        self.guide_text = tk.StringVar(value="尚未选定阵容")
        self.reading = Reading()
        self.window = None
        self.windows = {}
        self.manual_window = False
        self.running = True
        self.generation = 0
        self.active_job = None
        self.last_scan = 0
        self.last_windows = 0
        self.frame = None
        self.preview = False
        self.auto_states = {}
        self.manual_states = {}
        self.excluded = set()
        self.group = None
        self.groups = []
        self.partial_groups = False
        self.partial_pacts = set()
        self.last_bans = None
        self.observed_shop = False
        self.configure_styles()
        self.build()
        self.overlay = Overlay(root)
        self.scanner = Scanner(self.season)
        self.scanner.start()
        self.refresh_windows()
        self.update_views()
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.after(150, self.tick)

    @property
    def guide(self):
        return self.season.lineups.get(self.guide_id)

    @property
    def states(self):
        return self.auto_states | self.manual_states

    def configure_styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(".", background=BG, foreground=FG, fieldbackground=PANEL, font=FONT)
        style.configure("TFrame", background=BG)
        style.configure("Card.TFrame", background=PANEL)
        style.configure("TLabel", background=BG, foreground=FG)
        style.configure("Card.TLabel", background=PANEL, foreground=FG)
        style.configure("Title.TLabel", font=("Microsoft YaHei UI", 23, "bold"))
        style.configure("Sub.TLabel", foreground=SECONDARY)
        style.configure("Accent.TLabel", foreground=TEAL)
        style.configure("TButton", padding=(10, 6), borderwidth=0, background=ALT, foreground=FG)
        style.map("TButton", background=[("active", "#2a4356")])
        style.configure("Primary.TButton", background=TEAL, foreground="#0a2024")
        style.map("Primary.TButton", background=[("active", "#8ef1e1")])
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", padding=(18, 9), background=PANEL)
        style.map("TNotebook.Tab", background=[("selected", ALT)], foreground=[("selected", TEAL)])
        style.configure("Treeview", background=PANEL, fieldbackground=PANEL, rowheight=27, borderwidth=0)
        style.configure("Treeview.Heading", background=ALT, relief="flat")
        style.map("Treeview", background=[("selected", "#275467")], foreground=[("selected", FG)])
        style.configure("TCombobox", arrowsize=15, borderwidth=0, selectbackground=PANEL, selectforeground=FG)
        style.map("TCombobox", fieldbackground=[("readonly", PANEL)], foreground=[("readonly", FG)])
        style.configure("TEntry", borderwidth=0, padding=5)
        style.configure("TCheckbutton", background=BG, padding=4)
        style.map("TCheckbutton", background=[("active", ALT)])
        self.root.option_add("*TCombobox*Listbox.background", PANEL)
        self.root.option_add("*TCombobox*Listbox.foreground", FG)

    def label(self, parent, text="", **kw):
        return ttk.Label(parent, text=text, **kw)

    def button(self, parent, text, cmd, primary=False):
        return ttk.Button(parent, text=text, command=cmd, style="Primary.TButton" if primary else "TButton")

    def tree(self, parent, columns, headings, widths, height=10):
        host = ttk.Frame(parent)
        host.pack(fill="both", expand=True, pady=(4, 0))
        tree = ttk.Treeview(host, columns=columns, show="headings", height=height, selectmode="browse")
        scroll = ttk.Scrollbar(host, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        for col, heading, width in zip(columns, headings, widths):
            tree.heading(col, text=heading, anchor="w")
            tree.column(col, width=width, minwidth=min(60, width), stretch=(col == columns[-1]), anchor="w")
        tree.tag_configure("yes", foreground=TEAL)
        tree.tag_configure("no", foreground=RED)
        tree.tag_configure("maybe", foreground=SECONDARY)
        tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        return tree

    def build(self):
        main = ttk.Frame(self.root, padding=(22, 16))
        main.pack(fill="both", expand=True)
        mast = ttk.Frame(main)
        mast.pack(fill="x")
        self.label(mast, "STRONGHOLD PROTOCOL   /   SEQUENCE I", style="Accent.TLabel",
                   font=("Consolas", 10, "bold")).pack(anchor="w")
        self.label(mast, "卫戍协议助手", style="Title.TLabel").pack(anchor="w", pady=(1, 2))
        self.label(mast, textvariable=self.status, style="Sub.TLabel", wraplength=850).pack(anchor="w", pady=(0, 12))
        bar = ttk.Frame(main)
        bar.pack(fill="x", pady=(0, 9))
        self.window_box = ttk.Combobox(bar, textvariable=self.win_name, width=54, state="readonly")
        self.window_box.pack(side="left", fill="x", expand=True)
        self.window_box.bind("<<ComboboxSelected>>", self.pick_window)
        self.button(bar, "自动找窗口", self.auto_window).pack(side="left", padx=(8, 4))
        self.run_button = self.button(bar, "暂停识别", self.toggle, True)
        self.run_button.pack(side="left", padx=(4, 0))

        tabs = ttk.Notebook(main)
        tabs.pack(fill="both", expand=True)
        self.monitor, self.pool, self.guides, self.gear, self.settings = [
            ttk.Frame(tabs, padding=12) for _ in range(5)]
        for page, title in zip((self.monitor, self.pool, self.guides, self.gear, self.settings),
                               ("实时识别", "盟约与可用池", "阵容与攻略", "装备提示", "采集设置")):
            tabs.add(page, text=title)
        self.build_monitor()
        self.build_pool()
        self.build_guides()
        self.build_equipment()
        self.build_settings()

    def build_monitor(self):
        line = ttk.Frame(self.monitor)
        line.pack(fill="x")
        self.label(line, textvariable=self.guide_text, style="Accent.TLabel",
                   font=("Microsoft YaHei UI", 13, "bold")).pack(side="left")
        self.button(line, "结束回放", self.end_preview).pack(side="right", padx=(6, 0))
        self.button(line, "识别截图", self.open_image).pack(side="right")
        self.scene_text = self.label(self.monitor, "等待客户端画面", style="Sub.TLabel")
        self.scene_text.pack(anchor="w", pady=(8, 5))
        self.monitor_tree = self.tree(self.monitor, ("kind", "name", "hint"), ("类型", "识别结果", "阵容提示"),
                                      (95, 210, 490))
        self.raw_text = self.label(self.monitor, style="Sub.TLabel", wraplength=900)
        self.raw_text.pack(anchor="w", pady=(7, 0))
        self.button(self.monitor, "查看最近一帧", self.show_frame).pack(anchor="w", pady=(6, 0))

    def build_pool(self):
        bar = ttk.Frame(self.pool)
        bar.pack(fill="x")
        self.button(bar, "新一局 / 清除 BAN", self.reset_bans).pack(side="right")
        self.group_buttons = ttk.Frame(bar)
        self.group_buttons.pack(side="left", fill="x")
        self.pool_summary = self.label(self.pool, style="Sub.TLabel", wraplength=880)
        self.pool_summary.pack(anchor="w", pady=(7, 2))
        body = ttk.Frame(self.pool)
        body.pack(fill="both", expand=True)
        left, right = ttk.Frame(body), ttk.Frame(body)
        left.pack(side="left", fill="both", padx=(0, 9))
        right.pack(side="left", fill="both", expand=True)
        self.label(left, "盟约状态 · 双击校正").pack(anchor="w")
        self.label(right, "当前可用池 · 按盟约分组").pack(anchor="w")
        self.pact_tree = self.tree(left, ("pact", "state"), ("盟约", "状态"), (98, 130))
        self.pact_tree.bind("<<TreeviewSelect>>", lambda _: self.update_pool_operators())
        self.pact_tree.bind("<Double-1>", self.cycle_pact)
        self.pact_tree.bind("<Return>", self.cycle_pact)
        self.operator_tree = self.tree(right, ("tier", "name", "state", "pacts"),
                                       ("等阶", "干员", "可用状态", "所属盟约"), (55, 135, 85, 250))

    def build_guides(self):
        bar = ttk.Frame(self.guides)
        bar.pack(fill="x")
        self.button(bar, "选定阵容", self.select_guide, True).pack(side="left")
        self.button(bar, "导入攻略 JSON", self.import_guide).pack(side="left", padx=8)
        self.button(bar, "打开攻略来源", self.open_guide_source).pack(side="left")
        self.guide_tree = self.tree(self.guides, ("name", "viability", "strategies"),
                                    ("阵容 · 按当前可用池排序", "核心盟约", "推荐策略"), (220, 125, 440), height=5)
        self.guide_tree.bind("<<TreeviewSelect>>", lambda _: self.guide_detail())
        self.guide_tree.bind("<Double-1>", lambda _: self.select_guide())
        self.details = tk.Text(self.guides, height=8, relief="flat", wrap="word", background=PANEL,
                               foreground=FG, padx=12, pady=9, font=FONT, state="disabled")
        self.details.pack(fill="both", expand=True, pady=(8, 0))

    def build_equipment(self):
        bar = ttk.Frame(self.gear)
        bar.pack(fill="x")
        self.label(bar, "搜索").pack(side="left", padx=(0, 5))
        self.equipment_search = tk.StringVar()
        self.equipment_search.trace_add("write", lambda *_: self.update_equipment())
        ttk.Entry(bar, textvariable=self.equipment_search, width=23).pack(side="left")
        for text, mode in [("勾选提醒", "enabled"), ("屏蔽", "muted"), ("跟随攻略", "auto")]:
            self.button(bar, text, lambda mode=mode: self.equipment_action(mode)).pack(side="left", padx=(6, 0))
        self.label(self.gear, "屏蔽优先于攻略。勾选后，即使攻略没有列出这件装备也会提醒。",
                   style="Sub.TLabel").pack(anchor="w", pady=(7, 2))
        self.equipment_tree = self.tree(self.gear, ("tier", "name", "mode", "note"),
                                       ("等阶", "装备", "提示状态", "攻略建议"), (65, 190, 125, 380))

    def build_settings(self):
        self.label(self.settings, "采集方式", font=("Microsoft YaHei UI", 13, "bold")).pack(anchor="w", pady=(0, 8))
        self.label(self.settings, "默认读取游戏窗口。窗口在前台时会显示鼠标穿透提示。",
                   style="Sub.TLabel").pack(anchor="w")
        ttk.Checkbutton(self.settings, text="开启游戏内置顶浮层", variable=self.show_overlay,
                        command=self.save).pack(anchor="w", pady=7)
        ttk.Checkbutton(self.settings, text="通过 ADB 抓取模拟器画面", variable=self.use_adb,
                        command=self.invalidate).pack(anchor="w")
        for title, var in [("ADB 程序路径", self.adb), ("设备序列号", self.serial)]:
            row = ttk.Frame(self.settings)
            row.pack(fill="x", pady=4)
            self.label(row, title, width=15).pack(side="left")
            entry = ttk.Entry(row, textvariable=var)
            entry.pack(fill="x", expand=True)
            entry.bind("<Return>", lambda _: self.invalidate())
            entry.bind("<FocusOut>", lambda _: self.save())
        row = ttk.Frame(self.settings)
        row.pack(fill="x", pady=7)
        self.label(row, "识别场景", width=15).pack(side="left")
        selector = ttk.Combobox(row, values=SCENES, textvariable=self.scene, state="readonly", width=20)
        selector.pack(side="left")
        selector.bind("<<ComboboxSelected>>", lambda _: self.invalidate())
        self.label(self.settings, "默认自动识别。特殊皮肤或布局下可手动指定场景，或在盟约页校正。",
                   style="Sub.TLabel").pack(anchor="w", pady=8)

    def save(self):
        try:
            save_json(SETTINGS_DIR / "settings.json", {
                "guide": self.guide_id, "enabled": sorted(self.enabled), "muted": sorted(self.muted),
                "overlay": self.show_overlay.get(), "adb": self.adb.get(), "serial": self.serial.get(),
                "use_adb": self.use_adb.get(),
            })
        except OSError as exc:
            self.status.set(f"无法保存设置 · {exc}")

    def refresh_windows(self):
        items = windows.list_windows()
        self.windows = {item.label: item for item in items}
        self.window_box.configure(values=list(self.windows))
        if self.manual_window:
            current = next((item for item in items if self.window and item.hwnd == self.window.hwnd), None)
        else:
            active = windows.foreground()
            current = next((item for item in items if item.score and item.hwnd == active), None)
            if current is None:
                best = next((item for item in items if item.score), None)
                incumbent = next((item for item in items if self.window and item.hwnd == self.window.hwnd), None)
                current = incumbent if incumbent and best and incumbent.score >= best.score else best
        if not current and self.manual_window:
            self.manual_window = False
        self.attach(current)
        self.last_windows = time.monotonic()

    def attach(self, window):
        old_id = self.window.hwnd if self.window else None
        self.window = window
        self.win_name.set(window.label if window else "")
        if (window.hwnd if window else None) != old_id and not self.preview:
            self.reset_bans()
            self.invalidate()

    def pick_window(self, _):
        selected = self.windows.get(self.win_name.get())
        self.manual_window = True
        self.end_preview()
        self.attach(selected)

    def auto_window(self):
        self.manual_window = False
        self.end_preview()
        self.refresh_windows()

    def invalidate(self):
        self.generation += 1
        self.reading, self.frame = Reading(), None
        self.last_scan = 0
        self.overlay.hide()
        self.save()
        self.update_views()

    def toggle(self):
        self.running = not self.running
        self.run_button.configure(text="暂停识别" if self.running else "继续识别")
        self.invalidate()

    def reset_bans(self):
        self.auto_states.clear()
        self.manual_states.clear()
        self.excluded.clear()
        self.groups.clear()
        self.group = None
        self.partial_groups = False
        self.partial_pacts.clear()
        self.last_bans = None
        self.observed_shop = False
        self.update_views()

    def cycle_pact(self, _):
        selected = self.pact_tree.selection()
        if not selected:
            return
        name = selected[0]
        value = self.manual_states.get(name)
        if value is False:
            self.manual_states.pop(name, None)
        else:
            self.manual_states[name] = value is None
        self.update_views()

    def use_group(self, index):
        self.group = index
        self.partial_pacts.clear()
        for i, group in enumerate(self.groups):
            for name in group:
                if self.partial_groups and i != index:
                    self.auto_states.pop(name, None)
                    self.partial_pacts.add(name)
                else:
                    self.auto_states[name] = i == index
        self.update_views()

    def select_guide(self):
        chosen = self.guide_tree.selection()
        if chosen:
            self.guide_id = chosen[0]
            self.save()
            self.update_views()

    def open_guide_source(self):
        chosen = self.guide_tree.selection()
        if chosen:
            sources = self.season.lineups[chosen[0]]["sources"]
            if sources:
                webbrowser.open(sources[0]["url"])

    def import_guide(self):
        path = filedialog.askopenfilename(filetypes=[("攻略 JSON", "*.json")])
        if not path:
            return
        try:
            guide = self.season.add_guide(Path(path))
            import hashlib
            filename = hashlib.sha256(guide["id"].encode("utf-8")).hexdigest()[:16] + ".json"
            try:
                save_json(SETTINGS_DIR / "guides" / filename, guide)
            except OSError:
                self.season.lineups.pop(guide["id"])
                raise
        except (OSError, ValueError) as exc:
            messagebox.showerror("攻略导入失败", str(exc))
            return
        self.guide_id = guide["id"]
        self.save()
        self.update_views()

    def equipment_action(self, mode):
        chosen = self.equipment_tree.selection()
        if not chosen:
            return
        name = chosen[0]
        self.enabled.discard(name)
        self.muted.discard(name)
        if mode == "enabled":
            self.enabled.add(name)
        if mode == "muted":
            self.muted.add(name)
        self.save()
        self.update_views()

    def open_image(self):
        path = filedialog.askopenfilename(filetypes=[("图像", "*.png *.jpg *.jpeg *.webp *.bmp")])
        if not path:
            return
        self.preview = True
        self.reset_bans()
        self.invalidate()
        self.status.set("正在识别截图")
        self.submit(Path(path))

    def end_preview(self):
        if self.preview:
            self.preview = False
            self.reset_bans()
            self.invalidate()

    def show_frame(self):
        if self.frame is None:
            return
        window = tk.Toplevel(self.root)
        window.title("最近采集画面")
        im = self.frame.copy()
        im.thumbnail((1080, 650))
        preview = ImageTk.PhotoImage(im)
        label = ttk.Label(window, image=preview)
        label.image = preview
        label.pack()

    def submit(self, source):
        self.active_job = self.generation
        scene = self.scene.get()
        self.scanner.requests.put((self.generation, source, "" if scene == SCENES[0] else scene))

    def tick(self):
        now = time.monotonic()
        if now - self.last_windows > 2.5 and not self.preview:
            self.refresh_windows()
        try:
            while True:
                generation, reading, frame, error = self.scanner.responses.get_nowait()
                if generation == self.active_job:
                    self.active_job = None
                if generation == self.generation:
                    self.accept(reading, frame, error)
        except Empty:
            pass

        if not self.preview and self.running and self.active_job is None and self.scanner.requests.empty():
            if now - self.last_scan > .85:
                self.last_scan = now
                if self.window and windows.bounds(self.window.hwnd):
                    if self.use_adb.get():
                        if self.adb.get().strip() and self.serial.get().strip():
                            self.submit((self.adb.get().strip(), self.serial.get().strip()))
                        else:
                            self.status.set("请在采集设置填写 ADB 路径和设备序列号")
                    else:
                        self.submit(self.window.hwnd)
                else:
                    self.status.set("等待客户端 · 打开明日方舟或模拟器，或从下拉框手动绑定")
        self.paint_overlay()
        self.root.after(125, self.tick)

    def accept(self, reading, frame, error):
        if error:
            self.status.set(f"采集暂不可用 · {error}")
            self.reading, self.frame = Reading(), None
            self.update_views()
            return
        self.reading, self.frame = reading, frame
        if reading.scene == "调度中心":
            self.observed_shop = True
        if reading.scene == "盟约选择" and (reading.groups or reading.pacts or reading.excluded):
            if self.observed_shop and (reading.groups or reading.pacts != self.auto_states):
                self.reset_bans()
            fingerprint = (reading.pacts, reading.excluded, reading.groups,
                           reading.selected_group, reading.partial_groups)
            if self.preview or self.last_bans == fingerprint:
                self.auto_states.update(reading.pacts)
                self.excluded.update(reading.excluded)
                if reading.groups:
                    self.groups = reading.groups
                    self.partial_groups = reading.partial_groups
                if reading.selected_group is not None:
                    self.use_group(reading.selected_group)
            self.last_bans = fingerprint
        else:
            self.last_bans = None
        source = "截图回放" if self.preview else self.window.title
        self.status.set(f"{source}   /   {reading.scene or '等待卫戍协议界面'}")
        self.update_views()

    def callouts(self):
        return alerts(self.reading, self.guide, self.enabled, self.muted,
                      self.states, self.season, self.excluded)

    def paint_overlay(self):
        if (self.preview or not self.running or not self.frame or not self.window
                or windows.foreground() != self.window.hwnd or not self.show_overlay.get()):
            self.overlay.hide()
            return
        region = windows.capture_bounds(self.window.hwnd)
        if not region:
            self.overlay.hide()
            return
        callouts = self.callouts()
        banner = ""
        if self.reading.scene == "盟约选择":
            if self.groups:
                ranked = []
                for i, group in enumerate(self.groups):
                    other = self.groups[1-i]
                    ranked_guide = self.season.rank(self.states | dict.fromkeys(other, False)
                                                    | dict.fromkeys(group, True), self.excluded)[0]
                    ranked.append(f"{i+1}组 {ranked_guide['name']}")
                banner = "  /  ".join(ranked)
            elif self.states:
                guide = self.season.rank(self.states, self.excluded)[0]
                banner = f"阵容建议  {guide['name']}"
        elif self.reading.scene == "策略轮选" and self.guide:
            picks = self.guide["strategies"]
            if picks:
                visible = [name for name in picks if any(hit.name == name for hit, _ in callouts)]
                banner = ("当前可见  " if visible else "攻略优先  ") + "  →  ".join(visible or picks)
        if callouts or banner:
            self.overlay.show(region, self.frame.size, callouts, banner)
        else:
            self.overlay.hide()

    @staticmethod
    def fill(tree, rows):
        old = tree.get_children()
        if len(old) == len(rows) and all(
            item == row[0] and tuple(map(str, tree.item(item, "values"))) == tuple(map(str, row[1]))
            and tree.item(item, "tags") == tuple(filter(None, [row[2]]))
            for item, row in zip(old, rows)
        ):
            return
        selected = tree.selection()
        offset = tree.yview()[0]
        tree.delete(*old)
        for item, values, tag in rows:
            tree.insert("", "end", iid=item, values=values, tags=(tag,) if tag else ())
        if selected and tree.exists(selected[0]):
            tree.selection_set(selected[0])
        tree.yview_moveto(offset)

    def update_views(self):
        if self.guide:
            self.guide_text.set(f"已选阵容  /  {self.guide['name']}")
        else:
            self.guide_text.set("在「阵容与攻略」选定一套阵容")
        self.scene_text.configure(text=f"{self.reading.scene or '等待场景'}  ·  {len(self.reading.hits)} 条识别结果")
        self.raw_text.configure(text="OCR  /  " + " · ".join(self.reading.text[:24]) if self.reading.text else "")
        notices = dict(self.callouts())
        rows = [(str(i), (hit.kind, hit.name, notices.get(hit, "")), "yes" if hit in notices else "")
                for i, hit in enumerate(self.reading.hits)]
        self.fill(self.monitor_tree, rows)
        self.update_pool()
        self.update_guides()
        self.update_equipment()

    def update_pool(self):
        labels = {True: ("可用", "yes"), False: ("禁用", "no"), None: ("未确认", "maybe")}
        rows = []
        for name, pact in self.season.pacts.items():
            status, tag = labels[self.states.get(name)]
            if status == "未确认" and name in self.partial_pacts:
                status = "阵容不完整"
            if name in self.manual_states:
                status += " · 手动"
            rows.append((name, (name, ("核心" if pact["core"] else "附加") + " / " + status), tag))
        self.fill(self.pact_tree, rows)
        if not self.pact_tree.selection() and rows:
            self.pact_tree.selection_set(rows[0][0])
        group_buttons = tuple((i, "第 " + str(i+1) + " 组" + (" ✓" if i == self.group else ""))
                              for i in range(len(self.groups)))
        if group_buttons != getattr(self, "shown_group_buttons", ()):
            self.shown_group_buttons = group_buttons
            for widget in self.group_buttons.winfo_children():
                widget.destroy()
            for i, name in group_buttons:
                self.button(self.group_buttons, name, lambda i=i: self.use_group(i), i == self.group).pack(
                    side="left", padx=(0, 6))
        if self.groups:
            group_text = "  /  ".join(f"{i+1}组 {'、'.join(sorted(group))}" for i, group in enumerate(self.groups))
            self.pool_summary.configure(text=group_text)
        else:
            self.pool_summary.configure(text=f"已确认 {len(self.states)} 项盟约 · 已识别禁用干员 {len(self.excluded)} 名")
        self.update_pool_operators()

    def update_pool_operators(self):
        if not self.pact_tree.selection():
            return
        name = self.pact_tree.selection()[0]
        members = self.season.grouped(self.states, self.excluded)[name]
        labels = {True: ("可用", "yes"), None: ("待确认", "maybe")}
        rows = []
        for operator in sorted(members, key=lambda name: (self.season.operators[name]["tier"], name)):
            status, tag = labels[self.season.status(operator, self.states, self.excluded)]
            data = self.season.operators[operator]
            rows.append((operator, (data["tier"], operator, status, " · ".join(data["pacts"])), tag))
        self.fill(self.operator_tree, rows)

    def update_guides(self):
        names = [hit.name for hit in self.reading.hits if hit.kind == "干员" and hit.name not in self.excluded]
        rows = []
        for guide in self.season.rank(self.states, self.excluded, names):
            core = set(guide["targets"]) & self.season.core
            blocked = any(self.states.get(pact) is False for pact in core)
            open_core = bool(core) and all(self.states.get(pact) is True for pact in core)
            state, tag = ("已禁用", "no") if blocked else ("已确认", "yes") if open_core else ("待确认", "maybe")
            if state == "待确认" and core & self.partial_pacts:
                state = "阵容不完整"
            selected = "✓  " if guide["id"] == self.guide_id else ""
            rows.append((guide["id"], (selected + guide["name"], state, " → ".join(guide["strategies"])), tag))
        self.fill(self.guide_tree, rows)
        if not self.guide_tree.selection() and rows:
            self.guide_tree.selection_set(self.guide_id or rows[0][0])
        self.guide_detail()

    def guide_detail(self):
        choice = self.guide_tree.selection()
        if not choice:
            return
        guide = self.season.lineups[choice[0]]
        lines = ["成型目标  " + " · ".join(f"{pact} ×{count}" for pact, count in guide["targets"].items())]
        if guide["strategies"]:
            lines.append("策略顺位  " + " → ".join(guide["strategies"]))
        for stage in guide["stages"]:
            heading = "  ".join(filter(None, [stage["name"], str(stage.get("timing", ""))]))
            viable = lambda name: self.season.status(name, self.states, self.excluded) is not False
            core = [name for name in stage.get("core", []) if viable(name)]
            other = [name for name in stage.get("operators", []) if name not in core and viable(name)]
            lines.append(f"{heading}  核心 {'、'.join(core) or '—'}")
            if other:
                lines.append("      可选  " + "、".join(other))
        if guide["equipment"]:
            lines.append("关键装备  " + " · ".join(guide["equipment"]))
        if guide["sources"]:
            lines.append("攻略来源  " + " · ".join(src["label"] for src in guide["sources"]))
        value = "\n".join(lines)
        if self.details.get("1.0", "end-1c") != value:
            self.details.configure(state="normal")
            self.details.delete("1.0", "end")
            self.details.insert("1.0", value)
            self.details.configure(state="disabled")

    def update_equipment(self):
        search = key(self.equipment_search.get())
        recommendations = self.guide["equipment"] if self.guide else {}
        rows = []
        for name, item in self.season.equipment.items():
            if search and search not in key(name):
                continue
            if name in self.muted:
                mode, tag = "已屏蔽", "no"
            elif name in self.enabled:
                mode, tag = "已勾选", "yes"
            elif name in recommendations:
                mode, tag = "攻略提醒", "yes"
            else:
                mode, tag = "跟随攻略", "maybe"
            rows.append((name, (item["tier"], name, mode, recommendations.get(name, "")), tag))
        self.fill(self.equipment_tree, rows)

    def close(self):
        self.save()
        self.root.destroy()


def run():
    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=SETTINGS_DIR / "assistant.log", level=logging.INFO,
                        encoding="utf-8", format="%(asctime)s %(levelname)s %(message)s")
    windows.enable_dpi()
    root = tk.Tk()
    Dashboard(root)
    root.mainloop()
