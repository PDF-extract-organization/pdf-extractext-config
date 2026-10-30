"""Cableado de dependencias. Router y main lo importan; él no importa a ninguno."""

from functools import lru_cache

import consul.aio

from app.application.services.config_service import ConfigService
from app.core import Settings
from app.infrastructure.consul_repository import ConsulConfigRepository


@lru_cache
def get_settings() -> Settings:
    return Settings()


# El cliente asíncrono solo se puede crear con el event loop en marcha: por eso se crea
# en la primera petición y no al importar el módulo.
@lru_cache  # get_config_service, que la llama, debe ser async (ver abajo)
def get_repository() -> ConsulConfigRepository:
    settings = get_settings()
    client = consul.aio.Consul(
        host=settings.consul_host,
        port=settings.consul_port,
        connections_timeout=settings.consul_timeout_seconds,
    )
    return ConsulConfigRepository(client, settings.consul_prefix)


# async aunque no espere nada: FastAPI ejecuta las dependencias síncronas en un hilo
# aparte, sin event loop, y ahí crear el cliente de Consul falla
async def get_config_service() -> ConfigService:
    return ConfigService(get_repository())
