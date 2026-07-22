# Per-computer settings backups

The app writes the **latest** settings, bookmarks, and libraries here:

```
backup/settings/<computer-name>/
  settings.json
  bookmarks.json
  libraries.json
  state.json
  backup_manifest.json
```

Each computer keeps only its current files (overwritten on every settings/state save).
The app also tries to commit and push these files to the Git remote (uses saved PAT when available).
