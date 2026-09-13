"""DataUpdateCoordinator for the Škoda integration."""

from datetime import datetime, timedelta
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
from homeassistant.util import dt as dt_util

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
        self.last_update_time: datetime | None = None

        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_{vin}",
            update_interval=UPDATE_INTERVAL,
        )

    @override
    async def _async_update_data(self) -> SkodaState:
        """Fetch the latest vehicle state and rate limit data from API."""
        try:
            vehicle_openapi_resp = await self.openapi.get_vehicle(self.vin)
            self.last_update_time = dt_util.utcnow()

            return SkodaState(
                vin=self.vin,
                vehicle_response=vehicle_openapi_resp,
                api_key_expires_at=self.openapi.api_key_expires_at,
                rate_limit_remaining=self.openapi.rate_limit_remaining,
                rate_limit_reset=self.openapi.rate_limit_reset,
            )
        except OpenApiAuthenticationError as err:
            raise ConfigEntryAuthFailed(
                f"Authentication failed for VIN {self.vin}. API key may be invalid or expired: {err}"
            ) from err
        except OpenApiError as err:
            raise UpdateFailed(
                f"Error communicating with Škoda API for VIN {self.vin}: {err}"
            ) from err
        except Exception as err:
            raise UpdateFailed(
                f"Unexpected error fetching data for VIN {self.vin}: {err}"
            ) from err

    @property
    def rate_limit_reset_time(self) -> datetime | None:
        """Return the exact datetime when the rate limit quota will be reset."""
        if not self.last_update_time or self.openapi.rate_limit_reset is None:
            return None

        return self.last_update_time + timedelta(seconds=self.openapi.rate_limit_reset)

    @property
    def next_update_time(self) -> datetime | None:
        """Calculate the estimated datetime of the next update."""
        if self.last_update_time is None or self.update_interval is None:
            return None
        return self.last_update_time + self.update_interval
