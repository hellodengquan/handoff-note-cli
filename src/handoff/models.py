from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Optional
from enum import Enum


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class HandoffItem:
    id: int
    title: str
    description: str
    risk: RiskLevel = RiskLevel.LOW
    tags: List[str] = field(default_factory=list)
    owner: str = ""
    status: str = "pending"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        data = asdict(self)
        data["risk"] = self.risk.value
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "HandoffItem":
        item = cls(**data)
        item.risk = RiskLevel(data.get("risk", "low"))
        return item


@dataclass
class HandoffRecord:
    shift_name: str
    operator: str
    start_time: str
    end_time: str = ""
    items: List[HandoffItem] = field(default_factory=list)
    notes: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return {
            "shift_name": self.shift_name,
            "operator": self.operator,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "items": [item.to_dict() for item in self.items],
            "notes": self.notes,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "HandoffRecord":
        items = [HandoffItem.from_dict(i) for i in data.get("items", [])]
        return cls(
            shift_name=data["shift_name"],
            operator=data["operator"],
            start_time=data["start_time"],
            end_time=data.get("end_time", ""),
            items=items,
            notes=data.get("notes", ""),
            created_at=data.get("created_at", datetime.now().isoformat()),
        )
