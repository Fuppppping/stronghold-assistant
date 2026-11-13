"""Bounded capture scheduling; cached frames and failed capture aren't busy loops."""
from dataclasses import dataclass


@dataclass
class ScanCadence:
    reused: int = 0
    errors: int = 0
    cheap: bool = False

    def reset(self):
        self.reused = self.errors = 0
        self.cheap = False

    def observe(self, reading):
        self.errors = 0
        self.reused = min(8,self.reused+1) if reading.reused else 0
        costs = (reading.capture_ms,reading.elapsed_ms)
        self.cheap = bool(reading.reused and all(type(value) in (int,float) and value>=0 for value in costs)
                          and sum(costs)<=40)

    def failed(self):
        self.errors = min(3,self.errors+1)
        self.reused = 0
        self.cheap = False

    def interval(self, active, scene='', reset_hint=False, enabled=True):
        if self.errors:
            return max(1.5 if enabled and not active else .25,2**(self.errors-1))
        if not enabled:
            return .25
        if not active:
            return 1.5
        if scene in {'盟约选择','策略轮选'} or reset_hint:
            return .25
        return .5 if self.reused>=3 and not self.cheap else .25
