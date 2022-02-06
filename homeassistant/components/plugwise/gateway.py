"""Plugwise platform for Home Assistant Core."""
from __future__ import annotations

import asyncio

import async_timeout
from plugwise.exceptions import (
    InvalidAuthentication,
    PlugwiseException,
    XMLDataMissingError,
)
from plugwise.smile import Smile

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    COORDINATOR,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TIMEOUT,
    DEFAULT_USERNAME,
    DOMAIN,
    GATEWAY,
    LOGGER,
    PLATFORMS_GATEWAY,
    PW_TYPE,
    SENSOR_PLATFORMS,
)


async def async_setup_entry_gw(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Plugwise Smiles from a config entry."""
    websession = async_get_clientsession(hass, verify_ssl=False)
    api = Smile(
        host=entry.data[CONF_HOST],
        username=entry.data.get(CONF_USERNAME, DEFAULT_USERNAME),
        password=entry.data[CONF_PASSWORD],
        port=entry.data.get(CONF_PORT, DEFAULT_PORT),
        timeout=30,
        websession=websession,
    )

    try:
        connected = await api.connect()
    except InvalidAuthentication:
        LOGGER.error("Invalid username or Smile ID")
        return False
    except PlugwiseException as err:
        raise ConfigEntryNotReady(
            f"Error while communicating to device {api.smile_name}"
        ) from err
    except asyncio.TimeoutError as err:
        raise ConfigEntryNotReady(
            f"Timeout while connecting to Smile {api.smile_name}"
        ) from err

    if not connected:
        raise ConfigEntryNotReady("Unable to connect to Smile")

    async def async_update_data():
        """Update data via API endpoint."""
        try:
            async with async_timeout.timeout(DEFAULT_TIMEOUT):
                await api.full_update_device()
                return True
        except XMLDataMissingError as err:
            raise UpdateFailed("Smile update failed") from err

    coordinator = DataUpdateCoordinator(
        hass,
        LOGGER,
        name=f"Smile {api.smile_name}",
        update_method=async_update_data,
        update_interval=DEFAULT_SCAN_INTERVAL[api.smile_type],
    )
    await coordinator.async_config_entry_first_refresh()

    api.get_all_devices()

    if entry.unique_id is None and api.smile_version[0] != "1.8.0":
        hass.config_entries.async_update_entry(entry, unique_id=api.smile_hostname)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "api": api,
        COORDINATOR: coordinator,
        PW_TYPE: GATEWAY,
    }

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, str(api.gateway_id))},
        manufacturer="Plugwise",
        name=entry.title,
        model=f"Smile {api.smile_name}",
        sw_version=api.smile_version[0],
    )

    single_master_thermostat = api.single_master_thermostat()

    platforms = PLATFORMS_GATEWAY
    if single_master_thermostat is None:
        platforms = SENSOR_PLATFORMS

    hass.config_entries.async_setup_platforms(entry, platforms)

    return True


async def async_unload_entry_gw(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(
        entry, PLATFORMS_GATEWAY
    ):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
