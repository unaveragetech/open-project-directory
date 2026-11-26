"""Traffic/advertising analytics helpers.

Records impressions/clicks per placement. Revenue is recorded only from
actual network reports — never forecast from assumed CPMs (see README
economics table, labelled illustrative only).
"""
from dataclasses import dataclass, field


@dataclass
class AdStats:
    placement: str
    network: str = "adsterra"
    impressions: int = 0
    clicks: int = 0

    def record_impression(self):
        self.impressions += 1

    def record_click(self):
        self.clicks += 1

    @property
    def ctr(self):
        if not self.impressions:
            return 0.0
        return round(self.clicks / self.impressions, 4)


@dataclass
class DirectoryAnalytics:
    stats: dict = field(default_factory=dict)

    def for_placement(self, placement):
        return self.stats.setdefault(placement, AdStats(placement=placement))
