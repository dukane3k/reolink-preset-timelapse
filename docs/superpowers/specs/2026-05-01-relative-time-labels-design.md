# Relative Time Labels on Dashboard

**Date:** 2026-05-01  
**Status:** Approved

## Summary

Replace raw filenames shown under the latest snapshot and today's video on the dashboard with human-readable relative time labels (e.g. "3 minutes ago", "2 hours ago"). Labels update live in the browser every 30 seconds without a page reload.

## Server Changes (`src/web/app.py` — dashboard route)

### Snapshot timestamp

The latest snapshot is found by iterating date directories and globbing `.jpg` files. The filename format is `snapshot_HH-MM-SS.jpg` and the date is already known from `date_str`. Parse both to construct a full `datetime`:

```
date_str = "2026-05-01"           # from the directory name
filename = "snapshot_14-32-05.jpg"  # HH-MM-SS parsed from name
→ latest_snapshot_iso = "2026-05-01T14:32:05"
```

Pass `latest_snapshot_iso` (an ISO 8601 string) to the template. Only set when a snapshot exists.

### Video timestamp

When `today_video_path.is_file()`, read `today_video_path.stat().st_mtime`, convert to a local `datetime` using `datetime.fromtimestamp()`, and format as ISO 8601. Pass as `today_video_iso`. Only set when the video exists.

### Empty states

No change — "No snapshots yet" and "No timelapse built yet today" are unaffected.

## Template Changes (`src/web/templates/dashboard.html`)

### Snapshot label

Replace:
```html
<p style="color:#aaa;font-size:0.8rem;margin-top:8px;">
  {{ latest_snapshot }} &nbsp;·&nbsp; {{ snapshot_count_today }} today
</p>
```

With:
```html
<p style="color:#aaa;font-size:0.8rem;margin-top:8px;">
  <span data-ts="{{ latest_snapshot_iso }}"></span> &nbsp;·&nbsp; {{ snapshot_count_today }} today
</p>
```

### Video label

Replace:
```html
<p style="color:#aaa;font-size:0.8rem;margin-top:8px;">{{ today_video }}</p>
```

With:
```html
<p style="color:#aaa;font-size:0.8rem;margin-top:8px;">
  <span data-ts="{{ today_video_iso }}"></span>
</p>
```

### Inline script

Add a `<script>` block (inside `{% block content %}`, after the card markup):

```javascript
(function () {
  function formatRelative(isoString) {
    var then = new Date(isoString);
    var seconds = Math.round((Date.now() - then.getTime()) / 1000);
    if (seconds < 60) return "just now";
    var minutes = Math.floor(seconds / 60);
    if (minutes < 60) return minutes + " minute" + (minutes === 1 ? "" : "s") + " ago";
    var hours = Math.floor(minutes / 60);
    if (hours < 24) return hours + " hour" + (hours === 1 ? "" : "s") + " ago";
    var days = Math.floor(hours / 24);
    return days + " day" + (days === 1 ? "" : "s") + " ago";
  }

  function updateAll() {
    document.querySelectorAll("[data-ts]").forEach(function (el) {
      el.textContent = formatRelative(el.getAttribute("data-ts"));
    });
  }

  updateAll();
  setInterval(updateAll, 30000);
})();
```

## Behaviour

| Scenario | Label shown |
|---|---|
| Snapshot taken 45 seconds ago | "just now" |
| Snapshot taken 3 minutes ago | "3 minutes ago" |
| Snapshot taken 2 hours ago | "2 hours ago" |
| Snapshot from yesterday (stale) | "1 day ago" |
| Video built 2 hours ago | "2 hours ago" |
| No snapshot / no video | Empty state text unchanged |

## Out of Scope

- Snapshots page and Videos page labels (not changed)
- Tooltip showing the exact filename or timestamp
- Server-sent events / websocket for real-time push (polling interval is sufficient)
