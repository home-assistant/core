"""Support for WLED."""
from __future__ import annotations

from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import WLEDDataUpdateCoordinator

PLATFORMS = (LIGHT_DOMAIN, SENSOR_DOMAIN, SWITCH_DOMAIN)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up WLED from a config entry."""
    coordinator = WLEDDataUpdateCoordinator(hass, host=entry.data[CONF_HOST])
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # For backwards compat, set unique ID
    if entry.unique_id is None:
        hass.config_entries.async_update_entry(
            entry, unique_id=coordinator.data.info.mac_address
        )

    # Set up all platforms for this device/entry.
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload WLED config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        del hass.data[DOMAIN][entry.entry_id]
    return unload_ok
