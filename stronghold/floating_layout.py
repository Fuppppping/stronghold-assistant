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
    follow_game: bool = True
    auto_compact: bool = True
    snap_edges: bool = True

    @classmethod
    def load(cls, values):
        result = cls()
        if not isinstance(values, dict):
            return result
        for name in ("x", "y", "width", "height"):
            value = values.get(name)
            if type(value) is int and -50000 <= value <= 50000:
                setattr(result, name, value)
        for name in ("collapsed", "locked", "follow_game", "auto_compact", "snap_edges"):
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


def snap(placement, bounds, distance=16):
    """Magnetize only near an edge; allow a panel outside a window as well."""
    left,top,right,bottom = bounds
    total = HEADER if placement.collapsed else HEADER+placement.height
    def nearest(value, candidates):
        target = min(candidates,key=lambda item:abs(item-value))
        return target if abs(target-value)<=distance else value
    return replace(placement,
                   x=nearest(placement.x,(left,right-placement.width,left-placement.width,right)),
                   y=nearest(placement.y,(top,bottom-total,top-total,bottom)))


def follow(placement, previous, current):
    """Translate with the client, retaining right/bottom alignment on resize."""
    left,top,right,bottom = previous
    new_left,new_top,new_right,new_bottom = current
    total = HEADER if placement.collapsed else HEADER+placement.height
    right_gap = right-placement.x-placement.width
    bottom_gap = bottom-placement.y-total
    x = new_right-placement.width-right_gap if abs(right_gap)<=24 else placement.x+new_left-left
    y = new_bottom-total-bottom_gap if abs(bottom_gap)<=24 else placement.y+new_top-top
    return replace(placement,x=x,y=y)
