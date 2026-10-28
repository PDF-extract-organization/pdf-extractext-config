"""Adaptador del puerto ConfigRepository para el KV de Consul, con py-consul asíncrono."""

import asyncio
from functools import wraps

import aiohttp
import consul
import consul.aio

from app.application.entities import ConfigEntry
from app.application.interfaces.config_repository import (
    ConfigRepository,
    ConfigStoreUnavailableError,
)

CONNECTION_ERRORS = (aiohttp.ClientError, asyncio.TimeoutError, consul.ConsulException)


def _translate_errors(method):
    """Que la API responda 503 y no 500 cuando Consul no está."""

    @wraps(method)
    async def wrapper(*args, **kwargs):
        try:
            return await method(*args, **kwargs)
        except CONNECTION_ERRORS as error:
            raise ConfigStoreUnavailableError(f"Consul no responde: {error}") from error

    return wrapper


class ConsulConfigRepository(ConfigRepository):
    def __init__(self, client: consul.aio.Consul, prefix: str):
        self._client = client
        self._prefix = prefix

    @_translate_errors
    async def get(self, key: str) -> ConfigEntry | None:
        _, data = await self._client.kv.get(self._prefix + key)
        return self._to_entry(data) if data else None

    @_translate_errors
    async def list(self, prefix: str) -> list[ConfigEntry]:
        _, items = await self._client.kv.get(self._prefix + prefix, recurse=True)
        # La interfaz de Consul crea las carpetas como claves terminadas en "/"
        entries = [self._to_entry(d) for d in items or [] if not d["Key"].endswith("/")]
        return sorted(entries, key=lambda e: e.key)

    @_translate_errors
    async def create(self, key: str, value: str) -> ConfigEntry | None:
        # cas=0: solo escribe si la clave no existe
        if not await self._client.kv.put(self._prefix + key, value, cas=0):
            return None
        return await self.get(key)

    @_translate_errors
    async def update(self, key: str, value: str, index: int) -> ConfigEntry | None:
        if not await self._client.kv.put(self._prefix + key, value, cas=index):
            return None
        return await self.get(key)

    @_translate_errors
    async def delete(self, key: str, index: int) -> bool:
        return await self._client.kv.delete(self._prefix + key, cas=index)

    async def is_available(self) -> bool:
        # Sin líder el KV no responde, aunque el proceso esté vivo
        try:
            return bool(await self._client.status.leader())
        except CONNECTION_ERRORS:
            return False

    async def close(self) -> None:
        await self._client.http.close()

    def _to_entry(self, data: dict) -> ConfigEntry:
        return ConfigEntry(
            key=data["Key"].removeprefix(self._prefix),
            # Consul devuelve None para un valor vacío
            value=(data["Value"] or b"").decode("utf-8"),
            index=data["ModifyIndex"],
        )
