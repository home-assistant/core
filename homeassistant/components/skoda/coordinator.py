"""DataUpdateCoordinator for the Škoda integration."""

from datetime import timedelta
import logging
from typing import override

from skoda_public_api.api_layer.exceptions import (
    OpenApiAuthenticationError,
    OpenApiError,
)
from skoda_public_api.api_layer.open_api_client import OpenAPIClient

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .models import SkodaConfigEntry, SkodaState

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(minutes=5)


class SkodaUpdateCoordinator(DataUpdateCoordinator[SkodaState]):
    """Central coordinator for fetching and managing vehicle data updates."""

    config_entry: SkodaConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: SkodaConfigEntry,
        client: OpenAPIClient,
        vin: str,
    ) -> None:
        """Initialize the Škoda coordinator."""
        self.openapi = client
        self.vin = vin

        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_{vin}",
            update_interval=UPDATE_INTERVAL,
        )

    @override
    async def _async_update_data(self) -> SkodaState:
        """Fetch the latest vehicle state from the API."""
        try:
            vehicle_openapi_resp = await self.openapi.get_vehicle(self.vin)

            return SkodaState(
                vin=self.vin,
                vehicle_response=vehicle_openapi_resp,
            )
        except OpenApiAuthenticationError as err:
            raise ConfigEntryAuthFailed(
                f"Authentication failed for VIN {self.vin}. API key may be invalid or expired: {err}"
            ) from err
        except OpenApiError as err:
            raise UpdateFailed(
                f"Error communicating with Škoda API for VIN {self.vin}: {err}"
            ) from err
