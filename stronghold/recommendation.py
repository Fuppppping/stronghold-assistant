"""Whole-lineup fit, including banned operators and explicit role alternatives."""
from dataclasses import dataclass


@dataclass
class GuideFit:
    score: int
    viable: bool
    blocked_core: list[str]
    unknown_core: list[str]
    blocked_support: list[str]
    missing_roles: list[str]
    pending_roles: list[str]
    alternatives: list[str]
    blocked_targets: list[str]
    confirmed_core: int
    total_core: int

    @property
    def label(self):
        if not self.viable:
            return f"{self.score}分 · 关键位缺失"
        if self.blocked_core:
            return f"{self.score}分 · 需调整"
        if self.unknown_core or self.pending_roles:
            return f"{self.score}分 · 待确认"
        return f"{self.score}分 · 核心齐备"

    @property
    def reason(self):
        parts = []
        if self.blocked_targets:
            parts.append("目标受限 " + "、".join(self.blocked_targets))
        if self.missing_roles:
            parts.append("缺位 " + "、".join(self.missing_roles))
        if self.pending_roles:
            parts.append("关键位待确认 " + "、".join(self.pending_roles))
        if self.blocked_core:
            parts.append("核心BAN " + "、".join(self.blocked_core))
        if self.alternatives:
            parts.append("候选 " + "；".join(self.alternatives))
        if self.unknown_core:
            parts.append(f"核心待确认 {len(self.unknown_core)} 名")
        if self.blocked_support:
            parts.append(f"其他禁用 {len(self.blocked_support)} 名")
        return "；".join(parts) or f"核心已确认 {self.confirmed_core}/{self.total_core}"


def assess(season, guide, states, excluded=(), seen=(), current=(), pool=None, status=None):
    status = status if status is not None else {name: season.status(name, states, excluded, seen) for name in season.operators}
    pool = pool if pool is not None else season.grouped(states, excluded, seen)
    core = {name for stage in guide['stages'] for name in stage.get('core', [])}
    core.update(item['operator'] for item in guide.get('stacking', []) if item['role'] == 'core')
    operators = {name for stage in guide['stages'] for name in stage.get('operators', [])}
    support = operators | {item['operator'] for item in guide.get('stacking', [])}
    roles = guide.get('requirements')
    if roles is None:
        roles = [{'name': stage['name'], 'operators': stage['core'], 'minimum': 1}
                 for stage in guide['stages'] if stage.get('core')]
    for role in roles:
        support.update(role['operators'])
    support -= core
    availability = {True: 1.0, None: .4, False: 0.0}
    weights = dict.fromkeys(support, 1)
    weights.update(dict.fromkeys(core, 5))
    all_fit = sum(weight*availability[status[name]] for name, weight in weights.items()) / max(sum(weights.values()), 1)
    core_fit = sum(availability[status[name]] for name in core)/max(len(core), 1) if core else all_fit
    missing, pending, alternatives = [], [], []
    for role in roles:
        need = role.get('minimum', 1)
        candidates = [name for name in role['operators'] if status[name] is not False]
        banned = [name for name in role['operators'] if status[name] is False]
        if len(candidates) < need:
            missing.append(role['name'])
        else:
            if sum(status[name] is True for name in candidates) < need:
                pending.append(role['name'])
            if banned:
                choices = [name + ('?' if status[name] is None else '') for name in candidates]
                alternatives.append(role['name'] + '：' + '、'.join(choices))
    blocked_targets, coverage = [], []
    for pact, count in guide['targets'].items():
        possible = len(pool[pact])
        coverage.append(0 if states.get(pact) is False else min(possible/count, 1))
        if pact in season.core and (states.get(pact) is False or possible < count):
            blocked_targets.append(f"{pact}({possible}/{count})")
    score = round(100*(.65*all_fit + .25*core_fit + .1*sum(coverage)/len(coverage)))
    score -= min(45, len(missing)*15) + min(30, len(blocked_targets)*20)
    # A visible shop card is a small tie-breaker, not a reason to recommend a broken lineup.
    score += min(3, sum(1 for name in set(current) if name in weights))
    return GuideFit(max(0, min(100, score)), not missing and not blocked_targets,
                    sorted(name for name in core if status[name] is False),
                    sorted(name for name in core if status[name] is None),
                    sorted(name for name in support if status[name] is False), missing, pending, alternatives,
                    blocked_targets, sum(status[name] is True for name in core), len(core))
