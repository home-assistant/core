"""The Lektrico Charging Station integration."""

from __future__ import annotations

from aiohttp import ClientSession
from lektricowifi import Device

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_HW_VERSION,
    ATTR_SERIAL_NUMBER,
    CONF_FRIENDLY_NAME,
    CONF_HOST,
    CONF_TYPE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CHARGERS_PLATFORMS, DOMAIN, LB_DEVICES_PLATFORMS
from .coordinator import LektricoDeviceDataUpdateCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Lektrico Charging Station from a config entry."""
    session = async_get_clientsession(hass)

    coordinator = await _create_coordinator(hass, entry, session)

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, _get_platforms(entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(
        entry, _get_platforms(entry)
    ):
        # Cleanup
        del hass.data[DOMAIN][entry.entry_id]
        if not hass.data[DOMAIN]:
            del hass.data[DOMAIN]
    return unload_ok


async def _create_coordinator(
    hass: HomeAssistant, entry: ConfigEntry, session: ClientSession
) -> LektricoDeviceDataUpdateCoordinator:
    """Create the coordinator for Lektrico Charging Station device."""
    return LektricoDeviceDataUpdateCoordinator(
        hass,
        entry.data[CONF_FRIENDLY_NAME],
        entry.data[CONF_HOST],
        session,
        entry.data[ATTR_SERIAL_NUMBER],
        entry.data[ATTR_HW_VERSION],
        entry.data[CONF_TYPE],
    )


def _get_platforms(entry: ConfigEntry) -> list[Platform]:
    """Return the platforms for this type of device."""
    _device_type: str = entry.data[CONF_TYPE]
    if _device_type in (Device.TYPE_1P7K, Device.TYPE_3P22K):
        return CHARGERS_PLATFORMS
    return LB_DEVICES_PLATFORMS
