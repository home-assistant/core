"""Sensor to indicate whether the current day is a workday."""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from . import util
from .binary_sensor import WorkdayBinarySensor
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Workday from a config entry."""

    _LOGGER.debug(
        "Setting up a new Workday entry: %s", util.config_entry_to_string(entry)
    )

    hass.data.setdefault(DOMAIN, {})
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    if not entry.update_listeners:
        entry.add_update_listener(update_listener)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading Workday entry %s", util.config_entry_to_string(entry))
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        _LOGGER.debug("Removing Workday sensor for entry_id=%s", entry.entry_id)
        hass.data[DOMAIN].pop(entry.entry_id)

    _LOGGER.debug("Workday sensor %s unload_ok=%s", entry.entry_id, unload_ok)
    return unload_ok


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    _LOGGER.debug("Updating Workday listener: %s", util.config_entry_to_string(entry))
    sensor: WorkdayBinarySensor | None = hass.data[DOMAIN].get(entry.entry_id, None)
    if sensor is None:
        _LOGGER.warning(
            "Tried to update config for Workday sensor %s (%s) but none found!",
            entry.unique_id,
            entry.entry_id,
        )
        return

    sensor.update_attributes(entry)
    await sensor.async_update()

    await hass.config_entries.async_reload(entry.entry_id)
