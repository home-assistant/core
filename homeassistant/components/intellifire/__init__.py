"""The Intellifire integration."""
from __future__ import annotations

from datetime import timedelta
import logging
import logging.handlers

from async_timeout import timeout
from intellifire4py import IntellifireAsync

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
PLATFORMS: list[str] = [Platform.SENSOR, Platform.BINARY_SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Intellifire from a config entry."""

    _LOGGER.info("Setting up config entry: %s", entry.unique_id)

    # Define the API Object
    api_object = IntellifireAsync(entry.data["host"])
    # Define the update coordinator
    coordinator = IntellifireDataUpdateCoordinator(
        hass=hass, api=api_object, name=entry.data["name"]
    )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class IntellifireDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage teh polling of the stuff"""

    def __init__(self, hass, api: IntellifireAsync, name: str):
        """Initialize the Coordinator"""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=15),
            update_method=self._async_update_data,
        )
        self._api = api
        self._intellifire_name = name
        self._LOGGER = _LOGGER

    async def _async_update_data(self):
        _LOGGER.debug("Calling update loop on Intellifire")
        async with timeout(100):
            await self._api.poll(logging_level=logging.DEBUG)
        return self._api.data

    @property
    def intellifire_name(self):
        """Return the nanme entered by the users as-is"""
        return self._intellifire_name

    @property
    def safe_intellifire_name(self):
        """Return the name entered by user in all lowercase and without any spaces"""
        return self._intellifire_name.lower().replace(" ", "_")

    @property
    def api(self):
        """ "Return the API pointer"""
        return self._api
