"""The dobiss integration."""

import logging
from typing import Any

from dobissapi import DobissAPI

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema("dobiss")

PLATFORMS: list[Platform] = [Platform.LIGHT]


async def async_setup(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the dobiss component."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up dobiss from a config entry."""
    client = DobissClient(hass, entry)
    entry.runtime_data = client

    if not await client.async_setup():
        _LOGGER.warning("Dobiss setup failed")
        raise ConfigEntryError("Invalid Dobiss configuration")

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("async_unload_entry")

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)
    else:
        _LOGGER.warning("Unload failed")

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)


class DobissClient:
    """Handle communication and setup logic for a single Dobiss config entry."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the Dobiss data."""
        self.hass = hass
        self.config_entry = config_entry
        self.api = None
        self.available = False
        self.unsub = None
        self.devices: list[Any] = []

    @property
    def host(self):
        """Return client host."""
        return self.config_entry.data[CONF_HOST]

    async def async_setup(self):
        """Set up the Dobiss client."""
        try:
            self.api = DobissAPI(
                self.config_entry.data["secret"],
                self.config_entry.data["host"],
                self.config_entry.data["secure"],
            )

            devices = self.api.get_all_devices()
            self.devices = devices

            await self.api.discovery()
            self.hass.async_create_task(self.api.dobiss_monitor())

            self.available = True
            _LOGGER.debug("Successfully connected to Dobiss")

        except Exception as err:
            _LOGGER.exception("Can not connect to Dobiss")
            self.available = False
            raise ConfigEntryNotReady from err

        self.add_options()
        self.unsub = self.config_entry.add_update_listener(self.update_listener)
        self.config_entry.async_on_unload(self.unsub)

        await self.hass.config_entries.async_forward_entry_setups(
            self.config_entry, PLATFORMS
        )

        return True

    def add_options(self):
        """Add options for dobiss integration."""
        options = (
            self.config_entry.options.copy()
            if self.config_entry.options is not None
            else {}
        )

        self.hass.config_entries.async_update_entry(self.config_entry, options=options)

    @staticmethod
    async def update_listener(hass: HomeAssistant, entry: ConfigEntry):
        """Handle options update."""
        if entry.source == SOURCE_IMPORT:
            return
        await hass.config_entries.async_reload(entry.entry_id)
