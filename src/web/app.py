from __future__ import annotations
import re as _re
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

_TEMPLATES_DIR = Path(__file__).parent / "templates"


def create_app(
    snapshot_dir: Path,
    timelapse_dir: Path,
    env_path: Path,
) -> FastAPI:
    app = FastAPI()
    templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

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
                    break
            today_dir = snapshot_dir / today
            if today_dir.exists():
                snapshot_count_today = len(list(today_dir.glob("*.jpg")))

        # Find today's video
        today_video = None
        today_video_path = timelapse_dir / f"timelapse_{today}.mp4"
        if today_video_path.is_file():
            today_video = f"timelapse_{today}.mp4"

        return app.state.render(
            "dashboard.html", request, "dashboard",
            latest_snapshot=latest_snapshot,
            latest_snapshot_url=latest_snapshot_url,
            snapshot_count_today=snapshot_count_today,
            today=today,
            today_video=today_video,
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
        "CAMERA_IP", "CAMERA_USERNAME", "CAMERA_PASSWORD",
        "CAMERA_PRESET_NAME", "CAMERA_HOME_PRESET",
        "SNAPSHOT_24_7",
        "TIMEZONE",
        "TIMELAPSE_INCLUDE_NIGHT",
        "TIMELAPSE_ALIGN", "TIMELAPSE_STABILIZE",
        "TIMELAPSE_SUBTITLES", "TIMELAPSE_BURNIN",
        "TIMELAPSE_RETAIN_ALL",
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
        return app.state.redirect_with_flash("/settings", "Settings saved. Restart the timelapse container to apply.")

    # Store for use by route functions defined in later tasks
    app.state.snapshot_dir = snapshot_dir
    app.state.timelapse_dir = timelapse_dir
    app.state.env_path = env_path
    app.state.templates = templates
    app.state.render = _render
    app.state.redirect_with_flash = _redirect_with_flash

    return app
