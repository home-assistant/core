"""Support for Nexia / Trane XL Thermostats."""

import logging

import aiohttp
from nexia.const import BRAND_NEXIA
from nexia.home import NexiaHome
from nexia.thermostat import NexiaThermostat

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from .const import CONF_BRAND, DOMAIN, PLATFORMS
from .coordinator import NexiaDataUpdateCoordinator
from .util import is_invalid_auth_code

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.removed(DOMAIN, raise_if_present=False)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Configure the base Nexia device for Home Assistant."""

    conf = entry.data
    username = conf[CONF_USERNAME]
    password = conf[CONF_PASSWORD]
    brand = conf.get(CONF_BRAND, BRAND_NEXIA)

    state_file = hass.config.path(f"nexia_config_{username}.conf")
    session = async_get_clientsession(hass)
    nexia_home = NexiaHome(
        session,
        username=username,
        password=password,
        device_name=hass.config.location_name,
        state_file=state_file,
        brand=brand,
    )

    try:
        await nexia_home.login()
    except TimeoutError as ex:
        raise ConfigEntryNotReady(
            f"Timed out trying to connect to Nexia service: {ex}"
        ) from ex
    except aiohttp.ClientResponseError as http_ex:
        if is_invalid_auth_code(http_ex.status):
            _LOGGER.error(
                "Access error from Nexia service, please check credentials: %s", http_ex
            )
            return False
        raise ConfigEntryNotReady(f"Error from Nexia service: {http_ex}") from http_ex
    except aiohttp.ClientOSError as os_error:
        raise ConfigEntryNotReady(
            f"Error connecting to Nexia service: {os_error}"
        ) from os_error

    coordinator = NexiaDataUpdateCoordinator(hass, nexia_home)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    """Remove a nexia config entry from a device."""
    coordinator: NexiaDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    nexia_home: NexiaHome = coordinator.nexia_home
    dev_ids = {dev_id[1] for dev_id in device_entry.identifiers if dev_id[0] == DOMAIN}
    for thermostat_id in nexia_home.get_thermostat_ids():
        if thermostat_id in dev_ids:
            return False
        thermostat: NexiaThermostat = nexia_home.get_thermostat_by_id(thermostat_id)
        for zone_id in thermostat.get_zone_ids():
            if zone_id in dev_ids:
                return False
    return True
