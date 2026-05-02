# Error Notifications Design

**Date:** 2026-05-02
**Status:** Approved

## Problem

Scheduler errors (camera login failures, timelapse build failures, container crashes) are logged but never surfaced to the user in the web UI. Today's outage — where no snapshots were captured for 17+ hours — went unnoticed until the user manually checked.

## Goal

Show a dismissible alert banner on the dashboard when the timelapse container has logged errors or is not running. The user sees it, dismisses it, and it doesn't re-appear unless a new error arrives.

## Architecture

Two pieces:

1. **`GET /api/errors`** — new endpoint in `app.py` that reads Docker logs from the `reolink-preset-timelapse` container and returns recent ERROR/CRITICAL lines as JSON.
2. **Dashboard polling + alert UI** — JavaScript polls `/api/errors` every 30 seconds and renders a dismissible banner when new errors are present.

## `/api/errors` Endpoint

**Query param:** `since` (Unix timestamp float, optional — defaults to 1 hour ago if omitted)

**Logic:**
1. Get the `reolink-preset-timelapse` container via the Docker SDK (already used in settings save).
2. If container status is not `running`, return a synthesized error entry: `{timestamp: <now>, level: "CRITICAL", message: "Container is not running (status: <status>)"}`.
3. Otherwise, fetch `container.logs(since=<since>, timestamps=True)` and scan lines for those containing ` ERROR ` or ` CRITICAL `.
4. Parse each matching line into `{timestamp: <iso string>, level: "ERROR"|"CRITICAL", message: <text after level>}`.
5. Return up to 20 most recent entries.

**Response shape:**
```json
{
  "errors": [
    {"timestamp": "2026-05-01T21:54:47", "level": "ERROR", "message": "Camera error: login failed"}
  ],
  "container_status": "running"
}
```

**Error handling:** If the Docker SDK call itself fails (e.g. Docker not reachable), return `{"errors": [], "container_status": "unknown"}` — don't crash the page.

## Dashboard UI

**Polling:** Every 30 seconds, fetch `/api/errors?since=<last_poll_timestamp>`. On first load, use `now - 3600` (1 hour lookback) so recent errors are caught even if the user just opened the page.

**Banner behavior:**
- If `errors` is non-empty or `container_status` is not `"running"`, show the banner.
- Single error: show the message directly.
- Multiple errors: show "N errors since HH:MM AM — " with an expandable inline list (click to toggle).
- A dismiss button (×) hides the banner and stores the newest error's timestamp in `localStorage` under key `tl_errors_dismissed_until`.
- On subsequent polls, errors with timestamp ≤ `dismissed_until` are ignored. If a newer error arrives, the banner re-appears.

**Styling:** Reuse the existing `.flash.error` CSS class from `base.html`. The banner is positioned just below the nav bar, above the main content grid, and is not shown on other pages (snapshots, videos, settings) — dashboard only.

## What's Out of Scope

- Modifying the scheduler or any container other than the web container
- Errors from the web container itself
- Push notifications, email, or browser notifications
- Showing errors on pages other than the dashboard

## Files Changed

- `src/web/app.py` — add `/api/errors` endpoint
- `src/web/templates/dashboard.html` — add banner HTML + polling JS
