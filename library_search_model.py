"""
Paged Qt table model for multi-library catalog search.
Loads result pages on demand instead of the whole catalog.
"""

from datetime import datetime

from PyQt5.QtCore import QAbstractTableModel, QModelIndex, Qt


COLUMNS = [
    ("Name", "name"),
    ("Location", "relative_path"),
    ("Library", "library_name"),
    ("Size", "size"),
    ("Modified", "mtime_ns"),
    ("Tags", "tags"),
    ("Status", "status"),
]

ROLE_ITEM = Qt.UserRole + 1
PAGE_SIZE = 200


# ------------------------------------------------------------
# Helper: format size
# ------------------------------------------------------------
def _formatSize(size, is_dir):
    if is_dir or size < 0:
        return ""
    units = ("B", "KB", "MB", "GB", "TB")
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024.0
    return f"{size} B"


# ------------------------------------------------------------
# Class: LibrarySearchModel
# Purpose: Lazy-loading table of catalog search hits.
# ------------------------------------------------------------
class LibrarySearchModel(QAbstractTableModel):

    def __init__(self, library_manager, parent=None):
        super().__init__(parent)
        self._manager = library_manager
        self._spec = {
            "library_ids": [],
            "text": "",
            "tags_all": [],
            "tags_any": [],
            "field_filters": [],
            "include_missing": True,
            "sort_by": "name",
            "sort_desc": False,
        }
        self._rows = []
        self._total = 0
        self._loaded = False
        self._fetching = False

    def spec(self):
        return dict(self._spec)

    def setSpec(self, **changes):
        self._spec.update(changes)
        self.reload()

    def reload(self):
        self.beginResetModel()
        self._rows = []
        self._total = 0
        self._loaded = False
        self.endResetModel()
        if not self._loaded:
            self.fetchMore(QModelIndex())

    def rowCount(self, parent=QModelIndex()):
        if parent.isValid():
            return 0
        return len(self._rows)

    def columnCount(self, parent=QModelIndex()):
        del parent
        return len(COLUMNS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole or orientation != Qt.Horizontal:
            return None
        if 0 <= section < len(COLUMNS):
            return COLUMNS[section][0]
        return None

    def canFetchMore(self, parent):
        if parent.isValid():
            return False
        if not self._loaded:
            return True
        return len(self._rows) < self._total

    def fetchMore(self, parent):
        del parent
        if getattr(self, "_fetching", False):
            return
        self._fetching = True
        try:
            spec = dict(self._spec)
            spec["offset"] = len(self._rows)
            spec["limit"] = PAGE_SIZE
            result = self._manager.search(spec)
            rows = result.get("rows") or []
            total = int(result.get("total") or 0)
            if spec["offset"] == 0:
                self.beginResetModel()
                self._rows = rows
                self._total = total
                self._loaded = True
                self.endResetModel()
                return
            if not rows:
                self._total = spec["offset"]
                self._loaded = True
                return
            start = len(self._rows)
            self.beginInsertRows(QModelIndex(), start, start + len(rows) - 1)
            self._rows.extend(rows)
            self._total = total
            self.endInsertRows()
        finally:
            self._fetching = False

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._rows)):
            return None
        item = self._rows[index.row()]
        if role == ROLE_ITEM:
            return item
        if role == Qt.ToolTipRole:
            path = item.get("resolved_path") or item.get("relative_path") or ""
            tags = ", ".join(item.get("tags") or [])
            note = item.get("notes") or ""
            parts = [path]
            if tags:
                parts.append("Tags: " + tags)
            if note:
                parts.append(note)
            if not item.get("is_available"):
                parts.append("(offline or missing)")
            return "\n".join(parts)
        if role != Qt.DisplayRole:
            return None
        key = COLUMNS[index.column()][1]
        if key == "name":
            return item.get("name", "")
        if key == "relative_path":
            return item.get("relative_path", "") or "."
        if key == "library_name":
            return item.get("library_name", "")
        if key == "size":
            return _formatSize(item.get("size", 0), item.get("is_dir"))
        if key == "mtime_ns":
            mtime_ns = int(item.get("mtime_ns") or 0)
            if mtime_ns <= 0:
                return ""
            return datetime.fromtimestamp(mtime_ns / 1_000_000_000).strftime("%Y/%m/%d %H:%M")
        if key == "tags":
            return ", ".join(item.get("tags") or [])
        if key == "status":
            if item.get("is_missing"):
                return "Missing"
            if not item.get("is_available"):
                return "Offline"
            status = item.get("root_status") or ""
            if status == "verification_needed":
                return "Verify"
            return "Online"
        return ""

    def itemAt(self, row):
        if 0 <= row < len(self._rows):
            return self._rows[row]
        return None

    def totalCount(self):
        return self._total

    def sort(self, column, order=Qt.AscendingOrder):
        if column < 0 or column >= len(COLUMNS):
            return
        key = COLUMNS[column][1]
        sort_by = {
            "name": "name",
            "relative_path": "path",
            "library_name": "library",
            "size": "size",
            "mtime_ns": "modified",
        }.get(key, "name")
        self.setSpec(sort_by=sort_by, sort_desc=(order == Qt.DescendingOrder))
