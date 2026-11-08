"""Coordinator for the Hase iQ integration."""

from datetime import timedelta
from typing import override

from pyhaseiq import Client, HaseIQError, Status

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER

type HaseIQConfigEntry = ConfigEntry[HaseIQCoordinator]

SCAN_INTERVAL = timedelta(seconds=30)


class HaseIQCoordinator(DataUpdateCoordinator[Status]):
    """Poll the stove for its phase and the readings available in it."""

    config_entry: HaseIQConfigEntry

    def __init__(self, hass: HomeAssistant, entry: HaseIQConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

    @override
    async def _async_update_data(self) -> Status:
        """Read the stove."""
        # pyhaseiq never reconnects a lost connection, so each poll opens its own.
        try:
            async with Client(self.config_entry.data[CONF_HOST]) as stove:
                return await stove.get_status()
        except HaseIQError as err:
            raise UpdateFailed(f"Error reading the stove: {err}") from err
