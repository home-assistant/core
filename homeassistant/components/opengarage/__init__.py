"""The OpenGarage integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

import opengarage

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_VERIFY_SSL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import update_coordinator
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_DEVICE_KEY, DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.BINARY_SENSOR, Platform.BUTTON, Platform.COVER, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up OpenGarage from a config entry."""
    open_garage_connection = opengarage.OpenGarage(
        f"{entry.data[CONF_HOST]}:{entry.data[CONF_PORT]}",
        entry.data[CONF_DEVICE_KEY],
        entry.data[CONF_VERIFY_SSL],
        async_get_clientsession(hass),
    )
    open_garage_data_coordinator = OpenGarageDataUpdateCoordinator(
        hass,
        open_garage_connection=open_garage_connection,
    )
    await open_garage_data_coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = open_garage_data_coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class OpenGarageDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):  # pylint: disable=hass-enforce-coordinator-module
    """Class to manage fetching Opengarage data."""

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        open_garage_connection: opengarage.OpenGarage,
    ) -> None:
        """Initialize global Opengarage data updater."""
        self.open_garage_connection = open_garage_connection

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=5),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data."""
        data = await self.open_garage_connection.update_state()
        if data is None:
            raise update_coordinator.UpdateFailed(
                "Unable to connect to OpenGarage device"
            )
        return data
