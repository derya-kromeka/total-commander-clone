"""
FilterSpec — optional size/date constraints combined with AND/OR.
Used by FileSortFilterProxy after name + kind matching (always AND with those).
Folders skip size checks (pass); date applies to files and folders.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


class FilterSpec:
    """
    Advanced filter: optional size range and/or modified-date range.
    When both enabled, combine with combine_and (True=AND, False=OR).
    """

    __slots__ = ("size_enabled", "size_min", "size_max", "date_enabled", "date_after", "date_before", "combine_and")

    def __init__(self):
        self.size_enabled = False
        self.size_min: Optional[int] = None  # bytes, inclusive
        self.size_max: Optional[int] = None
        self.date_enabled = False
        self.date_after: Optional[float] = None  # unix timestamp, inclusive
        self.date_before: Optional[float] = None  # inclusive end of day if user picks date-only
        self.combine_and = True

    def is_empty(self) -> bool:
        size_active = self.size_enabled and (
            self.size_min is not None or self.size_max is not None
        )
        date_active = self.date_enabled and (
            self.date_after is not None or self.date_before is not None
        )
        return not size_active and not date_active

    def matches(self, entry: Dict[str, Any]) -> bool:
        """Return True if entry passes advanced rules (or no rules active)."""
        if self.is_empty():
            return True

        size_on = self.size_enabled and (
            self.size_min is not None or self.size_max is not None
        )
        date_on = self.date_enabled and (
            self.date_after is not None or self.date_before is not None
        )

        if not size_on and not date_on:
            return True

        sm = self._match_size(entry) if size_on else None
        dm = self._match_date(entry) if date_on else None

        if sm is None and dm is None:
            return True
        if sm is None:
            return bool(dm)
        if dm is None:
            return bool(sm)
        if self.combine_and:
            return sm and dm
        return sm or dm

    def _match_size(self, entry: Dict[str, Any]) -> bool:
        if entry.get("is_dir"):
            return True
        s = entry.get("size", 0)
        if s < 0:
            return True
        if self.size_min is not None and s < self.size_min:
            return False
        if self.size_max is not None and s > self.size_max:
            return False
        return True

    def _match_date(self, entry: Dict[str, Any]) -> bool:
        mt = float(entry.get("mod_time", 0))
        if self.date_after is not None and mt < self.date_after:
            return False
        if self.date_before is not None and mt > self.date_before:
            return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "size_enabled": self.size_enabled,
            "size_min": self.size_min,
            "size_max": self.size_max,
            "date_enabled": self.date_enabled,
            "date_after": self.date_after,
            "date_before": self.date_before,
            "combine_and": self.combine_and,
        }

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "FilterSpec":
        o = cls()
        if not data or not isinstance(data, dict):
            return o
        o.size_enabled = bool(data.get("size_enabled"))
        o.size_min = data.get("size_min")
        o.size_max = data.get("size_max")
        if o.size_min is not None:
            o.size_min = int(o.size_min)
        if o.size_max is not None:
            o.size_max = int(o.size_max)
        o.date_enabled = bool(data.get("date_enabled"))
        o.date_after = data.get("date_after")
        o.date_before = data.get("date_before")
        if o.date_after is not None:
            o.date_after = float(o.date_after)
        if o.date_before is not None:
            o.date_before = float(o.date_before)
        o.combine_and = bool(data.get("combine_and", True))
        return o


def filter_spec_from_dict(data: Optional[Dict[str, Any]]) -> FilterSpec:
    return FilterSpec.from_dict(data)
