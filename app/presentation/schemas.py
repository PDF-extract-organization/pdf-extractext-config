from pydantic import BaseModel, ConfigDict, Field, StrictStr


class CreateEntryRequest(BaseModel):
    key: StrictStr
    # Texto: interpretarlo (número, booleano, JSON) es cosa de quien lo lee
    value: StrictStr


class UpdateEntryRequest(BaseModel):
    value: StrictStr
    # Versión leída. Si no coincide con la actual, 409 en vez de pisar el cambio ajeno
    index: int | None = Field(default=None, ge=0)


class EntryResponse(BaseModel):
    # Se construye directamente desde la entidad ConfigEntry (un dataclass)
    model_config = ConfigDict(from_attributes=True)

    key: str
    value: str
    index: int


class EntryListResponse(BaseModel):
    entries: list[EntryResponse]
    total: int


class HealthResponse(BaseModel):
    status: str
    service: str
