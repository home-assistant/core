"""Models for the Škoda integration."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry

if TYPE_CHECKING:
    from skoda_public_api.api_layer.open_api_client import OpenAPIClient
    from skoda_public_api.models.vehicle import VehicleResponse

    from .coordinator import SkodaUpdateCoordinator


@dataclass
class SkodaState:
    """Vehicle state model reflecting OpenAPI status and response headers."""

    vin: str
    vehicle_response: VehicleResponse | None = None
    api_key_expires_at: str | None = None
    rate_limit_remaining: int | None = None
    rate_limit_reset: int | None = None


@dataclass
class SkodaData:
    """Runtime data stored in ConfigEntry."""

    openapi: OpenAPIClient
    coordinator: SkodaUpdateCoordinator
    vin: str


type SkodaConfigEntry = ConfigEntry[SkodaData]
