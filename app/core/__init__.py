"""Configuración leída de variables de entorno o del .env."""

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    consul_host: str = "localhost"
    consul_port: int = 8500
    consul_prefix: str = "pdf-extractext/"
    # Que las peticiones y /health fallen rápido si Consul no está
    consul_timeout_seconds: float = 3.0

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("consul_prefix")
    @classmethod
    def _prefix_ends_with_slash(cls, prefix: str) -> str:
        return prefix if prefix.endswith("/") else prefix + "/"
