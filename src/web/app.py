from __future__ import annotations
import logging
import os
import re as _re
from pathlib import Path
from fastapi import FastAPI, Request, BackgroundTasks
from dotenv import dotenv_values
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from src.capture import run_capture
from src.timelapse import build_timelapse, collect_snapshots, collect_snapshots_through_date

_TEMPLATES_DIR = Path(__file__).parent / "templates"


def create_app(
    snapshot_dir: Path,
    timelapse_dir: Path,
    env_path: Path,
) -> FastAPI:
    app = FastAPI()
    templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

    def _snap_time(filename: str) -> str:
        """Convert snapshot filename to formatted time, e.g. '10:08 AM'."""
        parts = filename.split("_")
        if len(parts) < 4:
            return ""
        h, m = parts[3].split("-")[:2]
        hour, minute = int(h), int(m)
        suffix = "AM" if hour < 12 else "PM"
        hour12 = hour % 12 or 12
        return f"{hour12}:{minute:02d} {suffix}"

    def _snap_label(filename: str) -> str:
        """Extract label from snapshot filename, e.g. 'day', 'night', 'sunrise', 'sunset'."""
        parts = filename.split("_")
        return parts[-1].replace(".jpg", "") if parts else ""

    templates.env.filters["snap_time"] = _snap_time
    templates.env.filters["snap_label"] = _snap_label

    def _flash(request: Request) -> tuple[str, str]:
        msg = request.cookies.get("flash_message", "")
        typ = request.cookies.get("flash_type", "success")
        return msg, typ

    def _render(template: str, request: Request, active: str, **ctx):
        flash_message, flash_type = _flash(request)
        context = {"active": active, "flash_message": flash_message, "flash_type": flash_type, **ctx}
        response = templates.TemplateResponse(request, template, context)
        response.delete_cookie("flash_message")
        response.delete_cookie("flash_type")
        return response

    def _redirect_with_flash(url: str, message: str, typ: str = "success"):
        resp = RedirectResponse(url=url, status_code=303)
        resp.set_cookie("flash_message", message, max_age=10)
        resp.set_cookie("flash_type", typ, max_age=10)
        return resp

    # --- Media routes ---

    @app.get("/media/snapshots/{date}/{filename}")
    def serve_snapshot(date: str, filename: str):
        path = (snapshot_dir / date / filename).resolve()
        if not str(path).startswith(str(snapshot_dir.resolve())):
            return JSONResponse({"detail": "Not found"}, status_code=404)
        if not path.is_file():
            return JSONResponse({"detail": "Not found"}, status_code=404)
        return FileResponse(str(path))

    @app.get("/media/videos/{filename}")
    def serve_video(filename: str):
        root = timelapse_dir.resolve()
        path = (timelapse_dir / filename).resolve()
        if not str(path).startswith(str(root)):
            return JSONResponse({"detail": "Not found"}, status_code=404)
        if path.is_file():
            return FileResponse(str(path))
        perm = (timelapse_dir / "permanent" / filename).resolve()
        if str(perm).startswith(str(root)) and perm.is_file():
            return FileResponse(str(perm))
        return JSONResponse({"detail": "Not found"}, status_code=404)

    # --- Dashboard ---

    @app.get("/", response_class=HTMLResponse)
    def dashboard(request: Request):
        from datetime import date, datetime
        today = date.today().isoformat()

        # Find latest snapshot across all dates
        latest_snapshot = None
        latest_snapshot_url = None
        latest_snapshot_iso = None
        snapshot_count_today = 0
        all_dates = sorted(
            [d.name for d in snapshot_dir.iterdir() if d.is_dir()],
            reverse=True,
        ) if snapshot_dir.exists() else []
        if all_dates:
            for date_str in all_dates:
                snaps = sorted((snapshot_dir / date_str).glob("*.jpg"), reverse=True)
                if snaps:
                    latest_snapshot = snaps[0].name
                    latest_snapshot_url = f"/media/snapshots/{date_str}/{latest_snapshot}"
                    stem = snaps[0].stem
                    m = _SNAPSHOT_TS_RE.search(stem)
                    if m:
                        latest_snapshot_iso = f"{m.group(1)}T{m.group(2).replace('-', ':')}"
                    break
            today_dir = snapshot_dir / today
            if today_dir.exists():
                snapshot_count_today = len(list(today_dir.glob("*.jpg")))

        # Find today's video
        today_video = None
        today_video_iso = None
        today_video_path = timelapse_dir / f"timelapse_{today}.mp4"
        if today_video_path.is_file():
            today_video = f"timelapse_{today}.mp4"
            today_video_iso = datetime.fromtimestamp(today_video_path.stat().st_mtime).strftime("%Y-%m-%dT%H:%M:%S")

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

    # --- Snapshots ---

    @app.get("/snapshots", response_class=HTMLResponse)
    def snapshots_page(request: Request, date: str = ""):
        all_dates = sorted(
            [d.name for d in snapshot_dir.iterdir() if d.is_dir()],
            reverse=True,
        ) if snapshot_dir.exists() else []

        selected_date = date or (all_dates[0] if all_dates else "")
        if selected_date and not _re.fullmatch(r'\d{4}-\d{2}-\d{2}', selected_date):
            selected_date = ""
        snaps: list[str] = []
        if selected_date:
            day_dir = snapshot_dir / selected_date
            snaps = sorted(p.name for p in day_dir.glob("*.jpg")) if day_dir.exists() else []

        return app.state.render(
            "snapshots.html", request, "snapshots",
            all_dates=all_dates,
            selected_date=selected_date,
            snaps=snaps,
        )

    # --- Videos ---

    @app.get("/videos", response_class=HTMLResponse)
    def videos_page(request: Request, video: str = ""):
        daily = sorted(
            [f.name for f in timelapse_dir.glob("timelapse_????-??-??.mp4")],
            reverse=True,
        )
        perm_dir = timelapse_dir / "permanent"
        permanent = sorted(
            [f.name for f in perm_dir.glob("*.mp4")],
            reverse=True,
        ) if perm_dir.exists() else []

        all_videos = set(daily) | set(permanent)
        selected = video if video in all_videos else (daily[0] if daily else (permanent[0] if permanent else ""))

        return app.state.render(
            "videos.html", request, "videos",
            daily=daily,
            permanent=permanent,
            selected=selected,
        )

    # --- Settings ---

    _INT_FIELDS = {
        "PTZ_SETTLE_DELAY", "PTZ_SPEED", "CAMERA_CHANNEL",
        "SNAPSHOT_INTERVAL", "SUNRISE_SUNSET_WINDOW",
        "TIMELAPSE_FPS", "TIMELAPSE_RETENTION_DAYS",
        "TIMELAPSE_ARCHIVE_EVERY", "TIMELAPSE_STABILIZE_CROP",
        "TIMELAPSE_STABILIZE_SMOOTHING", "TIMELAPSE_STABILIZE_SHAKINESS",
        "TIMELAPSE_SUBTITLE_EVERY", "TIMELAPSE_BURNIN_EVERY",
    }
    _FLOAT_FIELDS = {"LATITUDE", "LONGITUDE"}
    _ALL_FIELDS = _INT_FIELDS | _FLOAT_FIELDS | {
        "CAMERA_IP",
        "CAMERA_PRESET_NAME", "CAMERA_HOME_PRESET",
        "SNAPSHOT_24_7",
        "TIMEZONE",
        "TIMELAPSE_INCLUDE_NIGHT", "TIMELAPSE_INCLUDE_TRANSITIONS",
        "TIMELAPSE_ALIGN", "TIMELAPSE_STABILIZE",
        "TIMELAPSE_SUBTITLES", "TIMELAPSE_BURNIN",
        "TIMELAPSE_RETAIN_ALL",
        "TIMELAPSE_DAILY_MODE",
    }

    from src.web.env_editor import read_env, write_env

    @app.get("/settings", response_class=HTMLResponse)
    def settings_get(request: Request):
        values = read_env(env_path)
        return app.state.render(
            "settings.html", request, "settings",
            values=values, errors={},
        )

    @app.post("/settings", response_class=HTMLResponse)
    async def settings_post(request: Request):
        form = await request.form()
        data = {k: v for k, v in dict(form).items() if k in _ALL_FIELDS}
        errors: dict[str, str] = {}

        for key, value in data.items():
            if key in _INT_FIELDS:
                try:
                    int(value)
                except ValueError:
                    errors[key] = "Must be an integer"
            elif key in _FLOAT_FIELDS:
                try:
                    float(value)
                except ValueError:
                    errors[key] = "Must be a number"

        if errors:
            values = read_env(env_path)
            values.update(data)
            return app.state.render(
                "settings.html", request, "settings",
                values=values, errors=errors,
            )

        write_env(env_path, data)
        import docker as docker_sdk
        try:
            dc = docker_sdk.from_env()
            dc.containers.get("reolink-preset-timelapse").restart()
            msg = "Settings saved - timelapse container restarted."
        except Exception:
            msg = "Settings saved. Restart the timelapse container to apply."
        return app.state.redirect_with_flash("/settings", msg)

    # --- Actions ---

    @app.post("/actions/capture")
    async def action_capture(request: Request, background_tasks: BackgroundTasks):
        from src.config import Config
        from src.camera import CameraClient

        env_vals = dotenv_values(str(env_path))
        for k, v in env_vals.items():
            os.environ[k] = v or ""

        try:
            cfg = Config.from_env()
        except Exception as exc:
            return app.state.redirect_with_flash("/", f"Config error: {exc}", "error")

        camera = CameraClient(
            ip=cfg.camera_ip,
            username=cfg.camera_username,
            password=cfg.camera_password,
            channel=cfg.camera_channel,
            ptz_speed=cfg.ptz_speed,
        )

        def do_capture():
            try:
                run_capture(cfg, camera)
            except Exception as exc:
                logging.getLogger("web.actions").error("Capture failed: %s", exc)

        import time
        from datetime import date
        since = time.time()
        background_tasks.add_task(do_capture)
        today = date.today().isoformat()
        if "application/json" in request.headers.get("accept", ""):
            return JSONResponse({"watch": today, "type": "snapshot", "since": since})
        return app.state.redirect_with_flash(
            f"/?watch={today}&type=snapshot&since={since}",
            "Capture triggered - check Snapshots in a moment.",
        )

    @app.post("/actions/timelapse")
    async def action_timelapse(request: Request, background_tasks: BackgroundTasks):
        from datetime import date

        form = await request.form()
        date_str = form.get("date", "") or date.today().isoformat()
        if not _re.fullmatch(r'\d{4}-\d{2}-\d{2}', date_str):
            date_str = date.today().isoformat()

        env_vals = dotenv_values(str(env_path))
        for k, v in env_vals.items():
            os.environ[k] = v or ""

        try:
            from src.config import Config
            cfg = Config.from_env()
        except Exception as exc:
            return app.state.redirect_with_flash("/videos", f"Config error: {exc}", "error")

        from src.timelapse import collect_snapshots as _collect_day
        if cfg.timelapse_daily_mode == "cumulative":
            snaps = collect_snapshots_through_date(snapshot_dir, date_str, include_night=cfg.timelapse_include_night, include_transitions=cfg.timelapse_include_transitions)
        else:
            snaps = _collect_day(snapshot_dir / date_str, include_night=cfg.timelapse_include_night, include_transitions=cfg.timelapse_include_transitions)
        output = timelapse_dir / f"timelapse_{date_str}.mp4"

        def do_build():
            try:
                build_timelapse(
                    snaps, output, fps=cfg.timelapse_fps,
                    align=cfg.timelapse_align, stabilize=cfg.timelapse_stabilize,
                    stabilize_crop=cfg.timelapse_stabilize_crop,
                    stabilize_smoothing=cfg.timelapse_stabilize_smoothing,
                    stabilize_shakiness=cfg.timelapse_stabilize_shakiness,
                    subtitles=cfg.timelapse_subtitles,
                    subtitle_every=cfg.timelapse_subtitle_every,
                    burnin=cfg.timelapse_burnin,
                    burnin_every_minutes=cfg.timelapse_burnin_every,
                )
            except Exception as exc:
                logging.getLogger("web.actions").error("Timelapse build failed: %s", exc)

        import time
        since = time.time()
        background_tasks.add_task(do_build)
        watch = f"timelapse_{date_str}.mp4"
        if "application/json" in request.headers.get("accept", ""):
            return JSONResponse({"watch": watch, "type": "video", "since": since})
        return app.state.redirect_with_flash(
            f"/videos?watch={watch}&type=video&since={since}",
            f"Building timelapse for {date_str} - check Videos in a moment.",
        )

    @app.post("/actions/timelapse/permanent")
    async def action_timelapse_permanent(request: Request, background_tasks: BackgroundTasks):
        from datetime import datetime

        env_vals = dotenv_values(str(env_path))
        for k, v in env_vals.items():
            os.environ[k] = v or ""

        try:
            from src.config import Config
            cfg = Config.from_env()
        except Exception as exc:
            return app.state.redirect_with_flash("/videos", f"Config error: {exc}", "error")

        all_snaps: list[Path] = []
        if snapshot_dir.exists():
            for day_dir in sorted(snapshot_dir.iterdir()):
                if day_dir.is_dir():
                    all_snaps.extend(collect_snapshots(day_dir, include_night=cfg.timelapse_include_night, include_transitions=cfg.timelapse_include_transitions))

        perm_dir = timelapse_dir / "permanent"
        perm_dir.mkdir(exist_ok=True)
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        output = perm_dir / f"timelapse_permanent_{ts}.mp4"

        def do_build():
            try:
                build_timelapse(
                    all_snaps, output, fps=cfg.timelapse_fps,
                    align=cfg.timelapse_align, stabilize=cfg.timelapse_stabilize,
                    stabilize_crop=cfg.timelapse_stabilize_crop,
                    stabilize_smoothing=cfg.timelapse_stabilize_smoothing,
                    stabilize_shakiness=cfg.timelapse_stabilize_shakiness,
                    subtitles=cfg.timelapse_subtitles,
                    subtitle_every=cfg.timelapse_subtitle_every,
                    burnin=cfg.timelapse_burnin,
                    burnin_every_minutes=cfg.timelapse_burnin_every,
                )
            except Exception as exc:
                logging.getLogger("web.actions").error("Permanent timelapse build failed: %s", exc)

        import time
        since = time.time()
        background_tasks.add_task(do_build)
        watch = f"timelapse_permanent_{ts}.mp4"
        if "application/json" in request.headers.get("accept", ""):
            return JSONResponse({"watch": watch, "type": "permanent", "since": since})
        return app.state.redirect_with_flash(
            f"/videos?watch={watch}&type=permanent&since={since}",
            "Building permanent timelapse - this may take several minutes.",
        )

    _STATUS_VIDEO_RE = _re.compile(r'^timelapse_\d{4}-\d{2}-\d{2}\.mp4$')
    _STATUS_PERM_RE  = _re.compile(r'^timelapse_permanent_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}\.mp4$')
    _STATUS_DATE_RE  = _re.compile(r'^\d{4}-\d{2}-\d{2}$')
    _SNAPSHOT_TS_RE  = _re.compile(r'(\d{4}-\d{2}-\d{2})_(\d{2}-\d{2}-\d{2})')

    @app.get("/api/status")
    def api_status(watch: str = "", type: str = "", since: float = 0.0):
        if type == "video":
            if not _STATUS_VIDEO_RE.match(watch):
                return JSONResponse({"ready": False})
            path = timelapse_dir / watch
            if path.is_file() and path.stat().st_mtime > since:
                return JSONResponse({"ready": True, "file": watch})
            return JSONResponse({"ready": False})

        if type == "permanent":
            if not _STATUS_PERM_RE.match(watch):
                return JSONResponse({"ready": False})
            path = timelapse_dir / "permanent" / watch
            if path.is_file() and path.stat().st_mtime > since:
                return JSONResponse({"ready": True, "file": watch})
            return JSONResponse({"ready": False})

        if type == "snapshot":
            if not _STATUS_DATE_RE.match(watch):
                return JSONResponse({"ready": False})
            day_dir = snapshot_dir / watch
            if day_dir.exists():
                for jpg in day_dir.glob("*.jpg"):
                    if jpg.stat().st_mtime > since:
                        return JSONResponse({"ready": True, "file": jpg.name})
            return JSONResponse({"ready": False})

        return JSONResponse({"ready": False})

    _VIDEO_NAME_RE = _re.compile(r'^[a-zA-Z0-9_\-\.]+\.mp4$')
    _SNAP_DATE_RE  = _re.compile(r'^\d{4}-\d{2}-\d{2}$')
    _SNAP_NAME_RE  = _re.compile(r'^[a-zA-Z0-9_\-\.]+\.jpg$')

    @app.delete("/api/videos/permanent/{filename}")
    def delete_permanent_video(filename: str):
        if not _VIDEO_NAME_RE.match(filename):
            return JSONResponse({"error": "invalid filename"}, status_code=400)
        path = timelapse_dir / "permanent" / filename
        if not path.exists():
            return JSONResponse({"error": "not found"}, status_code=404)
        path.unlink()
        return JSONResponse({"deleted": filename})

    @app.delete("/api/videos/{filename}")
    def delete_daily_video(filename: str):
        if not _VIDEO_NAME_RE.match(filename):
            return JSONResponse({"error": "invalid filename"}, status_code=400)
        path = timelapse_dir / filename
        if not path.exists():
            return JSONResponse({"error": "not found"}, status_code=404)
        path.unlink()
        return JSONResponse({"deleted": filename})

    @app.delete("/api/snapshots/{date}")
    def delete_snapshot_day(date: str):
        import shutil
        if not _SNAP_DATE_RE.match(date):
            return JSONResponse({"error": "invalid date"}, status_code=400)
        path = snapshot_dir / date
        if not path.exists():
            return JSONResponse({"error": "not found"}, status_code=404)
        shutil.rmtree(path)
        return JSONResponse({"deleted": date})

    @app.delete("/api/snapshots/{date}/{filename}")
    def delete_snapshot(date: str, filename: str):
        if not _SNAP_DATE_RE.match(date):
            return JSONResponse({"error": "invalid date"}, status_code=400)
        if not _SNAP_NAME_RE.match(filename):
            return JSONResponse({"error": "invalid filename"}, status_code=400)
        path = snapshot_dir / date / filename
        if not path.exists():
            return JSONResponse({"error": "not found"}, status_code=404)
        path.unlink()
        return JSONResponse({"deleted": filename})

    @app.get("/api/errors")
    def api_errors(since: float | None = None):
        import time
        import docker as docker_sdk
        if since is None:
            since = time.time() - 3600
        try:
            dc = docker_sdk.from_env()
            container = dc.containers.get("reolink-preset-timelapse")
            if container.status != "running":
                import datetime
                return JSONResponse({
                    "errors": [{
                        "timestamp": datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0, tzinfo=None).isoformat(),
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
            parts = line.split(" ", 5)  # [docker_ts, date, time_ms, level, logger, message]
            if len(parts) < 6:
                continue
            level = parts[3]
            if level not in ("ERROR", "CRITICAL"):
                continue
            docker_ts = parts[0].rstrip("Z").split(".")[0]
            entries.append({
                "timestamp": docker_ts,
                "level": level,
                "message": parts[5].strip(),
            })

        return JSONResponse({
            "errors": entries[-20:],
            "container_status": "running",
        })

    # Build progress lines to surface in the dashboard
    _LOG_PREFIXES = (
        "Aligning ",
        "Aligned ",
        "Timelapse saved:",
        "Stabilized timelapse saved:",
        "Stabilization analysis failed",
        "Aligning frame ",
    )
    _LOG_EXCLUDE = ("crop=",)

    @app.get("/api/log")
    def api_log(since: float | None = None):
        import time
        import docker as docker_sdk
        if since is None:
            since = time.time() - 3600
        try:
            dc = docker_sdk.from_env()
            container = dc.containers.get("reolink-timelapse-web")
            raw = container.logs(since=since, timestamps=True)
        except Exception:
            return JSONResponse({"lines": []})

        lines = []
        for raw_line in raw.splitlines():
            try:
                line = raw_line.decode("utf-8", errors="replace")
            except AttributeError:
                line = raw_line
            parts = line.split(" ", 5)
            if len(parts) < 6:
                continue
            if parts[3] != "INFO":
                continue
            message = parts[5].strip()
            if not any(message.startswith(p) for p in _LOG_PREFIXES):
                continue
            if any(x in message for x in _LOG_EXCLUDE):
                continue
            docker_ts = parts[0].rstrip("Z").split(".")[0]
            lines.append({"timestamp": docker_ts, "message": message})

        return JSONResponse({"lines": lines[-50:]})

    # Store for use by route functions defined in later tasks
    app.state.snapshot_dir = snapshot_dir
    app.state.timelapse_dir = timelapse_dir
    app.state.env_path = env_path
    app.state.templates = templates
    app.state.render = _render
    app.state.redirect_with_flash = _redirect_with_flash

    return app


def app():
    """uvicorn --factory entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s,000 %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    env_path = Path("/app/.env")
    snapshot_dir = Path(os.environ.get("SNAPSHOT_DIR", "/data/snapshots"))
    timelapse_dir = Path(os.environ.get("TIMELAPSE_DIR", "/data/timelapse"))
    return create_app(
        snapshot_dir=snapshot_dir,
        timelapse_dir=timelapse_dir,
        env_path=env_path,
    )
