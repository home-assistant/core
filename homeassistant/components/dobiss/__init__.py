"""The dobiss integration."""

from asyncio import gather
import logging
from typing import Any

from dobissapi import DobissAPI

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import (
    CONF_COVER_CLOSETIME,
    CONF_COVER_SET_END_POSITION,
    CONF_COVER_USE_TIMED,
    CONF_IGNORE_ZIGBEE_DEVICES,
    CONF_INVERT_BINARY_SENSOR,
    CONF_WEBSOCKET_TIMEOUT,
    DEFAULT_COVER_CLOSETIME,
    DEFAULT_COVER_SET_END_POSITION,
    DEFAULT_COVER_USE_TIMED,
    DEFAULT_IGNORE_ZIGBEE_DEVICES,
    DEFAULT_INVERT_BINARY_SENSOR,
    DEFAULT_WEBSOCKET_TIMEOUT,
    DEVICES,
    DOMAIN,
    KEY_API,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.LIGHT]


async def async_setup(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the dobiss component."""
    _LOGGER.warning("DOBISS INTEGRATIE WORDT GELADEN")
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up dobiss from a config entry."""

    _LOGGER.debug("async_setup_entry")
    client = HADobiss(hass, entry)
    entry.runtime_data = client
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {KEY_API: client}

    if not await client.async_setup():
        _LOGGER.warning("Dobiss setup failed")
        return False

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("async_unload_entry")
    if hass.data[DOMAIN][entry.entry_id][KEY_API].unsub:
        hass.data[DOMAIN][entry.entry_id][KEY_API].unsub()
    unload_ok = all(
        await gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
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


class HADobiss:
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
            websocket_timeout = self.config_entry.options.get(
                CONF_WEBSOCKET_TIMEOUT, DEFAULT_WEBSOCKET_TIMEOUT
            )
            _LOGGER.debug(
                "(async_setup) Setting websocket timeout to %s", websocket_timeout
            )

            if websocket_timeout == 0:
                self.api.websocket_timeout = None
            else:
                self.api.websocket_timeout = websocket_timeout

            devices = self.api.get_all_devices()
            self.hass.data[DOMAIN][self.config_entry.entry_id][DEVICES] = devices

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
        if CONF_INVERT_BINARY_SENSOR not in options:
            options[CONF_INVERT_BINARY_SENSOR] = DEFAULT_INVERT_BINARY_SENSOR
        if CONF_IGNORE_ZIGBEE_DEVICES not in options:
            options[CONF_IGNORE_ZIGBEE_DEVICES] = DEFAULT_IGNORE_ZIGBEE_DEVICES
        if CONF_COVER_SET_END_POSITION not in options:
            options[CONF_COVER_SET_END_POSITION] = DEFAULT_COVER_SET_END_POSITION
        if CONF_COVER_CLOSETIME not in options:
            options[CONF_COVER_CLOSETIME] = DEFAULT_COVER_CLOSETIME
        if CONF_COVER_USE_TIMED not in options:
            options[CONF_COVER_USE_TIMED] = DEFAULT_COVER_USE_TIMED
        if CONF_WEBSOCKET_TIMEOUT not in options:
            options[CONF_WEBSOCKET_TIMEOUT] = DEFAULT_WEBSOCKET_TIMEOUT

        self.hass.config_entries.async_update_entry(self.config_entry, options=options)

    @staticmethod
    async def update_listener(hass: HomeAssistant, entry: ConfigEntry):
        """Handle options update."""
        if entry.source == SOURCE_IMPORT:
            return
        await hass.config_entries.async_reload(entry.entry_id)
