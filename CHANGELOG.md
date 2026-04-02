# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Placeholder for upcoming changes. When you ship, move items under a dated version section and bump `APP_VERSION` in `app_version.py`.

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
