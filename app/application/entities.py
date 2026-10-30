"""Entidades del dominio. Viven aparte de los puertos que las usan."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ConfigEntry:
    key: str
    value: str
    # Versión de la clave: cambia en cada escritura (el ModifyIndex de Consul)
    index: int
