"""Explicit, verified single-step input for the native PC shop."""
from dataclasses import dataclass
from pathlib import Path
from time import monotonic, sleep

from PIL import Image, ImageChops, ImageStat

from . import windows
from .domain import key
from .vision import HEIGHT, WIDTH, game_region

SHOP_LABELS = {"open": ("展开", "收起"), "close": ("收起", "展开")}
HEADER = (340, 0, WIDTH, 145)
SHOP_BUTTON = (1090, 595, WIDTH, HEIGHT)


@dataclass(frozen=True)
class ShopButton:
    label: str
    point: tuple[int, int]


def identify_shop_button(recognizer, image):
    x1, y1, x2, y2 = game_region(image)
    frame = image.crop((x1, y1, x2, y2)).resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)
    header = "".join(key(line.text) for line in recognizer.ocr(frame, HEADER, 1.2))
    if "回合" not in header or not any(marker in header for marker in ("休息一下", "准备就绪")):
        raise RuntimeError("请进入卫戍协议的回合整备界面")
    labels = [line for line in recognizer.ocr(frame, SHOP_BUTTON, 1.5)
              if key(line.text) in {"展开", "收起"}]
    if len(labels) != 1:
        raise RuntimeError("未能唯一识别调度中心的展开或收起按钮")
    label = labels[0]
    a, b, c, d = label.box
    x = x1 + round((a+c) * (x2-x1) / (2 * WIDTH))
    y = y1 + round((b+d) * (y2-y1) / (2 * HEIGHT))
    return ShopButton(key(label.text), (x, y))


def operate_shop(hwnd, action, recognizer, log_directory: Path):
    expected, confirmed = SHOP_LABELS[action]
    if not windows.is_admin():
        raise RuntimeError("PC 单步操作需要以管理员身份运行助手")
    target = next((item for item in windows.list_windows() if item.hwnd == hwnd), None)
    if target is None or target.process.casefold() != "arknights.exe" or target.title != "明日方舟":
        raise RuntimeError("请先绑定官方 PC 客户端的明日方舟窗口")
    if windows.foreground() != hwnd:
        raise RuntimeError("请将明日方舟切到前台后重试")

    from maa.controller import Win32Controller
    from maa.define import MaaWin32InputMethodEnum as Input, MaaWin32ScreencapMethodEnum as Screen
    from maa.toolkit import Toolkit

    log_directory.mkdir(parents=True, exist_ok=True)
    Toolkit.init_option(log_directory)
    controller = Win32Controller(hwnd, Screen.ScreenDC, Input.PostMessageWithCursorPos, Input.PostMessage)
    try:
        if not controller.set_screenshot_use_raw_size(True):
            raise RuntimeError("无法设置 MaaFramework 原始截图尺寸")
        if not controller.post_connection().wait().succeeded or not controller.post_screencap().wait().succeeded:
            raise RuntimeError("MaaFramework 无法连接或截图")
        geometry = windows.capture_bounds(hwnd)
        if windows.foreground() != hwnd or not geometry:
            raise RuntimeError("游戏窗口状态已改变")
        before = windows.capture(hwnd)
        if before.size != tuple(controller.resolution):
            raise RuntimeError("游戏截图与控制器坐标尺寸不一致")
        button = identify_shop_button(recognizer, before)
        if button.label == confirmed:
            return f"调度中心已经{expected}"
        if windows.foreground() != hwnd or windows.capture_bounds(hwnd) != geometry:
            raise RuntimeError("游戏窗口已移动或切到后台")
        x, y = button.point
        dx, dy = max(8, before.width // 60), max(8, before.height // 90)
        region = (x-dx, y-dy, x+dx, y+dy)
        latest = windows.capture(hwnd)
        changes = ImageChops.difference(before.crop(region), latest.crop(region))
        if max(ImageStat.Stat(changes).mean) > 24:
            raise RuntimeError("调度中心按钮画面已改变，请重试")
        try:
            down = controller.post_touch_down(*button.point).wait()
            sleep(.08)
        finally:
            up = controller.post_touch_up().wait()
        if not down.succeeded or not up.succeeded:
            raise RuntimeError("MaaFramework 未能完成鼠标按下和释放")
    finally:
        controller.post_inactive().wait()

    deadline = monotonic() + 3
    while monotonic() < deadline:
        sleep(.3)
        if windows.foreground() != hwnd or windows.capture_bounds(hwnd) != geometry:
            break
        try:
            current = identify_shop_button(recognizer, windows.capture(hwnd))
        except RuntimeError:
            continue
        if current.label == confirmed:
            return f"调度中心已{expected}"
    raise RuntimeError("点击已发送，画面未确认状态变化")
