# pdf-extractext-config

Microservicio dueño de la configuración centralizada. Forma parte de
[pdf-extractext](https://github.com/PDF-extract-organization/pdf-extractext), dividido
en microservicios (épica: pdf-extractext#74).

Es el **único** servicio que habla con Consul: crea, lista, consulta, actualiza y borra
claves de su KV con [`py-consul`](https://pypi.org/project/py-consul/). Guarda
configuración compartida y no secreta, como el modelo por defecto o el máximo de tokens.
**Nunca API keys**: el KV de Consul guarda en texto plano.

## Contrato HTTP

Escucha en el puerto `8000`. En el stack completo, Traefik le quitará el prefijo
`/config`, así que desde fuera `GET /summarizer/max_tokens` se verá como
`http://pdf.localhost/config/summarizer/max_tokens`.

| Método y ruta | Entrada | Respuesta |
|---|---|---|
| `POST /` | JSON `{"key", "value"}` | `201` `{"key", "value", "index"}` |
| `GET /?prefix=summarizer/` | `prefix` opcional | `200` `{"entries": [...], "total": n}`, ordenadas por clave |
| `GET /{key}` | — | `200` la entrada |
| `PUT /{key}` | JSON `{"value", "index"?}` | `200` la entrada actualizada |
| `DELETE /{key}` | — | `204` |
| `GET /health` | — | `200` si Consul tiene líder; `503` si no |

- **Claves:** `<servicio>/<nombre>`, en minúsculas, con dígitos, `_` y `-`. Por ejemplo
  `summarizer/max_tokens` o `web/cache_enabled`. Exigir dos segmentos hace que ninguna
  clave choque con `/health`.
- **Valores:** siempre texto. Interpretarlos (número, booleano, JSON) es cosa de quien
  los lee.
- **`index`:** la versión de la clave (el `ModifyIndex` de Consul); cambia en cada
  escritura. Si el `PUT` lo incluye, solo se aplica si nadie cambió la clave desde que
  se leyó (check-and-set). Sin `index`, se actualiza sobre la versión actual.

### Errores

Todos devuelven `{"detail": "..."}` en español.

| Código | Cuándo |
|---|---|
| `404` | La clave no existe (al leer, actualizar o borrar) |
| `409` | Al crear, la clave ya existe. Al actualizar o borrar, otro la cambió entre medio |
| `422` | Clave o prefijo con formato inválido, faltan campos, `value` no es texto o `index` es negativo |
| `503` | Consul no responde |

## Almacenamiento

Todas las claves viven bajo `CONSUL_PREFIX` (por defecto `pdf-extractext/`):
`summarizer/max_tokens` se guarda en Consul como `pdf-extractext/summarizer/max_tokens`.
Fuera del servicio el prefijo no se ve.

Las "carpetas" que crea la interfaz de Consul (claves vacías terminadas en `/`) no se
listan.

## Configuración

| Variable | Por defecto | Uso |
|---|---|---|
| `CONSUL_HOST` | `localhost` | Host de Consul. En el stack completo, `consul` |
| `CONSUL_PORT` | `8500` | Puerto de la API |
| `CONSUL_PREFIX` | `pdf-extractext/` | Prefijo de todas las claves. Si no termina en `/`, se añade |
| `CONSUL_TIMEOUT_SECONDS` | `3` | Espera máxima a Consul antes de responder `503` |

Ver `.env.example`.

## Desarrollo

```bash
uv sync --group dev
uv run pytest                   # unitarios: sin Consul

docker run -d -p 8500:8500 hashicorp/consul:2.1
uv run pytest -m integration    # contra Consul real; se saltan si no hay Consul

uv run uvicorn app.main:app --reload
```

La imagen de Consul arranca por defecto en modo `-dev`: un servidor en memoria con líder
propio. Basta para desarrollar y para la CI; en el stack completo corre como servidor con
datos persistentes.

## Docker

```bash
docker build -t pdf-extractext-config .
docker run -p 8000:8000 -e CONSUL_HOST=host.docker.internal pdf-extractext-config

curl -H "Content-Type: application/json" \
  -d '{"key": "summarizer/max_tokens", "value": "5000"}' http://localhost:8000/
curl http://localhost:8000/summarizer/max_tokens
```

La imagen corre con un usuario sin privilegios y declara un `HEALTHCHECK`. La CI
ejecuta los tests unitarios y los de integración (con un Consul como servicio) en cada
pull request, y al integrar en `main` publica la imagen en
`ghcr.io/pdf-extract-organization/pdf-extractext-config`.

## Arquitectura

| Capa | Contiene |
|---|---|
| `app/application/entities.py` | La entidad `ConfigEntry`, inmutable |
| `app/application/errors.py` | Errores del caso de uso; la presentación los traduce a HTTP |
| `app/application/interfaces` | Puerto `ConfigRepository`, con escrituras check-and-set |
| `app/application/services` | `ConfigService`: valida las claves y aplica las reglas del CRUD |
| `app/infrastructure` | `ConsulConfigRepository`: el único sitio que importa `consul` |
| `app/presentation` | Router, schemas y traducción de errores de FastAPI |
| `app/dependencies.py` | Cableado desde `Settings`; lo importan el router y `main` |

El cliente es el asíncrono de `py-consul` (`consul.aio.Consul`). Solo se puede crear con
el event loop en marcha, así que se crea en la primera petición, desde una dependencia
`async`. Un test lo comprueba con el cableado real.

## Flujo de trabajo

`main` y `develop` son las ramas principales. Los cambios entran por pull request a
`develop`, con los tests en verde en la CI. Los commits citan el issue (`#1`).
