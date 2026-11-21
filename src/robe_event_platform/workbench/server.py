from pathlib import Path

from fastapi import Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from robe_event_platform.workbench.api import app

UI = Path("/app/ui/dist")
if not (UI / "index.html").is_file():
    raise RuntimeError("Built workbench UI is missing")


@app.middleware("http")
async def local_host_only(request: Request, call_next):
    if request.headers.get("host") not in {"127.0.0.1:8083", "localhost:8083", "127.0.0.1:8000"}:
        return Response(status_code=400)
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    return response


app.mount("/assets", StaticFiles(directory=UI / "assets"), name="assets")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(UI / "index.html")
