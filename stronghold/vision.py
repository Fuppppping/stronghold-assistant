"""ROI OCR and icon detection for the simplified Chinese client."""
from dataclasses import dataclass
import re

import cv2
import numpy as np
from PIL import Image, ImageStat
from rapidocr import RapidOCR

from .domain import DATA, Hit, Reading, key

WIDTH, HEIGHT = 1280, 720


@dataclass(frozen=True)
class Line:
    text: str
    box: tuple[int, int, int, int]
    confidence: float


def game_region(image):
    """Strip solid letterboxing before mapping to canonical game coordinates."""
    width, height = image.size
    thumb = np.asarray(image.resize((128, 72)))
    dark = thumb.max(axis=2) < 15
    good_x = np.where(dark.mean(axis=0) < .97)[0]
    good_y = np.where(dark.mean(axis=1) < .97)[0]
    if len(good_x) < 85 or len(good_y) < 45:
        return 0, 0, width, height
    x1, x2 = good_x[0] * width // 128, (good_x[-1] + 1) * width // 128
    y1, y2 = good_y[0] * height // 72, (good_y[-1] + 1) * height // 72
    return int(x1), int(y1), int(x2), int(y2)


def find_name(raw, table):
    value = key(raw)
    if value in table:
        return table[value]
    # OCR can join the leading role icon to the first character.
    if 3 <= len(value) <= 15:
        for prefix_length in (1, 2):
            candidate = value[prefix_length:]
            if len(candidate) >= 2 and candidate in table:
                return table[candidate]
    return None


class Recognizer:
    def __init__(self, season):
        self.season = season
        self.engine = RapidOCR(params={
            "EngineConfig.onnxruntime.intra_op_num_threads": 3,
            "EngineConfig.onnxruntime.inter_op_num_threads": 1,
        })
        self.icons = self.load_pacts()
        self.strategy_templates = self.load_strategies()

    def load_strategies(self):
        templates = {}
        for name, strategy in self.season.strategies.items():
            file = DATA / "strat" / (strategy["icon"] + ".webp")
            if file.is_file():
                with Image.open(file) as image:
                    rgba = image.convert("RGBA")
                    base = Image.new("RGBA", rgba.size, (11, 20, 23))
                    templates[name] = np.asarray(Image.alpha_composite(base, rgba).convert("L"))
        return templates

    def load_pacts(self):
        result = {}
        for name, pact in self.season.pacts.items():
            file = DATA / "pact" / (pact["id"] + ".webp")
            if file.is_file():
                with Image.open(file) as image:
                    alpha = image.convert("RGBA").getchannel("A")
                    if alpha.getbbox():
                        result[name] = np.asarray(alpha.crop(alpha.getbbox()))
        return result

    def ocr(self, frame, rect, zoom=1):
        x1, y1, x2, y2 = rect
        crop = frame.crop(rect)
        if zoom != 1:
            crop = crop.resize((round(crop.width * zoom), round(crop.height * zoom)), Image.Resampling.BICUBIC)
        # RapidOCR interprets NumPy inputs as BGR.
        image = cv2.cvtColor(np.asarray(crop), cv2.COLOR_RGB2BGR)
        result = self.engine(image, use_cls=False, text_score=.55)
        lines = []
        for text, box, score in zip(result.txts or (), result.boxes if result.boxes is not None else (),
                                    result.scores or ()):
            if score < .62:
                continue
            xa, ya = box.min(axis=0)
            xb, yb = box.max(axis=0)
            lines.append(Line(text, (x1 + round(xa / zoom), y1 + round(ya / zoom),
                                     x1 + round(xb / zoom), y1 + round(yb / zoom)), float(score)))
        return lines

    def hits(self, lines, kinds):
        result = []
        for line in lines:
            for kind in kinds:
                name = find_name(line.text, self.season.names[kind])
                if name:
                    result.append(Hit(kind, name, line.box, line.confidence))
                    break
        return result

    def inspect(self, image, forced="", roi=None):
        region = game_region(image)
        frame = image.crop(region).convert("RGB").resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)
        reading = self.read(frame, forced, roi)
        x, y, x2, y2 = region

        def real_box(box):
            return tuple(round(value * ((x2 - x) / WIDTH if i % 2 == 0 else (y2 - y) / HEIGHT))
                         + (x if i % 2 == 0 else y) for i, value in enumerate(box))

        reading.hits = [Hit(hit.kind, hit.name, real_box(hit.box), hit.confidence) for hit in reading.hits]
        return reading

    def read(self, frame, forced="", roi=None):
        reading = Reading()
        if max(ImageStat.Stat(frame.resize((32, 18))).stddev) < 3:
            return reading
        if not forced:
            buttons = self.ocr(frame, (980, 375, 1280, 560), 1.5)
            controls = " ".join(key(line.text) for line in buttons)
            if "刷新" in controls and "冻结" in controls:
                forced = "调度中心"
        if forced == "调度中心":
            reading.scene = forced
            lines = self.ocr(frame, roi or (90, 655, 1150, 710), 1.8)
            reading.text = [line.text for line in lines]
            reading.hits = self.hits(lines, ("装备", "干员"))
            return reading

        lines = self.ocr(frame, roi or (0, 0, WIDTH, HEIGHT), 1.1)
        reading.text = [line.text for line in lines]
        text = " ".join(key(line.text) for line in lines)
        if not forced and "客户端版本已过时" in text:
            reading.scene = "游戏客户端需要更新"
        elif forced == "盟约选择" or any(anchor in text for anchor in (
            "盟约选择", "选择盟约", "盟约随机", "禁用干员", "不可用干员", "盟约结果", "确认本局信息", "可选型核心盟约组",
        )):
            reading.scene = "盟约选择"
            self.read_bans(frame, lines, reading, roi)
        elif forced == "策略轮选" or any(anchor in text for anchor in (
            "策略轮选", "选择策略", "策略选择", "请选择一项策略", "选择你的策略",
        )):
            reading.scene = "策略轮选"
            reading.hits = self.read_strategies(frame, lines)
        elif forced == "自选编队" or any(anchor in text for anchor in ("自选编队", "选择自选干员")):
            reading.scene = "自选编队"
            reading.hits = self.hits(lines, ("干员",))
        elif forced == "装备选择" or any(anchor in text for anchor in ("装备选择", "道具补给", "选择装备")):
            reading.scene = "装备选择"
            reading.hits = self.hits(lines, ("装备",))
        return reading

    def read_strategies(self, frame, lines):
        # Match the artwork inside each card, leaving borders, hover highlights and text outside.
        x1, y1, x2, y2 = 320, 70, 995, 663
        gray = portrait_features(np.asarray(frame.convert("L").crop((x1, y1, x2, y2))))
        candidates = []
        for name, template in self.strategy_templates.items():
            for size in (94, 102, 110, 118, 126):
                image = cv2.resize(template, (size, size), interpolation=cv2.INTER_AREA)
                margin = size // 5
                center = portrait_features(image)[margin:-margin, margin:-margin]
                response = cv2.matchTemplate(gray, center, cv2.TM_CCOEFF_NORMED)
                for column in (408, 535, 661, 787, 913):
                    x_start = column - x1 - size//2 + margin - 13
                    _, score, _, (x, y) = cv2.minMaxLoc(response[:, x_start:x_start+27])
                    if score >= .80:
                        left, top = x1+x+x_start-margin, y1+y-margin
                        candidates.append(Hit("策略", name, (left, top, left+size, top+size), score))
        result = []
        for hit in sorted(candidates, key=lambda hit: hit.confidence, reverse=True):
            if not any(hit.name == other.name or box_distance(hit.box, other.box) < 50 for other in result):
                result.append(hit)
        labels = self.hits(lines, ("策略",))
        for label in labels:
            if not any(label.name == hit.name for hit in result):
                result.append(label)
        return result

    def read_bans(self, frame, lines, reading, roi):
        self.read_pact_panel(frame, lines, reading)
        status = None
        group_rows = {}
        group_boxes = {}
        excluded = False
        pacts = self.season.names["盟约"]
        for line in sorted(lines, key=lambda line: (line.box[1] // 18, line.box[0])):
            value = key(line.text)
            if re.search(r"禁用干员|不可用干员|不会出现的干员|干员禁用", value):
                excluded, status = True, None
                continue
            if "核心盟约" in value or "附加盟约" in value:
                excluded, status = False, None
            group = re.search(r"(?:方案|分组|第)([12一二ABab])(?:组)?|([12一二ABab])组", value)
            if group:
                token = (group.group(1) or group.group(2)).casefold()
                index = int(token in {"2", "二", "b"})
                group_rows.setdefault(index, set())
                group_boxes[index] = line.box
                if re.search(r"已选|已确认", value):
                    reading.selected_group = index
            match = re.search(r"禁用盟约|不可用盟约|盟约禁用|已禁用|未开放|可用盟约|已启用|已开放|已选盟约", value)
            if match:
                status = not any(mark in match[0] for mark in ("禁用", "不可用", "未开放"))
                excluded = False
                value = value[:match.start()] + value[match.end():]
            if excluded:
                name = find_name(value, self.season.names["干员"])
                if name:
                    reading.excluded.add(name)
                    reading.hits.append(Hit("干员", name, line.box, line.confidence))
            for name in self.pact_labels(value, pacts):
                if not any(hit.name == name for hit in reading.hits):
                    reading.hits.append(Hit("盟约", name, line.box, line.confidence))
                if status is not None:
                    reading.pacts[name] = status
                if group_boxes and name in self.season.core:
                    index = min(group_boxes, key=lambda i: box_distance(line.box, group_boxes[i]))
                    group_rows[index].add(name)

        if roi or (not reading.pacts and not reading.groups) or len(group_boxes) == 2:
            matches = self.pact_icons(frame, roi or (90, 130, 1190, 640))
            reading.hits.extend(matches)
            for hit in matches:
                if group_boxes and hit.name in self.season.core:
                    index = min(group_boxes, key=lambda i: box_distance(hit.box, group_boxes[i]))
                    group_rows[index].add(hit.name)
            if not group_boxes:
                self.add_icon_states(frame, matches, reading)
        if len(group_rows) == 2 and all(len(group) >= 2 for group in group_rows.values()):
            left, right = group_rows[0], group_rows[1]
            if not left.intersection(right):
                reading.groups = [left, right]
        if not reading.groups:
            reading.selected_group = None

    def read_pact_panel(self, frame, lines, reading):
        headers = {}
        for line in lines:
            value = key(line.text)
            if value.startswith("核心盟约"):
                headers.setdefault("core", line.box)
            elif value.startswith("附加盟约"):
                headers.setdefault("extra", line.box)
            elif "本局禁用干员" in value:
                headers.setdefault("ban", line.box)
        if "core" not in headers:
            return
        core = headers["core"]
        extra = headers.get("extra")
        hsv = np.asarray(frame.convert("HSV"))
        rows = []
        for line in lines:
            value = key(line.text)
            name = self.season.names["盟约"].get(value)
            if name is None:
                continue
            x1, y1, x2, y2 = line.box
            x, y = (x1+x2)//2, (y1+y2)//2
            if not (core[0]-60 <= x <= min(1175, core[0]+760) and 55 <= y-core[1] <= 515):
                continue
            if name in self.season.core:
                if (extra and y >= extra[1]) or y-core[1] > 200:
                    continue
            elif not extra or not (55 <= y-extra[1] <= 310) or ("ban" in headers and y >= headers["ban"][1]):
                continue
            sample = hsv[max(0,y-72):max(0,y-20), max(0,x-24):x+24]
            if sample.size == 0:
                continue
            hue, saturation, value = sample[:, :, 0], sample[:, :, 1], sample[:, :, 2]
            teal = np.mean((hue >= 90) & (hue <= 140) & (saturation >= 105) & (value >= 99))
            neutral = np.mean((saturation < 95) & (value > 65))
            state = True if teal >= .13 else False if teal <= .045 and neutral >= .09 else None
            if state is not None:
                rows.append((name, state, line))
        if len(rows) < 3 or not any(state for _, state, _ in rows):
            return
        selectable = any(
            re.search(r"可选择?一组激活|可选型核心盟约组|另(?:外)?一组.*阵容.*不完整",
                      key(line.text))
            for line in lines
        )
        core_rows = [(name, state, line) for name, state, line in rows if name in self.season.core]
        if selectable:
            # In the personal-simulation panel the two groups are separated horizontally.
            ordered = sorted(core_rows, key=lambda row: row[2].box[0]+row[2].box[2])
            centers = [(row[2].box[0]+row[2].box[2])/2 for row in ordered]
            if len(centers) >= 4:
                index = max(range(1, len(centers)), key=lambda i: centers[i]-centers[i-1])
                if 2 <= index <= len(centers)-2:
                    parts = (ordered[:index], ordered[index:])
                    reading.groups = [{name for name, _, _ in part} for part in parts]
                    reading.partial_groups = True
                    bright = [sum(state for _, state, _ in part) for part in parts]
                    if min(bright) == 0 and max(bright) >= 2:
                        reading.selected_group = bright.index(max(bright))
        for name, state, line in rows:
            if not selectable or name not in self.season.core:
                reading.pacts[name] = state
            reading.hits.append(Hit("盟约", name, line.box, line.confidence))

    @staticmethod
    def pact_labels(value, pacts):
        if value in pacts:
            return [pacts[value]]
        return [name for token, name in pacts.items() if len(token) >= 2 and token in value]

    def pact_icons(self, frame, rect):
        x1, y1, x2, y2 = rect
        gray = cv2.cvtColor(np.asarray(frame.crop(rect)), cv2.COLOR_RGB2GRAY)
        hits = []
        for name, template in self.icons.items():
            height, width = template.shape
            for size in (18, 22, 26, 31, 37, 44, 52, 63):
                scale = size / max(height, width)
                w, h = max(4, round(width * scale)), max(4, round(height * scale))
                if w + 6 >= gray.shape[1] or h + 6 >= gray.shape[0]:
                    continue
                variant = cv2.resize(template, (w, h), interpolation=cv2.INTER_AREA)
                variant = cv2.copyMakeBorder(variant, 3, 3, 3, 3, cv2.BORDER_CONSTANT, value=0)
                response = np.abs(cv2.matchTemplate(gray, variant, cv2.TM_CCOEFF_NORMED))
                for _ in range(2):
                    _, score, _, point = cv2.minMaxLoc(response)
                    if score < .58:
                        break
                    x, y = point
                    box = (x1+x+3, y1+y+3, x1+x+3+w, y1+y+3+h)
                    hits.append(Hit("盟约", name, box, score))
                    response[max(0,y-h):y+h+1, max(0,x-w):x+w+1] = 0
        result = []
        for hit in sorted(hits, key=lambda hit: hit.confidence, reverse=True):
            if not any(box_distance(other.box, hit.box) < 23 for other in result):
                result.append(hit)
        # Require a row of icons to reject lookalikes in terrain and prose.
        return [hit for hit in result if sum(
            abs((other.box[1]+other.box[3]) - (hit.box[1]+hit.box[3])) < 22
            and other.name != hit.name for other in result
        ) >= 2]

    @staticmethod
    def add_icon_states(frame, hits, reading):
        by_name = {}
        for hit in hits:
            if hit.confidence >= .63:
                by_name.setdefault(hit.name, hit)
        measurements = {}
        hsv = np.asarray(frame.convert("HSV"))
        for name, hit in by_name.items():
            x1, y1, x2, y2 = hit.box
            dx, dy = (x2-x1)//5, (y2-y1)//5
            crop = hsv[y1-dy:y2+dy, x1-dx:x2+dx]
            if crop.size:
                saturation, value = crop[:, :, 1], crop[:, :, 2]
                measurements[name] = float(np.mean((saturation > 63) & (value > 110)))
        # Only apply a color split when there is evidence for both states.
        if any(v > .24 for v in measurements.values()) and any(v < .045 for v in measurements.values()):
            for name, colored in measurements.items():
                if colored > .24 or colored < .045:
                    reading.pacts.setdefault(name, colored > .24)


def box_distance(first, second):
    x = ((first[0]+first[2]) - (second[0]+second[2])) / 2
    y = ((first[1]+first[3]) - (second[1]+second[3])) / 2
    return (x*x + y*y) ** .5


def portrait_features(image):
    pixels = image.astype(np.float32)
    return cv2.GaussianBlur(pixels, (0, 0), 1.6) - cv2.GaussianBlur(pixels, (0, 0), 8)
