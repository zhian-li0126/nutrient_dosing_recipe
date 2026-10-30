"""FastAPI entry point for the nutrient solution calculator."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.models import CalculateRequest
from backend.nutrient_optimizer import calculate_nutrient_addition


LOGGER = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIRECTORY = PROJECT_ROOT / "frontend"


def _comma_separated_environment_value(name: str) -> list[str]:
    return [value.strip() for value in os.getenv(name, "").split(",") if value.strip()]


def _validation_details(exception: RequestValidationError) -> list[dict[str, Any]]:
    details: list[dict[str, Any]] = []
    for error in exception.errors():
        details.append(
            {
                "field": ".".join(str(part) for part in error["loc"] if part != "body"),
                "message": error["msg"],
                "type": error["type"],
            }
        )
    return details


docs_enabled = os.getenv("ENABLE_API_DOCS", "false").lower() in {"1", "true", "yes"}
app = FastAPI(
    title="Nutrient Solution Calculator API",
    version="1.0.0",
    debug=False,
    docs_url="/api/docs" if docs_enabled else None,
    redoc_url=None,
    openapi_url="/api/openapi.json" if docs_enabled else None,
)

cors_origins = _comma_separated_environment_value("CORS_ORIGINS")
if cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=False,
        allow_methods=["POST", "GET"],
        allow_headers=["Content-Type"],
    )


@app.middleware("http")
async def add_security_headers(request: Request, call_next: Any) -> Any:
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self'; "
        "img-src 'self' data:; connect-src 'self'; object-src 'none'; "
        "base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
    )
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    return response


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    _request: Request, exception: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "validation_error",
                "message": "Please correct the invalid calculation inputs.",
                "details": _validation_details(exception),
            }
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(
    _request: Request, exception: Exception
) -> JSONResponse:
    LOGGER.exception("Unhandled calculation error", exc_info=exception)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "calculation_error",
                "message": "The calculation could not be completed. Please verify the inputs.",
            }
        },
    )


@app.post("/api/calculate")
def calculate(request: CalculateRequest) -> dict[str, Any]:
    """Return calculated outputs while keeping the optimization model server-side."""
    return calculate_nutrient_addition(
        target=request.target,
        current=request.current,
        reservoir_volume_l=request.reservoir_volume,
        stock_concentrations=request.stock_concentrations,
    )


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(FRONTEND_DIRECTORY / "index.html")


app.mount(
    "/static",
    StaticFiles(directory=FRONTEND_DIRECTORY),
    name="static",
)
