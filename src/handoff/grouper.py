from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Set

from .models import HandoffRecord, HandoffItem, RiskLevel


RISK_SEVERITY_ORDER = {
    RiskLevel.CRITICAL: 4,
    RiskLevel.HIGH: 3,
    RiskLevel.MEDIUM: 2,
    RiskLevel.LOW: 1,
}


def _matches_any_risk(item_risks: Set[RiskLevel], target: RiskLevel) -> bool:
    target_weight = RISK_SEVERITY_ORDER[target]
    return any(RISK_SEVERITY_ORDER[lv] >= target_weight for lv in item_risks)


@dataclass
class ShiftGroup:
    operator: str
    records: List[HandoffRecord] = field(default_factory=list)

    @property
    def start_time(self) -> str:
        if not self.records:
            return ""
        return self.records[0].start_time

    @property
    def end_time(self) -> str:
        if not self.records:
            return ""
        last = self.records[-1]
        return last.end_time or last.start_time

    @property
    def risk_levels(self) -> Set[RiskLevel]:
        levels: Set[RiskLevel] = set()
        for r in self.records:
            for item in r.items:
                levels.add(item.risk)
        return levels

    @property
    def highest_risk(self) -> Optional[RiskLevel]:
        levels = self.risk_levels
        if not levels:
            return None
        return max(levels, key=lambda lv: RISK_SEVERITY_ORDER[lv])

    @property
    def total_items(self) -> int:
        return sum(len(r.items) for r in self.records)

    @property
    def high_risk_count(self) -> int:
        count = 0
        for r in self.records:
            for item in r.items:
                if item.risk in (RiskLevel.HIGH, RiskLevel.CRITICAL):
                    count += 1
        return count

    def contains_risk(self, target: RiskLevel) -> bool:
        return _matches_any_risk(self.risk_levels, target)

    def filtered_copy(self, target: RiskLevel) -> "ShiftGroup":
        new_records: List[HandoffRecord] = []
        for rec in self.records:
            matched_items = [i for i in rec.items if RISK_SEVERITY_ORDER[i.risk] >= RISK_SEVERITY_ORDER[target]]
            if not matched_items:
                continue
            new_rec = HandoffRecord(
                shift_name=rec.shift_name,
                operator=rec.operator,
                start_time=rec.start_time,
                end_time=rec.end_time,
                items=matched_items,
                notes=rec.notes,
                created_at=rec.created_at,
            )
            new_records.append(new_rec)
        return ShiftGroup(operator=self.operator, records=new_records)


def _parse_time(value: str) -> datetime:
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return datetime.now()


def _date_str(value: str) -> str:
    return _parse_time(value).strftime("%Y-%m-%d")


def sort_records_chronologically(records: List[HandoffRecord]) -> List[HandoffRecord]:
    return sorted(records, key=lambda r: _parse_time(r.start_time))


def group_by_shift(records: List[HandoffRecord]) -> List[ShiftGroup]:
    if not records:
        return []

    ordered = sort_records_chronologically(records)
    groups: List[ShiftGroup] = []
    current_group: ShiftGroup | None = None

    for record in ordered:
        should_split = False

        if current_group is None:
            should_split = True
        else:
            if current_group.operator != record.operator:
                should_split = True
            elif _date_str(current_group.records[-1].start_time) != _date_str(record.start_time):
                should_split = True

        if should_split:
            current_group = ShiftGroup(operator=record.operator, records=[record])
            groups.append(current_group)
        else:
            current_group.records.append(record)

    return groups


def filter_groups_by_risk(groups: List[ShiftGroup], target: RiskLevel) -> List[ShiftGroup]:
    kept: List[ShiftGroup] = []
    for g in groups:
        if not g.contains_risk(target):
            continue
        filtered = g.filtered_copy(target)
        if filtered.records:
            kept.append(filtered)
    return kept


def sort_groups_by_risk_severity(groups: List[ShiftGroup]) -> List[ShiftGroup]:
    def _key(g: ShiftGroup):
        highest = g.highest_risk
        weight = RISK_SEVERITY_ORDER[highest] if highest else 0
        return (-weight, g.start_time)

    return sorted(groups, key=_key)
