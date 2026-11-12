"""Stage advice follows explicit guide ranges, never guessed shop ownership."""
from dataclasses import dataclass, field
import re
import time


@dataclass
class StageProgress:
    round_number: int | None = None
    pending: int | None = None
    confirmations: int = 0
    updated: float = 0
    manual: dict[str, int] = field(default_factory=dict)

    def observe(self, number, replay=False):
        if type(number) is not int or not 1 <= number <= 99:
            self.pending, self.confirmations = None, 0
            return
        if self.round_number is not None and number < self.round_number:
            self.pending, self.confirmations = None, 0
            return
        self.confirmations = min(2, self.confirmations+1) if number == self.pending else 1
        self.pending = number
        if replay or self.confirmations >= 2:
            self.round_number, self.updated = number, time.time()

    def current_round(self):
        return self.round_number if 0 <= time.time()-self.updated <= 30 else None


def round_range(stage):
    if 'rounds' in stage:
        value = stage['rounds']
        if (isinstance(value, list) and len(value) == 2
                and all(type(n) is int for n in value) and 1 <= value[0] <= value[1] <= 99):
            return tuple(value)
        return None
    # "1–3 本" and "中后期" are not round ranges.
    found = re.findall(r'(?<!\w)R\s*(\d{1,2})\s*[-–—~～]\s*R?\s*(\d{1,2})(?!\d)',
                       stage.get('timing', ''), re.I)
    if len(found) == 1:
        low, high = map(int, found[0])
        if 1 <= low <= high <= 99:
            return low, high
    return None


@dataclass(frozen=True)
class StagePlan:
    stage: dict | None = None
    caption: str = '先选定阵容'
    manual: bool = False


def choose_stage(guide, progress):
    if not guide:
        return StagePlan()
    stages = guide['stages']
    manual = progress.manual.get(guide['id'])
    if type(manual) is int and 0 <= manual < len(stages):
        stage = stages[manual]
        return StagePlan(stage, '手动 · '+stage['name'], True)
    number = progress.current_round()
    if number is None:
        return StagePlan(caption='自动 · 回合待确认，显示整套思路')
    matches = [s for s in stages if (r := round_range(s)) and r[0] <= number <= r[1]]
    if len(matches) == 1:
        return StagePlan(matches[0], f'自动参考 R{number} · '+matches[0]['name'])
    return StagePlan(caption=f'自动 · R{number} '+('阶段区间重叠' if matches else '未配置对应阶段')+'，可手动选择')
