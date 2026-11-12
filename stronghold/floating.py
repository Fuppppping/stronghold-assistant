"""Draggable companion UI sharing the dashboard's single capture and match state."""
import tkinter as tk
import time
from dataclasses import replace
from tkinter import ttk
from PIL import Image, ImageTk

from . import VERSION, windows
from .domain import DATA, key
from .floating_layout import Placement, HEADER, fit, follow, snap
from .ui import BG, PANEL, ALT, LINE, FG, SECONDARY, TEAL, GOLD, RED, ScrollColumn


class FloatingAssistant:
    def __init__(self, app, settings=None):
        self.app = app
        self.placement = Placement.load(settings)
        self.active = False
        self.drag = None
        self.portraits = {}
        self.previous_alerts = None
        self.scale = None
        self.pc_feedback = False
        self.display_areas = ()
        self.last_display_check = 0
        self.auto_compacted = False
        self.attachment = None
        self.last_render = None
        self.follow_game = tk.BooleanVar(master=app.root,value=self.placement.follow_game)
        self.auto_compact = tk.BooleanVar(master=app.root,value=self.placement.auto_compact)
        self.snap_edges = tk.BooleanVar(master=app.root,value=self.placement.snap_edges)
        self.header = tk.Toplevel(app.root, bg=BG)
        self.body = tk.Toplevel(app.root, bg=BG)
        self.header.title('卫戍助手 · 可拖动悬浮窗')
        self.body.title('卫戍助手 · 悬浮内容')
        for window in (self.header, self.body):
            window.withdraw()
            window.overrideredirect(True)
            window.attributes('-topmost', True)
            window.protocol('WM_DELETE_WINDOW', self.restore)
        self.title = tk.Frame(self.header, bg=BG, highlightthickness=1, highlightbackground=LINE)
        self.title.pack(fill='both', expand=True)
        grip = tk.Canvas(self.title, bg=BG, width=20, height=28, bd=0, highlightthickness=0, cursor='fleur')
        grip.pack(side='left', padx=(7,3))
        for x in (6,11):
            for y in (8,13,18):
                grip.create_oval(x,y,x+2,y+2,fill=SECONDARY,outline='')
        self.heading = tk.Label(self.title,text='卫戍助手',bg=BG,fg=FG,font=('Microsoft YaHei UI',-15,'bold'),cursor='fleur')
        self.heading.pack(side='left')
        self.live_dot = tk.Label(self.title,text='●',bg=BG,fg=TEAL,font=('Microsoft YaHei UI',-11))
        self.live_dot.pack(side='left',padx=7)
        for widget in (self.title,grip,self.heading,self.live_dot):
            widget.bind('<ButtonPress-1>',self.begin_drag)
            widget.bind('<B1-Motion>',self.move_drag)
            widget.bind('<ButtonRelease-1>',self.end_drag)
        self.main_button = self.title_button('主窗',self.restore)
        self.lock_button = self.title_button('穿透',self.toggle_lock)
        self.collapse_button = self.title_button('收起',self.toggle_collapse)
        self.surface = tk.Frame(self.body,bg=BG,highlightbackground=LINE,highlightthickness=1)
        self.surface.pack(fill='both',expand=True)
        self.footer = tk.Frame(self.surface,bg=BG)
        self.footer.pack(side='bottom',fill='x',padx=10,pady=(3,5))
        self.footnote = tk.Label(self.footer,bg=BG,fg=SECONDARY,font=('Microsoft YaHei UI',-10),anchor='w')
        self.footnote.pack(side='left',fill='x',expand=True)
        resize = tk.Canvas(self.footer,width=16,height=16,bg=BG,bd=0,highlightthickness=0,cursor='size_nw_se')
        resize.pack(side='right')
        for i in (4,8,12):
            resize.create_line(i,15,15,i,fill=SECONDARY)
        resize.bind('<ButtonPress-1>',self.begin_resize)
        resize.bind('<B1-Motion>',self.move_resize)
        resize.bind('<ButtonRelease-1>',self.end_drag)
        self.tabs = ttk.Notebook(self.surface,style='Float.TNotebook')
        self.tabs.pack(fill='both',expand=True,padx=7,pady=(6,0))
        self.pages = []
        for title in ('监测','攻略','干员','BAN','装备','设置'):
            page = tk.Frame(self.tabs,bg=BG)
            self.tabs.add(page,text=title)
            self.pages.append(page)
        self.scrollers = {}
        self.labels = []
        self.build_monitor(self.scroll_page(0))
        self.build_guides(self.pages[1])
        self.build_pool(self.pages[2])
        self.build_bans(self.pages[3])
        self.build_gear(self.pages[4])
        self.build_settings(self.scroll_page(5))
        self.tabs.bind('<<NotebookTabChanged>>',lambda _:self.refresh())
        self.body.bind('<Configure>',self.wrap_labels,add='+')
        self.body.bind_all('<MouseWheel>',self.wheel,add='+')
        self.header.update_idletasks()
        self.header_hwnd = windows.floating_style(self.header)
        self.body_hwnd = windows.floating_style(self.body,self.placement.locked)

    def title_button(self,text,command):
        button = tk.Button(self.title,text=text,command=command,bg=BG,fg=SECONDARY,
                           activebackground=ALT,activeforeground=FG,relief='flat',bd=0,
                           font=('Microsoft YaHei UI',-11),padx=9,cursor='hand2')
        button.pack(side='right',fill='y')
        return button

    def scroll_page(self,index):
        scroller = ScrollColumn(self.pages[index])
        scroller.pack(fill='both',expand=True)
        scroller.configure(bg=BG)
        scroller.canvas.configure(bg=BG)
        scroller.body.configure(bg=BG)
        self.scrollers[index] = scroller
        return scroller.body

    def label(self,parent,text='',color=FG,bold=False,size=0):
        label = tk.Label(parent,text=text,bg=parent.cget('bg'),fg=color,anchor='w',justify='left',
                         font=('Microsoft YaHei UI',-(size or 14),'bold' if bold else 'normal'))
        self.labels.append((label,bold,size))
        return label

    def card(self,parent,title,color=TEAL):
        frame = tk.Frame(parent,bg=PANEL,highlightbackground=LINE,highlightthickness=1)
        frame.pack(fill='x',pady=(0,8),padx=2)
        accent = tk.Frame(frame,bg=color,height=2)
        accent.pack(fill='x')
        if title:
            self.label(frame,title,color=SECONDARY,size=11).pack(anchor='w',padx=10,pady=(8,3))
        return frame

    def button(self,parent,text,command,primary=False):
        return ttk.Button(parent,text=text,command=command,width=0,
                          style='Float.Primary.TButton' if primary else 'Float.TButton')

    def tree(self,parent,columns,widths):
        frame = tk.Frame(parent,bg=BG)
        frame.pack(fill='both',expand=True,pady=(5,0))
        tree = ttk.Treeview(frame,columns=tuple(c[0] for c in columns),show='headings',style='Float.Treeview',selectmode='browse')
        for (name,title),width in zip(columns,widths):
            tree.heading(name,text=title)
            tree.column(name,width=width,minwidth=40,stretch=True)
        vertical = ttk.Scrollbar(frame,orient='vertical',command=tree.yview)
        horizontal = ttk.Scrollbar(frame,orient='horizontal',command=tree.xview)
        tree.configure(yscrollcommand=vertical.set,xscrollcommand=horizontal.set)
        frame.rowconfigure(0,weight=1)
        frame.columnconfigure(0,weight=1)
        tree.grid(row=0,column=0,sticky='nsew')
        vertical.grid(row=0,column=1,sticky='ns')
        horizontal.grid(row=1,column=0,sticky='ew')
        for tag,color in (('core',GOLD),('yes',TEAL),('no',RED),('maybe',SECONDARY)):
            tree.tag_configure(tag,foreground=color)
        return tree

    def build_monitor(self,parent):
        row = tk.Frame(parent,bg=BG)
        row.pack(fill='x',pady=(3,8))
        self.stage = self.label(row,color=TEAL,bold=True)
        self.stage.pack(side='left')
        self.ban_count = self.label(row,color=RED,size=11)
        self.ban_count.pack(side='right')
        self.capture_notice = self.label(parent,color=RED,size=11)
        card = self.card(parent,'当前攻略 / 打法思路')
        self.plan_card = card
        self.guide_name = self.label(card,bold=True)
        self.guide_name.pack(fill='x',padx=10,pady=(0,3))
        self.phase_row = tk.Frame(card,bg=PANEL)
        self.phase_row.pack(fill='x',padx=10,pady=(0,4))
        self.phase_selector = ttk.Combobox(self.phase_row,textvariable=self.app.phase_choice,width=8,state='readonly',style='Stage.Float.TCombobox')
        self.phase_selector.pack(side='left')
        self.phase_selector.bind('<<ComboboxSelected>>',self.app.change_phase)
        self.phase_info = self.label(self.phase_row,color=TEAL,size=11)
        self.phase_info.pack(side='left',fill='x',expand=True,padx=(7,0))
        self.plan = self.label(card)
        self.plan.pack(fill='x',padx=10,pady=(0,5))
        self.fit_note = self.label(card,color=SECONDARY,size=11)
        self.fit_note.pack(fill='x',padx=10,pady=(0,5))
        card = self.card(parent,'',GOLD)
        self.stacking_card = card
        self.core = self.label(card,color=GOLD)
        self.core.pack(fill='x',padx=10,pady=(8,5))
        self.available = self.label(card,color=TEAL)
        self.available.pack(fill='x',padx=10,pady=(0,10))
        card = self.card(parent,'当前来牌 / 关键装备',TEAL)
        card.pack_configure(before=self.stacking_card)
        self.alert_empty = self.label(card,'等待商店、装备或策略画面',SECONDARY)
        self.alert_empty.pack(fill='x',padx=10,pady=(0,10))
        self.alert_rows = []
        for _ in range(6):
            frame = tk.Frame(card,bg=PANEL)
            icon = tk.Label(frame,bg=PANEL,width=30,height=30)
            icon.pack(side='left',padx=(0,7))
            content = tk.Frame(frame,bg=PANEL)
            content.pack(side='left',fill='x',expand=True)
            name = self.label(content,bold=True)
            name.pack(fill='x')
            note = self.label(content,color=SECONDARY,size=11)
            note.pack(fill='x')
            self.alert_rows.append((frame,icon,name,note))
        row = self.action_bar = tk.Frame(self.pages[0],bg=BG)
        row.pack(side='bottom',fill='x',padx=8,pady=(1,8),before=self.scrollers[0])
        self.pause = self.button(row,'暂停',self.app.toggle)
        self.action_buttons = [self.pause,self.button(row,'选阵容',lambda:self.tabs.select(1),True),
                               self.button(row,'展开商店',lambda:self.shop('open')),
                               self.button(row,'收起',lambda:self.shop('close'))]
        self.action_columns = None
        self.pc_note = self.label(self.pages[0],color=SECONDARY,size=11)

    def build_guides(self,parent):
        bar = tk.Frame(parent,bg=BG)
        bar.pack(fill='x',pady=6)
        self.button(bar,'选定阵容',self.choose_guide,True).pack(side='left')
        self.button(bar,'看详情',self.guide_details).pack(side='left',padx=5)
        self.button(bar,'导入 JSON',lambda:self.full_action(3,self.app.import_guide)).pack(side='left')
        self.guide_tree = self.tree(parent,(('name','阵容'),('fit','当前适配')),(210,110))
        self.guide_tree.bind('<Double-1>',lambda _:self.choose_guide())
        self.label(parent,'分数看当前 BAN 适配，不是胜率。',SECONDARY,size=11).pack(fill='x',pady=5)

    def build_pool(self,parent):
        self.pact = tk.StringVar(value='全部')
        selector = ttk.Combobox(parent,textvariable=self.pact,values=['全部',*self.app.season.pacts],
                                state='readonly',style='Float.TCombobox')
        selector.pack(fill='x',pady=7)
        selector.bind('<<ComboboxSelected>>',lambda _:self.refresh())
        self.pool_tree = self.tree(parent,(('name','干员'),('status','可用性'),('pacts','盟约')),(95,85,180))
        self.button(parent,'校正盟约 / 选择开局组',lambda:self.full_action(1)).pack(anchor='w',pady=6)

    def build_bans(self,parent):
        self.ban_mode = tk.StringVar(value='禁用名单')
        selector = ttk.Combobox(parent,textvariable=self.ban_mode,values=('禁用名单','共享卡池'),
                                state='readonly',style='Float.TCombobox')
        selector.pack(fill='x',pady=(7,0))
        selector.bind('<<ComboboxSelected>>',lambda _:self.refresh())
        self.ban_summary = self.label(parent,color=SECONDARY,size=11)
        self.ban_summary.pack(fill='x',pady=7)
        self.ban_tree = self.tree(parent,(('name','禁用干员'),('reason','判断依据'),('note','所属盟约')),(100,100,150))
        row = tk.Frame(parent,bg=BG)
        row.pack(fill='x',pady=6)
        self.button(row,'手动校正 / 总池量',lambda:self.full_action(2)).pack(side='left')
        self.button(row,'重置本局',self.app.reset_bans).pack(side='right')

    def build_gear(self,parent):
        self.gear_search = tk.StringVar()
        search = ttk.Entry(parent,textvariable=self.gear_search,style='Float.TEntry')
        search.pack(fill='x',pady=7)
        self.gear_search.trace_add('write',lambda *_:self.refresh())
        self.gear_tree = self.tree(parent,(('name','装备'),('mode','提醒状态')),(210,100))
        row = tk.Frame(parent,bg=BG)
        row.pack(fill='x',pady=6)
        for text,mode in (('勾选提醒','enabled'),('屏蔽','muted'),('跟随攻略','auto')):
            self.button(row,text,lambda mode=mode:self.change_gear(mode)).pack(side='left',padx=(0,5))

    def build_settings(self,parent):
        card = self.card(parent,'悬浮窗')
        self.label(card,'拖动顶栏移动，右下角拖动缩放。\n穿透只锁内容区，顶栏始终能点。',SECONDARY,size=12).pack(fill='x',padx=10,pady=(0,8))
        self.button(card,'恢复默认位置与尺寸',self.reset_position).pack(anchor='w',padx=10,pady=(0,10))
        for text,var in (('跟随游戏窗口',self.follow_game),('切出游戏时收起内容',self.auto_compact),
                         ('拖动后贴边吸附',self.snap_edges)):
            ttk.Checkbutton(parent,text=text,variable=var,command=self.change_behavior).pack(anchor='w',pady=3)
        self.alpha = tk.DoubleVar(value=self.placement.opacity*100)
        self.label(card,'面板不透明度',size=12).pack(anchor='w',padx=10)
        slider = ttk.Scale(card,from_=55,to=100,variable=self.alpha,command=self.set_alpha)
        slider.pack(fill='x',padx=10,pady=(3,10))
        slider.bind('<ButtonRelease-1>',lambda _:self.app.save())
        slider.bind('<KeyRelease>',lambda _:self.app.save())
        self.label(card,'提示与面板字号',size=12).pack(anchor='w',padx=10)
        self.font_slider = ttk.Scale(card,from_=80,to=200,value=self.app.overlay_scale.get()*100,
                                     command=self.set_font)
        self.font_slider.pack(fill='x',padx=10,pady=(3,6))
        self.font_slider.bind('<ButtonRelease-1>',lambda _:self.app.save())
        self.font_slider.bind('<KeyRelease>',lambda _:self.app.save())
        self.font_caption = self.label(card,color=TEAL,size=11)
        self.font_caption.pack(fill='x',padx=10,pady=(0,8))
        ttk.Checkbutton(parent,text='保留卡片位置提示',variable=self.app.show_overlay,command=self.app.save).pack(anchor='w',pady=4)
        ttk.Checkbutton(parent,text='后台/静止画面降低采样',variable=self.app.energy_saving,command=self.app.save).pack(anchor='w',pady=4)
        self.button(parent,'识别、窗口和 ADB 设置',lambda:self.full_action(5)).pack(fill='x',pady=6)
        self.button(parent,'检查 / 管理程序更新',lambda:self.full_action(5,self.app.updater.check)).pack(fill='x',pady=6)
        self.label(parent,f'v{VERSION} · 本地识别',SECONDARY,size=11).pack(anchor='w',pady=7)
        self.button(parent,'退出助手',self.app.close).pack(fill='x',pady=(0,12))

    def show(self):
        self.active = True
        self.last_render = None
        self.attachment = None
        self.auto_compacted = False
        self.apply_geometry()
        self.refresh()

    def hide(self):
        self.active = False
        self.auto_compacted = False
        self.header.withdraw()
        self.body.withdraw()

    def restore(self):
        self.app.leave_floating()

    def full_action(self,index,command=None):
        self.restore()
        self.app.navigate(index)
        if command:
            self.app.root.after_idle(command)

    def apply_geometry(self):
        self.display_areas = tuple(windows.work_areas())
        self.last_display_check = time.monotonic()
        self.placement = fit(self.placement,self.display_areas)
        p = self.placement
        self.header.geometry(f'{p.width}x{HEADER}')
        self.body.geometry(f'{p.width}x{p.height}')
        for window in (self.header,self.body):
            window.attributes('-alpha',p.opacity)
        self.collapse_button.configure(text='展开' if p.collapsed or self.auto_compacted else '收起')
        self.heading.configure(text='卫戍助手 · 后台' if self.auto_compacted else '卫戍助手')
        self.lock_button.configure(text='解锁' if p.locked else '穿透',fg=GOLD if p.locked else SECONDARY)
        self.header.configure(bg=GOLD if p.locked else BG)
        if self.active:
            if self.header.state() == 'withdrawn':
                self.header.deiconify()
            if p.collapsed or self.auto_compacted:
                if self.body.state() != 'withdrawn':
                    self.body.withdraw()
            elif self.body.state() == 'withdrawn':
                self.body.deiconify()
        self.header.update_idletasks()
        windows.floating_style(self.header)
        windows.floating_style(self.body,p.locked)
        windows.place_floating(self.header_hwnd,p.x,p.y,p.width,HEADER)
        windows.place_floating(self.body_hwnd,p.x,p.y+HEADER,p.width,p.height)

    def begin_drag(self,event):
        self.attachment = None
        self.drag = ('move',event.x_root,event.y_root,self.placement.x,self.placement.y)

    def begin_resize(self,event):
        self.attachment = None
        self.drag = ('resize',event.x_root,event.y_root,self.placement.width,self.placement.height)

    def move_drag(self,event):
        if self.drag and self.drag[0] == 'move':
            _,x,y,left,top = self.drag
            self.placement.x,self.placement.y = left+event.x_root-x,top+event.y_root-y
            self.apply_geometry()

    def move_resize(self,event):
        if self.drag and self.drag[0] == 'resize':
            _,x,y,width,height = self.drag
            self.placement.width,self.placement.height = width+event.x_root-x,height+event.y_root-y
            self.apply_geometry()

    def end_drag(self,_=None):
        if self.drag:
            if self.drag[0] == 'move' and self.placement.snap_edges:
                bounds = windows.bounds(self.app.window.hwnd) if self.app.window and not self.app.preview else None
                if not bounds and self.display_areas:
                    bounds = min(self.display_areas,key=lambda r:abs(r[0]-self.placement.x)+abs(r[1]-self.placement.y))
                if bounds:
                    self.placement = snap(self.placement,bounds)
                    self.apply_geometry()
            self.drag = None
            self.attachment = None
            self.app.save()

    def toggle_lock(self):
        self.placement.locked = not self.placement.locked
        if self.placement.locked:
            self.header.focus_set()
        self.apply_geometry()
        self.app.save()

    def toggle_collapse(self):
        self.placement.collapsed = False if self.auto_compacted else not self.placement.collapsed
        self.auto_compacted = False
        self.attachment = None
        self.apply_geometry()
        self.refresh()
        self.app.save()

    def reset_position(self):
        self.placement = Placement()
        self.attachment = None
        self.auto_compacted = False
        self.follow_game.set(self.placement.follow_game)
        self.auto_compact.set(self.placement.auto_compact)
        self.snap_edges.set(self.placement.snap_edges)
        self.apply_geometry()
        self.alpha.set(95)
        self.app.save()

    def change_behavior(self):
        self.placement.follow_game = self.follow_game.get()
        self.placement.auto_compact = self.auto_compact.get()
        self.placement.snap_edges = self.snap_edges.get()
        self.attachment = None
        self.track_client()
        self.app.save()

    def track_client(self):
        app = self.app
        target = app.window
        attached = bool(target and windows.is_window(target.hwnd)) and not app.preview
        bounds = windows.bounds(target.hwnd) if attached else None
        if not attached:
            self.attachment = None
        if bounds and self.placement.follow_game and not self.drag:
            if not self.attachment or self.attachment[0] != target.hwnd:
                self.attachment = (target.hwnd,bounds,replace(self.placement))
            else:
                _,previous,placement = self.attachment
                desired = fit(follow(placement,previous,bounds),self.display_areas)
                if (desired.x,desired.y) != (self.placement.x,self.placement.y):
                    self.placement = replace(self.placement,x=desired.x,y=desired.y)
                    self.apply_geometry()
        foreground = windows.foreground()
        compact = bool(attached and self.placement.auto_compact and not windows.owned_window(foreground)
                       and (foreground != target.hwnd or bounds is None))
        if compact != self.auto_compacted:
            self.auto_compacted = compact
            self.apply_geometry()

    def set_alpha(self,value):
        self.placement.opacity = max(.55,min(1,float(value)/100))
        for window in (self.header,self.body):
            window.attributes('-alpha',self.placement.opacity)

    def set_font(self,value):
        self.app.overlay_font_slider.set(float(value))
        self.refresh()

    def wrap_labels(self,_=None):
        for label,_,_ in self.labels:
            # Use the containing card, not the full window, for wrapped text.
            label.configure(wraplength=max(90,label.master.winfo_width()-24))
        self.phase_info.configure(wraplength=max(90,self.phase_row.winfo_width()-self.phase_selector.winfo_width()-10))
        self.layout_actions()

    def layout_actions(self):
        columns = 2 if self.placement.width < 380 or (self.scale or 15) >= 18 else 4
        if columns == self.action_columns:
            return
        self.action_columns = columns
        for i in range(4):
            self.action_bar.columnconfigure(i,weight=1 if i<columns else 0)
        for i,button in enumerate(self.action_buttons):
            button.grid_forget()
            button.grid(row=i//columns,column=i%columns,sticky='ew',padx=(0,4),pady=(0,4))

    def wheel(self,event):
        if event.widget.winfo_toplevel() != self.body:
            return
        index = self.tabs.index('current')
        scroll = self.scrollers.get(index)
        if scroll and event.widget != scroll.canvas:
            scroll.wheel(event)
            return 'break'

    def choose_guide(self):
        selection = self.guide_tree.selection()
        if selection:
            self.app.guide_tree.selection_set(selection[0])
            self.app.select_guide()
            self.tabs.select(0)

    def guide_details(self):
        selection = self.guide_tree.selection()
        if selection:
            self.app.guide_tree.selection_set(selection[0])
        self.full_action(3)
        if selection:
            self.app.guide_tree.selection_set(selection[0])
            self.app.guide_detail()

    def change_gear(self,mode):
        selection = self.gear_tree.selection()
        if selection:
            self.app.equipment_tree.selection_set(selection[0])
            self.app.equipment_action(mode)

    def shop(self,action):
        self.pc_feedback = True
        self.app.pc_shop(action)
        self.refresh()

    def portrait(self,name):
        if name not in self.portraits:
            head = self.app.season.operators.get(name,{}).get('head')
            path = DATA / 'head' / f'{head}.webp'
            if head and path.is_file():
                with Image.open(path) as image:
                    self.portraits[name] = ImageTk.PhotoImage(image.convert('RGB').resize((30,30)))
            else:
                self.portraits[name] = None
        return self.portraits[name]

    def refresh(self):
        if not self.active:
            return
        now = time.monotonic()
        if now - self.last_display_check >= 2:
            self.last_display_check = now
            if tuple(windows.work_areas()) != self.display_areas:
                self.apply_geometry()
                self.attachment = None
                self.app.save()
        self.track_client()
        app = self.app
        self.live_dot.configure(fg=RED if app.status.get().startswith('采集暂不可用') else
                                TEAL if app.running and (app.window or app.preview) else GOLD)
        if self.placement.collapsed or self.auto_compacted:
            self.last_render = None
            return
        page = self.tabs.index('current')
        stamp = (app.view_revision,page,app.overlay_scale.get(),app.running,app.preview,
                 self.placement.locked,self.pact.get(),self.gear_search.get(),self.ban_mode.get(),
                 app.status.get(),app.pc_status.get(),self.pc_feedback,
                 int(now) if page==3 and self.ban_mode.get()=='共享卡池' else None)
        if stamp == self.last_render:
            return
        self.last_render = stamp
        size = max(12,min(21,round(11*app.overlay_scale.get())))
        if size != self.scale:
            self.scale = size
            style = ttk.Style()
            style.configure('Stage.Float.TCombobox',padding=(3,2))
            self.phase_selector.configure(font=('Microsoft YaHei UI',-size))
            for name in ('Float.TButton','Float.Primary.TButton','Float.TCombobox','Float.TEntry'):
                style.configure(name,font=('Microsoft YaHei UI',-size),padding=(7,6))
            style.configure('Float.Primary.TButton',background=TEAL,foreground=BG)
            style.configure('Float.TNotebook',background=BG,borderwidth=0)
            style.configure('Float.TNotebook.Tab',font=('Microsoft YaHei UI',-12),padding=(8,9),
                            background=BG,foreground=SECONDARY,borderwidth=0)
            style.layout('Float.TNotebook.Tab',[('Notebook.padding',{'sticky':'nswe','children':[
                ('Notebook.label',{'sticky':'nswe'})]})])
            style.map('Float.TNotebook.Tab',background=[('selected',ALT)],foreground=[('selected',TEAL)])
            style.configure('Float.Treeview',font=('Microsoft YaHei UI',-size),rowheight=max(28,size+13))
            style.configure('Float.Treeview.Heading',font=('Microsoft YaHei UI',-12))
            for label,bold,fixed in self.labels:
                label.configure(font=('Microsoft YaHei UI',-(fixed or size),'bold' if bold else 'normal'))
            self.wrap_labels()
        self.stage.configure(text='回放 · '+(app.reading.scene or '等待画面') if app.preview else
                             '已暂停' if not app.running else app.reading.scene or ('等待画面' if app.window else '等待客户端'))
        status = app.status.get()
        if status.startswith(('采集暂不可用','请在采集设置','等待客户端')) and not app.preview:
            self.capture_notice.configure(text=status)
            self.capture_notice.pack(fill='x',padx=3,pady=(0,8),before=self.plan_card)
        else:
            self.capture_notice.pack_forget()
        banned = app.season.banned(app.states,app.match.excluded,app.match.seen)
        self.ban_count.configure(text=f'BAN {len(banned)}' if app.states or app.match.excluded else 'BAN 待确认')
        advice = app.guide or app.strategy_advice
        self.guide_name.configure(text=advice['name'] if advice else '先选一套想玩的阵容')
        self.plan.configure(text=app.plan_text(advice) if advice else '开局读出盟约后，在「攻略」页按本局卡池选阵容。')
        self.phase_info.configure(text=app.phase_caption.get())
        fit_info = app.fits.get(advice['id']) if advice else None
        self.fit_note.configure(text=(fit_info.label+' · '+fit_info.reason) if fit_info else '已选阵容会持续跟踪，重开后偏好保留。')
        for role,label,title in (('core',self.core,'核心'),('available',self.available,'可用')):
            names = []
            for item in advice.get('stacking',[]) if advice else []:
                if item['role'] == role:
                    available = app.season.status(item['operator'],app.states,app.match.excluded,app.match.seen)
                    if available is not False:
                        names.append(item['operator']+('?' if available is None else ''))
            limit = 4 if role == 'core' else 5
            label.configure(text=title+'  '+('、'.join(names[:limit]) if names else '—')
                            +(f'  +{len(names)-limit}' if len(names)>limit else ''))
        alerts = sorted(app.callouts(),key=lambda pair:(0 if '当前阶段优先' in pair[1] else
                        1 if pair[1].startswith('核心') else 2 if pair[0].kind=='装备' else 3))
        state = tuple((h.kind,h.name,note) for h,note in alerts[:6])
        if state != self.previous_alerts:
            self.previous_alerts = state
            if state:
                self.alert_empty.pack_forget()
            else:
                self.alert_empty.pack(fill='x',padx=10,pady=(0,10))
            for index,(frame,icon,name,note) in enumerate(self.alert_rows):
                if index < len(state):
                    kind,title,detail = state[index]
                    color = GOLD if detail.startswith('核心') or kind=='装备' else TEAL
                    picture = self.portrait(title)
                    icon.configure(image=picture or '',text='' if picture else '装' if kind=='装备' else '策',fg=color,
                                   font=('Microsoft YaHei UI',-14),width=30 if picture else 2,height=30 if picture else 1)
                    name.configure(text=title,fg=color)
                    note.configure(text=(detail.split(' · ')[0]+(' · 本阶段优先' if '当前阶段优先' in detail else ''))
                                   if kind=='干员' else detail)
                    frame.pack(fill='x',padx=10,pady=(0,6))
                else:
                    frame.pack_forget()
        self.pause.configure(text='暂停' if app.running else '继续')
        self.pc_feedback = self.pc_feedback or app.pc_pending
        self.pc_note.configure(text=app.pc_status.get() if self.pc_feedback else '')
        if self.pc_feedback:
            self.pc_note.pack(side='bottom',fill='x',padx=8,pady=(0,4),before=self.action_bar)
        else:
            self.pc_note.pack_forget()
        self.footnote.configure(text=('回放' if app.preview else '已暂停' if not app.running else '实时识别')
                                +f' · 采集 {app.reading.capture_ms} / 识别 {app.reading.elapsed_ms} ms'
                                +(' · 内容穿透中' if self.placement.locked else ''))
        self.font_caption.configure(text=app.overlay_font_text.get())
        self.font_slider.set(app.overlay_scale.get()*100) if abs(self.font_slider.get()-app.overlay_scale.get()*100)>.1 else None
        page = self.tabs.index('current')
        if page == 1:
            ranked = app.guide_tree.get_children()
            app.fill(self.guide_tree,[(identifier,(('✓ ' if identifier==app.guide_id else '')+app.season.lineups[identifier]['name'],
                                     app.fits[identifier].label),'no' if not app.fits[identifier].viable else 'yes') for identifier in ranked])
        elif page == 2:
            pact = self.pact.get()
            rows = []
            for name,operator in sorted(app.season.operators.items(),key=lambda pair:(pair[1]['tier'],pair[0])):
                if pact != '全部' and pact not in operator['pacts']:
                    continue
                status = app.season.status(name,app.states,app.match.excluded,app.match.seen)
                title,tag = {True:('可用','yes'),False:('禁用','no'),None:('待确认','maybe')}[status]
                rows.append((name,(name,title,' · '.join(operator['pacts'])),tag))
            app.fill(self.pool_tree,rows)
        elif page == 3:
            if self.ban_mode.get() == '共享卡池':
                self.ban_tree.heading('name',text='干员')
                self.ban_tree.heading('reason',text='已见占用')
                self.ban_tree.heading('note',text='剩余估算')
                names = [name for name in app.season.operators if app.match.stock.occupied(name)]
                self.ban_summary.configure(text=f'已记录 {len(app.match.stock.players)} 个面板 · 仅为可见占用下限')
                app.fill(self.ban_tree,[(name,(name,f'≥{app.match.stock.occupied(name)}',
                    app.match.stock.estimate(name,app.capacities.get(app.season.operators[name]['tier']))),'yes')
                    for name in sorted(names,key=lambda name:-app.match.stock.occupied(name))])
            else:
                self.ban_tree.heading('name',text='禁用干员')
                self.ban_tree.heading('reason',text='判断依据')
                self.ban_tree.heading('note',text='所属盟约')
                unknown = sum(app.season.status(name,app.states,app.match.excluded,app.match.seen) is None
                              for name in app.season.operators)
                self.ban_summary.configure(text=f'{len(banned)} 名禁用 · {unknown} 名待确认')
                app.fill(self.ban_tree,[(name,(name,reason,' · '.join(app.season.operators.get(name,{}).get('pacts',[]))),
                                        'no') for name,reason in sorted(banned.items())])
        elif page == 4:
            search = key(self.gear_search.get())
            gear = app.guide.get('equipment',{}) if app.guide else {}
            app.fill(self.gear_tree,[(name,(name,'已屏蔽' if name in app.muted else '手动提醒' if name in app.enabled
                                           else '攻略提醒' if name in gear else '跟随攻略'),
                                     'no' if name in app.muted else 'yes' if name in gear or name in app.enabled else '')
                                    for name in app.season.equipment if not search or search in key(name)])
