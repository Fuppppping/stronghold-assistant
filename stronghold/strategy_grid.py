"""Find strategy-card cells so template matching searches each cell, not the whole screen."""
import cv2
import numpy as np


def clusters(values, tolerance):
    groups = []
    for value in sorted(values):
        if not groups or abs(value-np.mean(groups[-1])) > tolerance:
            groups.append([])
        groups[-1].append(value)
    return [float(np.mean(group)) for group in groups]


def cells(frame):
    gray = np.asarray(frame.convert('L'))
    contours, _ = cv2.findContours(cv2.Canny(gray[70:710, 320:1230], 40, 110),
                                  cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    boxes = []
    for contour in contours:
        x, y, width, height = cv2.boundingRect(contour)
        if 88 <= width <= 150 and 80 <= height <= 150 and .8 < width/height < 1.2:
            boxes.append((x+320, y+70, width, height))
    if len(boxes) < 6:
        return []
    xs = clusters([x+w/2 for x, y, w, h in boxes], 30)
    if len(xs) < 3:
        return []
    step = float(np.median(np.diff(xs)))
    groups = []
    for x in xs:
        if not groups or x-groups[-1][-1] > step*1.6:
            groups.append([])
        groups[-1].append(x)
    xs = max(groups, key=len)
    boxes = [box for box in boxes if min(abs(box[0]+box[2]/2-x) for x in xs) < 30]
    ys = clusters([y+h/2 for x, y, w, h in boxes], 30)
    if not 3 <= len(xs) <= 6 or not 2 <= len(ys) <= 6:
        return []
    width = float(np.median([w for x, y, w, h in boxes]))
    height = float(np.median([h for x, y, w, h in boxes]))
    step_y = float(np.median(np.diff(ys)))
    if ys[-1]+step_y-height/2 < 675:
        ys.append(ys[-1]+step_y)
    return [(max(320, round(x-width/2-14)), max(70, round(y-height/2-14)),
             min(1230, round(x+width/2+14)), min(710, round(y+height/2+14))) for y in ys for x in xs]
