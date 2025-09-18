"""Data update coordinator for the PoolDose integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from pooldose.client import PooldoseClient
from pooldose.request_status import RequestStatus

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)

type PooldoseConfigEntry = ConfigEntry[PooldoseCoordinator]


class PooldoseCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for PoolDose integration."""

    device_info: dict[str, Any]

    def __init__(
        self,
        hass: HomeAssistant,
        client: PooldoseClient,
        config_entry: PooldoseConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Pooldose",
            update_interval=timedelta(seconds=600),  # Default update interval
            config_entry=config_entry,
        )
        self.client = client

    async def _async_setup(self) -> None:
        """Set up the coordinator."""
        # Update device info after successful connection
        self.device_info = self.client.device_info
        _LOGGER.debug("Device info: %s", self.device_info)

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from the PoolDose API."""
        try:
            status, instant_values = await self.client.instant_values_structured()
        except TimeoutError as err:
            raise UpdateFailed(
                f"Timeout fetching data from PoolDose device: {err}"
            ) from err
        except (ConnectionError, OSError) as err:
            raise UpdateFailed(
                f"Failed to connect to PoolDose device while fetching data: {err}"
            ) from err

        if status != RequestStatus.SUCCESS:
            raise UpdateFailed(f"API returned status: {status}")

        if instant_values is None:
            raise UpdateFailed("No data received from API")

        _LOGGER.debug("Instant values structured: %s", instant_values)
        return instant_values
