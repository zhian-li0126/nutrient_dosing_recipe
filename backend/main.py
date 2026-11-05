"""FastAPI entry point, static frontend, and narrow cross-origin configuration."""

from collections import deque
import logging
import os
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.types import ASGIApp, Receive, Scope, Send

from .fertilizer_config import public_configuration
from .models import CalculationRequest, CalculationResponse
from .nutrient_optimizer import calculate_nutrients


LOGGER = logging.getLogger(__name__)
FRONTEND_DIRECTORY = Path(__file__).resolve().parents[1] / "frontend"
MAX_BODY_BYTES = 64 * 1024


class CalculationBodyLimit:
    """Bound the small JSON calculation request, including chunked transfers."""

    def __init__(self, app: ASGIApp, max_bytes: int = MAX_BODY_BYTES):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("method") != "POST" or scope.get("path") != "/api/calculate":
            await self.app(scope, receive, send)
            return
        messages: deque = deque()
        total = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            messages.append(message)
            total += len(message.get("body", b""))
            if total > self.max_bytes:
                response = JSONResponse(status_code=413, content={"detail": "Calculation request is too large."})
                await response(scope, receive, send)
                return
            if not message.get("more_body", False):
                break

        async def buffered_receive():
            if messages:
                return messages.popleft()
            return await receive()

        await self.app(scope, buffered_receive, send)


def _allowed_origins() -> list[str]:
    origins = []
    for item in os.getenv("CORS_ORIGINS", "").split(","):
        origin = item.strip().rstrip("/")
        if not origin:
            continue
        parsed = urlsplit(origin)
        if (parsed.scheme not in {"http", "https"} or not parsed.netloc
                or parsed.path or parsed.query or parsed.fragment or parsed.username or parsed.password):
            raise ValueError("CORS_ORIGINS must contain origins such as https://account.github.io, without URL paths.")
        if origin not in origins:
            origins.append(origin)
    return origins


def create_app() -> FastAPI:
    """Build an app using environment settings at creation time."""
    docs_enabled = os.getenv("ENABLE_API_DOCS", "false").lower() in {"true", "1", "yes"}
    application = FastAPI(
        title="Nutrient Solution Calculator",
        version="1.0.0",
        docs_url="/api/docs" if docs_enabled else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if docs_enabled else None,
    )

    application.add_middleware(CalculationBodyLimit)
    origins = _allowed_origins()
    if origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=False,
            allow_methods=["GET", "POST"],
            allow_headers=["Content-Type"],
        )

    @application.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, exc: RequestValidationError):
        # Omitting raw input/context also makes NaN/Infinity validation errors
        # JSON-safe and prevents echoing arbitrarily large user inputs.
        errors = [
            {"loc": list(error["loc"]), "msg": error["msg"], "type": error["type"]}
            for error in exc.errors()
        ]
        return JSONResponse(status_code=422, content={"detail": errors})

    @application.exception_handler(Exception)
    async def unexpected_error(_request: Request, exc: Exception):
        LOGGER.error("Unexpected application error", exc_info=exc)
        return JSONResponse(status_code=500, content={"detail": "The calculation service encountered an unexpected error."})

    @application.get("/api/health")
    def health():
        return {"status": "ok"}

    @application.get("/api/config")
    def configuration():
        return public_configuration()

    @application.post("/api/calculate", response_model=CalculationResponse)
    def calculate(request: CalculationRequest):
        try:
            return calculate_nutrients(request)
        except ValueError as exc:
            LOGGER.info("Unrepresentable calculation: %s", exc)
            return JSONResponse(status_code=422, content={"detail": str(exc)})
        except Exception:
            LOGGER.exception("Nutrient calculation failed")
            return JSONResponse(status_code=500, content={"detail": "The calculation service encountered an unexpected error."})

    # The repository root and backend files are never mounted as static assets.
    # API-only deployments also work when the frontend directory is absent.
    if FRONTEND_DIRECTORY.is_dir():
        application.mount("/", StaticFiles(directory=FRONTEND_DIRECTORY, html=True), name="frontend")
    return application


app = create_app()
