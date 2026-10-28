"""Tests de integración del repositorio de Consul.

Necesitan un Consul en marcha en CONSUL_HOST:CONSUL_PORT (por defecto localhost:8500),
por ejemplo `docker run -d -p 8500:8500 hashicorp/consul:2.1`. Se saltan solos si no hay
conexión. Ejecutar con `uv run pytest -m integration`.

Cada test usa un prefijo propio que se borra al terminar, para no tocar datos reales.
"""

from uuid import uuid4

import consul.aio
import pytest

from app.application.interfaces.config_repository import ConfigStoreUnavailableError
from app.core import Settings
from app.infrastructure.consul_repository import ConsulConfigRepository

pytestmark = pytest.mark.integration


@pytest.fixture
async def client():
    settings = Settings()
    client = consul.aio.Consul(
        host=settings.consul_host, port=settings.consul_port, connections_timeout=2
    )
    try:
        leader = await client.status.leader()
    except Exception:
        leader = ""
    if not leader:
        await client.http.close()
        pytest.skip("no hay un Consul accesible")

    yield client
    await client.http.close()


@pytest.fixture
async def repo(client):
    prefix = f"pdf-extractext-test-{uuid4().hex}/"
    yield ConsulConfigRepository(client, prefix)
    await client.kv.delete(prefix, recurse=True)


async def test_create_guarda_y_get_la_recupera(repo):
    created = await repo.create("summarizer/model", "un-modelo")

    assert created.key == "summarizer/model"
    assert created.value == "un-modelo"
    assert await repo.get("summarizer/model") == created


async def test_create_de_una_clave_existente_devuelve_none(repo):
    await repo.create("summarizer/model", "a")

    assert await repo.create("summarizer/model", "b") is None
    assert (await repo.get("summarizer/model")).value == "a"


async def test_get_de_una_clave_inexistente_devuelve_none(repo):
    assert await repo.get("summarizer/model") is None


async def test_guarda_valores_vacios_y_con_acentos(repo):
    await repo.create("web/vacio", "")
    await repo.create("web/texto", "añadir ✓")

    assert (await repo.get("web/vacio")).value == ""
    assert (await repo.get("web/texto")).value == "añadir ✓"


async def test_list_devuelve_las_claves_relativas_ordenadas(repo):
    await repo.create("web/cache_enabled", "true")
    await repo.create("summarizer/model", "m")

    assert [e.key for e in await repo.list("")] == ["summarizer/model", "web/cache_enabled"]
    assert [e.key for e in await repo.list("web/")] == ["web/cache_enabled"]


async def test_list_sin_claves_devuelve_lista_vacia(repo):
    assert await repo.list("") == []


async def test_list_ignora_las_carpetas_que_crea_la_interfaz_de_consul(repo, client):
    # La interfaz de Consul crea las carpetas como claves vacías terminadas en "/"
    await client.kv.put(repo._prefix + "web/", None)
    await repo.create("web/cache_enabled", "true")

    assert [e.key for e in await repo.list("")] == ["web/cache_enabled"]


async def test_update_con_el_indice_actual_cambia_el_valor(repo):
    created = await repo.create("summarizer/max_tokens", "1024")

    updated = await repo.update("summarizer/max_tokens", "5000", created.index)

    assert updated.value == "5000"
    assert updated.index > created.index


async def test_update_con_un_indice_desactualizado_devuelve_none_sin_pisar(repo):
    created = await repo.create("summarizer/max_tokens", "1024")
    await repo.update("summarizer/max_tokens", "2048", created.index)

    assert await repo.update("summarizer/max_tokens", "5000", created.index) is None
    assert (await repo.get("summarizer/max_tokens")).value == "2048"


async def test_delete_con_el_indice_actual_borra(repo):
    created = await repo.create("summarizer/max_tokens", "1024")

    assert await repo.delete("summarizer/max_tokens", created.index) is True
    assert await repo.get("summarizer/max_tokens") is None


async def test_delete_con_un_indice_desactualizado_no_borra(repo):
    created = await repo.create("summarizer/max_tokens", "1024")
    await repo.update("summarizer/max_tokens", "2048", created.index)

    assert await repo.delete("summarizer/max_tokens", created.index) is False
    assert await repo.get("summarizer/max_tokens") is not None


async def test_las_claves_viven_bajo_el_prefijo(repo, client):
    await repo.create("summarizer/model", "m")

    _, data = await client.kv.get(repo._prefix + "summarizer/model")

    assert data["Value"] == b"m"


async def test_is_available_es_true_con_consul_en_marcha(repo):
    assert await repo.is_available() is True


async def test_sin_consul_is_available_es_false_y_el_resto_falla_con_error_propio():
    unreachable = consul.aio.Consul(host="localhost", port=1, connections_timeout=1)
    repo = ConsulConfigRepository(unreachable, "pdf-extractext-test/")

    assert await repo.is_available() is False
    with pytest.raises(ConfigStoreUnavailableError):
        await repo.get("summarizer/model")
    await unreachable.http.close()
