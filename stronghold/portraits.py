"""Conservative matching of small operator heads in BAN and teammate panels."""
import cv2
import numpy as np
from PIL import Image

from .domain import DATA, Hit
from .stock import Holding


def features(gray):
    data = gray.astype(np.float32)
    return cv2.GaussianBlur(data, (0, 0), 1.6) - cv2.GaussianBlur(data, (0, 0), 8)


class PortraitReader:
    def __init__(self, season):
        self.images, self.cache = {}, {}
        for name, operator in season.operators.items():
            path = DATA/'head'/(operator.get('head', '')+'.webp')
            if not path.is_file():
                continue
            with Image.open(path) as image:
                rgba = image.convert('RGBA')
                base = Image.new('RGBA', rgba.size, (35, 35, 35))
                self.images[name] = Image.alpha_composite(base, rgba).convert('L')

    def template(self, name, size):
        cache_key = (name, size)
        if cache_key not in self.cache:
            data = features(np.asarray(self.images[name].resize((size, size), Image.Resampling.BICUBIC)))
            margin = max(2, size//10)
            self.cache[cache_key] = data[margin:-margin, margin:-margin]
        return self.cache[cache_key]

    @staticmethod
    def cards(frame, rect=None):
        width, height = frame.size
        left, top, right, bottom = rect or (round(width*.45), 90, width-12, height-40)
        gray = np.asarray(frame.convert('L'))
        edges = cv2.Canny(gray[top:bottom, left:right], 45, 110)
        contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        boxes = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            if not (25 <= w <= 75 and 25 <= h <= 75 and .82 < w/h < 1.18):
                continue
            boxes.append((x+left, y+top, x+left+w, y+top+h))
        result = []
        for box in sorted(boxes, key=lambda b: (b[2]-b[0])*(b[3]-b[1]), reverse=True):
            cx, cy = (box[0]+box[2])/2, (box[1]+box[3])/2
            if any(abs(cx-(b[0]+b[2])/2) < (b[2]-b[0])*.4
                   and abs(cy-(b[1]+b[3])/2) < (b[3]-b[1])*.4 for b in result):
                continue
            result.append(box)
        return result

    @staticmethod
    def rows(boxes):
        rows = []
        for box in sorted(boxes, key=lambda b: (b[1]+b[3])/2):
            cy = (box[1]+box[3])/2
            if not rows or abs(cy - sum((b[1]+b[3])/2 for b in rows[-1])/len(rows[-1])) > 16:
                rows.append([])
            rows[-1].append(box)
        return rows

    def read(self, frame, boxes):
        gray = features(np.asarray(frame.convert('L')))
        hits = []
        for box in boxes:
            x1, y1, x2, y2 = box
            region = gray[max(0, y1-5):y2+5, max(0, x1-5):x2+5]
            scores = []
            sizes = sorted({round((x2-x1)*ratio) for ratio in (.80, .88, .96, 1.04)})
            for name in self.images:
                best = 0
                for size in sizes:
                    template = self.template(name, size)
                    if min(region.shape) < max(template.shape):
                        continue
                    response = cv2.matchTemplate(region, template, cv2.TM_CCOEFF_NORMED)
                    best = max(best, cv2.minMaxLoc(response)[1])
                scores.append((best, name))
            scores.sort(reverse=True)
            if len(scores) >= 2 and scores[0][0] >= .94 and scores[0][0]-scores[1][0] >= .025:
                score, name = scores[0]
                hits.append(Hit('干员', name, box, float(score)))
        return hits

    def team(self, frame, boxes):
        dense_rows = 0
        for row in self.rows(boxes):
            chain = 0
            previous = None
            for box in sorted(row):
                chain = chain+1 if previous and box[0]-previous[2] <= (box[2]-box[0])*.65 else 1
                previous = box
                if chain >= 3:
                    dense_rows += 1
                    break
        if dense_rows < 3:
            return [], {}
        hits = self.read(frame, boxes)
        groups = []
        by_box = {hit.box: hit for hit in hits}
        for row in self.rows([hit.box for hit in hits]):
            # Ignore player avatar on the left: take only a contiguous group of roster cards.
            clusters = []
            for box in sorted(row):
                if not clusters or box[0]-clusters[-1][-1][2] > max(box[2]-box[0], 25)*1.5:
                    clusters.append([])
                clusters[-1].append(box)
            usable = [cluster for cluster in clusters if len(cluster) >= 2]
            if usable:
                groups.append(max(usable, key=lambda cluster: cluster[-1][2]))
        if not 3 <= len(groups) <= 4:
            return [], {}
        left = min(box[0] for group in groups for box in group)
        right = max(box[2] for group in groups for box in group)
        layout = self.rows([box for box in boxes if left-8 <= box[0] and box[2] <= right+8])
        layout = [row for row in layout if len(row) >= 2]
        if not 3 <= len(layout) <= 4:
            return [], {}
        # One head border may be covered by a badge. Recover its cell from the other rows.
        columns = []
        for box in sorted([b for row in layout for b in row], key=lambda b: b[0]+b[2]):
            cx = (box[0]+box[2])/2
            if not columns or abs(cx-np.mean(columns[-1])) > 14:
                columns.append([])
            columns[-1].append(cx)
        cell_width = int(np.median([b[2]-b[0] for row in layout for b in row]))
        inferred = []
        for row in layout:
            cy = float(np.median([(b[1]+b[3])/2 for b in row]))
            for column in columns:
                cx = float(np.mean(column))
                if not any(abs((h.box[0]+h.box[2])/2-cx) < 14
                           and abs((h.box[1]+h.box[3])/2-cy) < 16 for h in hits):
                    x, y = round(cx-cell_width/2), round(cy-cell_width/2)
                    inferred.append((x, y, x+cell_width, y+cell_width))
        if inferred:
            hits.extend(self.read(frame, inferred))
            by_box.update({hit.box: hit for hit in hits})
        teams, accepted = {}, []
        for i, row in enumerate(layout, 1):
            cy = sum((b[1]+b[3])/2 for b in row)/len(row)
            group = [hit.box for hit in hits if left-8 <= hit.box[0] and hit.box[2] <= right+8
                     and abs((hit.box[1]+hit.box[3])/2-cy) < 16]
            counts = {}
            for box in group:
                hit = by_box[box]
                counts[hit.name] = counts.get(hit.name, 0)+1
                accepted.append(hit)
            # Head-only panels do not establish promotion rank, reserves or generated-card provenance.
            if counts:
                teams[f'面板{i}'] = [Holding(name, uncertain=count) for name, count in counts.items()]
        return accepted, teams
