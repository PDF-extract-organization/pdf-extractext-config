"""Caso de uso: el CRUD de la configuración centralizada."""

import re

from app.application.entities import ConfigEntry
from app.application.errors import (
    InvalidKeyError,
    KeyAlreadyExistsError,
    KeyNotFoundError,
    StaleIndexError,
)
from app.application.interfaces.config_repository import ConfigRepository

# <servicio>/<nombre>: al menos dos segmentos, así ninguna clave choca con /health
KEY_PATTERN = re.compile(r"[a-z0-9_-]+(/[a-z0-9_-]+)+")
PREFIX_PATTERN = re.compile(r"[a-z0-9_/-]*")

INVALID_KEY_DETAIL = (
    "Clave inválida: usa el formato <servicio>/<nombre>, en minúsculas, con dígitos, "
    "'_' o '-'. Por ejemplo summarizer/max_tokens."
)


class ConfigService:
    def __init__(self, repository: ConfigRepository):
        self._repository = repository

    async def create(self, key: str, value: str) -> ConfigEntry:
        _check_key(key)
        entry = await self._repository.create(key, value)
        if entry is None:
            raise KeyAlreadyExistsError(f"La clave '{key}' ya existe.")
        return entry

    async def get(self, key: str) -> ConfigEntry:
        _check_key(key)
        return await self._get_existing(key)

    async def list(self, prefix: str = "") -> list[ConfigEntry]:
        if not PREFIX_PATTERN.fullmatch(prefix) or ".." in prefix:
            raise InvalidKeyError(INVALID_KEY_DETAIL)
        return await self._repository.list(prefix)

    async def update(self, key: str, value: str, index: int | None = None) -> ConfigEntry:
        """Sin `index`, actualiza sobre la versión actual."""
        _check_key(key)
        current = await self._get_existing(key)
        expected = current.index if index is None else index
        updated = await self._repository.update(key, value, expected)
        if updated is None:
            raise _stale(key)
        return updated

    async def delete(self, key: str) -> None:
        _check_key(key)
        current = await self._get_existing(key)
        if not await self._repository.delete(key, current.index):
            raise _stale(key)

    async def is_available(self) -> bool:
        return await self._repository.is_available()

    async def _get_existing(self, key: str) -> ConfigEntry:
        entry = await self._repository.get(key)
        if entry is None:
            raise KeyNotFoundError(f"No existe la clave '{key}'.")
        return entry


def _check_key(key: str) -> None:
    if not KEY_PATTERN.fullmatch(key):
        raise InvalidKeyError(INVALID_KEY_DETAIL)


def _stale(key: str) -> StaleIndexError:
    return StaleIndexError(
        f"La clave '{key}' cambió desde que la leíste. Vuelve a leerla y repite el cambio."
    )
