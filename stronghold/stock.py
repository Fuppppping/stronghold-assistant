"""Replaceable, per-player observations; shop offers never consume pool slots."""
from dataclasses import dataclass, field
import time


@dataclass(frozen=True)
class Holding:
    name: str
    normal: int = 0
    elite: int = 0
    uncertain: int = 0

    def copies(self, merge=3):
        return self.normal + self.elite * merge + self.uncertain


@dataclass
class Snapshot:
    holdings: list[Holding]
    updated: float = field(default_factory=time.time)
    source: str = "画面识别 · 可见部分"


@dataclass
class StockLedger:
    players: dict[str, Snapshot] = field(default_factory=dict)
    manual: dict[str, dict[str, Holding]] = field(default_factory=dict)
    own_slot: str = ''

    def own_names(self):
        if not self.own_slot:
            return None
        snapshot = self.players.get(self.own_slot)
        if not snapshot or not 0 <= time.time()-snapshot.updated <= 30:
            return None
        return frozenset(item.name for item in snapshot.holdings if item.copies() > 0)

    def own_status(self):
        if not self.own_slot:
            return '我方未指定 · 排序仅按 BAN 与当前来牌'
        if self.own_slot not in self.players:
            return f'我方：{self.own_slot} · 等待读取或手动校正'
        names = self.own_names()
        if names is None:
            return f'我方：{self.own_slot} · 记录过期，暂不参与排序'
        source = '含手动校正' if self.manual.get(self.own_slot) else '面板识别'
        return f'我方：{self.own_slot} · 可见 {len(names)} 名（{source}）；按位置跟随，顺序变化需重选'

    def observe(self, slot, holdings, source="画面识别 · 可见部分"):
        items = {item.name: item for item in holdings}
        items.update(self.manual.get(slot, {}))
        if self.manual.get(slot):
            source += " / 含手动校正"
        self.players[slot] = Snapshot([item for item in items.values() if item.copies()], source=source)

    def correct(self, slot, item):
        self.manual.setdefault(slot, {})[item.name] = item
        snapshot = self.players.get(slot)
        self.observe(slot, snapshot.holdings if snapshot else [], "手动校正 · 可见部分")

    def forget(self, slot):
        self.players.pop(slot, None)
        self.manual.pop(slot, None)
        if self.own_slot == slot:
            self.own_slot = ''

    def occupied(self, name):
        # 星极 needs two copies to promote, rather than the usual three.
        merge = 2 if name == "星极" else 3
        return sum(item.copies(merge) for snap in self.players.values()
                   for item in snap.holdings if item.name == name)

    def uncertain(self, name):
        return any(item.uncertain for snap in self.players.values()
                   for item in snap.holdings if item.name == name)

    def estimate(self, name, capacity=None):
        used = self.occupied(name)
        if any(time.time()-snap.updated > 30 for snap in self.players.values()):
            return "快照已过期 · 重新查看队友面板"
        if capacity is None:
            return f"已见占用 ≥{used} · 总池待核实"
        if used > capacity:
            return f"记录冲突：占用 {used} > 总池 {capacity}"
        # Unseen reserves, elapsed time and generated cards prevent an exact remainder.
        return f"估算余量 0–{capacity-used} · 自设总池 {capacity}"
