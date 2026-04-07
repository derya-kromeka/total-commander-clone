# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Placeholder for upcoming changes. When you ship, move items under a dated version section and bump `APP_VERSION` in `app_version.py`.

## [0.4.7] - 2026-04-07

### Added

- **Settings** dialog (**File → Settings…**), aligned with the [denizko-gh/total-commander-clone-1](https://github.com/denizko-gh/total-commander-clone-1) fork: theme (dark / light / same as system), font size, show hidden files, confirm before delete, default left/right paths. **`theme.applyTheme`** in `theme.py` applies the custom dark stylesheet or Fusion light / native system look; `main.py` stores the initial style and palette for the “system” option.

## [0.4.6] - 2026-04-07

### Added

- **Folder tooltips**: **Size** line sums **only files directly in that folder** (one `scandir`, no subfolder recursion) so hover stays fast; footer clarifies that subfolders are not included.

## [0.4.5] - 2026-04-07

### Added

- **Column header menu**: **Distribute columns evenly** splits the panel width equally across all visible columns (turns off “stretch last column” so widths stay equal).

## [0.4.4] - 2026-04-07

### Added

- **Properties** (right-click): Tabbed dialog with **General** (name, type, location, full path, size or folder item count, created / modified / accessed, attributes), **Details** (MIME type, extension, symlink target, permissions, inode, device, owner/group on Unix, drive), and **Checksums** (MD5, SHA-1, SHA-256) for files.

## [0.4.3] - 2026-04-07

### Added

- **Tooltips**: Title plus short description on main menus, toolbar, center pane buttons, bottom F-key bar, sidebar tabs, bookmarks/libraries panels, library browser controls, and file context menu items. File list rows keep **summary card** HTML tooltips (path, size, dates, MIME, “Opens with” on Windows) from the file panel model; the file table enables mouse tracking so hover tips behave reliably.

## [0.4.2] - 2026-04-07

### Changed

- **File panel toolbar**: **New folder** sits immediately to the **right of Home** and to the **left of the drive** dropdown (before the filter row).

## [0.4.1] - 2026-04-07

### Added

- **Filter — subfolders**: Checkbox **Subfolders** next to the filter field lists and searches **recursively** under the current folder (names show as `subdir\\file`). The same filter modes (contains / wildcard / regex) and **Files only** / **Folders only** apply to that full tree. State is saved per pane. Large directories may take longer to scan.

## [0.4.0] - 2026-04-07

### Added

- **File panel columns**: Right-click the column header row to show a menu with checkboxes for **Name**, **Size**, **Type**, and **Date Modified** (at least one column must stay visible). Visibility is saved per pane in `state.json`.
- **Filter options**: A **gear-style** button next to the filter field opens a menu: **Match name** — contains text, wildcard (`*`, `?`), or regular expression; **Show** — all items, folders only, or files only. The filter box placeholder summarizes the active mode; filter text and options persist per pane.

## [0.3.12] - 2026-04-07

### Changed

- **Active panel**: The file list (`QTableView`) uses the same thin **orange** focus ring as the path field when that pane is active; inactive panes keep a neutral border on both.

## [0.3.11] - 2026-04-07

### Changed

- **File panels**: The **Date Modified** column stretches to the right edge of the pane (`stretchLastSection`), so the file list usually shows all four columns without a horizontal scrollbar. Saved column widths apply only to **Name**, **Size**, and **Type**.

## [0.3.10] - 2026-04-07

### Changed

- **Git helper scripts** (`scripts/git-hub-menu.bat`, `scripts/git-hub-menu.sh`): option **6 — Save to GitHub** keeps the safer flow (no `origin` → offer to set remote; identity check; **Proceed?**; optional `git ls-remote` warning and **Try push anyway?**; `git commit -F` message file, UTF-8 on Windows; push stderr tail + tips). **After setting `origin` from option 6**, the scripts now **continue** into add/commit/push instead of always returning to the menu.

## [0.3.9] - 2026-04-07

### Changed

- **Active panel**: The address bar (`QLineEdit` showing the current path) shows a thin orange border when that panel is active; inactive panels keep a neutral border. The file panel’s outer frame uses the same border for both states so focus reads on the path field.

## [0.3.8] - 2026-04-07

### Added

- **New folder** button on each file panel’s navigation bar (folder-with-plus style icon): creates a subfolder in that panel’s current directory; **F8** still uses the same logic for whichever panel is active.

## [0.3.7] - 2026-04-07

### Changed

- **Drive list**: Removed the separate refresh button; the drive list is re-scanned when you open the drive dropdown (Windows), so USB and external disks stay current without an extra click.

## [0.3.6] - 2026-04-02

### Changed

- **Drive picker**: left-click on the drive letter / combo field opens the drive list (same as the ▼ control), not only the separate arrow button.

## [0.3.5] - 2026-04-02

### Changed

- **Git helper scripts** (`scripts/git-hub-menu.bat`, `scripts/git-hub-menu.sh`): option **6 — Save to GitHub** now checks for `origin` and user identity first, asks **Proceed?** before `git add`, optionally warns when `git ls-remote` fails (offline/auth), commits via **`-F`** message file (UTF-8 on Windows), skips **push** after a failed commit, and shows only the **last lines** of push errors plus tips (options 4, 11, 12).

## [0.3.4] - 2026-04-02

### Fixed

- **Crash when opening some folders** (e.g. CAD paths with names starting with digits): natural name sorting used mixed `int` and `str` list elements, which raised `TypeError` during sort. Segments are now tagged `(numeric)` vs `(text)` so ordering is always comparable.

## [0.3.3] - 2026-04-02

### Fixed

- **Name column** sorting uses **natural order**: numeric runs in file names are compared as numbers, so e.g. `KT-167` sorts before `KT-1665` and `KT-173`, matching typical file manager expectations.

## [0.3.2] - 2026-04-02

### Changed

- Path bar **Open folder** button (folder icon) now opens **that panel’s** current directory in the system file manager (Windows Explorer / Finder / etc.) instead of showing a folder picker dialog.
- Inactive file panel: thin **gray** border (`overlay0`). Active file panel: thin **orange** border (`panel_focus_ring`).

## [0.3.1] - 2026-04-02

### Fixed

- File list scroll position resets to the top when navigating into a folder (e.g. double-click), so the new directory listing always starts from the first row.

## [0.3.0] - 2026-04-02

### Added

- **Library Browser Panel**: full panel-sized library browser that can replace either file panel, with library selector dropdown, categorized tag tree, and folder results list with action buttons.
- **Tag categories**: tags using `category:value` format are now grouped by category in the Library Browser. The Tag Assignment dialog shows known categories as hints and provides autocomplete for existing tags.
- **Mirror button**: new center column button to open the active panel's current folder in the other panel (Ctrl+Shift+M).
- **Panel toggle**: View menu actions and Ctrl+Shift+L shortcut to toggle any panel between file browser and library browser mode.
- QSS styling for library browser components and list widgets.

### Changed

- Home button icon replaced with a recognizable house emoji instead of the generic `SP_DirHomeIcon` which looked like a folder on Windows.

## [0.2.2] - 2026-04-01

### Changed

- `scripts/install.sh`: expanded macOS support — Homebrew on Apple Silicon (`/opt/homebrew`) and Intel (`/usr/local`), MacPorts (`python312` + `port select`), discovery of python.org Framework installs when not on `PATH`, and clearer manual install hints.

## [0.2.1] - 2026-04-01

### Added

- `scripts/install.sh`: detects OS and CPU architecture, installs Python when needed, creates `.venv`, installs `requirements.txt`, and generates `scripts/run.sh` to launch the app from the venv.

## [0.2.0] - 2026-03-30

### Added

- Application version in window title and About dialog (`app_version.py`).
- Libraries and folder tags (registry, marker file `.tcc_library_root.json`, Libraries sidebar tab, tag assignment).
- This changelog and versioning workflow for the project.
