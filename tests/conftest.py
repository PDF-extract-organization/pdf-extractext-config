"""Dobles de prueba compartidos por la suite."""

import pytest

from app.application.entities import ConfigEntry
from app.application.interfaces.config_repository import (
    ConfigRepository,
    ConfigStoreUnavailableError,
)


class FakeRepository(ConfigRepository):
    """Repositorio en memoria con el mismo contrato que el de Consul, check-and-set incluido."""

    def __init__(self, available: bool = True):
        self.entries: dict[str, ConfigEntry] = {}
        self._available = available
        self._last_index = 0

    async def get(self, key: str) -> ConfigEntry | None:
        self._fail_if_unavailable()
        return self.entries.get(key)

    async def list(self, prefix: str) -> list[ConfigEntry]:
        self._fail_if_unavailable()
        return [e for k, e in sorted(self.entries.items()) if k.startswith(prefix)]

    async def create(self, key: str, value: str) -> ConfigEntry | None:
        self._fail_if_unavailable()
        if key in self.entries:
            return None
        return self._store(key, value)

    async def update(self, key: str, value: str, index: int) -> ConfigEntry | None:
        self._fail_if_unavailable()
        current = self.entries.get(key)
        if current is None or current.index != index:
            return None
        return self._store(key, value)

    async def delete(self, key: str, index: int) -> bool:
        self._fail_if_unavailable()
        current = self.entries.get(key)
        if current is None or current.index != index:
            return False
        del self.entries[key]
        return True

    async def is_available(self) -> bool:
        return self._available

    def change_behind_the_back(self, key: str, value: str) -> ConfigEntry:
        """Simula que otro cliente cambia la clave entre una lectura y una escritura."""
        return self._store(key, value)

    def _store(self, key: str, value: str) -> ConfigEntry:
        self._last_index += 1
        self.entries[key] = ConfigEntry(key=key, value=value, index=self._last_index)
        return self.entries[key]

    def _fail_if_unavailable(self) -> None:
        if not self._available:
            raise ConfigStoreUnavailableError("Consul no responde.")


@pytest.fixture
def fake_repository() -> FakeRepository:
    return FakeRepository()
