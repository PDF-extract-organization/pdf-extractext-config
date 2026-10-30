from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import JSONResponse

from app.application.services.config_service import ConfigService
from app.dependencies import get_config_service
from app.presentation.schemas import (
    CreateEntryRequest,
    EntryListResponse,
    EntryResponse,
    HealthResponse,
    UpdateEntryRequest,
)

router = APIRouter()


# Declarada antes que /{key:path}. Además una clave siempre tiene dos segmentos,
# así que nunca se llama "health".
@router.get("/health", response_model=HealthResponse)
async def health(service: ConfigService = Depends(get_config_service)):
    if await service.is_available():
        return HealthResponse(status="healthy", service="config")
    return JSONResponse(
        status_code=503, content={"status": "unhealthy", "service": "config"}
    )


@router.post("/", response_model=EntryResponse, status_code=201)
async def create_entry(
    request: CreateEntryRequest, service: ConfigService = Depends(get_config_service)
):
    return await service.create(request.key, request.value)


@router.get("/", response_model=EntryListResponse)
async def list_entries(
    prefix: str = Query(""), service: ConfigService = Depends(get_config_service)
):
    entries = await service.list(prefix)
    return EntryListResponse(entries=entries, total=len(entries))


@router.get("/{key:path}", response_model=EntryResponse)
async def get_entry(key: str, service: ConfigService = Depends(get_config_service)):
    return await service.get(key)


@router.put("/{key:path}", response_model=EntryResponse)
async def update_entry(
    key: str,
    request: UpdateEntryRequest,
    service: ConfigService = Depends(get_config_service),
):
    return await service.update(key, request.value, request.index)


@router.delete("/{key:path}", status_code=204)
async def delete_entry(key: str, service: ConfigService = Depends(get_config_service)):
    await service.delete(key)
    return Response(status_code=204)
