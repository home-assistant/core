"""DataUpdateCoordinator for the Ness Alarm integration."""

from __future__ import annotations

import logging

from nessclient import Client

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

type NessAlarmConfigEntry = ConfigEntry[NessAlarmCoordinator]


class NessAlarmCoordinator(DataUpdateCoordinator[None]):
    """Coordinator for Ness Alarm updates."""

    config_entry: NessAlarmConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: NessAlarmConfigEntry,
        client: Client,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
            config_entry=config_entry,
        )
        self.client = client

    async def _async_update_data(self) -> None:
        """Fetch data from the alarm panel."""
        try:
            await self.client.update()
        except OSError as err:
            raise UpdateFailed(f"Error communicating with alarm panel: {err}") from err
