"""Support for the OSO Energy devices and setrvices."""
from functools import wraps
import logging

from aiohttp.web_exceptions import HTTPException
from apyosoenergyapi import OSOEnergy
from apyosoenergyapi.helper.osoenergy_exceptions import OSOEnergyReauthRequired

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, PLATFORM_LOOKUP, PLATFORMS

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up OSO Energy from a config entry."""

    subscription_key = entry.data[CONF_API_KEY]
    websession = aiohttp_client.async_get_clientsession(hass)
    osoenergy = OSOEnergy(subscription_key, websession)

    osoenergy_config = dict(entry.data)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = osoenergy

    try:
        devices = await osoenergy.session.start_session(osoenergy_config)
    except HTTPException as error:
        _LOGGER.error("Could not connect to the internet: %s", error)
        raise ConfigEntryNotReady() from error
    except OSOEnergyReauthRequired as err:
        raise ConfigEntryAuthFailed from err

    for ha_type, oso_type in PLATFORM_LOOKUP.items():
        device_list = devices.get(oso_type, [])
        if device_list:
            hass.async_create_task(
                hass.config_entries.async_forward_entry_setup(entry, ha_type)
            )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


def refresh_system(func):
    """Force update all entities after state change."""

    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        await func(self, *args, **kwargs)
        async_dispatcher_send(self.hass, DOMAIN)

    return wrapper


class OSOEnergyEntity(Entity):
    """Initiate OSO Energy Base Class."""

    def __init__(self, osoenergy, osoenergy_device):
        """Initialize the instance."""
        self.osoenergy = osoenergy
        self.device = osoenergy_device
        self.attributes = {}
        self._unique_id = self.device["device_id"]

    async def async_added_to_hass(self):
        """When entity is added to Home Assistant."""
        self.async_on_remove(
            async_dispatcher_connect(self.hass, DOMAIN, self.async_write_ha_state)
        )
