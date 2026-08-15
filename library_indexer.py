"""
Library root indexing: incremental checks, rebuilds, and rename detection.
Runs without Qt so unit tests can drive it directly.
"""

import os

from filesystem_scanner import walkFilesystem
from library_catalog import (
    ROOT_STATUS_ERROR,
    ROOT_STATUS_ONLINE,
    LibraryCatalog,
)


# ------------------------------------------------------------
# Function: indexRoot
# Purpose: Walk one library root and upsert catalog items.
#          Rebuild recreates derived search data but keeps
#          user properties attached to stable item rows.
# ------------------------------------------------------------
def indexRoot(db_path, root_id, mode="incremental", cancel_check=None, progress_cb=None):
    catalog = LibraryCatalog(db_path)
    conn = catalog.connect(primary=False)
    catalog._fts_enabled = catalog._ensureFts(conn)
    try:
        return _indexRootWithCatalog(
            catalog,
            conn,
            root_id,
            mode=mode,
            cancel_check=cancel_check,
            progress_cb=progress_cb,
        )
    finally:
        conn.close()


# ------------------------------------------------------------
# Internal: index using an open catalog/connection
# ------------------------------------------------------------
def _indexRootWithCatalog(catalog, conn, root_id, mode="incremental", cancel_check=None, progress_cb=None):
    root = catalog.getRoot(root_id, conn=conn)
    if root is None:
        return {"ok": False, "error": "Root not found.", "root_id": root_id}

    root_path = root.get("path") or ""
    if not root_path or not os.path.isdir(root_path):
        catalog.updateRootScanStats(
            root_id,
            {
                "last_scan_mode": mode,
                "last_error": "Root folder is offline or missing.",
                "status": "offline",
                "is_available": False,
                "item_count": root.get("item_count", 0),
                "added_count": 0,
                "changed_count": 0,
                "missing_count": root.get("missing_count", 0),
            },
            conn=conn,
        )
        return {
            "ok": False,
            "error": "Root folder is offline or missing.",
            "root_id": root_id,
            "offline": True,
        }

    existing = catalog.loadRootItemMap(root_id, conn=conn)
    native_to_rel = {}
    for rel, item in existing.items():
        native_id = item.get("native_id") or ""
        if native_id:
            native_to_rel.setdefault(native_id, []).append(rel)

    seen = set()
    added = 0
    changed = 0
    unchanged = 0
    new_by_native = {}
    pending_materialize = []
    batch = 0

    def cancelled():
        return bool(cancel_check and cancel_check())

    for entry in walkFilesystem(
        root_path,
        show_hidden=root.get("include_hidden", False),
        collect_dirs=root.get("include_folders", True),
        collect_files=root.get("include_files", True),
        include_globs=root.get("include_globs"),
        exclude_globs=root.get("exclude_globs"),
        include_root=True,
        cancel_check=cancelled,
        progress_cb=progress_cb,
    ):
        if cancelled():
            return {"ok": False, "cancelled": True, "root_id": root_id}

        rel = entry["relative_path"]
        seen.add(rel)
        current = existing.get(rel)
        item_id, status = catalog.upsertIndexedItem(
            root["library_id"],
            root_id,
            entry,
            existing=current,
            conn=conn,
        )
        if status == "added":
            added += 1
            native_id = entry.get("native_id") or ""
            if native_id:
                new_by_native.setdefault(native_id, []).append(
                    {"id": item_id, "entry": entry, "rel": rel}
                )
            pending_materialize.append(item_id)
        elif status == "changed":
            changed += 1
        else:
            unchanged += 1
        batch += 1
        if batch >= 1000:
            conn.commit()
            batch = 0

    if cancelled():
        conn.commit()
        return {"ok": False, "cancelled": True, "root_id": root_id}

    renamed = 0
    for native_id, newcomers in new_by_native.items():
        old_rels = native_to_rel.get(native_id) or []
        missing_old = [
            existing[rel] for rel in old_rels
            if rel not in seen
        ]
        if len(missing_old) == 1 and len(newcomers) == 1:
            keep = missing_old[0]
            drop = newcomers[0]
            catalog.rebindItemToPath(
                keep["id"],
                drop["id"],
                drop["rel"],
                drop["entry"].get("name", ""),
                drop["entry"],
                conn=conn,
            )
            if drop["id"] in pending_materialize:
                pending_materialize.remove(drop["id"])
            seen.add(drop["rel"])
            added = max(0, added - 1)
            renamed += 1

    missing_ids = catalog.markMissingExcept(root_id, seen, conn=conn)
    if mode == "rebuild":
        catalog.rematerializeRoot(root_id, conn=conn)
        catalog.rebuildFts(conn)
    else:
        for item_id in pending_materialize:
            catalog.rematerializeNewItem(item_id, conn=conn)

    item_count_row = conn.execute(
        "SELECT COUNT(*) AS n FROM items WHERE root_id = ? AND is_missing = 0",
        (root_id,),
    ).fetchone()
    item_count = int(item_count_row["n"] if item_count_row else 0)
    summary = {
        "ok": True,
        "root_id": root_id,
        "mode": mode,
        "added_count": added,
        "changed_count": changed,
        "unchanged_count": unchanged,
        "missing_count": len(missing_ids),
        "renamed_count": renamed,
        "item_count": item_count,
        "error": "",
    }
    catalog.updateRootScanStats(
        root_id,
        {
            "last_scan_mode": mode,
            "last_error": "",
            "status": ROOT_STATUS_ONLINE,
            "is_available": True,
            "item_count": item_count,
            "added_count": added,
            "changed_count": changed,
            "missing_count": len(missing_ids),
        },
        conn=conn,
    )
    conn.commit()
    return summary
