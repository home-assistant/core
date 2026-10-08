"""Support for the OSO Energy devices and services."""

from typing import Any

from aiohttp.web_exceptions import HTTPException
from apyosoenergyapi import OSOEnergy
from apyosoenergyapi.helper.osoenergy_exceptions import OSOEnergyReauthRequired

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client, config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .services import async_setup_services

type OSOEnergyConfigEntry = ConfigEntry[OSOEnergy]

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
    Platform.WATER_HEATER,
]
PLATFORM_LOOKUP = {
    Platform.BINARY_SENSOR: "binary_sensor",
    Platform.SENSOR: "sensor",
    Platform.WATER_HEATER: "water_heater",
}


CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the OSO Energy integration."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: OSOEnergyConfigEntry) -> bool:
    """Set up OSO Energy from a config entry."""
    subscription_key = entry.data[CONF_API_KEY]
    websession = aiohttp_client.async_get_clientsession(hass)
    osoenergy = OSOEnergy(subscription_key, websession)

    osoenergy_config = dict(entry.data)

    try:
        devices: Any = await osoenergy.session.start_session(osoenergy_config)
    except HTTPException as error:
        raise ConfigEntryNotReady from error
    except OSOEnergyReauthRequired as err:
        raise ConfigEntryAuthFailed from err

    entry.runtime_data = osoenergy

    platforms = set()
    for ha_type, oso_type in PLATFORM_LOOKUP.items():
        device_list = devices.get(oso_type, [])
        if device_list:
            platforms.add(ha_type)
    if platforms:
        await hass.config_entries.async_forward_entry_setups(entry, platforms)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: OSOEnergyConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
