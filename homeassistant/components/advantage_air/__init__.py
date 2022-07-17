"""Advantage Air climate integration."""
from datetime import timedelta
import logging

from advantage_air import ApiError, advantage_air

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    ADVANTAGE_AIR_COORDINATOR,
    ADVANTAGE_AIR_RETRY,
    ADVANTAGE_AIR_SET_AIRCON,
    ADVANTAGE_AIR_SET_LIGHT,
    DOMAIN,
)

ADVANTAGE_AIR_SYNC_INTERVAL = 15
PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.COVER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.LIGHT,
]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Advantage Air config."""
    ip_address = entry.data[CONF_IP_ADDRESS]
    port = entry.data[CONF_PORT]
    api = advantage_air(
        ip_address,
        port=port,
        session=async_get_clientsession(hass),
        retry=ADVANTAGE_AIR_RETRY,
    )

    async def async_get():
        try:
            return await api.async_get()
        except ApiError as err:
            raise UpdateFailed(err) from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="Advantage Air",
        update_method=async_get,
        update_interval=timedelta(seconds=ADVANTAGE_AIR_SYNC_INTERVAL),
    )

    async def async_set_aircon(change):
        try:
            if await api.aircon.async_set(change):
                await coordinator.async_refresh()
        except ApiError as err:
            _LOGGER.warning(err)

    async def async_set_light(change):
        try:
            if await api.lights.async_set(change):
                await coordinator.async_refresh()
        except ApiError as err:
            _LOGGER.warning(err)

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        ADVANTAGE_AIR_COORDINATOR: coordinator,
        ADVANTAGE_AIR_SET_AIRCON: async_set_aircon,
        ADVANTAGE_AIR_SET_LIGHT: async_set_light,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Advantage Air Config."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
