"""Puerto del almacén de configuración. Las claves son relativas: el prefijo es cosa del
adaptador. Las escrituras son check-and-set para no pisar cambios ajenos."""

from abc import ABC, abstractmethod

from app.application.entities import ConfigEntry


class ConfigStoreUnavailableError(Exception):
    """El almacén no responde."""


class ConfigRepository(ABC):
    @abstractmethod
    async def get(self, key: str) -> ConfigEntry | None: ...

    @abstractmethod
    async def list(self, prefix: str) -> list[ConfigEntry]:
        """Ordenadas por clave."""

    @abstractmethod
    async def create(self, key: str, value: str) -> ConfigEntry | None:
        """None si la clave ya existía: no la pisa."""

    @abstractmethod
    async def update(self, key: str, value: str, index: int) -> ConfigEntry | None:
        """Solo si la versión actual es `index`. None si no lo es o la clave ya no existe."""

    @abstractmethod
    async def delete(self, key: str, index: int) -> bool:
        """Solo si la versión actual es `index`. True si se borró."""

    @abstractmethod
    async def is_available(self) -> bool:
        """True si el almacén responde."""
