"""
Total Commander Clone - Library Manager
Facade over the SQLite catalog: portable roots, indexing requests,
property assignment, and folder context resolution.
"""

import os

from filesystem_scanner import canonicalRelativePath, relativeToRoot
from library_catalog import (
    APPLY_ALL,
    APPLY_FILES,
    APPLY_FOLDERS,
    FIELD_NOTES,
    FIELD_TAGS,
    ROOT_STATUS_OFFLINE,
    ROOT_STATUS_ONLINE,
    ROOT_STATUS_VERIFY,
    LibraryCatalog,
)
from library_paths import (
    LIBRARY_MARKER_FILENAME,
    LIBRARY_MARKER_VERSION,
    buildFolderKey,
    candidateScanBases,
    findMarkerDirectories,
    isPathInsideRoot,
    normalizePath,
    parseTagCategory,
    readLibraryMarker,
    removeLibraryMarker,
    setHiddenFile,
    writeLibraryMarker,
)


# Re-export helpers used by existing UI modules.
__all__ = [
    "LibraryManager",
    "LIBRARY_MARKER_FILENAME",
    "LIBRARY_MARKER_VERSION",
    "buildFolderKey",
    "isPathInsideRoot",
    "normalizePath",
    "parseTagCategory",
    "readLibraryMarker",
    "setHiddenFile",
]


# ------------------------------------------------------------
# Class: LibraryManager
# Purpose: Encapsulates catalog access and portable root discovery
#          so UI code stays lightweight.
# ------------------------------------------------------------
class LibraryManager:

    # --------------------------------------------------------
    # Method: __init__
    # --------------------------------------------------------
    def __init__(self, settings_manager):
        self._settings = settings_manager
        catalog = getattr(settings_manager, "libraryCatalog", None)
        if callable(catalog):
            self._catalog = catalog()
        else:
            self._catalog = getattr(settings_manager, "_catalog", None)
        if self._catalog is None:
            config_dir = getattr(settings_manager, "configDir", lambda: "")()
            self._catalog = LibraryCatalog(
                os.path.join(config_dir or ".", "library_catalog.sqlite3")
            )
            self._catalog.open()

    def catalog(self):
        return self._catalog

    def dbPath(self):
        return self._catalog.db_path

    # --------------------------------------------------------
    # Libraries / roots
    # --------------------------------------------------------
    def getLibraries(self):
        return self._catalog.listLibraries()

    def getLibrary(self, library_id):
        return self._catalog.getLibrary(library_id)

    def createLibrary(self, name, description=""):
        return self._catalog.createLibrary(name, description)

    def renameLibrary(self, library_id, name, description=None):
        return self._catalog.updateLibrary(library_id, name=name, description=description)

    def deleteLibrary(self, library_id):
        library = self._catalog.getLibrary(library_id)
        if library is None:
            return
        for root in library.get("roots", []):
            if root.get("is_available") and root.get("path"):
                removeLibraryMarker(root.get("path"))
        self._catalog.deleteLibrary(library_id)

    def deleteRoot(self, root_id):
        root = self._catalog.getRoot(root_id)
        if root is None:
            return
        if root.get("is_available") and root.get("path"):
            removeLibraryMarker(root.get("path"))
        self._catalog.deleteRoot(root_id)

    def updateRootSettings(self, root_id, **fields):
        return self._catalog.updateRoot(root_id, **fields)

    def rebindRoot(self, root_id, new_path, claim=False):
        return self._catalog.rebindRoot(root_id, new_path, claim=claim)

    def getSavedFilters(self):
        return self._settings.getSavedLibraryFilters()

    # --------------------------------------------------------
    # Method: registerLibraryRoot
    # Purpose: Create or extend a library with a root folder and
    #          write the hidden marker used for drive discovery.
    # --------------------------------------------------------
    def registerLibraryRoot(self, library_name, root_path, root_name="", description=""):
        library_name = (library_name or "").strip()
        root_path = normalizePath(root_path)
        root_name = (root_name or "").strip()
        if not library_name or not root_path or not os.path.isdir(root_path):
            return None

        library = self._catalog.createLibrary(library_name, description or "")
        if library is None:
            return None
        root = self._catalog.addRoot(library["id"], root_path, name=root_name)
        if root is None:
            return None
        writeLibraryMarker(root_path, library, root)
        return {"library": self._catalog.getLibrary(library["id"]), "root": root}

    # --------------------------------------------------------
    # Method: refreshLibraries
    # Purpose: Reconnect saved roots and flag relocated ones for
    #          verification instead of silently assuming the index
    #          still matches.
    # --------------------------------------------------------
    def refreshLibraries(self):
        libraries = self.getLibraries()
        discovered = self._discoverMarkers(libraries)
        verification_needed = []

        for library in libraries:
            for root in library.get("roots", []):
                key = (library.get("id", ""), root.get("id", ""))
                resolved_path = discovered.get(key, "")
                previous = normalizePath(root.get("path", ""))
                if resolved_path:
                    relocated = previous and previous != normalizePath(resolved_path)
                    had_index = int(root.get("item_count") or 0) > 0
                    status = ROOT_STATUS_VERIFY if relocated and had_index else ROOT_STATUS_ONLINE
                    updated = self._catalog.setRootAvailability(
                        root["id"], True, resolved_path, status
                    )
                    if status == ROOT_STATUS_VERIFY:
                        verification_needed.append(updated)
                else:
                    self._catalog.setRootAvailability(root["id"], False, "", ROOT_STATUS_OFFLINE)

        return {
            "libraries": self.getLibraries(),
            "verification_needed": verification_needed,
        }

    def rootsNeedingIndex(self):
        ready = []
        for library in self.getLibraries():
            for root in library.get("roots", []):
                if not root.get("is_available"):
                    continue
                if root.get("status") == ROOT_STATUS_VERIFY:
                    continue
                if not root.get("last_scan_at") or int(root.get("item_count") or 0) == 0:
                    ready.append(root)
                else:
                    ready.append(root)
        return ready

    def onlineRootsForQuietCheck(self):
        roots = []
        for library in self.getLibraries():
            for root in library.get("roots", []):
                if (
                    root.get("is_available")
                    and root.get("status") == ROOT_STATUS_ONLINE
                    and root.get("path")
                    and os.path.isdir(root.get("path"))
                ):
                    roots.append(root)
        return roots

    # --------------------------------------------------------
    # Context / properties
    # --------------------------------------------------------
    def resolveFolderContext(self, folder_path):
        return self.resolvePathContext(folder_path)

    def resolvePathContext(self, path):
        context = self._catalog.resolveAbsoluteContext(path)
        if context is None:
            return None
        root = context["root"]
        library = self._catalog.getLibrary(context["library_id"])
        rel = context["relative_path"]
        return {
            "library": library,
            "root": root,
            "relative_path": rel,
            "folder_key": buildFolderKey(library["id"], root["id"], rel),
            "matched_root_length": context.get("matched_len", 0),
        }

    def ensureItemForPath(self, path):
        return self._catalog.ensureItemForPath(path)

    def getItemRecordForPath(self, path):
        context = self.resolvePathContext(path)
        if context is None:
            return None
        item = self._catalog.getItemByRel(context["root"]["id"], context["relative_path"])
        if item is None:
            return None
        values = self._catalog.getEffectiveValues(item["id"])
        item["tags"] = values.get(FIELD_TAGS, [])
        notes = values.get(FIELD_NOTES, [])
        item["note"] = notes[0] if notes else ""
        item["values"] = values
        item["resolved_path"] = path
        return item

    def getFolderRecordForPath(self, folder_path):
        return self.getItemRecordForPath(folder_path)

    def assignTagsToFolder(self, folder_path, tags, note=""):
        item = self.ensureItemForPath(folder_path)
        if item is None:
            return None
        self._catalog.setDirectValuesMap(
            item["id"],
            {
                FIELD_TAGS: tags or [],
                FIELD_NOTES: [note] if (note or "").strip() else [],
            },
        )
        return self.getItemRecordForPath(folder_path)

    def assignProperties(self, paths, values_map, scope="selected", inherit=False, inherit_apply_to=APPLY_ALL):
        paths = [path for path in (paths or []) if path]
        if not paths:
            return {"updated": 0}

        updated = 0
        if scope == "selected":
            targets = list(paths)
        else:
            folder = paths[0]
            if not os.path.isdir(folder):
                targets = [folder]
            elif scope == "folder":
                targets = [folder]
            elif scope == "folder_files":
                targets = [
                    os.path.join(folder, name)
                    for name in os.listdir(folder)
                    if os.path.isfile(os.path.join(folder, name))
                ]
            else:
                targets = []
                for current, _dirs, files in os.walk(folder):
                    if scope in ("descendants", "descendant_all"):
                        if current != folder:
                            targets.append(current)
                    for name in files:
                        targets.append(os.path.join(current, name))
                    if scope == "descendant_folders" and current != folder:
                        pass

        for path in targets:
            item = self.ensureItemForPath(path)
            if item is None:
                continue
            self._catalog.setDirectValuesMap(item["id"], values_map)
            updated += 1

        if inherit:
            folder = paths[0]
            context = self.resolvePathContext(folder)
            if context is not None and os.path.isdir(folder):
                for field_id, values in (values_map or {}).items():
                    self._catalog.addInheritRule(
                        context["library"]["id"],
                        context["root"]["id"],
                        context["relative_path"],
                        field_id,
                        values,
                        apply_to=inherit_apply_to,
                    )
        return {"updated": updated}

    def getAvailableTags(self, library_id=""):
        del library_id
        return self._catalog.listUsedValues(FIELD_TAGS)

    def listFields(self):
        return self._catalog.listFields()

    def createField(self, name, field_type, options=None):
        return self._catalog.createField(name, field_type, options=options)

    def deleteField(self, field_id):
        return self._catalog.deleteField(field_id)

    def search(self, spec):
        return self._catalog.search(spec)

    def notifyPathRenamed(self, old_path, new_path):
        self._catalog.notifyPathRenamed(old_path, new_path)

    def notifyPathDeleted(self, path):
        self._catalog.notifyPathDeleted(path)

    def notifyPathCopied(self, path):
        self._catalog.notifyPathCopied(path)

    def findFirstAvailableRootPath(self, library_id):
        library = self.getLibrary(library_id)
        if library is None:
            return ""
        for root in library.get("roots", []):
            root_path = normalizePath(root.get("path", ""))
            if root_path and os.path.isdir(root_path):
                return root_path
        return ""

    def getTaggedFolders(self, library_id="", selected_tags=None):
        spec = {
            "library_ids": [library_id] if library_id else [],
            "tags_all": selected_tags or [],
            "is_dir": True,
            "include_missing": True,
            "limit": 500,
            "offset": 0,
        }
        result = self.search(spec)
        rows = []
        for item in result.get("rows", []):
            rows.append({
                "display_name": item.get("name") or "Folder",
                "library_id": item.get("library_id", ""),
                "library_name": item.get("library_name", ""),
                "root_id": item.get("root_id", ""),
                "root_name": item.get("root_name", ""),
                "relative_path": item.get("relative_path", ""),
                "resolved_path": item.get("resolved_path", ""),
                "is_available": item.get("is_available", False),
                "tags": item.get("tags", []),
                "note": item.get("notes", ""),
            })
        return rows

    # --------------------------------------------------------
    # Internal: discover roots by saved path and marker scans
    # --------------------------------------------------------
    def _discoverMarkers(self, libraries):
        discovered = {}
        missing_keys = set()

        for library in libraries:
            for root in library.get("roots", []):
                key = (library.get("id", ""), root.get("id", ""))
                root_path = normalizePath(root.get("path", ""))
                marker = readLibraryMarker(root_path) if root_path and os.path.isdir(root_path) else None
                if marker and marker.get("library_id") == key[0] and marker.get("root_id") == key[1]:
                    discovered[key] = root_path
                elif root_path and os.path.isdir(root_path) and not marker:
                    discovered[key] = root_path
                else:
                    missing_keys.add(key)

        if not missing_keys:
            return discovered

        for base_path in candidateScanBases():
            for candidate_path, marker in findMarkerDirectories(base_path):
                key = (marker.get("library_id", ""), marker.get("root_id", ""))
                if key in missing_keys:
                    discovered[key] = normalizePath(candidate_path)
                    missing_keys.remove(key)
                if not missing_keys:
                    return discovered
        return discovered
