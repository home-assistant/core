"""Support for Soma Smartshades."""
import asyncio

from api.soma_api import SomaApi
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import HomeAssistantType

from .const import API, DOMAIN, HOST, PORT

DEVICES = "devices"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {vol.Required(CONF_HOST): cv.string, vol.Required(CONF_PORT): cv.string}
        )
    },
    extra=vol.ALLOW_EXTRA,
)

PLATFORMS = ["cover", "sensor"]


async def async_setup(hass, config):
    """Set up the Soma component."""
    if DOMAIN not in config:
        return True

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            data=config[DOMAIN],
            context={"source": config_entries.SOURCE_IMPORT},
        )
    )

    return True


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry):
    """Set up Soma from a config entry."""
    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][API] = SomaApi(entry.data[HOST], entry.data[PORT])
    devices = await hass.async_add_executor_job(hass.data[DOMAIN][API].list_devices)
    hass.data[DOMAIN][DEVICES] = devices["shades"]

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    return True


async def async_unload_entry(hass: HomeAssistantType, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in PLATFORMS
            ]
        )
    )

    return unload_ok


class SomaEntity(Entity):
    """Representation of a generic Soma device."""

    def __init__(self, device, api):
        """Initialize the Soma device."""
        self.device = device
        self.api = api
        self.current_position = 50
        self.battery_state = 0
        self.is_available = True

    @property
    def available(self):
        """Return true if the last API commands returned successfully."""
        return self.is_available

    @property
    def unique_id(self):
        """Return the unique id base on the id returned by pysoma API."""
        return self.device["mac"]

    @property
    def name(self):
        """Return the name of the device."""
        return self.device["name"]

    @property
    def device_info(self):
        """Return device specific attributes.

        Implemented by platform classes.
        """
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": self.name,
            "manufacturer": "Wazombi Labs",
        }
