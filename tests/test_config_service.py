"""Tests del caso de uso con un repositorio en memoria."""

import pytest

from app.application.errors import (
    InvalidKeyError,
    KeyAlreadyExistsError,
    KeyNotFoundError,
    StaleIndexError,
)
from app.application.services.config_service import ConfigService
from tests.conftest import FakeRepository


@pytest.fixture
def service(fake_repository) -> ConfigService:
    return ConfigService(fake_repository)


# --- Claves válidas ---


@pytest.mark.parametrize(
    "key", ["summarizer/max_tokens", "web/cache-enabled", "a/b/c", "extractor/max_file_size_mb2"]
)
async def test_acepta_claves_servicio_barra_nombre(service, key):
    entry = await service.create(key, "1")

    assert entry.key == key


@pytest.mark.parametrize(
    "key",
    [
        "health",  # un solo segmento: chocaría con /health
        "",
        "summarizer/",
        "/summarizer/model",
        "summarizer//model",
        "Summarizer/Model",
        "summarizer/max tokens",
        "summarizer/../secreto",
        "summarizer/modelo-ñ",
    ],
)
async def test_rechaza_claves_invalidas_en_todas_las_operaciones(service, key):
    with pytest.raises(InvalidKeyError):
        await service.create(key, "1")
    with pytest.raises(InvalidKeyError):
        await service.get(key)
    with pytest.raises(InvalidKeyError):
        await service.update(key, "1")
    with pytest.raises(InvalidKeyError):
        await service.delete(key)


# --- Crear ---


async def test_create_guarda_la_clave_y_devuelve_su_indice(service, fake_repository):
    entry = await service.create("summarizer/max_tokens", "5000")

    assert entry.value == "5000"
    assert entry.index > 0
    assert fake_repository.entries["summarizer/max_tokens"] == entry


async def test_create_de_una_clave_existente_falla_sin_pisarla(service, fake_repository):
    original = await service.create("summarizer/max_tokens", "5000")

    with pytest.raises(KeyAlreadyExistsError):
        await service.create("summarizer/max_tokens", "1")

    assert fake_repository.entries["summarizer/max_tokens"] == original


# --- Leer y listar ---


async def test_get_devuelve_la_entrada(service):
    created = await service.create("summarizer/model", "un-modelo")

    assert await service.get("summarizer/model") == created


async def test_get_de_una_clave_inexistente_falla(service):
    with pytest.raises(KeyNotFoundError):
        await service.get("summarizer/model")


async def test_list_sin_prefijo_devuelve_todo_ordenado_por_clave(service):
    await service.create("web/cache_enabled", "true")
    await service.create("summarizer/model", "m")

    assert [e.key for e in await service.list()] == ["summarizer/model", "web/cache_enabled"]


async def test_list_con_prefijo_filtra(service):
    await service.create("web/cache_enabled", "true")
    await service.create("summarizer/model", "m")

    assert [e.key for e in await service.list("summarizer/")] == ["summarizer/model"]


@pytest.mark.parametrize("prefix", ["Web/", "web/ ", "../", "web/ñ"])
async def test_list_rechaza_prefijos_con_caracteres_invalidos(service, prefix):
    with pytest.raises(InvalidKeyError):
        await service.list(prefix)


# --- Actualizar ---


async def test_update_sin_indice_cambia_el_valor_y_el_indice(service):
    created = await service.create("summarizer/max_tokens", "1024")

    updated = await service.update("summarizer/max_tokens", "5000")

    assert updated.value == "5000"
    assert updated.index > created.index


async def test_update_con_el_indice_actual_cambia_el_valor(service):
    created = await service.create("summarizer/max_tokens", "1024")

    updated = await service.update("summarizer/max_tokens", "5000", index=created.index)

    assert updated.value == "5000"


async def test_update_con_un_indice_desactualizado_falla_sin_pisar(service, fake_repository):
    created = await service.create("summarizer/max_tokens", "1024")
    fake_repository.change_behind_the_back("summarizer/max_tokens", "2048")

    with pytest.raises(StaleIndexError):
        await service.update("summarizer/max_tokens", "5000", index=created.index)

    assert fake_repository.entries["summarizer/max_tokens"].value == "2048"


async def test_update_de_una_clave_inexistente_falla(service):
    with pytest.raises(KeyNotFoundError):
        await service.update("summarizer/max_tokens", "5000")


# --- Borrar ---


async def test_delete_borra_la_clave(service, fake_repository):
    await service.create("summarizer/max_tokens", "5000")

    await service.delete("summarizer/max_tokens")

    assert "summarizer/max_tokens" not in fake_repository.entries


async def test_delete_de_una_clave_inexistente_falla(service):
    with pytest.raises(KeyNotFoundError):
        await service.delete("summarizer/max_tokens")


# --- Disponibilidad ---


async def test_is_available_delega_en_el_repositorio():
    assert await ConfigService(FakeRepository(available=True)).is_available() is True
    assert await ConfigService(FakeRepository(available=False)).is_available() is False
