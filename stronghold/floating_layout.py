"""Validated floating-panel placement, including disconnected/negative monitors."""
from dataclasses import asdict, dataclass, replace

HEADER = 42


@dataclass
class Placement:
    x: int = 24
    y: int = 180
    width: int = 400
    height: int = 590  # body only; title bar remains interactive when body is locked
    collapsed: bool = False
    locked: bool = False
    opacity: float = .95

    @classmethod
    def load(cls, values):
        result = cls()
        if not isinstance(values, dict):
            return result
        for name in ("x", "y", "width", "height"):
            value = values.get(name)
            if type(value) is int and -50000 <= value <= 50000:
                setattr(result, name, value)
        for name in ("collapsed", "locked"):
            if type(values.get(name)) is bool:
                setattr(result, name, values[name])
        opacity = values.get("opacity")
        if type(opacity) in (int, float) and .55 <= opacity <= 1:
            result.opacity = opacity
        return result

    def dump(self):
        return asdict(self)


def fit(placement, areas):
    """Keep the full panel recoverable in one visible work area, not in a gap."""
    areas = [a for a in areas if len(a) == 4 and a[2] > a[0] and a[3] > a[1]]
    if not areas:
        areas = [(0, 0, 1920, 1080)]
    def distance(area):
        left, top, right, bottom = area
        dx = max(left - placement.x, 0, placement.x - right)
        dy = max(top - placement.y, 0, placement.y - bottom)
        return dx*dx + dy*dy
    left, top, right, bottom = min(areas, key=distance)
    width = min(max(320, placement.width), 640, right-left)
    height = min(max(330, placement.height), 1000, bottom-top-HEADER)
    height = max(1, height)
    total = HEADER if placement.collapsed else HEADER + height
    return replace(placement, width=width, height=height,
                   x=max(left, min(placement.x, right-width)),
                   y=max(top, min(placement.y, bottom-total)))
