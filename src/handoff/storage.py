import json
import os
from pathlib import Path
from typing import List, Optional

from .models import HandoffRecord, HandoffItem, RiskLevel


DEFAULT_STORE_DIR = Path.home() / ".handoff"
DEFAULT_STORE_FILE = DEFAULT_STORE_DIR / "records.json"


class Storage:
    def __init__(self, store_path: Optional[Path] = None):
        self.store_path = store_path or DEFAULT_STORE_FILE
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.store_path.exists():
            self._write_records([])

    def _read_records(self) -> List[dict]:
        with open(self.store_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _write_records(self, records: List[dict]) -> None:
        with open(self.store_path, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)

    def list_records(self) -> List[HandoffRecord]:
        data = self._read_records()
        return [HandoffRecord.from_dict(r) for r in data]

    def get_record(self, shift_name: str) -> Optional[HandoffRecord]:
        for record in self.list_records():
            if record.shift_name == shift_name:
                return record
        return None

    def save_record(self, record: HandoffRecord) -> None:
        records = self._read_records()
        for i, r in enumerate(records):
            if r["shift_name"] == record.shift_name:
                records[i] = record.to_dict()
                break
        else:
            records.append(record.to_dict())
        self._write_records(records)

    def delete_record(self, shift_name: str) -> bool:
        records = self._read_records()
        new_records = [r for r in records if r["shift_name"] != shift_name]
        if len(new_records) != len(records):
            self._write_records(new_records)
            return True
        return False

    def add_item(self, shift_name: str, item: HandoffItem) -> Optional[HandoffRecord]:
        record = self.get_record(shift_name)
        if not record:
            return None
        existing_ids = [i.id for i in record.items]
        if not existing_ids:
            item.id = 1
        else:
            item.id = max(existing_ids) + 1
        record.items.append(item)
        self.save_record(record)
        return record

    def update_item_risk(self, shift_name: str, item_id: int, risk: RiskLevel) -> Optional[HandoffRecord]:
        record = self.get_record(shift_name)
        if not record:
            return None
        for item in record.items:
            if item.id == item_id:
                item.risk = risk
                from datetime import datetime
                item.updated_at = datetime.now().isoformat()
                self.save_record(record)
                return record
        return None

    def update_item_status(self, shift_name: str, item_id: int, status: str) -> Optional[HandoffRecord]:
        record = self.get_record(shift_name)
        if not record:
            return None
        for item in record.items:
            if item.id == item_id:
                item.status = status
                from datetime import datetime
                item.updated_at = datetime.now().isoformat()
                self.save_record(record)
                return record
        return None

    def delete_item(self, shift_name: str, item_id: int) -> Optional[HandoffRecord]:
        record = self.get_record(shift_name)
        if not record:
            return None
        record.items = [i for i in record.items if i.id != item_id]
        self.save_record(record)
        return record
