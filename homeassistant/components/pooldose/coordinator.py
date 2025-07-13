"""Data update coordinator for PoolDose."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from pooldose.client import PooldoseClient
from pooldose.request_handler import RequestStatus

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)

type PooldoseConfigEntry = ConfigEntry[PooldoseClient]


class PooldoseCoordinator(DataUpdateCoordinator[tuple[RequestStatus, dict[str, Any]]]):
    """Class to manage fetching data from the PoolDose API."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: PooldoseClient,
        update_interval: timedelta,
        config_entry: PooldoseConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            logger=_LOGGER,
            name="pooldose",
            update_interval=update_interval,
            config_entry=config_entry,
        )
        self.client = client

    async def _async_update_data(self) -> tuple[RequestStatus, dict[str, Any]]:
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

        return status, instant_values

    @property
    def available(self) -> bool:
        """Return True if coordinator is available."""
        return self.last_update_success and self.data is not None
