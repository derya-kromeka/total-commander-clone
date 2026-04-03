"""
Total Commander Clone - Settings Manager
Handles loading and saving of settings.json and state.json.
Auto-creates config files with sensible defaults on first run.
"""

import json
import os


# ------------------------------------------------------------
# Default Settings
# These are written to settings.json on first run.
# ------------------------------------------------------------
DEFAULT_SETTINGS = {
    "show_hidden_files": False,
    "confirm_delete": True,
    "theme_mode": "dark",
    "default_left_path": "",
    "default_right_path": "",
    "column_widths": {
        "name": 300,
        "size": 100,
        "type": 120,
        "date_modified": 160,
    },
    "window_geometry": {
        "x": 100,
        "y": 100,
        "width": 1400,
        "height": 800,
    },
    "sort_column": 0,
    "sort_order": "ascending",
    "font_size": 10,
}


# ------------------------------------------------------------
# Default State
# These are written to state.json on first run.
# ------------------------------------------------------------
DEFAULT_STATE = {
    "left_panel": {
        "current_path": "",
        "history": [],
    },
    "right_panel": {
        "current_path": "",
        "history": [],
    },
    "bookmarks": [],
    "recent_paths": [],
    "libraries": [],
    "folder_tags": {},
    "saved_library_filters": [],
    "sidebar_state": {
        "current_tab": "bookmarks",
    },
}


# ------------------------------------------------------------
# Class: SettingsManager
# Purpose: Provides a unified interface for reading and writing
#          application settings and panel state from/to JSON.
#          Handles file I/O, defaults, and first-run creation.
# ------------------------------------------------------------
class SettingsManager:

    SETTINGS_FILENAME = "settings.json"
    STATE_FILENAME = "state.json"
    MAX_RECENT_PATHS = 30

    # --------------------------------------------------------
    # Method: __init__
    # Purpose: Initializes the manager, resolves file paths,
    #          and loads (or creates) both JSON config files.
    # Input:  base_path (str) - Directory where config files live.
    # --------------------------------------------------------
    def __init__(self, base_path):
        self._base_path = base_path
        self._settings_path = os.path.join(base_path, self.SETTINGS_FILENAME)
        self._state_path = os.path.join(base_path, self.STATE_FILENAME)

        self._settings = self._loadOrCreate(self._settings_path, DEFAULT_SETTINGS)
        self._state = self._loadOrCreate(self._state_path, DEFAULT_STATE)

    # --------------------------------------------------------
    # Method: _loadOrCreate
    # Purpose: Loads a JSON file if it exists, otherwise creates
    #          it with the supplied defaults and returns them.
    # Input:  path (str) - Full path to the JSON file.
    #         defaults (dict) - Default values to write if missing.
    # Output: dict - The loaded or default configuration data.
    # --------------------------------------------------------
    def _loadOrCreate(self, path, defaults):
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                merged = self._deepMerge(defaults, data)
                return merged
            except (json.JSONDecodeError, IOError):
                return dict(defaults)
        else:
            self._writeJson(path, defaults)
            return dict(defaults)

    # --------------------------------------------------------
    # Method: _deepMerge
    # Purpose: Recursively merges loaded data onto defaults so
    #          that any new keys added in future versions are
    #          present while preserving existing user values.
    # Input:  defaults (dict), override (dict)
    # Output: dict - Merged result.
    # --------------------------------------------------------
    def _deepMerge(self, defaults, override):
        result = dict(defaults)
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deepMerge(result[key], value)
            else:
                result[key] = value
        return result

    # --------------------------------------------------------
    # Method: _writeJson
    # Purpose: Writes a dictionary to a JSON file with pretty
    #          formatting for human readability.
    # --------------------------------------------------------
    def _writeJson(self, path, data):
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        except IOError as e:
            print(f"[SettingsManager] Error writing {path}: {e}")

    # --------------------------------------------------------
    # Settings Accessors
    # --------------------------------------------------------
    def getSetting(self, key, default=None):
        return self._settings.get(key, default)

    def setSetting(self, key, value):
        self._settings[key] = value

    def getSettings(self):
        return self._settings

    # --------------------------------------------------------
    # State Accessors
    # --------------------------------------------------------
    def getState(self, key, default=None):
        return self._state.get(key, default)

    def setState(self, key, value):
        self._state[key] = value

    def getFullState(self):
        return self._state

    # --------------------------------------------------------
    # Panel State Helpers
    # --------------------------------------------------------
    def getPanelState(self, panel_side):
        key = f"{panel_side}_panel"
        return self._state.get(key, DEFAULT_STATE.get(key, {}))

    def setPanelState(self, panel_side, data):
        key = f"{panel_side}_panel"
        self._state[key] = data

    # --------------------------------------------------------
    # Bookmarks (structure: list of nodes; node = bookmark or group)
    # --------------------------------------------------------
    def getBookmarksStructure(self):
        raw = self._state.get("bookmarks", [])
        if not raw:
            return []
        if isinstance(raw[0], dict) and "type" in raw[0]:
            return raw
        for bm in raw:
            if not isinstance(bm, dict) or "path" not in bm:
                return raw
        return [{"type": "bookmark", "name": b.get("name", ""), "path": b.get("path", "")} for b in raw]

    def setBookmarksStructure(self, structure):
        self._state["bookmarks"] = structure

    def addBookmark(self, name, path):
        structure = self.getBookmarksStructure()
        if self._findBookmarkByPath(structure, path) is not None:
            return
        structure.append({"type": "bookmark", "name": name, "path": path})
        self._state["bookmarks"] = structure

    def _findBookmarkByPath(self, structure, path):
        for node in structure:
            if node.get("type") == "bookmark" and node.get("path") == path:
                return node
            if node.get("type") == "group":
                found = self._findBookmarkByPath(node.get("children", []), path)
                if found is not None:
                    return found
        return None

    def _removeBookmarkFromList(self, nodes, path):
        for i, node in enumerate(nodes):
            if node.get("type") == "bookmark" and node.get("path") == path:
                nodes.pop(i)
                return True
            if node.get("type") == "group":
                if self._removeBookmarkFromList(node.get("children", []), path):
                    return True
        return False

    def removeBookmark(self, path):
        structure = self.getBookmarksStructure()
        self._removeBookmarkFromList(structure, path)
        self._state["bookmarks"] = structure

    def getBookmarks(self):
        out = []
        for node in self.getBookmarksStructure():
            if node.get("type") == "bookmark":
                out.append({"name": node.get("name", ""), "path": node.get("path", "")})
            elif node.get("type") == "group":
                for c in node.get("children", []):
                    if c.get("type") == "bookmark":
                        out.append({"name": c.get("name", ""), "path": c.get("path", "")})
        return out

    # --------------------------------------------------------
    # Libraries / Tags
    # --------------------------------------------------------
    def getLibraries(self):
        return self._state.get("libraries", [])

    def setLibraries(self, libraries):
        self._state["libraries"] = libraries or []

    def getFolderTags(self):
        return self._state.get("folder_tags", {})

    def setFolderTags(self, folder_tags):
        self._state["folder_tags"] = folder_tags or {}

    def getSavedLibraryFilters(self):
        return self._state.get("saved_library_filters", [])

    def setSavedLibraryFilters(self, filters):
        self._state["saved_library_filters"] = filters or []

    def getSidebarState(self):
        return self._state.get("sidebar_state", DEFAULT_STATE.get("sidebar_state", {}))

    def setSidebarState(self, sidebar_state):
        self._state["sidebar_state"] = self._deepMerge(
            DEFAULT_STATE.get("sidebar_state", {}),
            sidebar_state or {},
        )

    # --------------------------------------------------------
    # Recent Paths
    # --------------------------------------------------------
    def addRecentPath(self, path):
        recent = self._state.get("recent_paths", [])
        if path in recent:
            recent.remove(path)
        recent.insert(0, path)
        self._state["recent_paths"] = recent[:self.MAX_RECENT_PATHS]

    def getRecentPaths(self):
        return self._state.get("recent_paths", [])

    # --------------------------------------------------------
    # Persistence
    # --------------------------------------------------------
    def saveSettings(self):
        self._writeJson(self._settings_path, self._settings)

    def saveState(self):
        self._writeJson(self._state_path, self._state)

    def saveAll(self):
        self.saveSettings()
        self.saveState()
