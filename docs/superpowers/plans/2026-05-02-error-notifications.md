# Error Notifications Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show a dismissible error banner on the dashboard when the timelapse container logs errors or stops running.

**Architecture:** A new `/api/errors` endpoint reads Docker logs from the `reolink-preset-timelapse` container and returns parsed ERROR/CRITICAL lines as JSON. The dashboard polls this endpoint every 30 seconds and renders a dismissible banner, tracking dismissal state in `localStorage`.

**Tech Stack:** Python/FastAPI, Docker SDK (`docker` package), Jinja2 templates, vanilla JS

---

### Task 1: `/api/errors` endpoint

**Files:**
- Modify: `src/web/app.py` (add endpoint after `api_status`, around line 408)
- Test: `tests/test_web.py` (append new tests)

- [ ] **Step 1: Write failing tests**

Append to `tests/test_web.py`:

```python
def test_api_errors_returns_empty_when_docker_unavailable(client, monkeypatch):
    import docker
    monkeypatch.setattr(docker, "from_env", lambda: (_ for _ in ()).throw(Exception("Docker not available")))
    resp = client.get("/api/errors")
    assert resp.status_code == 200
    data = resp.json()
    assert data["errors"] == []
    assert data["container_status"] == "unknown"


def test_api_errors_returns_critical_when_container_not_running(client, monkeypatch):
    import docker

    class FakeContainer:
        status = "exited"
        def logs(self, **kwargs):
            return b""

    class FakeClient:
        def containers(self): pass

    fake_dc = FakeClient()
    fake_dc.containers = type("C", (), {"get": staticmethod(lambda name: FakeContainer())})()
    monkeypatch.setattr(docker, "from_env", lambda: fake_dc)

    resp = client.get("/api/errors")
    assert resp.status_code == 200
    data = resp.json()
    assert data["container_status"] == "exited"
    assert len(data["errors"]) == 1
    assert data["errors"][0]["level"] == "CRITICAL"
    assert "exited" in data["errors"][0]["message"]


def test_api_errors_parses_error_lines_from_logs(client, monkeypatch):
    import docker

    log_output = (
        b"2026-05-01T21:54:47.123456789Z 2026-05-01 21:54:47,217 ERROR scheduler Camera error: login failed\n"
        b"2026-05-01T21:55:00.000000000Z 2026-05-01 21:55:00,000 INFO scheduler Scheduler running\n"
        b"2026-05-01T21:56:00.000000000Z 2026-05-01 21:56:00,000 CRITICAL scheduler Configuration error: missing field\n"
    )

    class FakeContainer:
        status = "running"
        def logs(self, **kwargs):
            return log_output

    class FakeClient:
        def containers(self): pass

    fake_dc = FakeClient()
    fake_dc.containers = type("C", (), {"get": staticmethod(lambda name: FakeContainer())})()
    monkeypatch.setattr(docker, "from_env", lambda: fake_dc)

    resp = client.get("/api/errors")
    assert resp.status_code == 200
    data = resp.json()
    assert data["container_status"] == "running"
    assert len(data["errors"]) == 2
    messages = [e["message"] for e in data["errors"]]
    assert any("Camera error: login failed" in m for m in messages)
    assert any("Configuration error: missing field" in m for m in messages)
    levels = [e["level"] for e in data["errors"]]
    assert "ERROR" in levels
    assert "CRITICAL" in levels


def test_api_errors_respects_since_param(client, monkeypatch):
    import docker
    captured_kwargs = {}

    class FakeContainer:
        status = "running"
        def logs(self, **kwargs):
            captured_kwargs.update(kwargs)
            return b""

    class FakeClient:
        def containers(self): pass

    fake_dc = FakeClient()
    fake_dc.containers = type("C", (), {"get": staticmethod(lambda name: FakeContainer())})()
    monkeypatch.setattr(docker, "from_env", lambda: fake_dc)

    resp = client.get("/api/errors?since=1746000000.0")
    assert resp.status_code == 200
    assert captured_kwargs.get("since") == 1746000000.0


def test_api_errors_caps_at_20_results(client, monkeypatch):
    import docker

    # Generate 25 error lines
    lines = b""
    for i in range(25):
        lines += f"2026-05-01T21:54:{i:02d}.000000000Z 2026-05-01 21:54:{i:02d},000 ERROR scheduler Error {i}\n".encode()

    class FakeContainer:
        status = "running"
        def logs(self, **kwargs):
            return lines

    class FakeClient:
        def containers(self): pass

    fake_dc = FakeClient()
    fake_dc.containers = type("C", (), {"get": staticmethod(lambda name: FakeContainer())})()
    monkeypatch.setattr(docker, "from_env", lambda: fake_dc)

    resp = client.get("/api/errors")
    assert resp.status_code == 200
    assert len(resp.json()["errors"]) == 20
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /data/timelapse && python -m pytest tests/test_web.py::test_api_errors_returns_empty_when_docker_unavailable tests/test_web.py::test_api_errors_returns_critical_when_container_not_running tests/test_web.py::test_api_errors_parses_error_lines_from_logs tests/test_web.py::test_api_errors_respects_since_param tests/test_web.py::test_api_errors_caps_at_20_results -v 2>&1 | tail -20
```

Expected: All 5 FAIL with `404` or `AttributeError` — endpoint doesn't exist yet.

- [ ] **Step 3: Implement the endpoint**

In `src/web/app.py`, add the following immediately after the closing of the `api_status` function (around line 408, before the `app.state.snapshot_dir = ...` block):

```python
    @app.get("/api/errors")
    def api_errors(since: float = 0.0):
        import time
        import docker as docker_sdk
        if since == 0.0:
            since = time.time() - 3600
        try:
            dc = docker_sdk.from_env()
            container = dc.containers.get("reolink-preset-timelapse")
            if container.status != "running":
                import datetime
                return JSONResponse({
                    "errors": [{
                        "timestamp": datetime.datetime.utcnow().replace(microsecond=0).isoformat(),
                        "level": "CRITICAL",
                        "message": f"Container is not running (status: {container.status})",
                    }],
                    "container_status": container.status,
                })
            raw = container.logs(since=since, timestamps=True)
        except Exception:
            return JSONResponse({"errors": [], "container_status": "unknown"})

        entries = []
        for raw_line in raw.splitlines():
            try:
                line = raw_line.decode("utf-8", errors="replace")
            except AttributeError:
                line = raw_line
            for level in ("CRITICAL", "ERROR"):
                marker = f" {level} "
                if marker in line:
                    # line format: "<docker-ts> <date> <time>,<ms> LEVEL logger message"
                    # grab the docker timestamp (first token) for ISO output
                    parts = line.split(" ", 1)
                    docker_ts = parts[0].rstrip("Z").split(".")[0] if parts else ""
                    msg_start = line.find(marker) + len(marker)
                    # skip logger name token
                    remainder = line[msg_start:].split(" ", 1)
                    message = remainder[1] if len(remainder) > 1 else line[msg_start:]
                    entries.append({
                        "timestamp": docker_ts,
                        "level": level,
                        "message": message.strip(),
                    })
                    break

        return JSONResponse({
            "errors": entries[-20:],
            "container_status": "running",
        })
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /data/timelapse && python -m pytest tests/test_web.py::test_api_errors_returns_empty_when_docker_unavailable tests/test_web.py::test_api_errors_returns_critical_when_container_not_running tests/test_web.py::test_api_errors_parses_error_lines_from_logs tests/test_web.py::test_api_errors_respects_since_param tests/test_web.py::test_api_errors_caps_at_20_results -v 2>&1 | tail -20
```

Expected: All 5 PASS.

- [ ] **Step 5: Run full test suite to check for regressions**

```bash
cd /data/timelapse && python -m pytest tests/ -v 2>&1 | tail -30
```

Expected: All existing tests still pass.

- [ ] **Step 6: Commit**

```bash
cd /data/timelapse && git add src/web/app.py tests/test_web.py && git commit -m "feat: add /api/errors endpoint for scheduler error surfacing"
```

---

### Task 2: Dashboard error banner

**Files:**
- Modify: `src/web/templates/dashboard.html`

- [ ] **Step 1: Add banner HTML**

In `src/web/templates/dashboard.html`, insert the following immediately after `{% block content %}` (before the opening `<div style="display:grid...`):

```html
<div id="error-banner" class="flash error" style="display:none;justify-content:space-between;align-items:flex-start;gap:12px;">
  <span id="error-banner-text"></span>
  <button type="button" id="error-banner-dismiss"
          style="background:none;border:none;color:inherit;font-size:1.1rem;cursor:pointer;padding:0;line-height:1;flex-shrink:0;"
          aria-label="Dismiss">×</button>
</div>
<div id="error-banner-detail" style="display:none;margin-top:-12px;margin-bottom:16px;">
  <ul id="error-banner-list" style="margin:0;padding-left:20px;font-size:0.85rem;color:#cc3333;"></ul>
</div>
```

- [ ] **Step 2: Add error polling JS**

In `src/web/templates/dashboard.html`, add the following `<script>` block immediately before the closing `{% endblock %}` tag (after the existing `</script>`):

```html
<script>
(function () {
  var banner = document.getElementById('error-banner');
  var bannerText = document.getElementById('error-banner-text');
  var bannerDetail = document.getElementById('error-banner-detail');
  var bannerList = document.getElementById('error-banner-list');
  var dismissBtn = document.getElementById('error-banner-dismiss');

  var DISMISS_KEY = 'tl_errors_dismissed_until';
  var lastPoll = Math.floor(Date.now() / 1000) - 3600;

  function dismissedUntil() {
    return parseFloat(localStorage.getItem(DISMISS_KEY) || '0');
  }

  function isoToUnix(iso) {
    return iso ? Date.parse(iso.replace('T', ' ') + 'Z') / 1000 : 0;
  }

  function formatTime(iso) {
    if (!iso) return '';
    var d = new Date(iso + 'Z');
    return d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
  }

  function showBanner(errors) {
    var newest = errors.reduce(function (max, e) {
      return isoToUnix(e.timestamp) > isoToUnix(max.timestamp) ? e : max;
    }, errors[0]);

    if (isoToUnix(newest.timestamp) <= dismissedUntil()) return;

    if (errors.length === 1) {
      bannerText.textContent = errors[0].message;
      bannerDetail.style.display = 'none';
    } else {
      var since = formatTime(errors[0].timestamp);
      bannerText.innerHTML = errors.length + ' errors since ' + since + ' — <a href="#" id="error-expand-link" style="color:inherit;">expand</a>';
      bannerList.innerHTML = '';
      errors.forEach(function (e) {
        var li = document.createElement('li');
        li.textContent = '[' + formatTime(e.timestamp) + '] ' + e.message;
        bannerList.appendChild(li);
      });
      var expandLink = document.getElementById('error-expand-link');
      if (expandLink) {
        expandLink.addEventListener('click', function (ev) {
          ev.preventDefault();
          bannerDetail.style.display = bannerDetail.style.display === 'none' ? 'block' : 'none';
        });
      }
    }

    banner.style.display = 'flex';
    banner._newestTs = isoToUnix(newest.timestamp);
  }

  dismissBtn.addEventListener('click', function () {
    if (banner._newestTs) {
      localStorage.setItem(DISMISS_KEY, String(banner._newestTs));
    }
    banner.style.display = 'none';
    bannerDetail.style.display = 'none';
  });

  function poll() {
    var url = '/api/errors?since=' + lastPoll;
    lastPoll = Math.floor(Date.now() / 1000);
    fetch(url)
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (data) {
        if (!data) return;
        var errors = data.errors || [];
        var status = data.container_status;
        if (errors.length > 0) {
          showBanner(errors);
        } else if (status !== 'running' && status !== 'unknown') {
          showBanner([{ timestamp: new Date().toISOString().slice(0, 19), level: 'CRITICAL', message: 'Container is not running (status: ' + status + ')' }]);
        }
      })
      .catch(function () { /* silently ignore poll failures */ });
  }

  poll();
  setInterval(poll, 30000);
})();
</script>
```

- [ ] **Step 3: Manually verify the banner in the browser**

Restart the web container, open the dashboard, and confirm:
- No banner shown when no errors exist
- Open browser console and run:
  ```js
  fetch('/api/errors').then(r => r.json()).then(console.log)
  ```
  Confirm the endpoint returns `{"errors": [...], "container_status": "running"}`.

To test the banner manually without breaking anything, temporarily force it from the console:
```js
document.getElementById('error-banner-text').textContent = 'Test error message';
document.getElementById('error-banner').style.display = 'flex';
```
Confirm the banner appears, the × dismisses it, and it doesn't reappear on reload (check `localStorage.tl_errors_dismissed_until`).

- [ ] **Step 4: Commit**

```bash
cd /data/timelapse && git add src/web/templates/dashboard.html && git commit -m "feat: add dismissible error banner to dashboard with 30s polling"
```
