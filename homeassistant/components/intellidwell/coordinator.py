"""DataUpdateCoordinator for IntelliDwell Sprinkler Controller."""

import asyncio
from datetime import timedelta
import logging
from typing import override

from pyintellidwell import (
    IntelliDwellClient,
    IntelliDwellConnectionError,
    IntelliDwellInvalidResponseError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)


class IntelliDwellCoordinator(DataUpdateCoordinator[dict]):
    """Class to manage fetching IntelliDwell Sprinkler Controller data."""

    def __init__(
        self, hass: HomeAssistant, client: IntelliDwellClient, entry: ConfigEntry
    ) -> None:
        """Initialize."""
        self.client = client
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"IntelliDwell Sprinkler Coordinator ({client.host})",
            update_interval=timedelta(seconds=5),
        )

    @override
    async def _async_update_data(self) -> dict:
        """Fetch status, rain delay, and schedules from the controller REST API."""
        try:
            status_data, rain_delay_data, schedules_data = await asyncio.gather(
                self.client.get_status(),
                self.client.get_rain_delay(),
                self.client.get_schedules(),
                return_exceptions=False,
            )
            if isinstance(rain_delay_data, dict):
                status_data["rain_delay"] = rain_delay_data.get("days_remaining", 0)
            else:
                status_data["rain_delay"] = 0
            status_data["schedules"] = schedules_data
            return status_data  # noqa: TRY300
        except (IntelliDwellConnectionError, IntelliDwellInvalidResponseError) as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
        except (ValueError, KeyError, TypeError, AttributeError) as err:
            raise UpdateFailed(f"Invalid response from API: {err}") from err
