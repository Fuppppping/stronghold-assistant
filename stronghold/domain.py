"""Rules and guide data for Stronghold Protocol."""
from dataclasses import dataclass, field
import json
from pathlib import Path
import re
import unicodedata

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
    text: list[str] = field(default_factory=list)


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
        if not isinstance(strategies, list) or any(
            not isinstance(name, str) or name not in self.strategies for name in strategies
        ):
            raise ValueError("strategies 包含未知策略")
        if not isinstance(equipment, dict) or any(
            name not in self.equipment or not isinstance(note, str) for name, note in equipment.items()
        ):
            raise ValueError("equipment 需要已知装备及提示文字")
        guide.update(strategies=strategies, equipment=equipment, sources=[])
        self.lineups[guide["id"]] = guide
        return guide

    def status(self, name, states, excluded=()):
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

    def grouped(self, states, excluded=()):
        groups = {pact: [] for pact in self.pacts}
        for name, operator in self.operators.items():
            if self.status(name, states, excluded) is not False:
                for pact in operator["pacts"]:
                    groups[pact].append(name)
        return groups

    def rank(self, states, excluded=(), current=()):
        pool = self.grouped(states, excluded)

        def score(guide):
            blocked = any(states.get(pact) is False for pact in guide["targets"] if pact in self.core)
            can_build = all(len(pool[pact]) >= self.pacts[pact]["need"]
                            for pact in guide["targets"] if pact in self.core)
            main = set(guide["targets"]) & self.core
            confirmed = sum(states.get(pact) is True for pact in main)
            priorities = priority(guide)
            available = sum(self.status(name, states, excluded) is True for name in priorities)
            on_screen = sum(priorities.get(name, 0) for name in set(current))
            return (not blocked and can_build, confirmed, on_screen, available)
        return sorted(self.lineups.values(), key=score, reverse=True)


def priority(guide):
    result = {}
    for stage in guide["stages"]:
        for name in stage.get("operators", []):
            result.setdefault(name, 1)
        for name in stage.get("core", []):
            result[name] = 2
    return result


def alerts(reading, guide, enabled, muted, states, season, excluded=()):
    operators = priority(guide) if guide else {}
    gear = guide["equipment"] if guide else {}
    strategies = guide["strategies"] if guide else []
    result = []
    for hit in reading.hits:
        note = None
        if hit.kind == "干员" and hit.name in operators and reading.scene in {"调度中心", "自选编队"}:
            if season.status(hit.name, states, excluded) is not False:
                note = "核心干员" if operators[hit.name] == 2 else "阵容干员"
        elif hit.kind == "装备" and reading.scene in {"调度中心", "装备选择"}:
            if hit.name not in muted and (hit.name in enabled or hit.name in gear):
                note = gear.get(hit.name) or "关注装备"
        elif hit.kind == "策略" and reading.scene == "策略轮选" and hit.name in strategies:
            note = f"推荐策略 · 顺位 {strategies.index(hit.name) + 1}"
        if note:
            result.append((hit, note))
    return sorted(result, key=lambda pair: (pair[0].box[1], pair[0].box[0]))
