"""Whole-lineup fit, including banned operators and explicit role alternatives."""
from dataclasses import dataclass


@dataclass
class OwnershipFit:
    core: list[str]
    support: list[str]
    unrecorded_core: list[str]
    ready_roles: list[str]
    unrecorded_roles: list[str]
    outside: list[str]
    conflicts: list[str]

    @property
    def bonus(self):
        # Unique names only: extra copies, uncertain stars and long support lists
        # cannot outweigh unavailable key roles, which are gated separately.
        return min(16, len(self.core)*6) + min(4, len(self.support))

    @property
    def reusable(self):
        return self.core+self.support

    @property
    def reason(self):
        parts = ['可沿用 '+('、'.join(self.reusable[:5]) or '暂无匹配')]
        if self.unrecorded_roles:
            parts.append('关键位尚未记录 '+ '、'.join(self.unrecorded_roles[:3]))
        if self.outside:
            parts.append('攻略外已有 '+ '、'.join(self.outside[:4]))
        if self.conflicts:
            parts.append('持有/BAN冲突待核对 '+ '、'.join(self.conflicts[:4]))
        return '；'.join(parts)


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
    ownership: OwnershipFit | None = None

    @property
    def rank_score(self):
        return self.score + (self.ownership.bonus if self.ownership else 0)

    @property
    def ranking_label(self):
        return self.label + (f' · 持有+{self.ownership.bonus}' if self.ownership else '')

    @property
    def label(self):
        if not self.viable:
            return f"{self.score}分 · 关键位缺失"
        if self.blocked_core:
            return f"{self.score}分 · 需调整"
        if self.unknown_core or self.pending_roles:
            return f"{self.score}分 · 待确认"
        return f"{self.score}分 · 核心可用"

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
        return "；".join(parts) or f"核心可用 {self.confirmed_core}/{self.total_core}"


def assess(season, guide, states, excluded=(), seen=(), current=(), pool=None, status=None, owned=None):
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
    ownership = None
    if owned is not None:
        recorded = set(owned) & season.operators.keys()
        usable = {name for name in recorded if status[name] is not False}
        ready, unrecorded = [], []
        for role in roles:
            (ready if len(usable.intersection(role['operators'])) >= role.get('minimum',1) else unrecorded).append(role['name'])
        ownership = OwnershipFit(sorted(usable & core), sorted(usable & support), sorted(core-usable),
                                 ready, unrecorded, sorted(usable-core-support), sorted(recorded-usable))
    return GuideFit(max(0, min(100, score)), not missing and not blocked_targets,
                    sorted(name for name in core if status[name] is False),
                    sorted(name for name in core if status[name] is None),
                    sorted(name for name in support if status[name] is False), missing, pending, alternatives,
                    blocked_targets, sum(status[name] is True for name in core), len(core), ownership)


def pivot_advice(current_id, ranked, fits, owned):
    if owned is None:
        return '指定我方来源并读取阵容后，可比较沿用卡与转阵备选。'
    if not owned:
        return '我方尚未记录干员；未见备战区不等于空阵容。'
    current = fits.get(current_id)
    if current is None:
        return '持有匹配已参与排序；先选定当前阵容，再比较备选。'
    choices = [g for g in ranked if g['id'] != current_id and fits[g['id']].viable
               and fits[g['id']].ownership and (fits[g['id']].ownership.core
               or len(fits[g['id']].ownership.support) >= 2)][:2]
    lines = ['当前关键位受 BAN 限制，优先比较备选。' if not current.viable else
             '有匹配更高的备选，可比较后决定。' if choices and fits[choices[0]['id']].rank_score >= current.rank_score+8 else
             '当前未发现 BAN 硬缺位，转阵先比较沿用卡。']
    for g in choices:
        own = fits[g['id']].ownership
        lines.append(g['name']+'：沿用 '+'、'.join(own.reusable[:3])
                     +('；未记录 '+'、'.join(own.unrecorded_roles[:2]) if own.unrecorded_roles else
                       '；关键位已有记录' if own.ready_roles else '；按攻略名单比较')
                     +('（可用性待确认）' if fits[g['id']].unknown_core or fits[g['id']].pending_roles else
                       '（核心受禁需调整）' if fits[g['id']].blocked_core else ''))
    if not choices:
        lines.append('暂未找到有足够沿用基础的可用备选。')
    return '\n'.join(lines)
