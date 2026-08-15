"""Unit tests for the SQLite library catalog, indexing, and search."""

import os
import tempfile
import unittest

from filesystem_scanner import shouldIncludePath, walkFilesystem
from library_catalog import (
    APPLY_FILES,
    FIELD_NOTES,
    FIELD_TAGS,
    FIELD_TYPE_NUMBER,
    ROOT_STATUS_VERIFY,
    LibraryCatalog,
)
from library_indexer import indexRoot
from library_paths import writeLibraryMarker


# ------------------------------------------------------------
# Class: LibraryCatalogTests
# ------------------------------------------------------------
class LibraryCatalogTests(unittest.TestCase):

    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.dir = self._temp.name
        self.db_path = os.path.join(self.dir, "library_catalog.sqlite3")
        self.catalog = LibraryCatalog(self.db_path)
        self.catalog.open()

    def tearDown(self):
        self.catalog.close()
        self._temp.cleanup()

    def _makeTree(self, name="root"):
        root = os.path.join(self.dir, name)
        os.makedirs(os.path.join(root, "docs"), exist_ok=True)
        with open(os.path.join(root, "readme.txt"), "w", encoding="utf-8") as handle:
            handle.write("hello")
        with open(os.path.join(root, "docs", "spec.pdf"), "w", encoding="utf-8") as handle:
            handle.write("pdf")
        with open(os.path.join(root, "skip.tmp"), "w", encoding="utf-8") as handle:
            handle.write("tmp")
        return root

    def test_legacy_migration_and_tag_search(self):
        root = self._makeTree()
        library_id = "lib-1"
        root_id = "root-1"
        libraries = [{
            "id": library_id,
            "name": "Work",
            "description": "",
            "roots": [{
                "id": root_id,
                "name": "USB",
                "path": root,
                "last_seen_path": root,
                "is_available": True,
            }],
        }]
        folder_tags = {
            f"{library_id}:{root_id}:docs": {
                "library_id": library_id,
                "root_id": root_id,
                "relative_path": "docs",
                "tags": ["customer:Acme"],
                "note": "Hatchery",
            }
        }
        self.assertTrue(self.catalog.importLegacyState(libraries, folder_tags))
        self.assertEqual(self.catalog.libraryCount(), 1)
        result = self.catalog.search({"tags_all": ["customer:Acme"]})
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["rows"][0]["notes"], "Hatchery")

    def test_incremental_index_and_rebuild_keeps_metadata(self):
        root = self._makeTree()
        library = self.catalog.createLibrary("Media")
        saved = self.catalog.addRoot(library["id"], root, name="Disk")
        summary = indexRoot(self.db_path, saved["id"], mode="incremental")
        self.assertTrue(summary["ok"])
        self.assertGreaterEqual(summary["item_count"], 4)

        item = self.catalog.getItemByRel(saved["id"], "readme.txt")
        self.catalog.setDirectFieldValues(item["id"], FIELD_TAGS, ["keep-me"])

        rebuild = indexRoot(self.db_path, saved["id"], mode="rebuild")
        self.assertTrue(rebuild["ok"])
        item = self.catalog.getItemByRel(saved["id"], "readme.txt")
        values = self.catalog.getEffectiveValues(item["id"])
        self.assertIn("keep-me", values.get(FIELD_TAGS, []))

    def test_exclude_globs_and_field_query(self):
        root = self._makeTree()
        library = self.catalog.createLibrary("Docs")
        saved = self.catalog.addRoot(
            library["id"],
            root,
            exclude_globs=["*.tmp"],
        )
        indexRoot(self.db_path, saved["id"], mode="incremental")
        tmp = self.catalog.getItemByRel(saved["id"], "skip.tmp")
        self.assertIsNone(tmp)
        pdf = self.catalog.getItemByRel(saved["id"], "docs/spec.pdf")
        year = self.catalog.createField("Year", FIELD_TYPE_NUMBER)
        self.catalog.setDirectFieldValues(pdf["id"], year["id"], ["2024"])
        result = self.catalog.search({
            "field_filters": [{"field_id": year["id"], "op": "gte", "value": 2020}],
        })
        names = [row["name"] for row in result["rows"]]
        self.assertIn("spec.pdf", names)

    def test_inherited_tags_apply_to_descendants(self):
        root = self._makeTree()
        library = self.catalog.createLibrary("Inherit")
        saved = self.catalog.addRoot(library["id"], root)
        indexRoot(self.db_path, saved["id"], mode="incremental")
        self.catalog.addInheritRule(
            library["id"],
            saved["id"],
            "docs",
            FIELD_TAGS,
            ["project:Alpha"],
            apply_to=APPLY_FILES,
        )
        pdf = self.catalog.getItemByRel(saved["id"], "docs/spec.pdf")
        values = self.catalog.getEffectiveValues(pdf["id"])
        self.assertIn("project:Alpha", values.get(FIELD_TAGS, []))
        folder = self.catalog.getItemByRel(saved["id"], "docs")
        folder_values = self.catalog.getEffectiveValues(folder["id"])
        self.assertNotIn("project:Alpha", folder_values.get(FIELD_TAGS, []))

    def test_root_rebind_rejects_conflicting_marker(self):
        first = self._makeTree("one")
        second = self._makeTree("two")
        library = self.catalog.createLibrary("Portable")
        other = self.catalog.createLibrary("Other")
        root_a = self.catalog.addRoot(library["id"], first, name="A")
        root_b = self.catalog.addRoot(other["id"], second, name="B")
        writeLibraryMarker(first, library, root_a)
        writeLibraryMarker(second, other, root_b)
        result = self.catalog.rebindRoot(root_a["id"], second, claim=False)
        self.assertFalse(result["ok"])
        self.assertIn("different", result["error"].lower())

    def test_snapshot_round_trip_omits_file_rows(self):
        root = self._makeTree()
        library = self.catalog.createLibrary("Snap")
        saved = self.catalog.addRoot(library["id"], root)
        indexRoot(self.db_path, saved["id"], mode="incremental")
        item = self.catalog.getItemByRel(saved["id"], "readme.txt")
        self.catalog.setDirectFieldValues(item["id"], FIELD_NOTES, ["portable note"])
        snapshot = self.catalog.exportLogicalSnapshot()
        self.assertTrue(snapshot["metadata_items"])
        self.assertLess(len(snapshot["metadata_items"]), snapshot["libraries"][0]["roots"][0]["item_count"])

        other_path = os.path.join(self.dir, "other.sqlite3")
        other = LibraryCatalog(other_path)
        other.open()
        other.importLogicalSnapshot(snapshot, replace=True)
        restored = other.getItemByRel(saved["id"], "readme.txt")
        self.assertIsNotNone(restored)
        notes = other.getEffectiveValues(restored["id"]).get(FIELD_NOTES, [])
        self.assertEqual(notes, ["portable note"])
        other.close()

    def test_offline_search_still_returns_rows(self):
        root = self._makeTree()
        library = self.catalog.createLibrary("Offline")
        saved = self.catalog.addRoot(library["id"], root)
        indexRoot(self.db_path, saved["id"], mode="incremental")
        self.catalog.setRootAvailability(saved["id"], False, saved["path"], "offline")
        result = self.catalog.search({"text": "readme"})
        self.assertGreaterEqual(result["total"], 1)
        self.assertFalse(result["rows"][0]["is_available"])

    def test_include_glob_helper(self):
        self.assertTrue(shouldIncludePath("docs/spec.pdf", "spec.pdf", ["*.pdf"], []))
        self.assertFalse(shouldIncludePath("skip.tmp", "skip.tmp", [], ["*.tmp"]))

    def test_walk_include_root(self):
        root = self._makeTree()
        entries = list(walkFilesystem(root, include_root=True, collect_files=True, collect_dirs=True))
        rels = {item["relative_path"] for item in entries}
        self.assertIn("", rels)
        self.assertIn("docs", rels)
        self.assertIn("readme.txt", rels)


if __name__ == "__main__":
    unittest.main()
