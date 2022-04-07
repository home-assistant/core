"""The Reisinger Bridge integration."""
from __future__ import annotations

from datetime import timedelta
import logging

import reisingerdrive

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import update_coordinator
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_DEVICE_KEY, DOMAIN

_LOGGER = logging.getLogger(__name__)

# For your initial PR, limit it to 1 platform.
PLATFORMS: list[Platform] = [Platform.COVER]
# PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.COVER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Reisinger Bridge from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    open_reisinger_connection = reisingerdrive.OpenReisinger(
        f"{entry.data[CONF_HOST]}:{entry.data[CONF_PORT]}",
        entry.data[CONF_DEVICE_KEY],
        False,
        async_get_clientsession(hass),
    )

    open_reisinger_data_coordinator = OpenReisingerDataUpdateCoordinator(
        hass,
        open_reisinger_connection=open_reisinger_connection,
    )

    await open_reisinger_data_coordinator.async_config_entry_first_refresh()
    hass.data[DOMAIN][entry.entry_id] = open_reisinger_data_coordinator
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class OpenReisingerDataUpdateCoordinator(update_coordinator.DataUpdateCoordinator):
    """Class to manage fetching Openreisinger data."""

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        open_reisinger_connection: reisingerdrive.OpenReisinger,
    ) -> None:
        """Initialize global Openreisinger data updater."""
        self.open_reisinger_connection = open_reisinger_connection

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=5),
        )

    async def _async_update_data(self) -> None:
        """Fetch data."""
        data = await self.open_reisinger_connection.update_state()
        if data is None:
            raise update_coordinator.UpdateFailed(
                "Unable to connect to OpenReisinger device"
            )
        return data
