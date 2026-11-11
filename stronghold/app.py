"""Desktop dashboard and live capture loop."""
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from queue import Empty, Queue
from threading import Thread
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import webbrowser

from PIL import Image, ImageTk

from . import windows
from . import VERSION
from .updates_ui import UpdateController, complete_startup
from .domain import MatchState, Reading, Season, alerts, key
from .overlay import Overlay
from .pc_input import operate_shop
from .vision import Recognizer
from .stock import Holding
from .ui import (BG, PANEL, ALT, LINE, FG, SECONDARY, TEAL, GOLD, RED, FONT,
                 TerminalHeader, NavItem, SectionPanel, Metric, ScrollColumn)

SCENES = ("自动识别", "调度中心", "盟约选择", "策略轮选", "自选编队", "装备选择", "队友阵容")
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


@dataclass(frozen=True)
class ShopRequest:
    hwnd: int
    action: str


@dataclass(frozen=True)
class RosterRequest:
    frame: object
    slot: str


class Scanner(Thread):
    def __init__(self, season):
        super().__init__(daemon=True)
        self.season = season
        self.requests = Queue()
        self.responses = Queue()
        self.shop_responses = Queue()

    def run(self):
        recognizer = None
        while True:
            generation, source, scene = self.requests.get()
            if isinstance(source, ShopRequest):
                try:
                    if recognizer is None:
                        recognizer = Recognizer(self.season)
                    result = operate_shop(source.hwnd, source.action, recognizer, SETTINGS_DIR / "maa")
                    self.shop_responses.put(result)
                except Exception as exc:
                    logging.exception("PC single-step input failed")
                    self.shop_responses.put(f"PC 单步操作失败 · {exc}")
                continue
            try:
                capture_start = time.perf_counter()
                if isinstance(source, RosterRequest):
                    frame = source.frame
                elif isinstance(source, Path):
                    with Image.open(source) as image:
                        frame = image.convert("RGB")
                elif isinstance(source, tuple):
                    frame = windows.adb_capture(*source)
                else:
                    frame = windows.capture(source)
                capture_ms = round((time.perf_counter()-capture_start)*1000)
                if recognizer is None:
                    recognizer = Recognizer(self.season)
                reading = recognizer.inspect(frame, "队友阵容" if isinstance(source, RosterRequest) else scene)
                reading.capture_ms = capture_ms
                if isinstance(source, RosterRequest):
                    reading.roster_slot = source.slot
                self.responses.put((generation, reading, frame, None))
            except Exception as exc:
                logging.exception("Capture or OCR failed")
                self.responses.put((generation, None, None, str(exc)))


class Dashboard:
    def __init__(self, root):
        self.root = root
        root.title(f"卫戍协议助手 {VERSION} · 规程终端")
        root.geometry("1280x900")
        root.minsize(1080, 800)
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
        self.capacities = {int(k): v for k, v in settings.get("pool_capacity", {}).items()
                           if str(k) in {"1", "2", "3", "4", "5", "6"} and type(v) is int and v > 0}
        self.show_overlay = tk.BooleanVar(value=settings.get("overlay", True))
        scale = settings.get("overlay_scale", 1.35)
        scale = max(.8, min(2., scale)) if isinstance(scale, (int, float)) else 1.35
        self.overlay_scale = tk.DoubleVar(value=scale)
        self.overlay_font_text = tk.StringVar(value=f"浮层字号  {round(scale * 100)}%")
        self.scene = tk.StringVar(value=SCENES[0])
        self.adb = tk.StringVar(value=settings.get("adb") or windows.find_adb())
        self.serial = tk.StringVar(value=settings.get("serial", ""))
        self.use_adb = tk.BooleanVar(value=settings.get("use_adb", False))
        self.win_name = tk.StringVar()
        self.status = tk.StringVar(value="正在寻找客户端")
        self.guide_text = tk.StringVar(value="尚未选定阵容")
        self.pc_status = tk.StringVar(value="PC 单步操作 · 回合整备期" if windows.is_admin()
                                      else "PC 单步操作需以管理员身份运行助手")
        self.pc_pending = False
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
        self.match = MatchState()
        self.live_match = None
        self.strategy_advice = None
        self.banner = ""
        self.confirmed_only = tk.BooleanVar(value=False)
        self.updater = UpdateController(self, SETTINGS_DIR, settings.get("auto_update_check", True))
        self.configure_styles()
        self.build()
        self.overlay = Overlay(root)
        root.bind_all('<Map>', self.style_window, add='+')
        self.scanner = Scanner(self.season)
        self.scanner.start()
        self.refresh_windows()
        self.update_views()
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.after(150, self.tick)

    def style_window(self, event):
        if isinstance(event.widget, (tk.Tk, tk.Toplevel)):
            windows.terminal_window(event.widget.winfo_id())

    @property
    def guide(self):
        return self.season.lineups.get(self.guide_id)

    @property
    def states(self):
        return self.match.states

    def configure_styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(".", background=BG, foreground=FG, fieldbackground=PANEL, font=FONT)
        style.configure("TFrame", background=BG)
        style.configure("Card.TFrame", background=PANEL)
        style.configure("TLabel", background=BG, foreground=FG)
        style.configure("Card.TLabel", background=PANEL, foreground=FG)
        style.configure("Title.TLabel", font=("Microsoft YaHei UI", 18, "bold"))
        style.configure("Sub.TLabel", foreground=SECONDARY)
        style.configure("Accent.TLabel", foreground=TEAL)
        style.configure("TButton", padding=(12, 7), borderwidth=0, background=ALT, foreground=FG,
                        focusthickness=1, focuscolor=TEAL)
        style.map("TButton", background=[("active", "#2b493b"), ("disabled", PANEL)],
                  foreground=[("disabled", "#53685d")])
        style.configure("Primary.TButton", background=TEAL, foreground="#0a2017", font=("Microsoft YaHei UI",10,"bold"))
        style.map("Primary.TButton", background=[("active", "#8ef1e1")])
        style.configure("TNotebook", background=BG, borderwidth=0, bordercolor=BG, lightcolor=BG,darkcolor=BG)
        style.configure("TNotebook.Tab", padding=(14, 8), background=PANEL)
        style.map("TNotebook.Tab", background=[("selected", ALT)], foreground=[("selected", TEAL)])
        style.configure("Workspace.TNotebook", background=BG, borderwidth=0, tabmargins=0,
                        bordercolor=BG,lightcolor=BG,darkcolor=BG)
        style.layout("Workspace.TNotebook.Tab", [])
        style.configure("Treeview", background=PANEL, fieldbackground=PANEL, rowheight=32, borderwidth=0,
                        bordercolor=PANEL,lightcolor=PANEL,darkcolor=PANEL)
        style.configure("Treeview.Heading", background=ALT, foreground=SECONDARY, relief="flat",
                        padding=(7,7), font=("Microsoft YaHei UI",9,"bold"))
        style.map("Treeview", background=[("selected", "#28483a")], foreground=[("selected", FG)])
        style.configure("Vertical.TScrollbar", background=ALT, troughcolor=PANEL, borderwidth=0,
                        arrowcolor=SECONDARY, arrowsize=11)
        style.configure("Horizontal.TScrollbar", background=ALT, troughcolor=PANEL, borderwidth=0,
                        arrowcolor=SECONDARY, arrowsize=11)
        style.configure("TCombobox", arrowsize=15, borderwidth=0, selectbackground=PANEL, selectforeground=FG,
                        bordercolor=LINE,lightcolor=LINE,darkcolor=LINE,arrowcolor=TEAL)
        style.map("TCombobox", fieldbackground=[("readonly", PANEL)], foreground=[("readonly", FG)])
        style.configure("TEntry", borderwidth=0, padding=7, insertcolor=TEAL)
        style.configure("TCheckbutton", background=BG, padding=4)
        style.map("TCheckbutton", background=[("active", ALT)])
        self.root.option_add("*TCombobox*Listbox.background", PANEL)
        self.root.option_add("*TCombobox*Listbox.foreground", FG)

    def label(self, parent, text="", **kw):
        if isinstance(parent, tk.Frame):
            kw.setdefault('background', parent.cget('background'))
        return ttk.Label(parent, text=text, **kw)

    def button(self, parent, text, cmd, primary=False):
        return ttk.Button(parent, text=text, command=cmd, style="Primary.TButton" if primary else "TButton")

    def tree(self, parent, columns, headings, widths, height=10):
        host = ttk.Frame(parent)
        host.pack(fill="both", expand=True, pady=(4, 0))
        tree = ttk.Treeview(host, columns=columns, show="headings", height=height, selectmode="browse")
        scroll = ttk.Scrollbar(host, orient="vertical", command=tree.yview)
        horizontal = ttk.Scrollbar(host, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=scroll.set, xscrollcommand=horizontal.set)
        for col, heading, width in zip(columns, headings, widths):
            tree.heading(col, text=heading, anchor="w")
            tree.column(col, width=width, minwidth=min(60, width), stretch=(col == columns[-1]), anchor="w")
        tree.tag_configure("yes", foreground=TEAL)
        tree.tag_configure("no", foreground=RED)
        tree.tag_configure("maybe", foreground=SECONDARY)
        tree.tag_configure("core", foreground=GOLD)
        host.columnconfigure(0, weight=1)
        host.rowconfigure(0, weight=1)
        tree.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        return tree

    def build(self):
        main = ttk.Frame(self.root, padding=(18, 12))
        main.pack(fill="both", expand=True)
        self.terminal_header = TerminalHeader(main)
        self.terminal_header.pack(fill='x', pady=(0,10))
        footer = ttk.Frame(main)
        footer.pack(side='bottom', fill='x', pady=(8,0))
        self.footer_status = self.label(footer, textvariable=self.status, style="Sub.TLabel", font=("Microsoft YaHei UI",8))
        self.footer_status.pack(side='left', fill='x', expand=True)
        ttk.Button(footer, textvariable=self.updater.badge, command=self.updater.check).pack(side='right')
        body = ttk.Frame(main)
        body.pack(fill='both', expand=True)
        sidebar = ttk.Frame(body, width=172)
        sidebar.pack(side='left', fill='y', padx=(0,16))
        sidebar.pack_propagate(False)
        self.label(sidebar, '终端工作区', style='Sub.TLabel', font=('Microsoft YaHei UI',9)).pack(anchor='w', padx=14,pady=(8,12))
        self.nav_items = []
        navigation = [('实时监测','LIVE MONITOR'),('可用干员','OPERATOR POOL'),('禁用卡池','BAN / SHARED POOL'),
                      ('阵容攻略','LINEUP / GUIDE'),('装备提醒','EQUIPMENT'),('采集设置','TERMINAL SETTINGS')]
        for i, (title, caption) in enumerate(navigation):
            item = NavItem(sidebar, i+1, title, caption, lambda i=i:self.navigate(i))
            item.pack(fill='x', pady=2)
            self.nav_items.append(item)
            self.root.bind(f'<Control-Key-{i+1}>', lambda _, i=i:self.navigate(i))
        self.label(sidebar, 'SEQUENCE Ⅰ\n\n规程 · 序列 Ⅰ\n简中客户端\n\nCtrl + 1–6 切换', style='Sub.TLabel',
                   font=('Microsoft YaHei UI',8), justify='left').pack(side='bottom',anchor='w',padx=14,pady=18)
        workspace = ttk.Frame(body)
        workspace.pack(side='left', fill='both', expand=True)
        heading = ttk.Frame(workspace)
        heading.pack(fill='x', pady=(1,12))
        self.page_title = self.label(heading, style='Title.TLabel')
        self.page_title.pack(side='left')
        self.page_caption = self.label(heading, style='Sub.TLabel', font=('Consolas',9))
        self.page_caption.pack(side='right',pady=(9,0))
        bar = ttk.Frame(workspace)
        bar.pack(fill="x", pady=(0, 12))
        self.window_box = ttk.Combobox(bar, textvariable=self.win_name, width=24, state="readonly")
        self.window_box.bind("<<ComboboxSelected>>", self.pick_window)
        self.run_button = self.button(bar, "暂停识别", self.toggle, True)
        self.run_button.pack(side="right", padx=(8, 0))
        self.button(bar, "自动找窗口", self.auto_window).pack(side="right", padx=(8, 0))
        self.window_box.pack(side="left", fill="x", expand=True)

        tabs = self.tabs = ttk.Notebook(workspace, style='Workspace.TNotebook')
        tabs.pack(fill="both", expand=True)
        self.monitor, self.pool, self.evidence, self.guides, self.gear, self.settings = [
            ttk.Frame(tabs, padding=(0,0,0,0)) for _ in range(6)]
        for page, title in zip((self.monitor, self.pool, self.evidence, self.guides, self.gear, self.settings),
                               ("实时识别", "盟约与可用池", "BAN与共享池", "阵容与攻略", "装备提示", "采集设置")):
            tabs.add(page, text=title)
        self.build_monitor()
        self.build_pool()
        self.build_evidence()
        self.build_guides()
        self.build_equipment()
        self.build_settings()
        tabs.bind('<<NotebookTabChanged>>', self.page_changed)
        self.page_changed()

    def navigate(self, index):
        self.tabs.select(index)
        self.page_changed()

    def page_changed(self, _=None):
        index = self.tabs.index('current')
        previous = getattr(self,'page_index',None)
        self.page_index = index
        titles = ('实时监测','盟约与可用干员','本局禁用与共享卡池','阵容与攻略','关键装备提醒','采集与浮层设置')
        captions = ('LIVE / MONITOR','PACT / OPERATOR POOL','BAN / SHARED POOL','LINEUP / STRATEGY','EQUIPMENT / WATCHLIST','TERMINAL / CONFIG')
        self.page_title.configure(text=titles[index])
        self.page_caption.configure(text=captions[index])
        for i,item in enumerate(self.nav_items):
            item.select(i==index)
        if index==3 and previous!=index and self.guide_id and self.guide_tree.exists(self.guide_id):
            self.guide_tree.selection_set(self.guide_id)
            self.guide_tree.see(self.guide_id)
            self.guide_detail()

    def build_monitor(self):
        metrics = ttk.Frame(self.monitor)
        metrics.pack(fill='x', pady=(0,12))
        self.metrics = []
        for i, (title, color, text) in enumerate((('当前阶段',TEAL,True),('本局禁用',RED,False),('实时提醒',GOLD,False),('识别耗时',TEAL,False))):
            metrics.columnconfigure(i, weight=1, uniform='metric')
            metric = Metric(metrics,title,f'{i+1:02}',color,text)
            metric.grid(row=0,column=i,sticky='ew',padx=(0,10 if i<3 else 0))
            self.metrics.append(metric)
        line = ttk.Frame(self.monitor)
        line.pack(fill="x", pady=(0,10))
        self.label(line, textvariable=self.guide_text, style="Accent.TLabel",
                   font=("Microsoft YaHei UI", 11, "bold")).pack(side="left")
        self.end_preview_button = self.button(line, "结束回放", self.end_preview)
        self.end_preview_button.pack(side="right", padx=(6, 0))
        self.button(line, "识别截图", self.open_image).pack(side="right")
        controls = ttk.Frame(self.monitor)
        controls.pack(side='bottom',fill="x", pady=(10, 0))
        self.open_shop_button = self.button(controls, "展开商店", lambda: self.pc_shop("open"))
        self.close_shop_button = self.button(controls, "收起商店", lambda: self.pc_shop("close"))
        self.open_shop_button.pack(side="left")
        self.close_shop_button.pack(side="left", padx=(6, 8))
        self.label(controls, textvariable=self.pc_status, style="Sub.TLabel", font=('Microsoft YaHei UI',8),wraplength=350).pack(side="left")
        self.button(controls,'识别诊断',self.show_diagnostics).pack(side='right')
        ban = SectionPanel(self.monitor,'本局 BAN / EXCLUDED',RED)
        ban.pack(side='bottom',fill='x',pady=(10,0))
        self.button(ban.body,'完整名单 →',lambda:self.navigate(2)).pack(side='right',padx=(8,0))
        self.ban_brief = self.label(ban.body, style="Sub.TLabel", wraplength=690)
        self.ban_brief.pack(side='left',fill='x',expand=True)
        center = ttk.Frame(self.monitor)
        center.pack(fill='both',expand=True)
        center.columnconfigure(0,weight=4,uniform='monitor')
        center.columnconfigure(1,weight=5,uniform='monitor')
        center.rowconfigure(0,weight=1)
        self.plan_panel = SectionPanel(center,'当前攻略 / CURRENT PLAN')
        self.plan_panel.grid(row=0,column=0,sticky='nsew',padx=(0,12))
        self.button(self.plan_panel.body,'阵容详情 / 更换 →',self.open_current_guide).pack(side='bottom',anchor='w',pady=(10,0))
        self.role_names = {}
        role_box = tk.Frame(self.plan_panel.body,bg=PANEL)
        role_box.pack(side='bottom',fill='x',pady=(10,0))
        self.plan_scroll = ScrollColumn(self.plan_panel.body)
        self.plan_scroll.pack(fill='both',expand=True)
        body = self.plan_scroll.body
        self.plan_name = self.label(body, foreground=FG,font=('Microsoft YaHei UI',12,'bold'),wraplength=360)
        self.plan_name.pack(anchor='w',pady=(0,10))
        self.advice_text = self.label(body, foreground=FG,wraplength=360,justify='left',font=('Microsoft YaHei UI',9))
        self.advice_text.pack(anchor='w',pady=(0,10))
        self.core_text = self.label(role_box,foreground=GOLD,wraplength=360,justify='left',font=('Microsoft YaHei UI',9))
        self.core_text.pack(anchor='w',pady=(0,6))
        self.optional_text = self.label(role_box,foreground=TEAL,wraplength=360,justify='left',font=('Microsoft YaHei UI',9))
        self.optional_text.pack(anchor='w')
        self.fit_text = self.label(body,foreground=SECONDARY,wraplength=360,justify='left',font=('Microsoft YaHei UI',9))
        self.fit_text.pack(anchor='w')
        self.context_text = self.label(body,foreground=TEAL,wraplength=360,justify='left',font=('Microsoft YaHei UI',9))
        self.context_text.pack(anchor='w',pady=(12,0))
        results = SectionPanel(center,'画面提醒 / LIVE SIGNALS',GOLD)
        results.grid(row=0,column=1,sticky='nsew')
        self.scene_text = self.label(results.body,style='Sub.TLabel',font=('Microsoft YaHei UI',8))
        self.scene_text.pack(anchor='w',pady=(0,4))
        self.monitor_tree = self.tree(results.body,('kind','name','hint'),('类型','识别结果','提示'),(65,120,260),height=4)
        self.monitor_empty = self.label(self.monitor_tree,'等待可识别画面\n\n进入卫戍协议，或导入截图',background=PANEL,
                                        foreground=SECONDARY,justify='center',font=('Microsoft YaHei UI',10))
        self.raw_text = self.label(self.monitor,style='Sub.TLabel')
        self.plan_scroll.canvas.bind('<Configure>',self.resize_monitor,add='+')
        for widget in (self.plan_name,self.advice_text,self.core_text,self.optional_text,self.fit_text,self.context_text):
            widget.bind('<MouseWheel>',self.plan_scroll.wheel)

    def resize_monitor(self, _=None):
        width = max(200,self.plan_scroll.canvas.winfo_width()-10)
        for widget in (self.plan_name,self.advice_text,self.core_text,self.optional_text,self.fit_text,self.context_text):
            widget.configure(wraplength=width)
        self.ban_brief.configure(wraplength=max(350,self.monitor.winfo_width()-210))
        self.format_role_labels()

    def format_role_labels(self):
        if not self.role_names:
            return
        limit = 3 if self.plan_panel.body.winfo_width() >= 350 else 2
        for role,widget,title in [('core',self.core_text,'核心叠层'),('available',self.optional_text,'可用叠层')]:
            names=self.role_names.get(role,[])
            widget.configure(text=title+'  /  '+('、'.join(names[:limit])+('…' if len(names)>limit else '') if names else '本局暂无候选'))

    def open_current_guide(self):
        if self.guide_id and self.guide_tree.exists(self.guide_id):
            self.guide_tree.selection_set(self.guide_id)
            self.guide_tree.see(self.guide_id)
            self.guide_detail()
        self.navigate(3)

    def show_diagnostics(self):
        window = tk.Toplevel(self.root)
        window.title('识别诊断')
        window.geometry('800x560')
        window.configure(bg=BG)
        self.button(window,'查看最近一帧',self.show_frame).pack(side='bottom',anchor='e',padx=16,pady=12)
        text = tk.Text(window,bg=PANEL,fg=FG,relief='flat',wrap='word',height=1,padx=16,pady=14,font=FONT)
        text.pack(fill='both',expand=True,padx=12,pady=(12,0))
        text.insert('1.0',self.status.get()+'\n\n'+self.pc_status.get()+'\n\nOCR 原文\n'+'\n'.join(self.reading.text))
        text.configure(state='disabled')

    def build_pool(self):
        bar = ttk.Frame(self.pool)
        bar.pack(fill="x")
        self.button(bar, "新一局 / 清除 BAN", self.reset_bans).pack(side="right")
        ttk.Checkbutton(bar, text="仅显示已确认", variable=self.confirmed_only,
                        command=self.update_pool_operators).pack(side="right", padx=8)
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
        self.button(bar, "JSON 格式与模板", self.guide_format).pack(side="left", padx=8)
        self.guide_tree = self.tree(self.guides, ("name", "viability", "reason", "strategies"),
                                    ("阵容 · 按整套卡牌适配排序", "整套适配", "缺牌 / 替代依据", "推荐策略"),
                                    (220, 130, 340, 180), height=5)
        self.guide_tree.bind("<<TreeviewSelect>>", lambda _: self.guide_detail())
        self.guide_tree.bind("<Double-1>", lambda _: self.select_guide())
        details_panel = SectionPanel(self.guides,'攻略详情 / OPERATION NOTES')
        details_panel.pack(fill='both',expand=True,pady=(12,0))
        scroll = ttk.Scrollbar(details_panel.body,orient='vertical')
        scroll.pack(side='right',fill='y')
        self.details = tk.Text(details_panel.body, height=6, relief="flat", wrap="word", background=PANEL,
                               foreground=FG, padx=12, pady=9, font=FONT, state="disabled")
        self.details.pack(side='left',fill="both", expand=True)
        self.details.configure(yscrollcommand=scroll.set)
        scroll.configure(command=self.details.yview)

    def build_evidence(self):
        tabs = self.evidence_tabs = ttk.Notebook(self.evidence)
        tabs.pack(fill="both", expand=True)
        ban, stock = ttk.Frame(tabs, padding=8), ttk.Frame(tabs, padding=8)
        tabs.add(ban, text="本局 BAN 名单")
        tabs.add(stock, text="队友阵容 / 共享卡池")
        self.ban_summary = self.label(ban, wraplength=880)
        self.ban_summary.pack(anchor="w")
        self.ban_tree = self.tree(ban, ("name", "reason", "pacts"),
                                  ("禁用干员", "依据", "所属盟约"), (160, 135, 500))
        self.label(ban, "首帧盟约结果立即推算；向下滚动游戏名单会合并补读，未确认项不视为禁用。",
                   style="Sub.TLabel", wraplength=880).pack(anchor="w", pady=6)
        bar = ttk.Frame(stock)
        bar.pack(fill="x")
        self.stock_slot = tk.StringVar(value="面板1")
        ttk.Combobox(bar, textvariable=self.stock_slot, values=("面板1", "面板2", "面板3", "面板4"),
                     state="readonly", width=8).pack(side="left")
        self.button(bar, "从当前队友面板读取", self.capture_roster).pack(side="left", padx=5)
        self.button(bar, "清除此人记录", self.clear_roster).pack(side="left")
        self.button(bar, "设置总池量", self.pool_capacity).pack(side="right")
        self.stock_summary = self.label(stock, style="Sub.TLabel", wraplength=880)
        self.stock_summary.pack(anchor="w", pady=5)
        self.stock_tree = self.tree(stock, ("name", "tier", "used", "remaining"),
                                    ("干员", "等阶", "已见占用下限", "共享池估算"), (155, 55, 125, 470), height=5)
        self.stock_tree.bind("<<TreeviewSelect>>", self.choose_stock_operator)
        edit = ttk.Frame(stock)
        edit.pack(fill="x", pady=7)
        self.stock_operator = tk.StringVar(value=next(iter(self.season.operators)))
        ttk.Combobox(edit, textvariable=self.stock_operator, values=sorted(self.season.operators),
                     state="readonly", width=14).pack(side="left")
        self.stock_numbers = [tk.StringVar(value="0") for _ in range(3)]
        for title, var in zip(("普通", "精锐", "星级待确认"), self.stock_numbers):
            self.label(edit, title).pack(side="left", padx=(8, 3))
            ttk.Spinbox(edit, from_=0, to=99, textvariable=var, width=3).pack(side="left")
        self.button(edit, "保存此人持有量", self.save_holding).pack(side="left", padx=8)
        self.label(stock, "面板1–4按队友总览从上到下编号；自动识别头像只计占用下限，星级可校正。\n"
                   "记录按玩家覆盖，商店待售牌不扣卡池。默认总量待核实；普通1份、精锐暂按3份（星极2份）。\n"
                   "星级不清只计1份下限。未见备战区、赠送牌与记录时差使余量只能估算，可手动校正。",
                   style="Sub.TLabel", wraplength=880).pack(anchor="w")

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
        scroller = ScrollColumn(self.settings)
        scroller.pack(fill="both", expand=True)
        parent = scroller.body
        self.label(parent, "采集方式", font=("Microsoft YaHei UI", 13, "bold")).pack(anchor="w", pady=(0, 8))
        self.label(parent, "默认读取游戏窗口。窗口在前台时会显示鼠标穿透提示。",
                   style="Sub.TLabel").pack(anchor="w")
        ttk.Checkbutton(parent, text="开启游戏内置顶浮层", variable=self.show_overlay,
                        command=self.save).pack(anchor="w", pady=7)
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=(0, 10))
        self.label(row, textvariable=self.overlay_font_text, width=18).pack(side="left")
        slider = self.overlay_font_slider = ttk.Scale(row, from_=80, to=200,
                           value=self.overlay_scale.get() * 100, command=self.change_overlay_font)
        slider.pack(side="left", fill="x", expand=True, padx=8)
        slider.bind("<ButtonRelease-1>", lambda _: self.save())
        slider.bind("<KeyRelease>", lambda _: self.save())
        self.button(row, "恢复默认", self.reset_overlay_font).pack(side="left")
        ttk.Checkbutton(parent, text="通过 ADB 抓取模拟器画面", variable=self.use_adb,
                        command=self.invalidate).pack(anchor="w")
        for title, var in [("ADB 程序路径", self.adb), ("设备序列号", self.serial)]:
            row = ttk.Frame(parent)
            row.pack(fill="x", pady=4)
            self.label(row, title, width=15).pack(side="left")
            entry = ttk.Entry(row, textvariable=var)
            entry.pack(fill="x", expand=True)
            entry.bind("<Return>", lambda _: self.invalidate())
            entry.bind("<FocusOut>", lambda _: self.save())
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=7)
        self.label(row, "识别场景", width=15).pack(side="left")
        selector = ttk.Combobox(row, values=SCENES, textvariable=self.scene, state="readonly", width=20)
        selector.pack(side="left")
        selector.bind("<<ComboboxSelected>>", lambda _: self.invalidate())
        self.label(parent, "默认自动识别。特殊皮肤或布局下可手动指定场景，或在盟约页校正。",
                   style="Sub.TLabel").pack(anchor="w", pady=8)
        self.updater.settings(parent)

    def save(self):
        try:
            save_json(SETTINGS_DIR / "settings.json", {
                "guide": self.guide_id, "enabled": sorted(self.enabled), "muted": sorted(self.muted),
                "pool_capacity": self.capacities,
                "overlay": self.show_overlay.get(), "adb": self.adb.get(), "serial": self.serial.get(),
                "overlay_scale": self.overlay_scale.get(),
                "use_adb": self.use_adb.get(),
                "auto_update_check": self.updater.auto.get(),
            })
        except OSError as exc:
            self.status.set(f"无法保存设置 · {exc}")

    def change_overlay_font(self, value):
        self.overlay_scale.set(round(float(value)) / 100)
        self.overlay_font_text.set(f"浮层字号  {round(float(value))}%")

    def reset_overlay_font(self):
        self.overlay_font_slider.set(135)
        self.save()

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
        self.match = MatchState()
        self.update_views()

    def cycle_pact(self, _):
        selected = self.pact_tree.selection()
        if not selected:
            return
        name = selected[0]
        value = self.match.manual.get(name)
        if value is False:
            self.match.manual.pop(name, None)
        else:
            self.match.manual[name] = value is None
        self.update_views()

    def use_group(self, index):
        if not 0 <= index < len(self.match.groups):
            return
        self.match.choose(index)
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

    def guide_format(self):
        window = tk.Toplevel(self.root)
        window.title("攻略 JSON 格式 · 可直接复制并导入")
        window.geometry("820x620")
        sample = json.loads((Path(__file__).parent.parent / "data" / "guide.example.json").read_text(encoding="utf-8"))
        text = tk.Text(window, height=1, wrap="word", bg=PANEL, fg=FG, padx=14, pady=12, font=FONT)
        text.pack(fill="both", expand=True)
        text.insert("end", "UTF-8 JSON 对象，名称必须使用游戏简中全名。\n"
                    "必填：id（唯一）、name、targets（盟约→人数）、stages（至少一个阶段）。\n"
                    "阶段：name、timing（可选）、plan（可选）、core（必拿）、operators（可选干员）。\n"
                    "可选：plan（常驻思路）、stacking（叠层角色）、requirements（关键功能位候选）、strategies、equipment、sources。\n"
                    "stacking.role：core=核心叠层，available=可用叠层；note 写触发条件或站位。\n"
                    "requirements：name 为功能位，operators 为替代候选，minimum 为至少可用人数（默认1）；候选不代表等强。\n"
                    "策略、装备、干员、盟约均校验名称。下面是完整可导入模板：\n\n")
        text.insert("end", json.dumps(sample, ensure_ascii=False, indent=2))
        def export():
            path = filedialog.asksaveasfilename(defaultextension=".json", initialfile="guide.example.json",
                                              filetypes=[("攻略 JSON", "*.json")], parent=window)
            if path:
                save_json(Path(path), sample)
        self.button(window, "另存模板 JSON", export, True).pack(pady=8)

    def capture_roster(self):
        if self.frame is None or self.active_job is not None:
            self.stock_summary.configure(text="等待当前帧采集完成后再读取队友面板")
            return
        if self.reading.scene in {"调度中心", "自选编队", "盟约选择", "策略轮选"}:
            self.stock_summary.configure(text="当前是商店或战前界面。打开游戏内队友阵容面板后再读取。")
            return
        self.submit(RosterRequest(self.frame.copy(), self.stock_slot.get()))

    def clear_roster(self):
        self.match.stock.forget(self.stock_slot.get())
        self.update_stock()

    def choose_stock_operator(self, _=None):
        selected = self.stock_tree.selection()
        if not selected:
            return
        name = selected[0]
        self.stock_operator.set(name)
        snap = self.match.stock.players.get(self.stock_slot.get())
        item = next((item for item in snap.holdings if item.name == name), Holding(name)) if snap else Holding(name)
        for var, value in zip(self.stock_numbers, (item.normal, item.elite, item.uncertain)):
            var.set(str(value))

    def save_holding(self):
        try:
            values = [int(var.get()) for var in self.stock_numbers]
            if any(not 0 <= value <= 99 for value in values):
                raise ValueError
        except ValueError:
            self.stock_summary.configure(text="普通、精锐、待确认数量需要是 0–99 的整数")
            return
        name, slot = self.stock_operator.get(), self.stock_slot.get()
        self.match.stock.correct(slot, Holding(name, *values))
        self.update_stock()

    def pool_capacity(self):
        window = tk.Toplevel(self.root)
        window.title("自设每名干员总池量 · 未核实请留空")
        self.label(window, "当前赛季总池量尚无可靠依据，默认留空。填写后仅用于估算上界。", wraplength=460).pack(padx=15, pady=10)
        values = {}
        for tier in range(1, 7):
            row = ttk.Frame(window)
            row.pack(padx=15, pady=4)
            self.label(row, f"{tier} 阶每名干员份数", width=24).pack(side="left")
            values[tier] = tk.StringVar(value=str(self.capacities.get(tier, "")))
            ttk.Entry(row, textvariable=values[tier], width=8).pack(side="left")
        def apply():
            try:
                result = {tier: int(var.get()) for tier, var in values.items() if var.get().strip()}
                if any(not 1 <= value <= 999 for value in result.values()):
                    raise ValueError
            except ValueError:
                messagebox.showerror("总池量", "填写 1–999 的整数，或留空", parent=window)
                return
            self.capacities = result
            self.save()
            self.update_stock()
            window.destroy()
        self.button(window, "保存", apply, True).pack(pady=12)

    def update_stock(self):
        ledger = self.match.stock
        names = set(self.season.operators)
        names.update(item.name for snap in ledger.players.values() for item in snap.holdings)
        rows = []
        for name in sorted(names, key=lambda name: (-ledger.occupied(name), name)):
            tier = self.season.operators.get(name, {}).get("tier")
            used = ledger.occupied(name)
            rows.append((name, (name, tier or "自选", f"≥{used}", ledger.estimate(name, self.capacities.get(tier))),
                         "yes" if used else "maybe"))
        self.fill(self.stock_tree, rows)
        snapshots = " / ".join(f"{slot} {time.strftime('%H:%M:%S', time.localtime(snap.updated))} · {snap.source}"
                               for slot, snap in ledger.players.items())
        self.stock_summary.configure(text=snapshots or "尚未记录队友。展开队友总览会自动读取；单人详情可选面板编号后读取，也可手动校正。")

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
        if not self.preview:
            self.live_match = self.match
        self.preview = True
        self.reset_bans()
        self.invalidate()
        self.status.set("正在识别截图")
        self.submit(Path(path))

    def end_preview(self):
        if self.preview:
            self.preview = False
            self.match = self.live_match or MatchState()
            self.live_match = None
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

    def pc_shop(self, action):
        if self.updater.installing:
            self.pc_status.set("正在准备程序更新，请稍后再进行 PC 单步操作")
            return
        if self.pc_pending:
            return
        if not windows.is_admin():
            self.pc_status.set("请以管理员身份运行助手，再使用 PC 单步操作")
            return
        if self.preview or not self.window or self.window.process.casefold() != "arknights.exe":
            self.pc_status.set("请先绑定官方 PC 客户端并结束截图回放")
            return
        hwnd = self.window.hwnd
        if not windows.bounds(hwnd) or (windows.foreground() != hwnd and not windows.activate(hwnd)):
            self.pc_status.set("无法激活游戏窗口")
            return
        self.pc_pending = True
        self.pc_status.set("正在检查游戏画面并执行单步操作")
        self.open_shop_button.state(["disabled"])
        self.close_shop_button.state(["disabled"])
        self.scanner.requests.put((self.generation, ShopRequest(hwnd, action), ""))

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
        if self.pc_pending:
            try:
                self.pc_status.set(self.scanner.shop_responses.get_nowait())
                self.pc_pending = False
                self.open_shop_button.state(["!disabled"])
                self.close_shop_button.state(["!disabled"])
            except Empty:
                pass

        if (not self.preview and self.running and not self.pc_pending
                and self.active_job is None and self.scanner.requests.empty()):
            if now - self.last_scan > .25:
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
        self.match.observe(reading, self.preview)
        source = "截图回放" if self.preview else self.window.title
        reuse = " · 关键区域复用" if reading.reused else ""
        self.status.set(f"{source}   /   {reading.scene or '等待卫戍协议界面'}   /   "
                        f"采集 {reading.capture_ms} ms · 识别 {reading.elapsed_ms} ms{reuse}")
        self.update_views()
        if reading.roster_slot and not reading.holdings:
            self.stock_summary.configure(text="此帧没有读到可靠干员姓名，原记录保留。头像阵容可先手动补录；未识别项不视为0。")

    def callouts(self):
        return alerts(self.reading, self.guide, self.enabled, self.muted,
                      self.states, self.season, self.match.excluded, self.strategy_advice)

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
        if callouts or self.banner:
            self.overlay.show(region, self.frame.size, callouts, self.banner, self.reading.scene,
                              self.overlay_scale.get())
        else:
            self.overlay.hide()

    def recommendation_banner(self, ranked):
        context = self.scene_recommendation(ranked)
        self.scene_hint = context
        if not self.guide:
            return context
        guide = self.guide
        lines = [f"当前攻略  {guide['name']}", "思路  " + guide.get("plan", "按阶段补齐核心，结合可用池选择替代。")]
        fit = self.fits[guide['id']]
        if fit.blocked_core or fit.missing_roles or fit.blocked_targets:
            lines.append("适配  " + fit.reason)
        for role, title in (("core", "核心叠层"), ("available", "可用叠层")):
            names = []
            for item in guide.get("stacking", []):
                if item["role"] != role:
                    continue
                state = self.season.status(item["operator"], self.states, self.match.excluded, self.match.seen)
                if state is not False:
                    names.append(item["operator"] + ("?" if state is None else ""))
            if names:
                lines.append(title + "  " + "、".join(names[:6]) + ("…" if len(names) > 6 else ""))
        if context:
            lines.append(context)
        return "\n".join(lines)

    def scene_recommendation(self, ranked):
        if self.reading.scene == "盟约选择":
            if self.match.groups:
                choices = []
                for i, group in enumerate(self.match.groups):
                    other = self.match.groups[1-i]
                    states = self.states | dict.fromkeys(other, False) | dict.fromkeys(group, True)
                    group_ranked, group_fits = self.season.evaluate(states, self.match.excluded, seen=self.match.seen)
                    ranked_guide = group_ranked[0]
                    fit = group_fits[ranked_guide['id']]
                    choices.append(f"{i+1}组 {ranked_guide['name']} · {fit.label}")
                return "  /  ".join(choices)
            if self.states and ranked:
                fit = self.fits[ranked[0]['id']]
                return f"阵容建议  {ranked[0]['name']} · {fit.label}\n{fit.reason}"
        if self.reading.scene == "策略轮选" and self.strategy_advice:
            picks = self.strategy_advice["strategies"]
            if picks:
                visible = {hit.name for hit in self.reading.hits if hit.kind == "策略"}
                current = [name for name in picks if name in visible]
                caption = "当前可见" if current else "攻略优先"
                return f"{self.strategy_advice['name']}  ·  {caption}  " + "  →  ".join(current or picks)
        return ""

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
        visible = [hit.name for hit in self.reading.hits
                   if hit.kind == "干员" and self.reading.scene in {"调度中心", "自选编队"}]
        ranked, self.fits = self.season.evaluate(self.states, self.match.excluded, visible, self.match.seen)
        self.strategy_advice = self.guide
        if not self.strategy_advice and self.reading.scene == "策略轮选":
            self.strategy_advice = self.season.strategy_guide(
                ranked, self.states, self.reading.hits, self.match.excluded, self.match.seen, self.fits)
        self.banner = self.recommendation_banner(ranked)
        self.guide_text.set('本局追踪  /  ' + ('截图回放' if self.preview else '实时识别'))
        self.scene_text.configure(text=f"{self.reading.scene or '等待场景'}  ·  {len(self.reading.hits)} 条识别结果")
        self.raw_text.configure(text="OCR  /  " + " · ".join(self.reading.text[:24]) if self.reading.text else "")
        notices = dict(self.callouts())
        rows = [(str(i), (hit.kind, hit.name, notices.get(hit, "")),
                 "core" if notices.get(hit,'').startswith('核心') else "yes" if hit in notices else "")
                for i, hit in enumerate(self.reading.hits)]
        self.fill(self.monitor_tree, rows)
        self.update_monitor(ranked, notices)
        self.update_pool()
        self.update_bans()
        self.update_stock()
        self.update_guides(ranked)
        self.update_equipment()

    def update_monitor(self, ranked, notices):
        connected = bool(self.window)
        mode = '截图回放' if self.preview else '识别已暂停' if not self.running else '客户端已接入' if connected else '等待客户端'
        self.terminal_header.set_status(mode,self.preview or (connected and self.running))
        stage = self.reading.scene or '等待画面'
        self.metrics[0].set(stage if len(stage)<=6 else '等待确认','截图回放' if self.preview else '持续跟踪当前画面')
        banned = self.season.banned(self.states,self.match.excluded,self.match.seen)
        self.metrics[1].set(len(banned) if self.states or self.match.excluded else '—','已确认 + 盟约推算')
        self.metrics[2].set(len(notices),'核心 / 可用 / 装备')
        self.metrics[3].set(self.reading.elapsed_ms if self.frame else '—','ms · 区域复用' if self.reading.reused else 'ms · 当前画面')
        self.end_preview_button.state(['!disabled'] if self.preview else ['disabled'])
        self.context_text.configure(text=self.scene_hint)
        if self.reading.hits:
            self.monitor_empty.place_forget()
        else:
            self.monitor_empty.place(relx=.5,rely=.52,anchor='center')
        advice = self.guide or self.strategy_advice or (ranked[0] if self.states and ranked else None)
        if not advice:
            self.role_names = {}
            self.plan_name.configure(text='等待本局信息')
            self.advice_text.configure(text='进入卫戍协议的「确认本局信息」，读取 BAN 后，为你推荐当前可用的阵容。')
            self.core_text.configure(text='核心叠层  /  金色标记')
            self.optional_text.configure(text='可用叠层  /  青绿标记')
            self.fit_text.configure(text='也可从「阵容攻略」手动选定思路，提示会常驻在游戏浮层。')
            return
        fit = self.fits[advice['id']]
        self.plan_name.configure(text=('' if self.guide else '建议 · ')+advice['name'])
        self.advice_text.configure(text=advice.get('plan','按当前可用卡补齐核心，关注缺失的功能位。'))
        for role, widget, title in [('core',self.core_text,'核心叠层'),('available',self.optional_text,'可用叠层')]:
            names=[]
            for item in advice.get('stacking',[]):
                state=self.season.status(item['operator'],self.states,self.match.excluded,self.match.seen)
                if item['role']==role and state is not False:
                    names.append(item['operator']+('?' if state is None else ''))
            self.role_names[role]=names
        self.format_role_labels()
        self.fit_text.configure(text=fit.label+'\n'+fit.reason,foreground=GOLD if fit.blocked_core or not fit.viable else SECONDARY)

    def update_bans(self):
        banned = self.season.banned(self.states, self.match.excluded, self.match.seen)
        unknown = sum(self.season.status(name, self.states, self.match.excluded, self.match.seen) is None
                      for name in self.season.operators)
        direct = sum(reason == "名单识别" for reason in banned.values())
        summary = f"本局禁用 {len(banned)} 名（名单识别 {direct} / 盟约推算 {len(banned)-direct}）· 可用性待确认 {unknown} 名"
        self.ban_summary.configure(text=summary)
        names = "、".join(sorted(banned)[:6])
        self.ban_brief.configure(text=f"BAN {len(banned)}  /  {names}"
                                 + ("…" if len(banned) > 6 else "")
                                 if banned else "BAN  /  等待开局盟约结果，未确认项不会标成禁用")
        self.fill(self.ban_tree, [(name, (name, banned[name], " · ".join(
            self.season.operators.get(name, {}).get("pacts", []))), "no") for name in sorted(banned)])

    def update_pool(self):
        labels = {True: ("可用", "yes"), False: ("禁用", "no"), None: ("未确认", "maybe")}
        rows = []
        for name, pact in self.season.pacts.items():
            status, tag = labels[self.states.get(name)]
            if status == "未确认" and name in self.match.incomplete:
                status = "阵容不完整"
            if name in self.match.manual:
                status += " · 手动"
            rows.append((name, (name, ("核心" if pact["core"] else "附加") + " / " + status), tag))
        self.fill(self.pact_tree, rows)
        if not self.pact_tree.selection() and rows:
            self.pact_tree.selection_set(rows[0][0])
        group_buttons = tuple((i, "第 " + str(i+1) + " 组" + (" ✓" if i == self.match.selected else ""))
                              for i in range(len(self.match.groups)))
        if group_buttons != getattr(self, "shown_group_buttons", ()):
            self.shown_group_buttons = group_buttons
            for widget in self.group_buttons.winfo_children():
                widget.destroy()
            for i, name in group_buttons:
                self.button(self.group_buttons, name, lambda i=i: self.use_group(i), i == self.match.selected).pack(
                    side="left", padx=(0, 6))
        group_text = "  /  ".join(f"{i+1}组 {'、'.join(sorted(group))}" for i, group in enumerate(self.match.groups))
        counts = (f"已确认 {len(self.states)} 项盟约 · 本局商店已见 {len(self.match.seen)} 名 · "
                  f"读到禁用干员 {len(self.match.excluded - self.match.seen)} 名")
        self.pool_summary.configure(text="\n".join(filter(None, (group_text, counts))))
        self.update_pool_operators()

    def update_pool_operators(self):
        if not self.pact_tree.selection():
            return
        name = self.pact_tree.selection()[0]
        members = self.season.grouped(self.states, self.match.excluded, self.match.seen)[name]
        labels = {True: ("可用", "yes"), None: ("待确认", "maybe")}
        rows = []
        for operator in sorted(members, key=lambda name: (self.season.operators[name]["tier"], name)):
            available = self.season.status(operator, self.states, self.match.excluded, self.match.seen)
            if self.confirmed_only.get() and available is not True:
                continue
            status, tag = labels[available]
            if operator in self.match.seen:
                status = "本局已见"
            data = self.season.operators[operator]
            rows.append((operator, (data["tier"], operator, status, " · ".join(data["pacts"])), tag))
        self.fill(self.operator_tree, rows)

    def update_guides(self, ranked):
        rows = []
        for guide in ranked:
            fit = self.fits[guide['id']]
            tag = "no" if not fit.viable else "maybe" if fit.blocked_core or fit.unknown_core or fit.pending_roles else "yes"
            selected = "✓  " if guide["id"] == self.guide_id else ""
            rows.append((guide["id"], (selected + guide["name"], fit.label, fit.reason, " → ".join(guide["strategies"])), tag))
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
        fit = self.fits[guide['id']]
        lines.append("整套适配  " + fit.label + "；" + fit.reason)
        lines.append("分数是当前 BAN 与可用池的适配分，不是胜率；? 为待确认，功能位候选不代表等强替换。")
        for role in guide.get("requirements", []):
            candidates = [name for name in role['operators'] if self.season.status(
                name, self.states, self.match.excluded, self.match.seen) is not False]
            lines.append(f"关键位 {role['name']}（至少{role.get('minimum', 1)}名）：{'、'.join(candidates) or '已全部禁用'}")
        if guide.get("plan"):
            lines.append("常驻思路  " + guide["plan"])
        for item in guide.get("stacking", []):
            state = self.season.status(item["operator"], self.states, self.match.excluded, self.match.seen)
            label = "核心叠层" if item["role"] == "core" else "可用叠层"
            suffix = "【本局禁用】" if state is False else "【可用性待确认】" if state is None else ""
            lines.append(f"{label}  {item['operator']}{suffix}  {item.get('note', '')}")
        if guide["strategies"]:
            lines.append("策略顺位  " + " → ".join(guide["strategies"]))
        for stage in guide["stages"]:
            heading = "  ".join(filter(None, [stage["name"], str(stage.get("timing", ""))]))
            viable = lambda name: self.season.status(
                name, self.states, self.match.excluded, self.match.seen) is not False
            core = [name for name in stage.get("core", []) if viable(name)]
            other = [name for name in stage.get("operators", []) if name not in core and viable(name)]
            lines.append(f"{heading}  核心 {'、'.join(core) or '—'}")
            if stage.get("plan"):
                lines.append("      " + stage["plan"])
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
        if self.updater.installing:
            self.status.set("更新准备中，完成后会自动重启")
            return
        if self.pc_pending:
            self.pc_status.set("等待本次单步操作结束")
            return
        self.save()
        self.root.destroy()


def run(update_health=None, update_result=None):
    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=SETTINGS_DIR / "assistant.log", level=logging.INFO,
                        encoding="utf-8", format="%(asctime)s %(levelname)s %(message)s")
    windows.enable_dpi()
    root = tk.Tk()
    app = Dashboard(root)
    complete_startup(app, update_health, update_result)
    root.mainloop()
