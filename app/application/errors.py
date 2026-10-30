"""Errores del caso de uso. La presentación los traduce a códigos HTTP."""


class InvalidKeyError(ValueError):
    pass


class KeyNotFoundError(LookupError):
    pass


class KeyAlreadyExistsError(Exception):
    pass


class StaleIndexError(Exception):
    """Otro cliente cambió la clave desde que se leyó."""
