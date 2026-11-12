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


def fresh(when, now):
    return type(when) in (int,float) and 0 <= now-when <= 30


@dataclass(frozen=True)
class Record:
    holding: Holding
    updated: float
    source: str
    fresh: bool
    expired_override: bool = False
    expired_value: Holding | None = None


@dataclass
class StockView:
    records: dict[str, list[tuple[str, Record]]]
    by_slot: dict[str, dict[str, Record]]
    counts: dict[str, int]
    stale_names: set[str]
    now: float

    def occupied(self, name):
        return self.counts.get(name,0)

    def amount(self, name):
        number = self.occupied(name)
        return f'{number}（含旧记录）' if name in self.stale_names else f'≥{number}'

    def note(self, name):
        notes = []
        for slot, record in self.records.get(name,[]):
            age = f'{int(self.now-record.updated)}秒前' if 0 < record.updated <= self.now else '时间待确认'
            copies = record.holding.copies(2 if name=='星极' else 3)
            old = record.expired_value.copies(2 if name=='星极' else 3) if record.expired_value else None
            notes.append(f'{slot} · {record.source} · 记录{copies}份 · {age}'
                         +(' · 已过期' if not record.fresh else '')
                         +(f' · 旧校正已停用（{old}份）' if record.expired_override else ''))
        return ' / '.join(notes) or '尚无此卡记录'

    def estimate(self, name, capacity=None):
        used = self.occupied(name)
        if self.stale_names:
            return '快照已过期 · 重新查看队友面板'
        if capacity is None:
            return f'已见占用 ≥{used} · 总池待核实'
        if used > capacity:
            return f'记录冲突：占用 {used} > 总池 {capacity}'
        return f'估算余量 0–{capacity-used} · 自设总池 {capacity}'


@dataclass
class StockLedger:
    players: dict[str, Snapshot] = field(default_factory=dict)
    manual: dict[str, dict[str, Holding]] = field(default_factory=dict)
    own_slot: str = ''
    manual_times: dict[str, dict[str, float]] = field(default_factory=dict)
    record_format: int = 2

    def records(self, slot, include_stale=False, now=None):
        now = time.time() if now is None else now
        snapshot = self.players.get(slot)
        result = {}
        if snapshot:
            for item in snapshot.holdings:
                valid = fresh(snapshot.updated,now)
                if valid or include_stale:
                    result[item.name] = Record(item,snapshot.updated,'画面识别',valid)
        for name,item in self.manual.get(slot,{}).items():
            when = self.manual_times.get(slot,{}).get(name,0)
            valid = fresh(when,now)
            automatic = result.get(name)
            if valid or (include_stale and (not automatic or not automatic.fresh and when >= automatic.updated)):
                result[name] = Record(item,when,'手动校正',valid)
            elif automatic:
                result[name] = Record(automatic.holding,automatic.updated,automatic.source,
                                      automatic.fresh,expired_override=True,expired_value=item)
        return result

    def view(self):
        now = time.time()
        by_slot = {slot:self.records(slot,True,now) for slot in sorted(self.players.keys() | self.manual.keys())}
        records, counts, stale = {}, {}, set()
        for slot,items in by_slot.items():
            for name,record in items.items():
                records.setdefault(name,[]).append((slot,record))
                copies = record.holding.copies(2 if name=='星极' else 3)
                counts[name] = counts.get(name,0)+copies
                if copies and not record.fresh:
                    stale.add(name)
        return StockView(records,by_slot,counts,stale,now)

    def own_names(self):
        if not self.own_slot:
            return None
        now = time.time()
        records = self.records(self.own_slot,now=now)
        snapshot = self.players.get(self.own_slot)
        if not records and not (snapshot and fresh(snapshot.updated,now)):
            return None
        return frozenset(name for name,record in records.items() if record.holding.copies() > 0)

    def own_status(self):
        if not self.own_slot:
            return '我方未指定 · 排序仅按 BAN 与当前来牌'
        snapshot = self.players.get(self.own_slot)
        if (self.own_slot not in self.players and self.own_slot not in self.manual
                or not self.records(self.own_slot,True) and (not snapshot or snapshot.updated<=0)):
            return f'我方：{self.own_slot} · 等待读取或手动校正'
        names = self.own_names()
        if names is None:
            return f'我方：{self.own_slot} · 记录过期，暂不参与排序'
        records = self.records(self.own_slot,True)
        source = '含手动校正' if any(r.fresh and r.source=='手动校正' for r in records.values()) else '面板识别'
        old = sum(not r.fresh and r.holding.copies()>0 for r in records.values())
        return f'我方：{self.own_slot} · 新近确认 {len(names)} 名（{source}）'+(f'；另有{old}条旧记录' if old else '')+'；顺序变化需重选'

    def observe(self, slot, holdings, source="画面识别 · 可见部分"):
        items = {item.name: item for item in holdings}
        self.players[slot] = Snapshot([item for item in items.values() if item.copies()],updated=time.time(),source=source)

    def correct(self, slot, item):
        self.manual.setdefault(slot, {})[item.name] = item
        self.manual_times.setdefault(slot,{})[item.name] = time.time()
        self.players.setdefault(slot,Snapshot([],updated=0,source='尚无画面读取'))

    def clear_correction(self, slot, name):
        for collection in (self.manual,self.manual_times):
            collection.get(slot,{}).pop(name,None)
            if slot in collection and not collection[slot]:
                collection.pop(slot)

    def forget(self, slot):
        self.players.pop(slot, None)
        self.manual.pop(slot, None)
        self.manual_times.pop(slot,None)
        if self.own_slot == slot:
            self.own_slot = ''

    def occupied(self, name):
        return self.view().occupied(name)

    def uncertain(self, name):
        return any(record.holding.uncertain for _,record in self.view().records.get(name,[]))

    def estimate(self, name, capacity=None):
        return self.view().estimate(name,capacity)
