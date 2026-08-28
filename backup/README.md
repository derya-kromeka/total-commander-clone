# Local per-computer settings backups

The app writes the **latest** settings, bookmarks, and libraries to the
local user-data directory (outside Git):

```
%APPDATA%\TotalCommanderClone\backups\<computer-name>\   (Windows)
~/.config/TotalCommanderClone/backups/<computer-name>/  (other platforms)

  settings.json
  bookmarks.json
  libraries.json
  state.json
  backup_manifest.json
```

Each computer keeps only its current files (overwritten on every settings/state save).
These files are **not** committed or pushed. Git push/pull syncs source code only.

To copy settings between machines, use **Settings → Export profile / Import profile**.
The older `backup/settings/<computer-name>/` copies that used to live in this
repository are obsolete and ignored if still present on disk.
