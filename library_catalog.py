"""
Total Commander Clone - Local library catalog
SQLite source of truth for libraries, portable roots, indexed items,
typed properties, inheritance rules, and fast multi-library search.
"""

import json
import os
import sqlite3
import time
import uuid

from filesystem_scanner import canonicalRelativePath, relativeToRoot, parseGlobList
from library_paths import (
    isPathInsideRoot,
    normalizePath,
    readLibraryMarker,
    writeLibraryMarker,
)


# ------------------------------------------------------------
# Constants
# ------------------------------------------------------------
SCHEMA_VERSION = 1
CATALOG_FILENAME = "library_catalog.sqlite3"

FIELD_TAGS = "tags"
FIELD_NOTES = "notes"

FIELD_TYPE_TEXT = "text"
FIELD_TYPE_NUMBER = "number"
FIELD_TYPE_DATE = "date"
FIELD_TYPE_BOOLEAN = "boolean"
FIELD_TYPE_CHOICE = "choice"
FIELD_TYPE_MULTI = "multi_choice"

SCALAR_FIELD_TYPES = {
    FIELD_TYPE_TEXT,
    FIELD_TYPE_NUMBER,
    FIELD_TYPE_DATE,
    FIELD_TYPE_BOOLEAN,
    FIELD_TYPE_CHOICE,
}
ALL_FIELD_TYPES = SCALAR_FIELD_TYPES | {FIELD_TYPE_MULTI}

ROOT_STATUS_ONLINE = "online"
ROOT_STATUS_OFFLINE = "offline"
ROOT_STATUS_VERIFY = "verification_needed"
ROOT_STATUS_INDEXING = "indexing"
ROOT_STATUS_ERROR = "error"

APPLY_FILES = "files"
APPLY_FOLDERS = "folders"
APPLY_ALL = "all"


# ------------------------------------------------------------
# Helper: now
# ------------------------------------------------------------
def _now():
    return time.time()


# ------------------------------------------------------------
# Helper: json list helpers
# ------------------------------------------------------------
def _dumpList(value):
    items = parseGlobList(value)
    return json.dumps(items, ensure_ascii=False)


def _loadList(value):
    return parseGlobList(value)


# ------------------------------------------------------------
# Helper: SQL LIKE escape
# ------------------------------------------------------------
def _escapeLike(text):
    return (
        (text or "")
        .replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )


# ------------------------------------------------------------
# Helper: FTS query from free text
# ------------------------------------------------------------
def _ftsQuery(text):
    tokens = []
    for raw in (text or "").split():
        cleaned = "".join(ch for ch in raw if ch.isalnum() or ch in ("-", "_"))
        if cleaned:
            tokens.append(cleaned)
    if not tokens:
        return ""
    return " AND ".join(tokens)


# ------------------------------------------------------------
# Class: LibraryCatalog
# Purpose: Owns the SQLite file, schema migrations, CRUD, search,
#          logical snapshot export/import, and legacy JSON import.
# ------------------------------------------------------------
class LibraryCatalog:

    # --------------------------------------------------------
    # Method: __init__
    # --------------------------------------------------------
    def __init__(self, db_path):
        self.db_path = db_path
        self._conn = None
        self._fts_enabled = False

    # --------------------------------------------------------
    # Method: open
    # Purpose: Create the database file, apply pragmas, migrate.
    # --------------------------------------------------------
    def open(self):
        parent = os.path.dirname(self.db_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        self._conn = self.connect(primary=True)
        self._migrate(self._conn)
        return self

    # --------------------------------------------------------
    # Method: connect
    # Purpose: Open a SQLite connection. Workers pass primary=False.
    # --------------------------------------------------------
    def connect(self, primary=False):
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=5000")
        if primary:
            self._conn = conn
        return conn

    # --------------------------------------------------------
    # Method: connection
    # --------------------------------------------------------
    def connection(self):
        if self._conn is None:
            self.open()
        return self._conn

    # --------------------------------------------------------
    # Method: close
    # --------------------------------------------------------
    def close(self):
        if self._conn is not None:
            try:
                self._conn.close()
            except sqlite3.Error:
                pass
            self._conn = None

    # --------------------------------------------------------
    # Method: ftsEnabled
    # --------------------------------------------------------
    def ftsEnabled(self):
        return bool(self._fts_enabled)

    # --------------------------------------------------------
    # Internal: schema
    # --------------------------------------------------------
    def _migrate(self, conn):
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS schema_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )
        current = self._meta(conn, "schema_version", "0")
        try:
            version = int(current)
        except (TypeError, ValueError):
            version = 0
        if version < 1:
            self._applyV1(conn)
            version = 1
        self._setMeta(conn, "schema_version", str(version))
        self._ensureBuiltinFields(conn)
        self._fts_enabled = self._ensureFts(conn)
        conn.commit()

    def _meta(self, conn, key, default=""):
        row = conn.execute(
            "SELECT value FROM schema_meta WHERE key = ?",
            (key,),
        ).fetchone()
        return row["value"] if row else default

    def _setMeta(self, conn, key, value):
        conn.execute(
            "INSERT INTO schema_meta(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, str(value)),
        )

    def _applyV1(self, conn):
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS libraries (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS roots (
                id TEXT PRIMARY KEY,
                library_id TEXT NOT NULL REFERENCES libraries(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                path TEXT NOT NULL DEFAULT '',
                last_seen_path TEXT NOT NULL DEFAULT '',
                is_available INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'offline',
                include_files INTEGER NOT NULL DEFAULT 1,
                include_folders INTEGER NOT NULL DEFAULT 1,
                include_hidden INTEGER NOT NULL DEFAULT 0,
                include_globs TEXT NOT NULL DEFAULT '[]',
                exclude_globs TEXT NOT NULL DEFAULT '[]',
                last_scan_at REAL,
                last_scan_mode TEXT NOT NULL DEFAULT '',
                last_error TEXT NOT NULL DEFAULT '',
                item_count INTEGER NOT NULL DEFAULT 0,
                added_count INTEGER NOT NULL DEFAULT 0,
                changed_count INTEGER NOT NULL DEFAULT 0,
                missing_count INTEGER NOT NULL DEFAULT 0,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY,
                library_id TEXT NOT NULL,
                root_id TEXT NOT NULL REFERENCES roots(id) ON DELETE CASCADE,
                relative_path TEXT NOT NULL,
                name TEXT NOT NULL,
                is_dir INTEGER NOT NULL DEFAULT 0,
                size INTEGER NOT NULL DEFAULT 0,
                mtime_ns INTEGER NOT NULL DEFAULT 0,
                native_id TEXT NOT NULL DEFAULT '',
                extension TEXT NOT NULL DEFAULT '',
                is_missing INTEGER NOT NULL DEFAULT 0,
                indexed_at REAL NOT NULL,
                UNIQUE(root_id, relative_path)
            );

            CREATE INDEX IF NOT EXISTS idx_items_library ON items(library_id);
            CREATE INDEX IF NOT EXISTS idx_items_name ON items(name COLLATE NOCASE);
            CREATE INDEX IF NOT EXISTS idx_items_root_missing ON items(root_id, is_missing);
            CREATE INDEX IF NOT EXISTS idx_items_native ON items(root_id, native_id);

            CREATE TABLE IF NOT EXISTS fields (
                id TEXT PRIMARY KEY,
                key TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                is_builtin INTEGER NOT NULL DEFAULT 0,
                created_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS field_options (
                id INTEGER PRIMARY KEY,
                field_id TEXT NOT NULL REFERENCES fields(id) ON DELETE CASCADE,
                value TEXT NOT NULL,
                UNIQUE(field_id, value)
            );

            CREATE TABLE IF NOT EXISTS item_values (
                item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
                field_id TEXT NOT NULL REFERENCES fields(id) ON DELETE CASCADE,
                value TEXT NOT NULL,
                PRIMARY KEY (item_id, field_id, value)
            );

            CREATE INDEX IF NOT EXISTS idx_item_values_field ON item_values(field_id, value);

            CREATE TABLE IF NOT EXISTS inherit_rules (
                id INTEGER PRIMARY KEY,
                library_id TEXT NOT NULL,
                root_id TEXT NOT NULL REFERENCES roots(id) ON DELETE CASCADE,
                folder_rel_path TEXT NOT NULL,
                field_id TEXT NOT NULL REFERENCES fields(id) ON DELETE CASCADE,
                value TEXT NOT NULL,
                apply_to TEXT NOT NULL DEFAULT 'all',
                UNIQUE(root_id, folder_rel_path, field_id, value)
            );

            CREATE TABLE IF NOT EXISTS effective_values (
                item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
                field_id TEXT NOT NULL,
                value TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'direct',
                PRIMARY KEY (item_id, field_id, value)
            );

            CREATE INDEX IF NOT EXISTS idx_effective_field_value
                ON effective_values(field_id, value);
            CREATE INDEX IF NOT EXISTS idx_effective_item ON effective_values(item_id);
            """
        )

    def _ensureBuiltinFields(self, conn):
        stamp = _now()
        conn.execute(
            "INSERT OR IGNORE INTO fields(id, key, name, type, is_builtin, created_at) "
            "VALUES(?, ?, ?, ?, 1, ?)",
            (FIELD_TAGS, FIELD_TAGS, "Tags", FIELD_TYPE_MULTI, stamp),
        )
        conn.execute(
            "INSERT OR IGNORE INTO fields(id, key, name, type, is_builtin, created_at) "
            "VALUES(?, ?, ?, ?, 1, ?)",
            (FIELD_NOTES, FIELD_NOTES, "Notes", FIELD_TYPE_TEXT, stamp),
        )

    def _ensureFts(self, conn):
        try:
            conn.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS items_fts USING fts5("
                "name, relative_path, content='items', content_rowid='id')"
            )
            conn.executescript(
                """
                CREATE TRIGGER IF NOT EXISTS items_ai AFTER INSERT ON items BEGIN
                    INSERT INTO items_fts(rowid, name, relative_path)
                    VALUES (new.id, new.name, new.relative_path);
                END;
                CREATE TRIGGER IF NOT EXISTS items_ad AFTER DELETE ON items BEGIN
                    INSERT INTO items_fts(items_fts, rowid, name, relative_path)
                    VALUES('delete', old.id, old.name, old.relative_path);
                END;
                CREATE TRIGGER IF NOT EXISTS items_au AFTER UPDATE ON items BEGIN
                    INSERT INTO items_fts(items_fts, rowid, name, relative_path)
                    VALUES('delete', old.id, old.name, old.relative_path);
                    INSERT INTO items_fts(rowid, name, relative_path)
                    VALUES (new.id, new.name, new.relative_path);
                END;
                """
            )
            return True
        except sqlite3.OperationalError:
            return False

    def rebuildFts(self, conn=None):
        conn = conn or self.connection()
        if not self._fts_enabled:
            return
        try:
            conn.execute("INSERT INTO items_fts(items_fts) VALUES('rebuild')")
        except sqlite3.OperationalError:
            pass

    # --------------------------------------------------------
    # Libraries
    # --------------------------------------------------------
    def libraryCount(self, conn=None):
        conn = conn or self.connection()
        row = conn.execute("SELECT COUNT(*) AS n FROM libraries").fetchone()
        return int(row["n"] if row else 0)

    def listLibraries(self, conn=None):
        conn = conn or self.connection()
        libraries = []
        for row in conn.execute(
            "SELECT * FROM libraries ORDER BY name COLLATE NOCASE"
        ):
            library = self._libraryFromRow(row)
            library["roots"] = self.listRoots(library["id"], conn=conn)
            libraries.append(library)
        return libraries

    def getLibrary(self, library_id, conn=None):
        conn = conn or self.connection()
        row = conn.execute(
            "SELECT * FROM libraries WHERE id = ?",
            (library_id,),
        ).fetchone()
        if row is None:
            return None
        library = self._libraryFromRow(row)
        library["roots"] = self.listRoots(library_id, conn=conn)
        return library

    def findLibraryByName(self, name, conn=None):
        conn = conn or self.connection()
        row = conn.execute(
            "SELECT * FROM libraries WHERE lower(name) = lower(?)",
            ((name or "").strip(),),
        ).fetchone()
        if row is None:
            return None
        return self.getLibrary(row["id"], conn=conn)

    def createLibrary(self, name, description="", library_id="", conn=None):
        conn = conn or self.connection()
        name = (name or "").strip()
        if not name:
            return None
        existing = self.findLibraryByName(name, conn=conn)
        if existing is not None:
            if description and not existing.get("description"):
                self.updateLibrary(existing["id"], description=description, conn=conn)
                existing["description"] = description
            return existing
        stamp = _now()
        library_id = library_id or str(uuid.uuid4())
        conn.execute(
            "INSERT INTO libraries(id, name, description, created_at, updated_at) "
            "VALUES(?, ?, ?, ?, ?)",
            (library_id, name, description or "", stamp, stamp),
        )
        conn.commit()
        return self.getLibrary(library_id, conn=conn)

    def updateLibrary(self, library_id, name=None, description=None, conn=None):
        conn = conn or self.connection()
        library = self.getLibrary(library_id, conn=conn)
        if library is None:
            return None
        if name is not None:
            library["name"] = name.strip()
        if description is not None:
            library["description"] = description
        conn.execute(
            "UPDATE libraries SET name = ?, description = ?, updated_at = ? WHERE id = ?",
            (library["name"], library.get("description", ""), _now(), library_id),
        )
        conn.commit()
        return self.getLibrary(library_id, conn=conn)

    def deleteLibrary(self, library_id, conn=None):
        conn = conn or self.connection()
        conn.execute("DELETE FROM libraries WHERE id = ?", (library_id,))
        conn.commit()

    def _libraryFromRow(self, row):
        return {
            "id": row["id"],
            "name": row["name"],
            "description": row["description"] or "",
        }

    # --------------------------------------------------------
    # Roots
    # --------------------------------------------------------
    def listRoots(self, library_id=None, conn=None):
        conn = conn or self.connection()
        if library_id:
            rows = conn.execute(
                "SELECT * FROM roots WHERE library_id = ? ORDER BY name COLLATE NOCASE",
                (library_id,),
            )
        else:
            rows = conn.execute("SELECT * FROM roots ORDER BY name COLLATE NOCASE")
        return [self._rootFromRow(row) for row in rows]

    def getRoot(self, root_id, conn=None):
        conn = conn or self.connection()
        row = conn.execute("SELECT * FROM roots WHERE id = ?", (root_id,)).fetchone()
        if row is None:
            return None
        return self._rootFromRow(row)

    def addRoot(
        self,
        library_id,
        path,
        name="",
        root_id="",
        include_files=True,
        include_folders=True,
        include_hidden=False,
        include_globs=None,
        exclude_globs=None,
        conn=None,
    ):
        conn = conn or self.connection()
        path = normalizePath(path) if path else ""
        if not library_id:
            return None
        if path:
            for existing in self.listRoots(library_id, conn=conn):
                if normalizePath(existing.get("path", "")) == path:
                    self.setRootAvailability(existing["id"], True, path, conn=conn)
                    return self.getRoot(existing["id"], conn=conn)
        stamp = _now()
        root_id = root_id or str(uuid.uuid4())
        root_name = (name or "").strip() or os.path.basename(path) or "Root"
        available = 1 if path and os.path.isdir(path) else 0
        status = ROOT_STATUS_ONLINE if available else ROOT_STATUS_OFFLINE
        conn.execute(
            """
            INSERT INTO roots(
                id, library_id, name, path, last_seen_path, is_available, status,
                include_files, include_folders, include_hidden, include_globs, exclude_globs,
                last_scan_at, last_scan_mode, last_error, item_count, added_count,
                changed_count, missing_count, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, '', '', 0, 0, 0, 0, ?, ?)
            """,
            (
                root_id,
                library_id,
                root_name,
                path,
                path,
                available,
                status,
                1 if include_files else 0,
                1 if include_folders else 0,
                1 if include_hidden else 0,
                _dumpList(include_globs),
                _dumpList(exclude_globs),
                stamp,
                stamp,
            ),
        )
        conn.commit()
        return self.getRoot(root_id, conn=conn)

    def updateRoot(self, root_id, **fields):
        conn = self.connection()
        root = self.getRoot(root_id, conn=conn)
        if root is None:
            return None
        allowed = {
            "name",
            "include_files",
            "include_folders",
            "include_hidden",
            "include_globs",
            "exclude_globs",
            "last_error",
            "status",
        }
        for key, value in fields.items():
            if key not in allowed:
                continue
            if key in ("include_globs", "exclude_globs"):
                root[key] = _loadList(value)
            elif key in ("include_files", "include_folders", "include_hidden"):
                root[key] = bool(value)
            else:
                root[key] = value
        conn.execute(
            """
            UPDATE roots SET
                name = ?, include_files = ?, include_folders = ?, include_hidden = ?,
                include_globs = ?, exclude_globs = ?, last_error = ?, status = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                root["name"],
                1 if root["include_files"] else 0,
                1 if root["include_folders"] else 0,
                1 if root["include_hidden"] else 0,
                _dumpList(root["include_globs"]),
                _dumpList(root["exclude_globs"]),
                root.get("last_error", "") or "",
                root.get("status", ROOT_STATUS_OFFLINE),
                _now(),
                root_id,
            ),
        )
        conn.commit()
        return self.getRoot(root_id, conn=conn)

    def deleteRoot(self, root_id, conn=None):
        conn = conn or self.connection()
        conn.execute("DELETE FROM roots WHERE id = ?", (root_id,))
        conn.commit()

    def setRootAvailability(self, root_id, available, path="", status="", conn=None):
        conn = conn or self.connection()
        root = self.getRoot(root_id, conn=conn)
        if root is None:
            return None
        path = normalizePath(path) if path else root.get("path", "")
        previous = normalizePath(root.get("path", ""))
        if available:
            if not status:
                if previous and path and previous != path:
                    status = ROOT_STATUS_VERIFY
                else:
                    status = ROOT_STATUS_ONLINE
            conn.execute(
                """
                UPDATE roots SET path = ?, last_seen_path = ?, is_available = 1,
                    status = ?, updated_at = ?
                WHERE id = ?
                """,
                (path, path, status, _now(), root_id),
            )
        else:
            conn.execute(
                """
                UPDATE roots SET is_available = 0, status = ?, updated_at = ?
                WHERE id = ?
                """,
                (status or ROOT_STATUS_OFFLINE, _now(), root_id),
            )
        conn.commit()
        return self.getRoot(root_id, conn=conn)

    def updateRootScanStats(self, root_id, stats, conn=None):
        conn = conn or self.connection()
        conn.execute(
            """
            UPDATE roots SET
                last_scan_at = ?, last_scan_mode = ?, last_error = ?,
                item_count = ?, added_count = ?, changed_count = ?, missing_count = ?,
                status = ?, is_available = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                stats.get("last_scan_at", _now()),
                stats.get("last_scan_mode", "incremental"),
                stats.get("last_error", "") or "",
                int(stats.get("item_count", 0) or 0),
                int(stats.get("added_count", 0) or 0),
                int(stats.get("changed_count", 0) or 0),
                int(stats.get("missing_count", 0) or 0),
                stats.get("status", ROOT_STATUS_ONLINE),
                1 if stats.get("is_available", True) else 0,
                _now(),
                root_id,
            ),
        )
        conn.commit()

    def _rootFromRow(self, row):
        return {
            "id": row["id"],
            "library_id": row["library_id"],
            "name": row["name"],
            "path": row["path"],
            "last_seen_path": row["last_seen_path"],
            "is_available": bool(row["is_available"]),
            "status": row["status"],
            "include_files": bool(row["include_files"]),
            "include_folders": bool(row["include_folders"]),
            "include_hidden": bool(row["include_hidden"]),
            "include_globs": _loadList(row["include_globs"]),
            "exclude_globs": _loadList(row["exclude_globs"]),
            "last_scan_at": row["last_scan_at"],
            "last_scan_mode": row["last_scan_mode"] or "",
            "last_error": row["last_error"] or "",
            "item_count": int(row["item_count"] or 0),
            "added_count": int(row["added_count"] or 0),
            "changed_count": int(row["changed_count"] or 0),
            "missing_count": int(row["missing_count"] or 0),
        }

    # --------------------------------------------------------
    # Method: rebindRoot
    # Purpose: Point a saved root at a user-selected folder.
    #          Matching markers bind immediately; unmarked folders
    #          require claim=True; conflicting markers are rejected.
    # --------------------------------------------------------
    def rebindRoot(self, root_id, new_path, claim=False, conn=None):
        conn = conn or self.connection()
        root = self.getRoot(root_id, conn=conn)
        if root is None:
            return {"ok": False, "error": "Root not found.", "needs_claim": False}
        new_path = normalizePath(new_path)
        if not new_path or not os.path.isdir(new_path):
            return {"ok": False, "error": "Choose a valid folder.", "needs_claim": False}

        marker = readLibraryMarker(new_path)
        if marker:
            if (
                marker.get("library_id") == root.get("library_id")
                and marker.get("root_id") == root_id
            ):
                self.setRootAvailability(
                    root_id, True, new_path, ROOT_STATUS_VERIFY, conn=conn
                )
                return {"ok": True, "error": "", "needs_claim": False, "root": self.getRoot(root_id, conn=conn)}
            return {
                "ok": False,
                "error": "That folder already belongs to a different library root.",
                "needs_claim": False,
            }

        if not claim:
            return {
                "ok": False,
                "error": "This folder has no library marker.",
                "needs_claim": True,
            }

        library = self.getLibrary(root["library_id"], conn=conn)
        writeLibraryMarker(new_path, library, root)
        self.setRootAvailability(root_id, True, new_path, ROOT_STATUS_VERIFY, conn=conn)
        return {
            "ok": True,
            "error": "",
            "needs_claim": False,
            "root": self.getRoot(root_id, conn=conn),
        }

    # --------------------------------------------------------
    # Items
    # --------------------------------------------------------
    def getItem(self, item_id, conn=None):
        conn = conn or self.connection()
        row = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
        return self._itemFromRow(row) if row else None

    def getItemByRel(self, root_id, relative_path, conn=None):
        conn = conn or self.connection()
        rel = canonicalRelativePath(relative_path)
        row = conn.execute(
            "SELECT * FROM items WHERE root_id = ? AND relative_path = ?",
            (root_id, rel),
        ).fetchone()
        return self._itemFromRow(row) if row else None

    def loadRootItemMap(self, root_id, conn=None):
        conn = conn or self.connection()
        mapping = {}
        for row in conn.execute(
            "SELECT id, relative_path, is_dir, size, mtime_ns, native_id, is_missing "
            "FROM items WHERE root_id = ?",
            (root_id,),
        ):
            mapping[row["relative_path"]] = {
                "id": row["id"],
                "is_dir": bool(row["is_dir"]),
                "size": int(row["size"] or 0),
                "mtime_ns": int(row["mtime_ns"] or 0),
                "native_id": row["native_id"] or "",
                "is_missing": bool(row["is_missing"]),
            }
        return mapping

    def upsertIndexedItem(self, library_id, root_id, entry, existing=None, conn=None):
        conn = conn or self.connection()
        rel = canonicalRelativePath(entry.get("relative_path", ""))
        name = entry.get("name") or os.path.basename(rel) or entry.get("name") or ""
        is_dir = 1 if entry.get("is_dir") else 0
        size = int(entry.get("size", 0) or 0)
        if is_dir:
            size = -1
        mtime_ns = int(entry.get("mtime_ns", 0) or 0)
        native_id = entry.get("native_id", "") or ""
        extension = ""
        if not is_dir:
            _, ext = os.path.splitext(name)
            extension = ext[1:].lower()
        stamp = _now()
        if existing:
            conn.execute(
                """
                UPDATE items SET name = ?, is_dir = ?, size = ?, mtime_ns = ?,
                    native_id = ?, extension = ?, is_missing = 0, indexed_at = ?
                WHERE id = ?
                """,
                (name, is_dir, size, mtime_ns, native_id, extension, stamp, existing["id"]),
            )
            return existing["id"], "changed" if (
                existing.get("is_missing")
                or existing.get("size") != size
                or existing.get("mtime_ns") != mtime_ns
                or bool(existing.get("is_dir")) != bool(is_dir)
            ) else "unchanged"
        cursor = conn.execute(
            """
            INSERT INTO items(
                library_id, root_id, relative_path, name, is_dir, size, mtime_ns,
                native_id, extension, is_missing, indexed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
            """,
            (
                library_id,
                root_id,
                rel,
                name,
                is_dir,
                size,
                mtime_ns,
                native_id,
                extension,
                stamp,
            ),
        )
        return cursor.lastrowid, "added"

    def markMissingExcept(self, root_id, seen_paths, conn=None):
        conn = conn or self.connection()
        seen = {canonicalRelativePath(path) for path in seen_paths}
        missing_ids = []
        for row in conn.execute(
            "SELECT id, relative_path FROM items WHERE root_id = ? AND is_missing = 0",
            (root_id,),
        ):
            if row["relative_path"] not in seen:
                missing_ids.append(row["id"])
        if missing_ids:
            conn.executemany(
                "UPDATE items SET is_missing = 1 WHERE id = ?",
                [(item_id,) for item_id in missing_ids],
            )
        return missing_ids

    def rebindItemToPath(self, keep_id, drop_id, relative_path, name, entry, conn=None):
        conn = conn or self.connection()
        rel = canonicalRelativePath(relative_path)
        conn.execute("DELETE FROM items WHERE id = ?", (drop_id,))
        size = int(entry.get("size", 0) or 0)
        if entry.get("is_dir"):
            size = -1
        conn.execute(
            """
            UPDATE items SET relative_path = ?, name = ?, is_dir = ?, size = ?,
                mtime_ns = ?, native_id = ?, is_missing = 0, indexed_at = ?
            WHERE id = ?
            """,
            (
                rel,
                name,
                1 if entry.get("is_dir") else 0,
                size,
                int(entry.get("mtime_ns", 0) or 0),
                entry.get("native_id", "") or "",
                _now(),
                keep_id,
            ),
        )

    def _itemFromRow(self, row):
        if row is None:
            return None
        return {
            "id": row["id"],
            "library_id": row["library_id"],
            "root_id": row["root_id"],
            "relative_path": row["relative_path"],
            "name": row["name"],
            "is_dir": bool(row["is_dir"]),
            "size": int(row["size"] or 0),
            "mtime_ns": int(row["mtime_ns"] or 0),
            "native_id": row["native_id"] or "",
            "extension": row["extension"] or "",
            "is_missing": bool(row["is_missing"]),
            "indexed_at": row["indexed_at"],
        }

    def resolveAbsoluteContext(self, abs_path, conn=None):
        conn = conn or self.connection()
        abs_path = normalizePath(abs_path)
        if not abs_path:
            return None
        best = None
        for root in self.listRoots(conn=conn):
            root_path = normalizePath(root.get("path", ""))
            if not root_path or not os.path.isdir(root_path):
                continue
            if not isPathInsideRoot(abs_path, root_path):
                continue
            rel = relativeToRoot(abs_path, root_path)
            if rel is None:
                continue
            candidate = {
                "library_id": root["library_id"],
                "root": root,
                "relative_path": rel,
                "matched_len": len(root_path),
            }
            if best is None or candidate["matched_len"] > best["matched_len"]:
                best = candidate
        return best

    def ensureItemForPath(self, abs_path, conn=None):
        conn = conn or self.connection()
        context = self.resolveAbsoluteContext(abs_path, conn=conn)
        if context is None:
            return None
        root = context["root"]
        rel = context["relative_path"]
        existing = self.getItemByRel(root["id"], rel, conn=conn)
        if existing is not None:
            return existing
        is_dir = os.path.isdir(abs_path)
        name = os.path.basename(abs_path) if rel else (root.get("name") or os.path.basename(root.get("path", "")))
        item_id, _ = self.upsertIndexedItem(
            context["library_id"],
            root["id"],
            {
                "relative_path": rel,
                "name": name,
                "is_dir": is_dir,
                "size": -1 if is_dir else 0,
                "mtime_ns": 0,
                "native_id": "",
            },
            conn=conn,
        )
        conn.commit()
        return self.getItem(item_id, conn=conn)

    def notifyPathRenamed(self, old_path, new_path, conn=None):
        conn = conn or self.connection()
        old_ctx = self.resolveAbsoluteContext(old_path, conn=conn)
        if old_ctx is None:
            if os.path.exists(new_path):
                self.ensureItemForPath(new_path, conn=conn)
            return
        item = self.getItemByRel(old_ctx["root"]["id"], old_ctx["relative_path"], conn=conn)
        new_ctx = self.resolveAbsoluteContext(new_path, conn=conn)
        if item is None:
            if new_ctx is not None:
                self.ensureItemForPath(new_path, conn=conn)
            return
        if new_ctx is None or new_ctx["root"]["id"] != old_ctx["root"]["id"]:
            conn.execute("UPDATE items SET is_missing = 1 WHERE id = ?", (item["id"],))
            conn.commit()
            return
        old_rel = old_ctx["relative_path"]
        new_rel = new_ctx["relative_path"]
        new_name = os.path.basename(new_path) if new_rel else item["name"]
        conn.execute(
            "UPDATE items SET relative_path = ?, name = ?, is_missing = 0 WHERE id = ?",
            (new_rel, new_name, item["id"]),
        )
        if item["is_dir"] and old_rel != new_rel:
            prefix = old_rel + "/" if old_rel else ""
            new_prefix = new_rel + "/" if new_rel else ""
            rows = conn.execute(
                "SELECT id, relative_path FROM items WHERE root_id = ? AND relative_path LIKE ?",
                (item["root_id"], prefix + "%"),
            ).fetchall()
            for row in rows:
                if row["id"] == item["id"]:
                    continue
                suffix = row["relative_path"][len(prefix):]
                conn.execute(
                    "UPDATE items SET relative_path = ? WHERE id = ?",
                    (new_prefix + suffix, row["id"]),
                )
        conn.commit()
        self.rematerializeItem(item["id"], conn=conn)

    def notifyPathDeleted(self, abs_path, conn=None):
        conn = conn or self.connection()
        context = self.resolveAbsoluteContext(abs_path, conn=conn)
        if context is None:
            return
        item = self.getItemByRel(context["root"]["id"], context["relative_path"], conn=conn)
        if item is None:
            return
        conn.execute("UPDATE items SET is_missing = 1 WHERE id = ?", (item["id"],))
        if item["is_dir"]:
            prefix = item["relative_path"] + "/" if item["relative_path"] else ""
            if prefix:
                conn.execute(
                    "UPDATE items SET is_missing = 1 WHERE root_id = ? AND relative_path LIKE ?",
                    (item["root_id"], prefix + "%"),
                )
        conn.commit()

    def notifyPathCopied(self, dest_path, conn=None):
        self.ensureItemForPath(dest_path, conn=conn)

    # --------------------------------------------------------
    # Fields
    # --------------------------------------------------------
    def listFields(self, conn=None):
        conn = conn or self.connection()
        fields = []
        for row in conn.execute("SELECT * FROM fields ORDER BY is_builtin DESC, name COLLATE NOCASE"):
            field = {
                "id": row["id"],
                "key": row["key"],
                "name": row["name"],
                "type": row["type"],
                "is_builtin": bool(row["is_builtin"]),
                "options": [],
            }
            if field["type"] in (FIELD_TYPE_CHOICE, FIELD_TYPE_MULTI):
                field["options"] = self.listFieldOptions(field["id"], conn=conn)
            fields.append(field)
        return fields

    def getField(self, field_id, conn=None):
        conn = conn or self.connection()
        row = conn.execute("SELECT * FROM fields WHERE id = ?", (field_id,)).fetchone()
        if row is None:
            row = conn.execute("SELECT * FROM fields WHERE key = ?", (field_id,)).fetchone()
        if row is None:
            return None
        return {
            "id": row["id"],
            "key": row["key"],
            "name": row["name"],
            "type": row["type"],
            "is_builtin": bool(row["is_builtin"]),
            "options": self.listFieldOptions(row["id"], conn=conn),
        }

    def createField(self, name, field_type, key="", options=None, conn=None):
        conn = conn or self.connection()
        name = (name or "").strip()
        field_type = (field_type or "").strip()
        if not name or field_type not in ALL_FIELD_TYPES:
            return None
        key = (key or "").strip() or name.lower().replace(" ", "_")
        existing = conn.execute("SELECT id FROM fields WHERE key = ?", (key,)).fetchone()
        if existing:
            return self.getField(existing["id"], conn=conn)
        field_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO fields(id, key, name, type, is_builtin, created_at) VALUES(?, ?, ?, ?, 0, ?)",
            (field_id, key, name, field_type, _now()),
        )
        for option in options or []:
            self.addFieldOption(field_id, option, conn=conn)
        conn.commit()
        return self.getField(field_id, conn=conn)

    def deleteField(self, field_id, conn=None):
        conn = conn or self.connection()
        field = self.getField(field_id, conn=conn)
        if field is None or field["is_builtin"]:
            return False
        conn.execute("DELETE FROM item_values WHERE field_id = ?", (field["id"],))
        conn.execute("DELETE FROM effective_values WHERE field_id = ?", (field["id"],))
        conn.execute("DELETE FROM inherit_rules WHERE field_id = ?", (field["id"],))
        conn.execute("DELETE FROM fields WHERE id = ?", (field["id"],))
        conn.commit()
        return True

    def listFieldOptions(self, field_id, conn=None):
        conn = conn or self.connection()
        rows = conn.execute(
            "SELECT value FROM field_options WHERE field_id = ? ORDER BY value COLLATE NOCASE",
            (field_id,),
        )
        return [row["value"] for row in rows]

    def addFieldOption(self, field_id, value, conn=None):
        conn = conn or self.connection()
        value = (value or "").strip()
        if not value:
            return
        conn.execute(
            "INSERT OR IGNORE INTO field_options(field_id, value) VALUES(?, ?)",
            (field_id, value),
        )
        conn.commit()

    def listUsedValues(self, field_id, conn=None):
        conn = conn or self.connection()
        values = set(self.listFieldOptions(field_id, conn=conn))
        for row in conn.execute(
            "SELECT DISTINCT value FROM effective_values WHERE field_id = ?",
            (field_id,),
        ):
            if row["value"]:
                values.add(row["value"])
        return sorted(values, key=lambda item: item.lower())

    # --------------------------------------------------------
    # Direct values and inheritance
    # --------------------------------------------------------
    def getDirectValues(self, item_id, conn=None):
        conn = conn or self.connection()
        result = {}
        for row in conn.execute(
            "SELECT field_id, value FROM item_values WHERE item_id = ?",
            (item_id,),
        ):
            result.setdefault(row["field_id"], []).append(row["value"])
        return result

    def getEffectiveValues(self, item_id, conn=None):
        conn = conn or self.connection()
        result = {}
        for row in conn.execute(
            "SELECT field_id, value, source FROM effective_values WHERE item_id = ?",
            (item_id,),
        ):
            result.setdefault(row["field_id"], []).append(row["value"])
        return result

    def setDirectFieldValues(self, item_id, field_id, values, conn=None, rematerialize=True):
        conn = conn or self.connection()
        field = self.getField(field_id, conn=conn)
        if field is None:
            return
        field_id = field["id"]
        cleaned = []
        seen = set()
        if not isinstance(values, (list, tuple)):
            values = [] if values in (None, "") else [values]
        for raw in values:
            text = "" if raw is None else str(raw).strip()
            if field["type"] == FIELD_TYPE_BOOLEAN:
                text = "1" if str(raw).strip().lower() in ("1", "true", "yes", "on") else "0"
            if field["type"] in SCALAR_FIELD_TYPES and not text and field["type"] != FIELD_TYPE_BOOLEAN:
                continue
            key = text.lower() if field["id"] == FIELD_TAGS else text
            if key in seen:
                continue
            seen.add(key)
            cleaned.append(text)
            if field["type"] in (FIELD_TYPE_CHOICE, FIELD_TYPE_MULTI) and text:
                self.addFieldOption(field_id, text, conn=conn)
            if field["type"] in SCALAR_FIELD_TYPES:
                break
        conn.execute(
            "DELETE FROM item_values WHERE item_id = ? AND field_id = ?",
            (item_id, field_id),
        )
        for value in cleaned:
            conn.execute(
                "INSERT INTO item_values(item_id, field_id, value) VALUES(?, ?, ?)",
                (item_id, field_id, value),
            )
        if rematerialize:
            self.rematerializeItem(item_id, conn=conn)
            conn.commit()

    def setDirectValuesMap(self, item_id, values_map, conn=None):
        conn = conn or self.connection()
        for field_id, values in (values_map or {}).items():
            self.setDirectFieldValues(item_id, field_id, values, conn=conn, rematerialize=False)
        self.rematerializeItem(item_id, conn=conn)
        conn.commit()

    def addInheritRule(self, library_id, root_id, folder_rel_path, field_id, values, apply_to=APPLY_ALL, conn=None):
        conn = conn or self.connection()
        field = self.getField(field_id, conn=conn)
        if field is None:
            return
        folder_rel_path = canonicalRelativePath(folder_rel_path)
        apply_to = apply_to if apply_to in (APPLY_FILES, APPLY_FOLDERS, APPLY_ALL) else APPLY_ALL
        if field["type"] in SCALAR_FIELD_TYPES:
            conn.execute(
                "DELETE FROM inherit_rules WHERE root_id = ? AND folder_rel_path = ? AND field_id = ?",
                (root_id, folder_rel_path, field["id"]),
            )
        if not isinstance(values, (list, tuple)):
            values = [] if values in (None, "") else [values]
        for raw in values:
            text = "" if raw is None else str(raw).strip()
            if not text and field["type"] != FIELD_TYPE_BOOLEAN:
                continue
            if field["type"] == FIELD_TYPE_BOOLEAN:
                text = "1" if str(raw).strip().lower() in ("1", "true", "yes", "on") else "0"
            conn.execute(
                """
                INSERT OR IGNORE INTO inherit_rules(
                    library_id, root_id, folder_rel_path, field_id, value, apply_to
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (library_id, root_id, folder_rel_path, field["id"], text, apply_to),
            )
            if field["type"] in (FIELD_TYPE_CHOICE, FIELD_TYPE_MULTI) and text:
                self.addFieldOption(field["id"], text, conn=conn)
        conn.commit()
        self.rematerializeDescendants(root_id, folder_rel_path, conn=conn)

    def listInheritRules(self, root_id, folder_rel_path=None, conn=None):
        conn = conn or self.connection()
        if folder_rel_path is None:
            rows = conn.execute(
                "SELECT * FROM inherit_rules WHERE root_id = ?",
                (root_id,),
            )
        else:
            rows = conn.execute(
                "SELECT * FROM inherit_rules WHERE root_id = ? AND folder_rel_path = ?",
                (root_id, canonicalRelativePath(folder_rel_path)),
            )
        return [dict(row) for row in rows]

    def rematerializeItem(self, item_id, conn=None):
        conn = conn or self.connection()
        item = self.getItem(item_id, conn=conn)
        if item is None:
            return
        fields = {field["id"]: field for field in self.listFields(conn=conn)}
        direct = self.getDirectValues(item_id, conn=conn)
        rules = self.listInheritRules(item["root_id"], conn=conn)
        inherited = {}
        rel = item["relative_path"]
        for rule in rules:
            folder = rule["folder_rel_path"]
            if not self._isDescendant(rel, folder):
                continue
            apply_to = rule["apply_to"]
            if apply_to == APPLY_FILES and item["is_dir"]:
                continue
            if apply_to == APPLY_FOLDERS and not item["is_dir"]:
                continue
            inherited.setdefault(rule["field_id"], []).append(
                (len(folder), rule["value"])
            )

        conn.execute("DELETE FROM effective_values WHERE item_id = ?", (item_id,))
        for field_id, field in fields.items():
            direct_vals = direct.get(field_id, [])
            inherited_vals = inherited.get(field_id, [])
            rows = []
            if field["type"] in SCALAR_FIELD_TYPES:
                if direct_vals:
                    rows.append((direct_vals[0], "direct"))
                elif inherited_vals:
                    inherited_vals.sort(key=lambda pair: pair[0], reverse=True)
                    rows.append((inherited_vals[0][1], "inherited"))
            else:
                seen = set()
                for value in direct_vals:
                    key = value.lower()
                    if key in seen:
                        continue
                    seen.add(key)
                    rows.append((value, "direct"))
                for _depth, value in inherited_vals:
                    key = value.lower()
                    if key in seen:
                        continue
                    seen.add(key)
                    rows.append((value, "inherited"))
            for value, source in rows:
                conn.execute(
                    "INSERT INTO effective_values(item_id, field_id, value, source) "
                    "VALUES(?, ?, ?, ?)",
                    (item_id, field_id, value, source),
                )

    def rematerializeDescendants(self, root_id, folder_rel_path, conn=None):
        conn = conn or self.connection()
        folder_rel_path = canonicalRelativePath(folder_rel_path)
        ids = []
        for row in conn.execute(
            "SELECT id, relative_path FROM items WHERE root_id = ?",
            (root_id,),
        ):
            if self._isDescendant(row["relative_path"], folder_rel_path):
                ids.append(row["id"])
        for item_id in ids:
            self.rematerializeItem(item_id, conn=conn)
        conn.commit()

    def rematerializeRoot(self, root_id, conn=None):
        conn = conn or self.connection()
        for row in conn.execute("SELECT id FROM items WHERE root_id = ?", (root_id,)):
            self.rematerializeItem(row["id"], conn=conn)
        conn.commit()

    def rematerializeNewItem(self, item_id, conn=None):
        self.rematerializeItem(item_id, conn=conn)

    def _isDescendant(self, rel_path, folder_rel_path):
        rel = canonicalRelativePath(rel_path)
        folder = canonicalRelativePath(folder_rel_path)
        if rel == folder:
            return False
        if not folder:
            return True
        return rel.startswith(folder + "/")

    # --------------------------------------------------------
    # Search
    # --------------------------------------------------------
    def search(self, spec, conn=None):
        conn = conn or self.connection()
        spec = spec or {}
        library_ids = [value for value in (spec.get("library_ids") or []) if value]
        text = (spec.get("text") or "").strip().replace("\\", "/")
        is_dir = spec.get("is_dir")
        include_missing = spec.get("include_missing", True)
        tags_all = [tag for tag in (spec.get("tags_all") or []) if tag]
        tags_any = [tag for tag in (spec.get("tags_any") or []) if tag]
        field_filters = spec.get("field_filters") or []
        sort_by = spec.get("sort_by") or "name"
        sort_desc = bool(spec.get("sort_desc"))
        offset = max(0, int(spec.get("offset") or 0))
        limit = max(1, min(500, int(spec.get("limit") or 200)))

        where = ["1=1"]
        params = []
        if library_ids:
            placeholders = ",".join("?" * len(library_ids))
            where.append(f"items.library_id IN ({placeholders})")
            params.extend(library_ids)
        if is_dir is True:
            where.append("items.is_dir = 1")
        elif is_dir is False:
            where.append("items.is_dir = 0")
        if not include_missing:
            where.append("items.is_missing = 0")

        if text:
            tokens = [token for token in text.split() if token]
            if self._fts_enabled:
                fts = _ftsQuery(text)
                if fts:
                    where.append(
                        "items.id IN (SELECT rowid FROM items_fts WHERE items_fts MATCH ?)"
                    )
                    params.append(fts)
            else:
                for token in tokens:
                    where.append(
                        "(items.name LIKE ? ESCAPE '\\' OR items.relative_path LIKE ? ESCAPE '\\')"
                    )
                    like = "%" + _escapeLike(token) + "%"
                    params.extend([like, like])

        for tag in tags_all:
            where.append(
                "items.id IN (SELECT item_id FROM effective_values "
                "WHERE field_id = ? AND lower(value) = lower(?))"
            )
            params.extend([FIELD_TAGS, tag])
        if tags_any:
            placeholders = ",".join("?" * len(tags_any))
            where.append(
                "items.id IN (SELECT item_id FROM effective_values "
                f"WHERE field_id = ? AND lower(value) IN ({placeholders}))"
            )
            params.append(FIELD_TAGS)
            params.extend([tag.lower() for tag in tags_any])

        for filt in field_filters:
            clause, extra = self._fieldFilterClause(filt)
            if clause:
                where.append(clause)
                params.extend(extra)

        sort_map = {
            "name": "items.name COLLATE NOCASE",
            "path": "items.relative_path COLLATE NOCASE",
            "size": "items.size",
            "modified": "items.mtime_ns",
            "library": "libraries.name COLLATE NOCASE",
        }
        order = sort_map.get(sort_by, sort_map["name"])
        direction = "DESC" if sort_desc else "ASC"

        from_sql = (
            " FROM items "
            "JOIN libraries ON libraries.id = items.library_id "
            "JOIN roots ON roots.id = items.root_id "
            "WHERE " + " AND ".join(where)
        )
        count_row = conn.execute("SELECT COUNT(*) AS n" + from_sql, params).fetchone()
        total = int(count_row["n"] if count_row else 0)
        rows = conn.execute(
            "SELECT items.*, libraries.name AS library_name, roots.name AS root_name, "
            "roots.path AS root_path, roots.is_available AS root_available, "
            "roots.status AS root_status "
            + from_sql
            + f" ORDER BY {order} {direction}, items.id ASC LIMIT ? OFFSET ?",
            params + [limit, offset],
        ).fetchall()

        results = []
        item_ids = []
        for row in rows:
            item_ids.append(row["id"])
            rel = row["relative_path"]
            root_path = row["root_path"] or ""
            resolved = root_path
            if rel and root_path:
                resolved = os.path.normpath(os.path.join(root_path, rel.replace("/", os.sep)))
            results.append({
                "item_id": row["id"],
                "library_id": row["library_id"],
                "library_name": row["library_name"],
                "root_id": row["root_id"],
                "root_name": row["root_name"],
                "relative_path": rel,
                "name": row["name"],
                "is_dir": bool(row["is_dir"]),
                "size": int(row["size"] or 0),
                "mtime_ns": int(row["mtime_ns"] or 0),
                "is_missing": bool(row["is_missing"]),
                "resolved_path": resolved,
                "is_available": bool(row["root_available"]) and not bool(row["is_missing"]),
                "root_status": row["root_status"] or "",
                "tags": [],
                "notes": "",
                "values": {},
            })

        if item_ids:
            placeholders = ",".join("?" * len(item_ids))
            by_id = {item["item_id"]: item for item in results}
            for row in conn.execute(
                f"SELECT item_id, field_id, value FROM effective_values "
                f"WHERE item_id IN ({placeholders})",
                item_ids,
            ):
                item = by_id.get(row["item_id"])
                if item is None:
                    continue
                item["values"].setdefault(row["field_id"], []).append(row["value"])
                if row["field_id"] == FIELD_TAGS:
                    item["tags"].append(row["value"])
                elif row["field_id"] == FIELD_NOTES:
                    item["notes"] = row["value"]

        return {"rows": results, "total": total}

    def _fieldFilterClause(self, filt):
        field_id = (filt or {}).get("field_id") or ""
        op = ((filt or {}).get("op") or "contains").lower()
        value = filt.get("value")
        if not field_id:
            return "", []
        if op == "exists":
            return (
                "items.id IN (SELECT item_id FROM effective_values WHERE field_id = ?)",
                [field_id],
            )
        if op == "not_exists":
            return (
                "items.id NOT IN (SELECT item_id FROM effective_values WHERE field_id = ?)",
                [field_id],
            )
        if op == "is_true":
            return (
                "items.id IN (SELECT item_id FROM effective_values "
                "WHERE field_id = ? AND value = '1')",
                [field_id],
            )
        if op == "is_false":
            return (
                "items.id IN (SELECT item_id FROM effective_values "
                "WHERE field_id = ? AND value = '0')",
                [field_id],
            )
        if value is None or value == "":
            return "", []
        if op == "equals":
            return (
                "items.id IN (SELECT item_id FROM effective_values "
                "WHERE field_id = ? AND lower(value) = lower(?))",
                [field_id, str(value)],
            )
        if op == "contains":
            return (
                "items.id IN (SELECT item_id FROM effective_values "
                "WHERE field_id = ? AND value LIKE ? ESCAPE '\\')",
                [field_id, "%" + _escapeLike(str(value)) + "%"],
            )
        if op in ("gt", "gte", "lt", "lte"):
            sql_op = { "gt": ">", "gte": ">=", "lt": "<", "lte": "<=" }[op]
            return (
                "items.id IN (SELECT item_id FROM effective_values "
                f"WHERE field_id = ? AND CAST(value AS REAL) {sql_op} ?)",
                [field_id, float(value)],
            )
        return "", []

    def explainSearch(self, spec, conn=None):
        conn = conn or self.connection()
        query = "SELECT * FROM items WHERE items.name LIKE '%x%'"
        try:
            return conn.execute("EXPLAIN QUERY PLAN " + query).fetchall()
        except sqlite3.Error:
            return []

    # --------------------------------------------------------
    # Snapshots / legacy import
    # --------------------------------------------------------
    def exportLogicalSnapshot(self, conn=None):
        conn = conn or self.connection()
        libraries = []
        for library in conn.execute("SELECT * FROM libraries ORDER BY name COLLATE NOCASE"):
            lib = self._libraryFromRow(library)
            lib["roots"] = []
            for root_row in conn.execute(
                "SELECT * FROM roots WHERE library_id = ?",
                (library["id"],),
            ):
                root = self._rootFromRow(root_row)
                lib["roots"].append(root)
            libraries.append(lib)

        fields = []
        for field in self.listFields(conn=conn):
            fields.append({
                "id": field["id"],
                "key": field["key"],
                "name": field["name"],
                "type": field["type"],
                "is_builtin": field["is_builtin"],
                "options": field.get("options") or [],
            })

        metadata_items = []
        for row in conn.execute(
            "SELECT DISTINCT items.id, items.library_id, items.root_id, items.relative_path, "
            "items.name, items.is_dir "
            "FROM items JOIN item_values ON item_values.item_id = items.id"
        ):
            values = self.getDirectValues(row["id"], conn=conn)
            metadata_items.append({
                "library_id": row["library_id"],
                "root_id": row["root_id"],
                "relative_path": row["relative_path"],
                "name": row["name"],
                "is_dir": bool(row["is_dir"]),
                "values": values,
            })

        rules = [dict(row) for row in conn.execute("SELECT * FROM inherit_rules")]
        return {
            "format": "total-commander-clone-library-catalog",
            "format_version": 1,
            "libraries": libraries,
            "fields": fields,
            "metadata_items": metadata_items,
            "inherit_rules": rules,
        }

    def importLogicalSnapshot(self, snapshot, replace=True, conn=None):
        conn = conn or self.connection()
        if not isinstance(snapshot, dict):
            return False
        if replace:
            conn.execute("DELETE FROM libraries")
            conn.execute("DELETE FROM fields")
            self._ensureBuiltinFields(conn)

        id_remap_fields = {}
        for field in snapshot.get("fields") or []:
            if field.get("is_builtin") or field.get("id") in (FIELD_TAGS, FIELD_NOTES):
                existing = self.getField(field.get("id") or field.get("key"), conn=conn)
                if existing:
                    id_remap_fields[field.get("id", existing["id"])] = existing["id"]
                continue
            created = self.createField(
                field.get("name", ""),
                field.get("type", FIELD_TYPE_TEXT),
                key=field.get("key", ""),
                options=field.get("options") or [],
                conn=conn,
            )
            if created:
                id_remap_fields[field.get("id", created["id"])] = created["id"]

        for library in snapshot.get("libraries") or []:
            created = self.createLibrary(
                library.get("name", ""),
                library.get("description", ""),
                library_id=library.get("id", ""),
                conn=conn,
            )
            if created is None:
                continue
            for root in library.get("roots") or []:
                self.addRoot(
                    created["id"],
                    root.get("path", "") or root.get("last_seen_path", ""),
                    name=root.get("name", ""),
                    root_id=root.get("id", ""),
                    include_files=root.get("include_files", True),
                    include_folders=root.get("include_folders", True),
                    include_hidden=root.get("include_hidden", False),
                    include_globs=root.get("include_globs"),
                    exclude_globs=root.get("exclude_globs"),
                    conn=conn,
                )
                path = normalizePath(root.get("path", ""))
                available = bool(path and os.path.isdir(path))
                self.setRootAvailability(
                    root.get("id"),
                    available,
                    path,
                    ROOT_STATUS_ONLINE if available else ROOT_STATUS_OFFLINE,
                    conn=conn,
                )

        for item in snapshot.get("metadata_items") or []:
            item_id, _ = self.upsertIndexedItem(
                item.get("library_id"),
                item.get("root_id"),
                {
                    "relative_path": item.get("relative_path", ""),
                    "name": item.get("name", ""),
                    "is_dir": item.get("is_dir", True),
                    "size": -1 if item.get("is_dir", True) else 0,
                    "mtime_ns": 0,
                    "native_id": "",
                },
                existing=self.getItemByRel(item.get("root_id"), item.get("relative_path", ""), conn=conn),
                conn=conn,
            )
            if isinstance(item_id, dict):
                continue
            values = item.get("values") or {}
            mapped = {}
            for field_id, field_values in values.items():
                mapped[id_remap_fields.get(field_id, field_id)] = field_values
            self.setDirectValuesMap(item_id, mapped, conn=conn)

        for rule in snapshot.get("inherit_rules") or []:
            field_id = id_remap_fields.get(rule.get("field_id"), rule.get("field_id"))
            self.addInheritRule(
                rule.get("library_id"),
                rule.get("root_id"),
                rule.get("folder_rel_path", ""),
                field_id,
                [rule.get("value")],
                apply_to=rule.get("apply_to", APPLY_ALL),
                conn=conn,
            )
        conn.commit()
        return True

    def importLegacyState(self, libraries, folder_tags, conn=None):
        conn = conn or self.connection()
        libraries = libraries or []
        folder_tags = folder_tags or {}
        if not libraries and not folder_tags:
            return False
        for library in libraries:
            created = self.createLibrary(
                library.get("name", ""),
                library.get("description", ""),
                library_id=library.get("id", ""),
                conn=conn,
            )
            if created is None:
                continue
            for root in library.get("roots") or []:
                path = root.get("path") or root.get("last_seen_path") or ""
                added = self.addRoot(
                    created["id"],
                    path,
                    name=root.get("name", ""),
                    root_id=root.get("id", ""),
                    conn=conn,
                )
                if added is None:
                    continue
                available = bool(path and os.path.isdir(normalizePath(path)))
                self.setRootAvailability(
                    added["id"],
                    available,
                    normalizePath(path),
                    ROOT_STATUS_ONLINE if available else ROOT_STATUS_OFFLINE,
                    conn=conn,
                )

        for record in folder_tags.values():
            library_id = record.get("library_id", "")
            root_id = record.get("root_id", "")
            rel = canonicalRelativePath(record.get("relative_path", ""))
            name = os.path.basename(rel) if rel else (record.get("display_name") or "Folder")
            existing = self.getItemByRel(root_id, rel, conn=conn)
            item_id, _ = self.upsertIndexedItem(
                library_id,
                root_id,
                {
                    "relative_path": rel,
                    "name": name,
                    "is_dir": True,
                    "size": -1,
                    "mtime_ns": 0,
                    "native_id": "",
                },
                existing=existing,
                conn=conn,
            )
            values = {}
            if record.get("tags"):
                values[FIELD_TAGS] = record.get("tags")
            if (record.get("note") or "").strip():
                values[FIELD_NOTES] = [(record.get("note") or "").strip()]
            if values:
                self.setDirectValuesMap(item_id, values, conn=conn)
        conn.commit()
        self._setMeta(conn, "legacy_imported", "1")
        conn.commit()
        return True
