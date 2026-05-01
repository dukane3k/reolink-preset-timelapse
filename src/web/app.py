from __future__ import annotations
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
        response = templates.TemplateResponse(
            template,
            {"request": request, "active": active,
             "flash_message": flash_message, "flash_type": flash_type, **ctx},
        )
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

    # Store for use by route functions defined in later tasks
    app.state.snapshot_dir = snapshot_dir
    app.state.timelapse_dir = timelapse_dir
    app.state.env_path = env_path
    app.state.templates = templates
    app.state.render = _render
    app.state.redirect_with_flash = _redirect_with_flash

    return app
