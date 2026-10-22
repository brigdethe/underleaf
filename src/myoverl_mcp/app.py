from __future__ import annotations

from pathlib import Path
import base64
import json
import mimetypes
import os
import tempfile
import uuid

mimetypes.add_type("text/javascript", ".mjs")

from starlette.applications import Starlette
from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, Response
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles
from starlette.types import ASGIApp, Receive, Scope, Send

try:
    from mcp.server.transport_security import TransportSecuritySettings
except ImportError:
    TransportSecuritySettings = None

from myoverl_mcp.compile import CompileError, compile_pdf, compile_preview
from myoverl_mcp.errors import (
    ConflictError,
    NotFoundError,
    SourceProtectedError,
    ValidationError,
)
from myoverl_mcp.seed import seed_bright
from myoverl_mcp.server import make_server
from myoverl_mcp.store import ResumeStore
from myoverl_mcp.tools import (
    add_person,
    add_project,
    copy_resume,
    get_resume,
    list_resumes,
    rename_resume,
    update_resume,
)

WEB_DIR = Path(__file__).parent / "web"


def _json(resume) -> dict:
    return json.loads(resume.model_dump_json())


def _error(exc: Exception) -> JSONResponse:
    if isinstance(exc, NotFoundError):
        return JSONResponse({"error": "resume not found"}, status_code=404)
    if isinstance(exc, ConflictError):
        return JSONResponse(
            {"error": "revision conflict", "current_revision": exc.current_revision},
            status_code=409,
        )
    if isinstance(exc, SourceProtectedError):
        return JSONResponse({"error": "source is protected; copy_resume first"}, status_code=403)
    if isinstance(exc, ValidationError):
        return JSONResponse({"error": str(exc)}, status_code=400)
    if isinstance(exc, CompileError):
        return JSONResponse({"error": str(exc), "log": exc.log}, status_code=500)
    raise exc


def _request_id(body: dict) -> str:
    return str(body.get("request_id") or f"ui-{uuid.uuid4().hex[:12]}")


class AuthMiddleware:
    def __init__(self, app: ASGIApp, api_key: str | None = None) -> None:
        self.app = app
        self.api_key = api_key

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and self.api_key:
            path = scope.get("path", "")
            if path.startswith("/api") or path.startswith("/mcp"):
                headers = dict(scope.get("headers", []))
                auth_header = headers.get(b"authorization", b"").decode("latin-1")
                x_api_key = headers.get(b"x-api-key", b"").decode("latin-1")
                query_string = scope.get("query_string", b"").decode("latin-1")

                token = None
                if auth_header.lower().startswith("bearer "):
                    token = auth_header[7:].strip()
                elif x_api_key:
                    token = x_api_key.strip()
                elif "token=" in query_string:
                    from urllib.parse import parse_qs

                    params = parse_qs(query_string)
                    token_list = params.get("token", [])
                    if token_list:
                        token = token_list[0].strip()

                if not token or token != self.api_key:
                    res = JSONResponse(
                        {"error": "unauthorized: invalid or missing API key"},
                        status_code=401,
                        headers={"WWW-Authenticate": "Bearer"},
                    )
                    await res(scope, receive, send)
                    return

        await self.app(scope, receive, send)


def create_app(store: ResumeStore | None = None, api_key: str | None = None) -> Starlette:
    if store is None:
        data_dir = Path(os.environ.get("MYOVERL_DATA", Path.cwd() / "data"))
        store = ResumeStore(data_dir)
        if not store.list_all():
            seed_bright(store)

    if api_key is None:
        api_key = os.environ.get("UNDERLEAF_API_KEY") or os.environ.get("MCP_AUTH_TOKEN")

    async def homepage(request: Request) -> FileResponse:
        return FileResponse(WEB_DIR / "index.html")

    async def app_js(request: Request) -> FileResponse:
        return FileResponse(WEB_DIR / "app.js", media_type="text/javascript")

    async def pdf_view_js(request: Request) -> FileResponse:
        return FileResponse(WEB_DIR / "pdf-view.mjs", media_type="text/javascript")

    async def people(request: Request) -> Response:
        try:
            if request.method == "GET":
                sources = [r for r in store.list_all() if r.role == "source"]
                return JSONResponse(
                    [
                        {
                            "name": r.name,
                            "source_id": r.resume_id,
                            "heading": r.heading.name,
                            "revision": r.revision,
                        }
                        for r in sources
                    ]
                )
            body = await request.json()
            bright = next(r for r in store.list_all() if r.role == "source" and r.name == "Bright")
            created = add_person(
                store,
                bright.resume_id,
                bright.revision,
                _request_id(body),
                body.get("person_name", ""),
                body.get("heading_name", ""),
            )
            return JSONResponse(_json(created))
        except (NotFoundError, ConflictError, ValidationError, StopIteration) as exc:
            if isinstance(exc, StopIteration):
                return JSONResponse({"error": "Bright source is missing"}, status_code=404)
            return _error(exc)

    async def resumes(request: Request) -> Response:
        person = request.query_params.get("person")
        rows = list_resumes(store)
        if person:
            source = next(
                (r for r in store.list_all() if r.role == "source" and r.name == person),
                None,
            )
            if source is None:
                return JSONResponse({"error": "person not found"}, status_code=404)
            rows = [
                r
                for r in rows
                if r.resume_id == source.resume_id or r.resume_id in {
                    c.resume_id for c in store.list_all() if c.source_id == source.resume_id
                }
            ]
        return JSONResponse([_json(r) for r in rows])

    async def resume_one(request: Request) -> Response:
        try:
            return JSONResponse(_json(get_resume(store, request.path_params["resume_id"])))
        except NotFoundError as exc:
            return _error(exc)

    async def resume_copy(request: Request) -> Response:
        try:
            body = await request.json()
            current = get_resume(store, request.path_params["resume_id"])
            copied = copy_resume(
                store,
                current.resume_id,
                current.revision,
                _request_id(body),
                body.get("copy_name", "Untitled copy"),
            )
            return JSONResponse(_json(copied))
        except (NotFoundError, ConflictError, ValidationError) as exc:
            return _error(exc)

    async def resume_rename(request: Request) -> Response:
        try:
            body = await request.json()
            current = get_resume(store, request.path_params["resume_id"])
            updated = rename_resume(
                store,
                current.resume_id,
                current.revision,
                _request_id(body),
                body.get("name", ""),
            )
            return JSONResponse(_json(updated))
        except (NotFoundError, ConflictError, ValidationError) as exc:
            return _error(exc)

    async def resume_update(request: Request) -> Response:
        try:
            body = await request.json()
            current = get_resume(store, request.path_params["resume_id"])
            updated = update_resume(
                store,
                current.resume_id,
                body.get("base_revision", current.revision),
                _request_id(body),
                heading=body.get("heading"),
                bullets=body.get("bullets"),
                entry_fields=body.get("entry_fields"),
                skill_rows=body.get("skill_rows"),
                coursework=body.get("coursework"),
            )
            return JSONResponse(_json(updated))
        except (NotFoundError, ConflictError, ValidationError, SourceProtectedError) as exc:
            return _error(exc)

    async def resume_add_project(request: Request) -> Response:
        try:
            body = await request.json()
            current = get_resume(store, request.path_params["resume_id"])
            updated = add_project(
                store,
                current.resume_id,
                current.revision,
                _request_id(body),
                title=body.get("title", ""),
                technologies=body.get("technologies"),
                link_url=body.get("link_url") or None,
                link_text=body.get("link_text") or None,
                bullets=body.get("bullets") or [],
            )
            return JSONResponse(_json(updated))
        except (NotFoundError, ConflictError, ValidationError) as exc:
            return _error(exc)

    async def resume_pdf(request: Request) -> Response:
        try:
            resume = get_resume(store, request.path_params["resume_id"])
            def build() -> bytes:
                with tempfile.TemporaryDirectory() as raw:
                    path = compile_pdf(resume, Path(raw) / "resume.pdf")
                    return path.read_bytes()

            pdf = await run_in_threadpool(build)
            filename = f"{resume.name.replace(' ', '_')}.pdf"
            from urllib.parse import quote
            return Response(pdf, media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"})
        except (NotFoundError, CompileError) as exc:
            return _error(exc)

    async def resume_preview(request: Request) -> Response:
        try:
            resume = get_resume(store, request.path_params["resume_id"])
            revision = request.query_params.get("revision")
            if revision is not None and revision != str(resume.revision):
                return JSONResponse({"error": "revision conflict", "current_revision": resume.revision}, status_code=409)
            pdf, fields = await run_in_threadpool(compile_preview, resume)
            return JSONResponse({
                "pdf": base64.b64encode(pdf).decode("ascii"),
                "fields": fields,
                "revision": resume.revision,
                "resume_id": resume.resume_id,
            }, headers={"Cache-Control": "no-store"})
        except (NotFoundError, CompileError) as exc:
            return _error(exc)

    sec = None
    if TransportSecuritySettings is not None:
        sec = TransportSecuritySettings(enable_dns_rebinding_protection=False)

    mcp_app = make_server(store).streamable_http_app(
        streamable_http_path="/mcp",
        transport_security=sec,
    )
    extra = [
        Route("/", homepage),
        Route("/app.js", app_js),
        Route("/pdf-view.mjs", pdf_view_js),
        Mount("/vendor", StaticFiles(directory=WEB_DIR / "vendor", check_dir=False), name="vendor"),
        Mount("/fonts", StaticFiles(directory=WEB_DIR / "fonts"), name="fonts"),
        Route("/api/people", people, methods=["GET", "POST"]),
        Route("/api/resumes", resumes),
        Route("/api/resumes/{resume_id}", resume_one),
        Route("/api/resumes/{resume_id}/copy", resume_copy, methods=["POST"]),
        Route("/api/resumes/{resume_id}/rename", resume_rename, methods=["POST"]),
        Route("/api/resumes/{resume_id}/update", resume_update, methods=["POST"]),
        Route("/api/resumes/{resume_id}/projects", resume_add_project, methods=["POST"]),
        Route("/api/resumes/{resume_id}/pdf", resume_pdf),
        Route("/api/resumes/{resume_id}/preview", resume_preview),
    ]
    mcp_app.router.routes[0:0] = extra
    if api_key:
        mcp_app.add_middleware(AuthMiddleware, api_key=api_key)
    return mcp_app


def main() -> None:
    import argparse

    import uvicorn

    default_host = os.environ.get("HOST", "127.0.0.1")
    default_port = int(os.environ.get("PORT", "8765"))
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=default_host)
    parser.add_argument("--port", type=int, default=default_port)
    parser.add_argument(
        "--api-key",
        default=os.environ.get("UNDERLEAF_API_KEY") or os.environ.get("MCP_AUTH_TOKEN"),
        help="Optional API key for authenticating /mcp and /api endpoints",
    )
    args = parser.parse_args()

    if args.api_key:
        os.environ["UNDERLEAF_API_KEY"] = args.api_key
        print("[Underleaf] Authentication enabled with API key.")
    else:
        print("[Underleaf] Running in unauthenticated local mode (set UNDERLEAF_API_KEY to protect).")

    public_base = (
        os.environ.get("UNDERLEAF_PUBLIC_BASE")
        or os.environ.get("MYOVERL_PUBLIC_BASE")
    )
    if not public_base:
        if os.environ.get("RAILWAY_PUBLIC_DOMAIN"):
            public_base = f"https://{os.environ['RAILWAY_PUBLIC_DOMAIN']}"
        elif os.environ.get("RENDER_EXTERNAL_URL"):
            public_base = os.environ["RENDER_EXTERNAL_URL"].rstrip("/")
        else:
            public_base = f"http://{args.host}:{args.port}"
    os.environ["MYOVERL_PUBLIC_BASE"] = public_base
    os.environ["UNDERLEAF_PUBLIC_BASE"] = public_base

    uvicorn.run(create_app(api_key=args.api_key), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
