"""Topmost, non-activating callouts over the attached window."""
import tkinter as tk

from . import windows
from .ui import TEAL, GOLD, PANEL

KEY_COLOR = "#010203"


class Overlay:
    def __init__(self, root):
        self.window = tk.Toplevel(root, bg=KEY_COLOR)
        self.window.withdraw()
        self.window.overrideredirect(True)
        self.window.attributes("-transparentcolor", KEY_COLOR)
        self.window.attributes("-topmost", True)
        self.canvas = tk.Canvas(self.window, bg=KEY_COLOR, bd=0, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.window.update_idletasks()
        self.hwnd = windows.overlay_handle(self.window)
        self.shown = False
        self.previous = None

    def hide(self):
        if self.shown:
            self.window.withdraw()
            self.shown = False
        self.previous = None

    def show(self, rect, source_size, callouts, banner=""):
        state = (rect, source_size, tuple(callouts), banner)
        if state == self.previous:
            return
        self.previous = state
        left, top, right, bottom = rect
        width, height = right - left, bottom - top
        font_size = min(18, max(10, round(height / 105)))
        label_offset = round(font_size * 2.8)
        self.canvas.delete("all")
        scale_x, scale_y = width / source_size[0], height / source_size[1]
        for hit, note in callouts:
            x1, y1, x2, y2 = [round(v * (scale_x if i % 2 == 0 else scale_y))
                              for i, v in enumerate(hit.box)]
            color = GOLD if hit.kind == '装备' else TEAL
            if note.startswith("核心"):
                color = GOLD
                title = f"★ {hit.name} · {note}"
            elif note.startswith("可用叠层"):
                title = f"{hit.name} · {note}"
            else:
                title = hit.name + " · " + note
            span = min(12, max(5, (x2-x1)//6))
            for x, y, dx, dy in ((x1-2,y1-2,1,1),(x2+3,y1-2,-1,1),(x1-2,y2+3,1,-1),(x2+3,y2+3,-1,-1)):
                self.canvas.create_line(x+span*dx,y,x,y,x,y+span*dy,fill=color,width=2)
            self.label(x1, max(0, y1 - label_offset), title, color, width, font_size)
        if banner:
            self.label(22, max(18, round(height * .13)), banner, TEAL, width, font_size,
                       wrap=round(width * .46))
        if not self.shown:
            self.window.deiconify()
            self.shown = True
        windows.move_overlay(self.hwnd, rect)

    def label(self, x, y, text, color, width, font_size, wrap=None):
        text_id = self.canvas.create_text(x + 9, y + 3, text=text, fill=color,
                                          width=wrap or min(round(width * .32), 580),
                                          anchor="nw", font=("Microsoft YaHei UI", font_size, "bold"))
        bx1, by1, bx2, by2 = self.canvas.bbox(text_id)
        if bx2 + 9 > width:
            shift = width - bx2 - 9
            self.canvas.move(text_id, shift, 0)
            bx1, by1, bx2, by2 = self.canvas.bbox(text_id)
        bg = self.canvas.create_polygon(bx1-8,by1-4,bx2+2,by1-4,bx2+8,by1+2,bx2+8,by2+4,
                                         bx1-8,by2+4,fill=PANEL,outline=color)
        self.canvas.tag_lower(bg, text_id)
