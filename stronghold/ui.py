"""Original vector UI components inspired by the Regulation terminal."""
import tkinter as tk
from tkinter import ttk

BG = '#0a100f'
PANEL = '#121c1a'
ALT = '#1c2b27'
LINE = '#294038'
FG = '#edf3ef'
SECONDARY = '#8ca69a'
TEAL = '#59f4c2'
GOLD = '#efba69'
RED = '#f38e7e'
FONT = ('Microsoft YaHei UI', 10)
MONO = 'Consolas'


class TerminalHeader(tk.Canvas):
    def __init__(self, parent):
        super().__init__(parent, height=94, bg=BG, highlightthickness=0, bd=0)
        self.mode = '等待接入'
        self.online = False
        self.bind('<Configure>', self.draw)

    def set_status(self, text, online=False):
        if (text, online) != (self.mode, self.online):
            self.mode, self.online = text, online
            self.draw()

    def draw(self, _=None):
        self.delete('all')
        width = self.winfo_width()
        for x in range(0, width, 26):
            self.create_line(x, 0, x, 84, fill='#11201a')
        for y in range(6, 84, 26):
            self.create_line(0, y, width, y, fill='#11201a')
        self.create_polygon(8,16,50,16,64,30,64,65,22,65,8,51, fill=TEAL, outline='')
        for y in (26, 37, 48):
            self.create_polygon(20,y,48,y,42,y+6,20,y+6, fill=BG, outline='')
        self.create_text(82, 9, text='STRONGHOLD PROTOCOL  /  REGULATION', anchor='nw',
                         fill=SECONDARY, font=(MONO, 9))
        title = self.create_text(80, 29, text='卫戍协议', anchor='nw', fill=FG,
                                 font=('Microsoft YaHei UI', 23, 'bold'))
        self.create_text(self.bbox(title)[2]+14, 46, text='助手', anchor='nw', fill=TEAL,
                         font=('Microsoft YaHei UI', 13, 'bold'))
        self.create_text(width-10, 13, text='规程 · 序列 Ⅰ', anchor='ne', fill=FG,
                         font=('Microsoft YaHei UI', 12, 'bold'))
        color = TEAL if self.online else SECONDARY
        self.create_oval(width-158, 53, width-150, 61, fill=color, outline='')
        self.create_text(width-139, 57, text=self.mode, anchor='w', fill=color,
                         font=('Microsoft YaHei UI', 9))
        self.create_line(0, 86, width, 86, fill=LINE)
        self.create_line(0, 86, 170, 86, fill=TEAL, width=2)
        self.create_polygon(width-92,83,width-84,83,width-80,87,width-88,87,fill=TEAL,outline='')


class NavItem(tk.Canvas):
    def __init__(self, parent, number, title, subtitle, command):
        super().__init__(parent, height=64, width=172, bg=BG, highlightthickness=0,
                         bd=0, cursor='hand2', takefocus=True)
        self.number, self.title, self.subtitle = number, title, subtitle
        self.command, self.selected, self.hover = command, False, False
        self.bind('<Configure>', self.draw)
        self.bind('<Button-1>', lambda _: self.command())
        self.bind('<Return>', lambda _: self.command())
        self.bind('<space>', lambda _: self.command())
        self.bind('<Enter>', lambda _: self.set_hover(True))
        self.bind('<Leave>', lambda _: self.set_hover(False))
        self.bind('<FocusIn>', lambda _: self.set_hover(True))
        self.bind('<FocusOut>', lambda _: self.set_hover(False))

    def set_hover(self, state):
        self.hover = state
        self.draw()

    def select(self, state):
        if self.selected != state:
            self.selected = state
            self.draw()

    def draw(self, _=None):
        self.delete('all')
        width = self.winfo_width()
        color = TEAL if self.selected else FG if self.hover else SECONDARY
        if self.selected or self.hover:
            self.create_polygon(0,2,width-10,2,width,12,width,61,0,61,
                                fill='#1b3027' if self.selected else PANEL, outline='')
        if self.selected:
            self.create_rectangle(0,2,3,61,fill=TEAL,outline='')
            self.create_polygon(width-12,27,width-7,31,width-12,35,fill=TEAL,outline='')
        self.create_text(14, 21, text=f'{self.number:02}', anchor='w', fill=color, font=(MONO,10))
        self.create_text(42, 18, text=self.title, anchor='nw', fill=color,
                         font=('Microsoft YaHei UI',10,'bold'))
        self.create_text(42, 43, text=self.subtitle, anchor='nw', fill=SECONDARY, font=(MONO,7))


class SectionPanel(tk.Frame):
    def __init__(self, parent, title, accent=TEAL):
        super().__init__(parent, bg=BG, bd=0, highlightthickness=0)
        self.title, self.accent = title, accent
        self.art = tk.Canvas(self, bg=BG, bd=0, highlightthickness=0)
        self.art.place(relwidth=1, relheight=1)
        self.body = tk.Frame(self, bg=PANEL, bd=0)
        self.body.pack(fill='both', expand=True, padx=14, pady=(42,14))
        self.art.bind('<Configure>', self.draw)

    def draw(self, _=None):
        self.art.delete('all')
        w, h = self.winfo_width()-1, self.winfo_height()-1
        self.art.create_polygon(0,0,w-12,0,w,12,w,h,12,h,0,h-12,
                                fill=PANEL, outline=LINE)
        self.art.create_rectangle(0,0,28,2,fill=self.accent,outline='')
        self.art.create_text(14,18,text=self.title,anchor='w',fill=FG,
                             font=('Microsoft YaHei UI',9,'bold'))
        self.art.create_line(14,34,w-14,34,fill=LINE)
        self.art.create_line(w-27,h-5,w-14,h-5,fill=self.accent)


class Metric(tk.Canvas):
    def __init__(self, parent, title, number, color=TEAL, text_value=False):
        super().__init__(parent, height=96, bg=BG, highlightthickness=0, bd=0)
        self.title, self.number, self.color = title, number, color
        self.value, self.note, self.text_value = '—', '等待画面', text_value
        self.bind('<Configure>', self.draw)

    def set(self, value, note):
        if (str(value), note) != (self.value, self.note):
            self.value, self.note = str(value), note
            self.draw()

    def draw(self, _=None):
        self.delete('all')
        w = self.winfo_width()-1
        self.create_polygon(0,0,w-10,0,w,10,w,94,0,94,fill=PANEL,outline=LINE)
        self.create_text(14,14,text=self.title,anchor='w',fill=SECONDARY,font=('Microsoft YaHei UI',9))
        self.create_text(w-12,14,text=self.number,anchor='e',fill=LINE,font=(MONO,9))
        font = ('Microsoft YaHei UI',14,'bold') if self.text_value else (MONO,26,'bold')
        self.create_text(13,46,text=self.value,anchor='w',fill=self.color,font=font)
        self.create_text(14,79,text=self.note,anchor='w',fill=SECONDARY,font=('Microsoft YaHei UI',8))
        self.create_line(w-43,89,w-13,89,fill=self.color,width=2)


class ScrollColumn(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent,bg=PANEL)
        self.canvas = tk.Canvas(self,bg=PANEL,highlightthickness=0,bd=0,height=1)
        scroll = ttk.Scrollbar(self,orient='vertical',command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right',fill='y')
        self.canvas.pack(side='left',fill='both',expand=True)
        self.body = tk.Frame(self.canvas,bg=PANEL)
        self.content = self.canvas.create_window(0,0,window=self.body,anchor='nw')
        self.canvas.bind('<Configure>',lambda e:self.canvas.itemconfigure(self.content,width=e.width))
        self.body.bind('<Configure>',lambda _:self.canvas.configure(scrollregion=self.canvas.bbox('all')))
        self.canvas.bind('<MouseWheel>',self.wheel)

    def wheel(self, event):
        self.canvas.yview_scroll(-int(event.delta/120),'units')
