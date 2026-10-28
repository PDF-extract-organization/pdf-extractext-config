from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.dependencies import get_repository
from app.presentation.errors import register_error_handlers
from app.presentation.routers import config


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    # Cierra la sesión HTTP con Consul solo si llegó a abrirse
    if get_repository.cache_info().currsize:
        await get_repository().close()


app = FastAPI(title="pdf-extractext-config", lifespan=lifespan)
register_error_handlers(app)
app.include_router(config.router)
