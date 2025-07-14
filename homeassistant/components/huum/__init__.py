"""The Huum integration."""

from __future__ import annotations

from datetime import timedelta

from huum.huum import Huum

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN, PLATFORMS, UPDATE_INTERVAL
from .coordinator import HuumDataUpdateCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Huum from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]

    huum = Huum(username, password, session=async_get_clientsession(hass))

    device_info = DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name="Huum sauna",
        manufacturer="Huum",
        model="UKU WiFi",
    )

    coordinator = HuumDataUpdateCoordinator(
        hass,
        huum=huum,
        device_info=device_info,
        unique_id=entry.entry_id,
        update_interval=timedelta(seconds=UPDATE_INTERVAL),
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
