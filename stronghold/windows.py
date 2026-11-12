"""Win32 window discovery, capture, and the input-transparent overlay."""
import ctypes as c
from ctypes import wintypes as w
from dataclasses import dataclass
from io import BytesIO
import os
from pathlib import Path
import re
import shutil
import subprocess

from PIL import Image, ImageGrab, ImageStat

user32 = c.WinDLL("user32", use_last_error=True)
kernel32 = c.WinDLL("kernel32", use_last_error=True)
shell32 = c.WinDLL("shell32", use_last_error=True)
ENUM = c.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)
HWND_TOPMOST = -1
GWL_EXSTYLE = -20


def signature(dll, name, args, result=w.BOOL):
    fn = getattr(dll, name)
    fn.argtypes = args
    fn.restype = result
    return fn


enum_windows = signature(user32, "EnumWindows", [ENUM, w.LPARAM])
enum_children = signature(user32, "EnumChildWindows", [w.HWND, ENUM, w.LPARAM])
visible = signature(user32, "IsWindowVisible", [w.HWND])
is_window = signature(user32, "IsWindow", [w.HWND])
minimized = signature(user32, "IsIconic", [w.HWND])
foreground = signature(user32, "GetForegroundWindow", [], w.HWND)
activate = signature(user32, "SetForegroundWindow", [w.HWND])
is_admin = signature(shell32, "IsUserAnAdmin", [])
ancestor = signature(user32, "GetAncestor", [w.HWND, w.UINT], w.HWND)
related_window = signature(user32, "GetWindow", [w.HWND, w.UINT], w.HWND)
class_name = signature(user32, "GetClassNameW", [w.HWND, w.LPWSTR, c.c_int], c.c_int)
window_title = signature(user32, "GetWindowTextW", [w.HWND, w.LPWSTR, c.c_int], c.c_int)
window_pid = signature(user32, "GetWindowThreadProcessId", [w.HWND, c.POINTER(w.DWORD)], w.DWORD)
client_rect = signature(user32, "GetClientRect", [w.HWND, c.POINTER(w.RECT)])
window_rect = signature(user32, "GetWindowRect", [w.HWND, c.POINTER(w.RECT)])
to_screen = signature(user32, "ClientToScreen", [w.HWND, c.POINTER(w.POINT)])
get_style = signature(user32, "GetWindowLongPtrW", [w.HWND, c.c_int], c.c_ssize_t)
set_style = signature(user32, "SetWindowLongPtrW", [w.HWND, c.c_int, c.c_ssize_t], c.c_ssize_t)
set_position = signature(user32, "SetWindowPos", [w.HWND, w.HWND, c.c_int, c.c_int, c.c_int, c.c_int, w.UINT])
set_affinity = signature(user32, "SetWindowDisplayAffinity", [w.HWND, w.DWORD])
open_process = signature(kernel32, "OpenProcess", [w.DWORD, w.BOOL, w.DWORD], w.HANDLE)
query_process = signature(kernel32, "QueryFullProcessImageNameW", [w.HANDLE, w.DWORD, w.LPWSTR, c.POINTER(w.DWORD)])
close_handle = signature(kernel32, "CloseHandle", [w.HANDLE])


def enable_dpi():
    try:
        signature(user32, "SetProcessDpiAwarenessContext", [w.HANDLE])(-4)
    except AttributeError:
        user32.SetProcessDPIAware()


@dataclass(frozen=True)
class Window:
    hwnd: int
    title: str
    process: str
    score: int

    @property
    def label(self):
        return f"{self.title}  ·  {self.process or '未知进程'}  [{self.hwnd:X}]"


def bounds(hwnd):
    if not is_window(hwnd) or minimized(hwnd):
        return None
    rect, origin = w.RECT(), w.POINT()
    if client_rect(hwnd, c.byref(rect)) and to_screen(hwnd, c.byref(origin)):
        if rect.right >= 360 and rect.bottom >= 200:
            return origin.x, origin.y, origin.x + rect.right, origin.y + rect.bottom
    return None


def process_name(pid):
    handle = open_process(0x1000, False, pid)
    if not handle:
        return ""
    try:
        buffer = c.create_unicode_buffer(2048)
        size = w.DWORD(len(buffer))
        return Path(buffer.value).name if query_process(handle, 0, buffer, c.byref(size)) else ""
    finally:
        close_handle(handle)


def capture_bounds(hwnd):
    outer = bounds(hwnd)
    if not outer:
        return None
    left, top, right, bottom = outer
    area = (right - left) * (bottom - top)
    surfaces = []

    @ENUM
    def collect(child, _):
        name = c.create_unicode_buffer(128)
        class_name(child, name, len(name))
        if not visible(child) or not re.search(r"BlueStacksApp|RenderWindow|RenderSurface", name.value, re.I):
            return True
        region = bounds(child)
        if region:
            x1, y1, x2, y2 = region
            width, height = x2 - x1, y2 - y1
            if (left <= x1 < x2 <= right and top <= y1 < y2 <= bottom
                    and width * height > area * .55 and 1.5 <= width / height <= 2.2):
                surfaces.append((width * height, region))
        return True

    enum_children(hwnd, collect, 0)
    return max(surfaces)[1] if surfaces else outer


def window_score(title, process):
    name, exe = title.casefold(), process.casefold()
    if re.search(r"maaassistant|launcher|multi(?:player|instance)|chrome|msedge|firefox|browser|chatgpt", exe):
        return 0
    if re.search(r"终末地|終末地|endfield|多开|多開|启动器|遊戲手把|游戏手柄", name):
        return 0
    if re.search(r"明日方[舟轴]|arknights", name) or exe == "arknights.exe":
        return 100
    if re.search(r"mumuplayer|nemuplayer|hd-player|dnplayer|ldplayer|nox(?:vm)?|memu|androidemulator", exe):
        return 70
    if re.match(r"mumu|bluestacks|雷电模拟器|夜神模拟器|逍遥模拟器", name):
        return 50
    return 0


def list_windows():
    results = []
    own = os.getpid()

    @ENUM
    def collect(hwnd, _):
        if not visible(hwnd) or (not minimized(hwnd) and not bounds(hwnd)):
            return True
        pid = w.DWORD()
        window_pid(hwnd, c.byref(pid))
        if pid.value == own:
            return True
        title = c.create_unicode_buffer(512)
        window_title(hwnd, title, len(title))
        if title.value:
            exe = process_name(pid.value)
            score = window_score(title.value, exe)
            if score < 100 and related_window(hwnd, 4):  # GW_OWNER
                score = 0
            results.append(Window(hwnd, title.value, exe, score))
        return True

    enum_windows(collect, 0)
    active = foreground()
    return sorted(results, key=lambda item: (item.score, item.hwnd == active), reverse=True)


def terminal_window(hwnd):
    """Style only this application's caption; unsupported DWM attributes are ignored."""
    try:
        dwm = c.WinDLL('dwmapi')
        set_attribute = signature(dwm, 'DwmSetWindowAttribute', [w.HWND,w.DWORD,c.c_void_p,w.DWORD], c.c_long)
        handle = ancestor(hwnd, 2)
        for attribute, value in ((20,1),(34,0x384029),(35,0x0f100a),(36,0xeff3ed)):
            color = w.DWORD(value)
            set_attribute(handle,attribute,c.byref(color),c.sizeof(color))
    except (OSError,AttributeError):
        pass


def capture(hwnd):
    region = capture_bounds(hwnd)
    if region is None:
        raise RuntimeError("游戏窗口已最小化或关闭")
    # A foreground desktop capture works with GPU-rendered emulator windows.
    if foreground() == hwnd:
        return ImageGrab.grab(bbox=region, all_screens=True).convert("RGB")
    outer = w.RECT()
    if not window_rect(hwnd, c.byref(outer)):
        raise RuntimeError("无法读取窗口边界")
    frame = ImageGrab.grab(window=hwnd).convert("RGB")
    x1, y1, x2, y2 = region
    frame = frame.crop((x1 - outer.left, y1 - outer.top, x2 - outer.left, y2 - outer.top))
    if max(ImageStat.Stat(frame.resize((32, 18))).stddev) < 3:
        raise RuntimeError("后台抓屏无画面，请把游戏切到前台")
    return frame


def find_adb():
    path = shutil.which("adb")
    if path:
        return path
    root = Path(os.environ.get("ProgramFiles", "C:/Program Files"))
    choices = [
        root / "BlueStacks_nxt" / "HD-Adb.exe",
        root / "MuMuPlayer-12.0" / "shell" / "adb.exe",
        root / "Netease" / "MuMuPlayer-12.0" / "shell" / "adb.exe",
    ]
    return str(next((path for path in choices if path.is_file()), ""))


def adb_capture(exe, serial):
    command = [exe, "-s", serial, "exec-out", "screencap", "-p"]
    output = subprocess.run(command, capture_output=True, timeout=6, creationflags=subprocess.CREATE_NO_WINDOW)
    if output.returncode or not output.stdout.startswith(b"\x89PNG"):
        raise RuntimeError("ADB 截图失败，请确认 adb devices 中设备状态为 device")
    with Image.open(BytesIO(output.stdout)) as frame:
        return frame.convert("RGB")


def overlay_handle(toplevel):
    hwnd = ancestor(toplevel.winfo_id(), 2)  # GA_ROOT
    flags = 0x80000 | 0x20 | 0x08000000 | 0x80  # layered, transparent, no-activate, tool window
    set_style(hwnd, GWL_EXSTYLE, get_style(hwnd, GWL_EXSTYLE) | flags)
    set_affinity(hwnd, 0x11)  # WDA_EXCLUDEFROMCAPTURE
    return hwnd


def move_overlay(hwnd, rect):
    x1, y1, x2, y2 = rect
    set_position(hwnd, HWND_TOPMOST, x1, y1, x2 - x1, y2 - y1, 0x10 | 0x40)


def floating_style(toplevel, locked=False):
    """Only the body is locked; the separate title bar always stays clickable."""
    hwnd = ancestor(toplevel.winfo_id(), 2)
    flags = get_style(hwnd, GWL_EXSTYLE) | 0x80000 | 0x80
    flags = flags | 0x20 | 0x08000000 if locked else flags & ~(0x20 | 0x08000000)
    set_style(hwnd, GWL_EXSTYLE, flags)
    set_affinity(hwnd, 0x11)
    set_position(hwnd, HWND_TOPMOST, 0, 0, 0, 0, 0x1 | 0x2 | 0x10 | 0x20)
    return hwnd


def place_floating(hwnd, x, y, width, height):
    # Native desktop coordinates also support monitors left of the primary.
    # Unlike Tk's -x geometry syntax these are absolute, not right-edge offsets.
    set_position(hwnd, HWND_TOPMOST, x, y, width, height, 0x10)


def work_areas():
    class MonitorInfo(c.Structure):
        _fields_ = [("size", w.DWORD), ("monitor", w.RECT), ("work", w.RECT), ("flags", w.DWORD)]
    callback_type = c.WINFUNCTYPE(w.BOOL, w.HANDLE, w.HDC, c.POINTER(w.RECT), w.LPARAM)
    get_info = signature(user32, 'GetMonitorInfoW', [w.HANDLE, c.POINTER(MonitorInfo)])
    enumerate_monitors = signature(user32, 'EnumDisplayMonitors', [w.HDC,c.POINTER(w.RECT),callback_type,w.LPARAM])
    areas = []
    @callback_type
    def collect(handle, dc, region, data):
        info = MonitorInfo()
        info.size = c.sizeof(info)
        if get_info(handle, c.byref(info)):
            r = info.work
            areas.append((r.left,r.top,r.right,r.bottom))
        return True
    enumerate_monitors(None,None,collect,0)
    return areas


def owned_window(hwnd):
    """Include our dialogs when deciding whether the user is using the assistant."""
    if not hwnd:
        return False
    pid = w.DWORD()
    window_pid(hwnd,c.byref(pid))
    return pid.value == os.getpid()
