"""Rules and guide data for Stronghold Protocol."""
from dataclasses import dataclass, field
import json
from pathlib import Path
import re
import unicodedata

from .stock import StockLedger

DATA = Path(__file__).resolve().parent.parent / "data"


def key(text):
    return re.sub(r"[^\w\u3400-\u9fff]", "", unicodedata.normalize("NFKC", text)).casefold()


@dataclass(frozen=True)
class Hit:
    kind: str
    name: str
    box: tuple[int, int, int, int]
    confidence: float


@dataclass
class Reading:
    scene: str = ""
    hits: list[Hit] = field(default_factory=list)
    pacts: dict[str, bool] = field(default_factory=dict)
    excluded: set[str] = field(default_factory=set)
    groups: list[set[str]] = field(default_factory=list)
    selected_group: int | None = None
    partial_groups: bool = False
    setup: bool = False
    verified_panel: bool = False
    reset_hint: bool = False
    roster_slot: str = ""
    holdings: list = field(default_factory=list)
    team_holdings: dict = field(default_factory=dict)
    text: list[str] = field(default_factory=list)


@dataclass
class MatchState:
    auto: dict[str, bool] = field(default_factory=dict)
    manual: dict[str, bool] = field(default_factory=dict)
    excluded: set[str] = field(default_factory=set)
    seen: set[str] = field(default_factory=set)
    groups: list[set[str]] = field(default_factory=list)
    selected: int | None = None
    partial: bool = False
    incomplete: set[str] = field(default_factory=set)
    last_bans: tuple | None = None
    played: bool = False
    in_setup: bool = False
    stock: StockLedger = field(default_factory=StockLedger)
    reset_frames: int = 0
    epoch: int = 1

    @property
    def states(self):
        return self.auto | self.manual

    def choose(self, index):
        self.selected = index
        self.incomplete.clear()
        for i, group in enumerate(self.groups):
            for name in group:
                if self.partial and i != index:
                    self.auto.pop(name, None)
                    self.incomplete.add(name)
                else:
                    self.auto[name] = i == index

    def observe(self, reading, replay=False):
        self.reset_frames = self.reset_frames + 1 if reading.reset_hint else 0
        if self.reset_frames == 2:
            self.clear()
            self.reset_frames = 2
        if reading.scene in {"调度中心", "策略轮选", "自选编队", "队友阵容"}:
            self.played = True
            self.in_setup = False
        if reading.roster_slot and reading.holdings:
            self.stock.observe(reading.roster_slot, reading.holdings)
        for slot, holdings in reading.team_holdings.items():
            if holdings:
                self.stock.observe(slot, holdings, "队友面板头像 · 星级待确认 / 可见部分")
        if reading.scene == "调度中心":
            self.seen.update(hit.name for hit in reading.hits if hit.kind == "干员" and hit.confidence >= .83)
        if reading.scene != "盟约选择":
            self.last_bans = None
            return
        signature = (reading.pacts, reading.excluded, reading.groups, reading.selected_group, reading.partial_groups)
        confirmed = replay or reading.verified_panel or self.last_bans == signature
        self.last_bans = signature
        if not confirmed or not (reading.pacts or reading.groups or reading.excluded):
            return
        if reading.setup and self.played and not self.in_setup:
            self.clear()
        if reading.setup:
            self.in_setup = True
        self.auto.update(reading.pacts)
        self.excluded.update(reading.excluded)
        if reading.groups:
            self.groups = [set(group) for group in reading.groups]
            self.partial = reading.partial_groups
            if reading.selected_group is not None:
                self.choose(reading.selected_group)

    def clear(self):
        epoch = self.epoch + 1
        self.__dict__.update(MatchState(epoch=epoch).__dict__)


class Season:
    def __init__(self, file=DATA / "season.json"):
        source = json.loads(file.read_text(encoding="utf-8-sig"))
        self.name = source["season"]
        self.operators = {item["name"]: item for item in source["operators"]}
        self.pacts = {item["name"]: item for item in source["pacts"]}
        self.equipment = {item["name"]: item for item in source["equipment"]}
        self.strategies = {item["name"]: item for item in source["strategies"]}
        self.lineups = {item["id"]: item for item in source["lineups"]}
        self.names = {
            kind: {key(name): name for name in entries}
            for kind, entries in [
                ("干员", self.operators), ("装备", self.equipment),
                ("策略", self.strategies), ("盟约", self.pacts),
            ]
        }
        self.core = {name for name, pact in self.pacts.items() if pact["core"]}

    def add_guide(self, path):
        guide = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(guide, dict):
            raise ValueError("攻略 JSON 必须是一个对象")
        for field_name in ("id", "name"):
            if not isinstance(guide.get(field_name), str) or not guide[field_name].strip():
                raise ValueError(f"缺少文本字段 {field_name}")
        if guide["id"] in self.lineups:
            raise ValueError(f"攻略 ID 已存在：{guide['id']}")
        targets = guide.get("targets")
        if not isinstance(targets, dict) or not targets:
            raise ValueError("targets 至少要有一个盟约目标")
        if any(pact not in self.pacts or type(count) is not int or count < 1
               for pact, count in targets.items()):
            raise ValueError("targets 需要已知盟约和正整数人数")
        stages = guide.get("stages")
        if not isinstance(stages, list) or not stages:
            raise ValueError("stages 至少需要一个阶段")
        for stage in stages:
            if not isinstance(stage, dict) or not isinstance(stage.get("name"), str):
                raise ValueError("每个阶段需要 name")
            for field_name in ("operators", "core"):
                names = stage.get(field_name, [])
                if not isinstance(names, list) or any(
                    not isinstance(name, str) or name not in self.operators for name in names
                ):
                    raise ValueError(f"{field_name} 包含未知干员")
        strategies = guide.get("strategies", [])
        equipment = guide.get("equipment", {})
        for field_name in ("plan",):
            if not isinstance(guide.get(field_name, ""), str):
                raise ValueError(f"{field_name} 需要文字")
        for stage in stages:
            for field_name in ("timing", "plan"):
                if not isinstance(stage.get(field_name, ""), str):
                    raise ValueError(f"阶段 {field_name} 需要文字")
        stacking = guide.get("stacking", [])
        if not isinstance(stacking, list) or any(
            not isinstance(item, dict) or not isinstance(item.get("operator"), str)
            or item["operator"] not in self.operators or not isinstance(item.get("role"), str)
            or item["role"] not in {"core", "available"} or not isinstance(item.get("note", ""), str)
            for item in stacking
        ):
            raise ValueError("stacking 需要 operator（干员）、role（core/available）、note（提示文字）")
        if not isinstance(strategies, list) or any(
            not isinstance(name, str) or name not in self.strategies for name in strategies
        ):
            raise ValueError("strategies 包含未知策略")
        if not isinstance(equipment, dict) or any(
            name not in self.equipment or not isinstance(note, str) for name, note in equipment.items()
        ):
            raise ValueError("equipment 需要已知装备及提示文字")
        sources = guide.get("sources", [])
        if not isinstance(sources, list) or any(
            not isinstance(src, dict) or not isinstance(src.get("label"), str)
            or not isinstance(src.get("url"), str) or not re.match(r"https?://", src["url"])
            for src in sources
        ):
            raise ValueError("sources 需要 label 和 http(s) 来源网址")
        guide.update(strategies=strategies, equipment=equipment, sources=sources, stacking=stacking)
        self.lineups[guide["id"]] = guide
        return guide

    def status(self, name, states, excluded=(), seen=()):
        if name in seen:
            return True
        if name in excluded:
            return False
        pacts = self.operators[name]["pacts"]
        primary = self.core.intersection(pacts)
        if primary:
            values = [states.get(pact) for pact in primary]
            if True in values:
                return True
            return False if all(value is False for value in values) else None
        if not pacts:
            return True
        values = [states.get(pact) for pact in pacts]
        if True in values:
            return True
        return False if all(value is False for value in values) else None

    def grouped(self, states, excluded=(), seen=()):
        groups = {pact: [] for pact in self.pacts}
        for name, operator in self.operators.items():
            if self.status(name, states, excluded, seen) is not False:
                for pact in operator["pacts"]:
                    groups[pact].append(name)
        return groups

    def banned(self, states, excluded=(), seen=()):
        """Inferred names are available on the very first verified pact frame."""
        return {name: "名单识别" if name in excluded else "盟约推算"
                for name in self.operators if self.status(name, states, excluded, seen) is False} | {
                    name: "名单识别" for name in set(excluded)-set(seen) if name not in self.operators}

    def rank(self, states, excluded=(), current=(), seen=()):
        pool = self.grouped(states, excluded, seen)
        visible = set(current)

        def score(guide):
            main = set(guide["targets"]) & self.core
            viable = self.core_viable(guide, states, pool)
            confirmed = sum(states.get(pact) is True for pact in main)
            priorities = priority(guide)
            available = sum(weight for name, weight in priorities.items()
                            if self.status(name, states, excluded, seen) is True)
            on_screen = sum(priorities.get(name, 0) for name in visible)
            coverage = sum(min(len(pool[pact]), count) / count for pact, count in guide["targets"].items())
            return (viable, confirmed, on_screen, available / max(sum(priorities.values()), 1),
                    coverage / len(guide["targets"]))
        return sorted(self.lineups.values(), key=score, reverse=True)

    def core_viable(self, guide, states, pool):
        return all(states.get(pact) is not False and len(pool[pact]) >= self.pacts[pact]["need"]
                   for pact in guide["targets"] if pact in self.core)

    def strategy_guide(self, ranked, states, hits, excluded=(), seen=()):
        pool = self.grouped(states, excluded, seen)
        usable = [guide for guide in ranked if guide["strategies"] and self.core_viable(guide, states, pool)]
        visible = {hit.name for hit in hits if hit.kind == "策略"}
        return next((guide for guide in usable if visible.intersection(guide["strategies"])),
                    usable[0] if usable else None)


def priority(guide):
    result = {}
    for stage in guide["stages"]:
        for name in stage.get("operators", []):
            result.setdefault(name, 1)
        for name in stage.get("core", []):
            result[name] = 2
    return result


def alerts(reading, guide, enabled, muted, states, season, excluded=(), strategy_guide=None):
    operators = priority(guide) if guide else {}
    stacking = {item["operator"]: item for item in guide.get("stacking", [])} if guide else {}
    gear = guide["equipment"] if guide else {}
    advice = guide or strategy_guide
    strategies = advice["strategies"] if advice else []
    result = []
    for hit in reading.hits:
        note = None
        if hit.kind == "干员" and (hit.name in operators or hit.name in stacking) and reading.scene in {"调度中心", "自选编队"}:
            if reading.scene == "调度中心" or season.status(hit.name, states, excluded) is not False:
                stack = stacking.get(hit.name)
                note = (("核心叠层" if stack["role"] == "core" else "可用叠层")
                        + (" · " + stack["note"] if stack.get("note") else "")) if stack else (
                            "核心干员" if operators.get(hit.name) == 2 else "阵容干员")
        elif hit.kind == "装备" and reading.scene in {"调度中心", "装备选择"}:
            if hit.name not in muted and (hit.name in enabled or hit.name in gear):
                note = gear.get(hit.name) or "关注装备"
        elif hit.kind == "策略" and reading.scene == "策略轮选" and hit.name in strategies:
            note = f"推荐策略 · 顺位 {strategies.index(hit.name) + 1}"
        if note:
            result.append((hit, note))
    return sorted(result, key=lambda pair: (pair[0].box[1], pair[0].box[0]))
