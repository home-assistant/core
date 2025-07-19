"""Data update coordinator for PoolDose."""

from __future__ import annotations

import logging
from typing import Any

from pooldose.client import PooldoseClient
from pooldose.request_status import RequestStatus

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)


class PooldoseCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for Pooldose integration."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: PooldoseClient,
        update_interval,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Pooldose",
            update_interval=update_interval,
            config_entry=config_entry,
        )
        self.client = client
        self.device_info: dict[str, str | None] = {}

    async def _async_setup(self) -> None:
        """Set up the coordinator."""
        # Connect to the client
        client_status = await self.client.connect()
        if client_status != RequestStatus.SUCCESS:
            raise ConfigEntryNotReady(
                f"Failed to connect to PoolDose client: {client_status}"
            )

        # Update device info after successful connection
        self.device_info = self.client.device_info

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from the PoolDose API."""
        try:
            status, instant_values = await self.client.instant_values()
        except TimeoutError as err:
            raise UpdateFailed(
                f"Timeout communicating with PoolDose device: {err}"
            ) from err
        except (ConnectionError, OSError) as err:
            raise UpdateFailed(f"Failed to connect to PoolDose device: {err}") from err
        except Exception as err:
            raise UpdateFailed(
                f"Unexpected error communicating with device: {err}"
            ) from err

        if status != RequestStatus.SUCCESS:
            raise UpdateFailed(f"API returned status: {status}")

        if instant_values is None:
            raise UpdateFailed("No data received from API")

        return instant_values

    @property
    def available(self) -> bool:
        """Return True if coordinator is available."""
        return self.last_update_success and self.data is not None
