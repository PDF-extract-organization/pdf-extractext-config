"""Tests de los endpoints HTTP con un repositorio en memoria. Sin Consul."""

import pytest
from fastapi.testclient import TestClient

from app.application.services.config_service import ConfigService
from app.dependencies import get_config_service, get_repository, get_settings
from app.main import app
from tests.conftest import FakeRepository


def client_con(repository: FakeRepository) -> TestClient:
    app.dependency_overrides[get_config_service] = lambda: ConfigService(repository)
    return TestClient(app)


@pytest.fixture
def client(fake_repository):
    yield client_con(fake_repository)
    app.dependency_overrides.clear()


@pytest.fixture
def client_sin_consul():
    yield client_con(FakeRepository(available=False))
    app.dependency_overrides.clear()


def crear(client, key="summarizer/max_tokens", value="5000"):
    return client.post("/", json={"key": key, "value": value})


# --- POST / ---


def test_crear_devuelve_201_con_la_entrada(client):
    response = crear(client)

    assert response.status_code == 201
    body = response.json()
    assert body["key"] == "summarizer/max_tokens"
    assert body["value"] == "5000"
    assert isinstance(body["index"], int)


def test_crear_una_clave_existente_devuelve_409(client):
    crear(client)

    response = crear(client, value="1")

    assert response.status_code == 409
    assert "ya existe" in response.json()["detail"]


@pytest.mark.parametrize(
    "body", [{}, {"key": "summarizer/max_tokens"}, {"value": "1"}, {"key": "x", "value": 1}]
)
def test_crear_con_datos_incompletos_devuelve_422(client, body):
    assert client.post("/", json=body).status_code == 422


def test_crear_con_una_clave_invalida_devuelve_422_explicando_el_formato(client):
    response = crear(client, key="health")

    assert response.status_code == 422
    assert "<servicio>/<nombre>" in response.json()["detail"]


# --- GET / ---


def test_listar_devuelve_las_entradas_y_el_total(client):
    crear(client, "web/cache_enabled", "true")
    crear(client, "summarizer/model", "m")

    body = client.get("/").json()

    assert body["total"] == 2
    assert [e["key"] for e in body["entries"]] == ["summarizer/model", "web/cache_enabled"]


def test_listar_con_prefijo_filtra(client):
    crear(client, "web/cache_enabled", "true")
    crear(client, "summarizer/model", "m")

    body = client.get("/?prefix=web/").json()

    assert [e["key"] for e in body["entries"]] == ["web/cache_enabled"]


def test_listar_sin_entradas_devuelve_lista_vacia(client):
    assert client.get("/").json() == {"entries": [], "total": 0}


def test_listar_con_un_prefijo_invalido_devuelve_422(client):
    assert client.get("/?prefix=Web/").status_code == 422


# --- GET /{key} ---


def test_obtener_devuelve_la_entrada(client):
    created = crear(client).json()

    response = client.get("/summarizer/max_tokens")

    assert response.status_code == 200
    assert response.json() == created


def test_obtener_una_clave_inexistente_devuelve_404(client):
    response = client.get("/summarizer/max_tokens")

    assert response.status_code == 404
    assert "No existe" in response.json()["detail"]


# --- PUT /{key} ---


def test_actualizar_sin_indice_devuelve_200_con_el_valor_nuevo(client):
    created = crear(client, value="1024").json()

    response = client.put("/summarizer/max_tokens", json={"value": "5000"})

    assert response.status_code == 200
    assert response.json()["value"] == "5000"
    assert response.json()["index"] > created["index"]


def test_actualizar_con_el_indice_actual_devuelve_200(client):
    created = crear(client, value="1024").json()

    response = client.put(
        "/summarizer/max_tokens", json={"value": "5000", "index": created["index"]}
    )

    assert response.status_code == 200


def test_actualizar_con_un_indice_desactualizado_devuelve_409(client, fake_repository):
    created = crear(client, value="1024").json()
    fake_repository.change_behind_the_back("summarizer/max_tokens", "2048")

    response = client.put(
        "/summarizer/max_tokens", json={"value": "5000", "index": created["index"]}
    )

    assert response.status_code == 409
    assert "cambió" in response.json()["detail"]
    assert client.get("/summarizer/max_tokens").json()["value"] == "2048"


def test_actualizar_una_clave_inexistente_devuelve_404(client):
    assert client.put("/summarizer/max_tokens", json={"value": "5000"}).status_code == 404


@pytest.mark.parametrize("body", [{}, {"value": 5000}, {"value": "1", "index": -1}])
def test_actualizar_con_datos_invalidos_devuelve_422(client, body):
    crear(client)

    assert client.put("/summarizer/max_tokens", json=body).status_code == 422


# --- DELETE /{key} ---


def test_borrar_devuelve_204_y_la_clave_desaparece(client):
    crear(client)

    response = client.delete("/summarizer/max_tokens")

    assert response.status_code == 204
    assert client.get("/summarizer/max_tokens").status_code == 404


def test_borrar_una_clave_inexistente_devuelve_404(client):
    assert client.delete("/summarizer/max_tokens").status_code == 404


# --- Consul caído ---


@pytest.mark.parametrize(
    "method, path, body",
    [
        ("POST", "/", {"key": "summarizer/model", "value": "m"}),
        ("GET", "/", None),
        ("GET", "/summarizer/model", None),
        ("PUT", "/summarizer/model", {"value": "m"}),
        ("DELETE", "/summarizer/model", None),
    ],
)
def test_sin_consul_todas_las_operaciones_devuelven_503(client_sin_consul, method, path, body):
    response = client_sin_consul.request(method, path, json=body)

    assert response.status_code == 503
    assert "Consul" in response.json()["detail"]


# --- GET /health ---


def test_health_responde_200_si_consul_responde(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "service": "config"}


def test_health_responde_503_si_consul_no_responde(client_sin_consul):
    response = client_sin_consul.get("/health")

    assert response.status_code == 503
    assert response.json() == {"status": "unhealthy", "service": "config"}


# --- El cableado real, sin dobles ---


@pytest.fixture
def consul_inalcanzable(monkeypatch):
    monkeypatch.setenv("CONSUL_PORT", "1")
    get_settings.cache_clear()
    get_repository.cache_clear()
    yield
    get_settings.cache_clear()
    get_repository.cache_clear()


def test_el_cableado_real_crea_el_cliente_de_consul_dentro_del_event_loop(consul_inalcanzable):
    """El cliente asíncrono de py-consul falla con 'no running event loop' si se crea
    fuera del event loop, por ejemplo en una dependencia síncrona que FastAPI ejecuta en
    un hilo aparte. Sin Consul, lo correcto es 503 y no 500."""
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 503
