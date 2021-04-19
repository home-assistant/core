"""The FAA Delays integration."""
import asyncio
from datetime import timedelta
import logging

from aiohttp import ClientConnectionError
from async_timeout import timeout
from faadelays import Airport

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["binary_sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up FAA Delays from a config entry."""
    code = entry.data[CONF_ID]

    coordinator = FAADataUpdateCoordinator(hass, code)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class FAADataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching FAA API data from a single endpoint."""

    def __init__(self, hass, code):
        """Initialize the coordinator."""
        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=timedelta(minutes=1)
        )
        self.session = aiohttp_client.async_get_clientsession(hass)
        self.data = Airport(code, self.session)
        self.code = code

    async def _async_update_data(self):
        try:
            with timeout(10):
                await self.data.update()
        except ClientConnectionError as err:
            raise UpdateFailed(err) from err
        return self.data
