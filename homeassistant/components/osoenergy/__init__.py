"""Support for the OSO Energy devices and services."""

from typing import Any

from aiohttp.web_exceptions import HTTPException
from apyosoenergyapi import OSOEnergy
from apyosoenergyapi.helper.const import (
    OSOEnergyBinarySensorData,
    OSOEnergySensorData,
    OSOEnergyWaterHeaterData,
)
from apyosoenergyapi.helper.osoenergy_exceptions import OSOEnergyReauthRequired

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN

MANUFACTURER = "OSO Energy"
PLATFORMS = [
    Platform.SENSOR,
    Platform.WATER_HEATER,
]
PLATFORM_LOOKUP = {
    Platform.SENSOR: "sensor",
    Platform.WATER_HEATER: "water_heater",
}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up OSO Energy from a config entry."""
    subscription_key = entry.data[CONF_API_KEY]
    websession = aiohttp_client.async_get_clientsession(hass)
    osoenergy = OSOEnergy(subscription_key, websession)

    osoenergy_config = dict(entry.data)

    hass.data.setdefault(DOMAIN, {})

    try:
        devices: Any = await osoenergy.session.start_session(osoenergy_config)
    except HTTPException as error:
        raise ConfigEntryNotReady from error
    except OSOEnergyReauthRequired as err:
        raise ConfigEntryAuthFailed from err

    hass.data[DOMAIN][entry.entry_id] = osoenergy

    platforms = set()
    for ha_type, oso_type in PLATFORM_LOOKUP.items():
        device_list = devices.get(oso_type, [])
        if device_list:
            platforms.add(ha_type)
    if platforms:
        await hass.config_entries.async_forward_entry_setups(entry, platforms)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class OSOEnergyEntity[
    _OSOEnergyT: (
        OSOEnergyBinarySensorData,
        OSOEnergySensorData,
        OSOEnergyWaterHeaterData,
    )
](Entity):
    """Initiate OSO Energy Base Class."""

    _attr_has_entity_name = True

    def __init__(self, osoenergy: OSOEnergy, entity_data: _OSOEnergyT) -> None:
        """Initialize the instance."""
        self.osoenergy = osoenergy
        self.entity_data = entity_data
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entity_data.device_id)},
            manufacturer=MANUFACTURER,
            model=entity_data.device_type,
            name=entity_data.device_name,
        )
