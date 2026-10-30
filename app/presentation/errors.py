"""Traducción de los errores del caso de uso a respuestas HTTP `{"detail": "..."}`."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.application.errors import (
    InvalidKeyError,
    KeyAlreadyExistsError,
    KeyNotFoundError,
    StaleIndexError,
)
from app.application.interfaces.config_repository import ConfigStoreUnavailableError

UNAVAILABLE_DETAIL = "Consul no responde. Inténtalo de nuevo en unos segundos."

STATUS_BY_ERROR = {
    InvalidKeyError: 422,
    KeyNotFoundError: 404,
    KeyAlreadyExistsError: 409,
    StaleIndexError: 409,
}


def register_error_handlers(app: FastAPI) -> None:
    for error, status_code in STATUS_BY_ERROR.items():
        app.add_exception_handler(error, _handler(status_code))

    @app.exception_handler(ConfigStoreUnavailableError)
    async def unavailable(request: Request, error: ConfigStoreUnavailableError):
        # El detalle técnico no sale del servicio
        return JSONResponse(status_code=503, content={"detail": UNAVAILABLE_DETAIL})


def _handler(status_code: int):
    async def handler(request: Request, error: Exception):
        return JSONResponse(status_code=status_code, content={"detail": str(error)})

    return handler
