"""Coordinator for refreshing Wyoming service info."""

from datetime import timedelta
import logging
from typing import override

from wyoming.info import Info

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .data import load_wyoming_info

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(seconds=30)


class WyomingInfoCoordinator(DataUpdateCoordinator[Info]):
    """Periodically refresh info from a Wyoming service.

    Services can gain or lose voices, wake word models, etc. while Home
    Assistant is running, so the info collected during setup goes stale.
    """

    def __init__(
        self, hass: HomeAssistant, config_entry: ConfigEntry, host: str, port: int
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{host}:{port}",
            update_interval=UPDATE_INTERVAL,
            always_update=False,
        )
        self.host = host
        self.port = port

    @override
    async def _async_update_data(self) -> Info:
        """Fetch info from the Wyoming service."""
        # A single attempt is enough because the next interval retries anyway.
        info = await load_wyoming_info(self.host, self.port, retries=0)
        if info is None:
            raise UpdateFailed(f"Unable to get info from {self.host}:{self.port}")

        return info
