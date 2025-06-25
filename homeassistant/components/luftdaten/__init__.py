"""Support for Sensor.Community stations.

Sensor.Community was previously called Luftdaten, hence the domain differs from
the integration name.
"""

from __future__ import annotations

from luftdaten import Luftdaten

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import CONF_SENSOR_ID, DOMAIN
from .coordinator import LuftdatenDataUpdateCoordinator

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Sensor.Community as config entry."""

    # For backwards compat, set unique ID
    if entry.unique_id is None:
        hass.config_entries.async_update_entry(
            entry, unique_id=str(entry.data[CONF_SENSOR_ID])
        )

    sensor_community = Luftdaten(entry.data[CONF_SENSOR_ID])

    coordinator = LuftdatenDataUpdateCoordinator(hass, entry, sensor_community)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an Sensor.Community config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        del hass.data[DOMAIN][entry.entry_id]
    return unload_ok
