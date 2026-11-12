"""Topmost, non-activating callouts over the attached window."""
import tkinter as tk

from . import windows
from .ui import TEAL, GOLD

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

    def show(self, rect, source_size, callouts, banner="", scene="", font_scale=1.35):
        state = (rect, source_size, tuple(callouts), banner, scene, font_scale)
        if state == self.previous:
            return
        self.previous = state
        left, top, right, bottom = rect
        width, height = right - left, bottom - top
        self.draw(width, height, source_size, callouts, banner, scene, font_scale)
        if not self.shown:
            self.window.deiconify()
            self.shown = True
        windows.move_overlay(self.hwnd, rect)

    def draw(self, width, height, source_size, callouts, banner="", scene="", font_scale=1.35):
        # Negative Tk sizes are physical pixels: Windows scaling must not enlarge
        # these labels into a second HUD. Reserve the top 18% for game counters.
        font_size = round(min(17, max(9, round(height / 140))) * max(.8, min(2., font_scale)))
        label_offset = round(font_size * 2.0)
        protected_top = round(height * .18)
        self.canvas.delete("all")
        scale_x, scale_y = width / source_size[0], height / source_size[1]
        for hit, note in callouts:
            x1, y1, x2, y2 = [round(v * (scale_x if i % 2 == 0 else scale_y))
                              for i, v in enumerate(hit.box)]
            # During combat/preparation only annotate bottom shop cards. Unit
            # names over the board should never turn into battlefield labels.
            if scene in {"", "调度中心"} and y1 < height * .70:
                continue
            note = note.split(" · ")[0]+(' · 本阶段' if '当前阶段优先' in note else '')
            color = GOLD if hit.kind == '装备' else TEAL
            if note.startswith("核心"):
                color = GOLD
                title = f"★ {hit.name} · {note}"
            elif note.startswith("可用叠层"):
                title = f"{hit.name} · {note}"
            else:
                title = hit.name + " · " + note
            span = min(8, max(4, (x2-x1)//8))
            for x, y, dx, dy in ((x1-2,y1-2,1,1),(x2+3,y1-2,-1,1),(x1-2,y2+3,1,-1),(x2+3,y2+3,-1,-1)):
                if y >= protected_top:
                    self.canvas.create_line(x+span*dx,y,x,y,x,y+span*dy,fill=color,width=1, tags="callout")
            self.label(x1, max(protected_top + 5, y1 - label_offset), title, color, width, font_size)
        if banner:
            # A narrow transparent rail at the upper left, below game counters.
            # Full unabridged advice stays in the dashboard.
            self.label(round(width * .008), round(height * .19), banner, TEAL, width, font_size,
                       wrap=round(width * .14), max_height=round(height * .25), tag="plan")

    def label(self, x, y, text, color, width, font_size, wrap=None, max_height=None, bottom=None, tag="callout"):
        lines = [line[:80] + ("…" if len(line) > 80 else "") for line in text.splitlines()[:7]]
        text_id = self.canvas.create_text(x + 7, y + 3, text="\n".join(lines), fill=color,
                                          width=wrap or min(round(width * .23), 480), tags=tag,
                                          anchor="nw", font=("Microsoft YaHei UI", -font_size))
        if max_height:
            # Keep the guide within its reserved rail even for imported essays.
            while self.canvas.bbox(text_id)[3] - self.canvas.bbox(text_id)[1] > max_height - 10:
                index = max(range(len(lines)), key=lambda i: len(lines[i]))
                if len(lines[index]) > 8:
                    lines[index] = lines[index].rstrip("…")[:-5] + "…"
                elif len(lines) > 1:
                    lines.pop()
                else:
                    break
                self.canvas.itemconfigure(text_id, text="\n".join(lines))
        if bottom:
            self.canvas.move(text_id, 0, bottom - self.canvas.bbox(text_id)[3] - 4)
        bx1, by1, bx2, by2 = self.canvas.bbox(text_id)
        if bx2 + 7 > width:
            shift = width - bx2 - 7
            self.canvas.move(text_id, shift, 0)
            bx1, by1, bx2, by2 = self.canvas.bbox(text_id)
        # A one-pixel text shadow improves contrast without covering game pixels
        # with an opaque panel. The window itself remains color-key transparent.
        text_x, text_y = self.canvas.coords(text_id)
        shadow = self.canvas.create_text(text_x + 1, text_y + 1,
                                        text=self.canvas.itemcget(text_id, "text"), fill="#000000",
                                        width=wrap or min(round(width * .23), 480), tags=tag,
                                        anchor="nw", font=("Microsoft YaHei UI", -font_size))
        self.canvas.tag_lower(shadow, text_id)
