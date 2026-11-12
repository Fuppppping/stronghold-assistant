"""Bounded capture scheduling; cached frames and failed capture aren't busy loops."""
from dataclasses import dataclass


@dataclass
class ScanCadence:
    reused: int = 0
    errors: int = 0

    def reset(self):
        self.reused = self.errors = 0

    def observe(self, reading):
        self.errors = 0
        self.reused = min(8,self.reused+1) if reading.reused else 0

    def failed(self):
        self.errors = min(3,self.errors+1)
        self.reused = 0

    def interval(self, active, scene='', reset_hint=False, enabled=True):
        if self.errors:
            return max(1.5 if enabled and not active else .25,2**(self.errors-1))
        if not enabled:
            return .25
        if not active:
            return 1.5
        if scene in {'盟约选择','策略轮选'} or reset_hint:
            return .25
        return .5 if self.reused>=3 else .25
