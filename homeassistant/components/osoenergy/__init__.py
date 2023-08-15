"""Support for the OSO Energy devices and services."""
import logging
from typing import Any

from aiohttp.web_exceptions import HTTPException
from apyosoenergyapi import OSOEnergy
from apyosoenergyapi.helper.osoenergy_exceptions import OSOEnergyReauthRequired

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client
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
        devices: Any = await osoenergy.session.start_session(osoenergy_config)
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


class OSOEnergyEntity(Entity):
    """Initiate OSO Energy Base Class."""

    _attr_has_entity_name = True

    def __init__(self, osoenergy, osoenergy_device) -> None:
        """Initialize the instance."""
        self.osoenergy = osoenergy
        self.device = osoenergy_device

    @property
    def unique_id(self) -> str:
        """Return unique ID of entity."""
        return self.device["device_id"]
