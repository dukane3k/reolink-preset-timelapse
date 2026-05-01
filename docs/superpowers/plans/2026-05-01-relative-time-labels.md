# Relative Time Labels on Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace raw filenames under the latest snapshot and today's video on the dashboard with live-updating relative time labels ("3 minutes ago", "2 hours ago").

**Architecture:** The server parses a full ISO 8601 datetime from each file (snapshot: date dir + filename timestamp; video: file mtime) and passes it as a template variable. The template renders a `<span data-ts="...">` for each. A small inline JS IIFE formats the spans on load and refreshes every 30 seconds via `setInterval`.

**Tech Stack:** Python 3 / FastAPI / Jinja2 templates, vanilla JS (no libraries)

---

## File Map

| File | Change |
|---|---|
| `src/web/app.py` | Parse snapshot datetime from dir+filename; parse video datetime from mtime; pass both as ISO strings to template |
| `src/web/templates/dashboard.html` | Replace filename text with `<span data-ts="...">` elements; add inline JS `formatRelative` + `setInterval` |
| `tests/test_web.py` | Update existing dashboard tests; add new tests for ISO timestamp presence and JS `data-ts` attributes |

---

## Task 1: Parse snapshot ISO timestamp in dashboard route

**Files:**
- Modify: `src/web/app.py` (dashboard route, lines 69–106)

The snapshot filename format is `{preset}_{YYYY-MM-DD}_{HH-MM-SS}_{label}.jpg`. The date is already available as `date_str` from the directory-iteration loop. Parse both to build a full ISO datetime string.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_web.py`:

```python
def test_dashboard_snapshot_iso_in_data_ts(client, dirs):
    date_dir = dirs["snap_dir"] / "2026-05-01"
    date_dir.mkdir()
    img = date_dir / "Full_Garden_2026-05-01_14-32-05_day.jpg"
    img.write_bytes(b"FAKEJPEG")
    resp = client.get("/")
    assert resp.status_code == 200
    assert b'data-ts="2026-05-01T14:32:05"' in resp.content
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python3 -m pytest tests/test_web.py::test_dashboard_snapshot_iso_in_data_ts -v
```

Expected: FAIL — `data-ts` attribute not present yet.

- [ ] **Step 3: Implement snapshot ISO parsing in app.py**

In the dashboard route, after `latest_snapshot = snaps[0].name` and `latest_snapshot_url = ...`, add parsing logic. The filename stem has the form `{preset}_{YYYY-MM-DD}_{HH-MM-SS}_{label}`. Split on `_` from the right to extract the date and time fields.

Replace the snapshot-finding block (lines 82–88 in `src/web/app.py`) with:

```python
import re as _re2
if all_dates:
    for date_str in all_dates:
        snaps = sorted((snapshot_dir / date_str).glob("*.jpg"), reverse=True)
        if snaps:
            latest_snapshot = snaps[0].name
            latest_snapshot_url = f"/media/snapshots/{date_str}/{latest_snapshot}"
            # Parse ISO timestamp from filename: {preset}_{YYYY-MM-DD}_{HH-MM-SS}_{label}.jpg
            stem = snaps[0].stem  # e.g. Full_Garden_2026-05-01_14-32-05_day
            m = _re.search(r'(\d{4}-\d{2}-\d{2})_(\d{2}-\d{2}-\d{2})', stem)
            if m:
                latest_snapshot_iso = f"{m.group(1)}T{m.group(2).replace('-', ':')}"
            else:
                latest_snapshot_iso = None
            break
```

Note: `_re` is already imported at module level in `app.py`. Initialize `latest_snapshot_iso = None` before the `if all_dates:` block alongside the other `None` initializations.

Also pass `latest_snapshot_iso` to `_render`:

```python
return app.state.render(
    "dashboard.html", request, "dashboard",
    latest_snapshot=latest_snapshot,
    latest_snapshot_url=latest_snapshot_url,
    latest_snapshot_iso=latest_snapshot_iso,
    snapshot_count_today=snapshot_count_today,
    today=today,
    today_video=today_video,
)
```

(Add `today_video_iso=None` here for now — it will be filled in Task 2.)

- [ ] **Step 4: Run test to verify it passes**

```bash
python3 -m pytest tests/test_web.py::test_dashboard_snapshot_iso_in_data_ts -v
```

Expected: still FAIL — template not yet updated. That's fine; we'll fix the template in Task 3.

- [ ] **Step 5: Commit**

```bash
git add src/web/app.py tests/test_web.py
git commit -m "feat: parse snapshot ISO timestamp in dashboard route"
```

---

## Task 2: Parse video ISO timestamp from mtime in dashboard route

**Files:**
- Modify: `src/web/app.py` (dashboard route, lines 94–97)

- [ ] **Step 1: Write the failing test**

Add to `tests/test_web.py`:

```python
def test_dashboard_video_iso_in_data_ts(client, dirs):
    from datetime import date, datetime
    today = date.today().strftime("%Y-%m-%d")
    mp4 = dirs["video_dir"] / f"timelapse_{today}.mp4"
    mp4.write_bytes(b"FAKEMP4")
    mtime = mp4.stat().st_mtime
    expected_iso = datetime.fromtimestamp(mtime).strftime("%Y-%m-%dT%H:%M:%S")
    resp = client.get("/")
    assert resp.status_code == 200
    assert f'data-ts="{expected_iso}"'.encode() in resp.content
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python3 -m pytest tests/test_web.py::test_dashboard_video_iso_in_data_ts -v
```

Expected: FAIL — `data-ts` for video not present yet.

- [ ] **Step 3: Implement video ISO parsing in app.py**

Replace the today's-video block (lines 94–97 in `src/web/app.py`) with:

```python
today_video = None
today_video_iso = None
today_video_path = timelapse_dir / f"timelapse_{today}.mp4"
if today_video_path.is_file():
    today_video = f"timelapse_{today}.mp4"
    today_video_iso = datetime.fromtimestamp(today_video_path.stat().st_mtime).strftime("%Y-%m-%dT%H:%M:%S")
```

`datetime` is already imported inside the dashboard route function (`from datetime import date, datetime`).

Also update the `_render` call to pass `today_video_iso` (replacing the `today_video_iso=None` placeholder added in Task 1):

```python
return app.state.render(
    "dashboard.html", request, "dashboard",
    latest_snapshot=latest_snapshot,
    latest_snapshot_url=latest_snapshot_url,
    latest_snapshot_iso=latest_snapshot_iso,
    snapshot_count_today=snapshot_count_today,
    today=today,
    today_video=today_video,
    today_video_iso=today_video_iso,
)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python3 -m pytest tests/test_web.py::test_dashboard_video_iso_in_data_ts -v
```

Expected: still FAIL — template not updated yet. That's fine.

- [ ] **Step 5: Commit**

```bash
git add src/web/app.py tests/test_web.py
git commit -m "feat: parse video mtime ISO timestamp in dashboard route"
```

---

## Task 3: Update dashboard template with data-ts spans and live-update JS

**Files:**
- Modify: `src/web/templates/dashboard.html`

- [ ] **Step 1: Verify what the template currently renders**

No test to write here — tests in Task 1 and 2 are already checking for `data-ts`. Confirm they still fail (template not yet changed):

```bash
python3 -m pytest tests/test_web.py::test_dashboard_snapshot_iso_in_data_ts tests/test_web.py::test_dashboard_video_iso_in_data_ts -v
```

Expected: both FAIL.

- [ ] **Step 2: Update the snapshot label in dashboard.html**

In `src/web/templates/dashboard.html`, replace:

```html
      <p style="color:#aaa;font-size:0.8rem;margin-top:8px;">
        {{ latest_snapshot }} &nbsp;·&nbsp; {{ snapshot_count_today }} today
      </p>
```

With:

```html
      <p style="color:#aaa;font-size:0.8rem;margin-top:8px;">
        {% if latest_snapshot_iso %}<span data-ts="{{ latest_snapshot_iso }}"></span>{% else %}{{ latest_snapshot }}{% endif %} &nbsp;·&nbsp; {{ snapshot_count_today }} today
      </p>
```

- [ ] **Step 3: Update the video label in dashboard.html**

Replace:

```html
      <p style="color:#aaa;font-size:0.8rem;margin-top:8px;">{{ today_video }}</p>
```

With:

```html
      <p style="color:#aaa;font-size:0.8rem;margin-top:8px;">
        {% if today_video_iso %}<span data-ts="{{ today_video_iso }}"></span>{% else %}{{ today_video }}{% endif %}
      </p>
```

- [ ] **Step 4: Add the inline JS block at the end of dashboard.html (before `{% endblock %}`)**

```html
<script>
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
</script>
```

- [ ] **Step 5: Run all dashboard tests**

```bash
python3 -m pytest tests/test_web.py::test_dashboard_snapshot_iso_in_data_ts tests/test_web.py::test_dashboard_video_iso_in_data_ts tests/test_web.py::test_dashboard_renders_empty_state tests/test_web.py::test_dashboard_shows_latest_snapshot tests/test_web.py::test_dashboard_shows_todays_video tests/test_web.py::test_dashboard_has_action_buttons -v
```

Expected: all PASS.

Note: `test_dashboard_shows_latest_snapshot` currently asserts `b"Full_Garden_2026-05-01_10-00-00_day.jpg" in resp.content` — this will now FAIL because the filename is replaced by a `data-ts` span. Update that test:

```python
def test_dashboard_shows_latest_snapshot(client, dirs):
    date_dir = dirs["snap_dir"] / "2026-05-01"
    date_dir.mkdir()
    img = date_dir / "Full_Garden_2026-05-01_10-00-00_day.jpg"
    img.write_bytes(b"FAKEJPEG")
    resp = client.get("/")
    assert resp.status_code == 200
    assert b'data-ts="2026-05-01T10:00:00"' in resp.content
```

And `test_dashboard_shows_todays_video` asserts `today.encode() in resp.content` — the date still appears in the video `src` attribute, so this test should still pass. Confirm it does before committing.

- [ ] **Step 6: Run the full test suite**

```bash
python3 -m pytest tests/test_web.py -v
```

Expected: all tests PASS.

- [ ] **Step 7: Commit**

```bash
git add src/web/templates/dashboard.html tests/test_web.py
git commit -m "feat: show relative time labels on dashboard with live JS updates"
```

---

## Task 4: Verify full suite still green

**Files:** none (verification only)

- [ ] **Step 1: Run all tests**

```bash
python3 -m pytest -q --no-header
```

Expected: all tests pass, no regressions.

- [ ] **Step 2: Confirm no regressions**

If any tests fail, fix them before proceeding. Do not skip or delete tests to make this step pass.
