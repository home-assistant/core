"""The PTDevices integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_TOKEN, CONF_DEVICE_ID, Platform
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN
from .coordinator import PTDevicesCoordinator

# PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]
PLATFORMS: list[Platform] = [Platform.SENSOR]


CONFIG_SCHEMA = cv.removed(DOMAIN, raise_if_present=False)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up PTDevices from a config entry."""
    deviceId: str = config_entry.data[CONF_DEVICE_ID]
    authToken: str = config_entry.data[CONF_API_TOKEN]

    coordinator = PTDevicesCoordinator(hass, deviceId, authToken)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][config_entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok and DOMAIN in hass.data:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
