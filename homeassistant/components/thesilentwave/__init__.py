"""The Silent Wave integration."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from pysilentwave.exceptions import SilentWaveError

from .coordinator import (
    TheSilentWaveCoordinator,
    TheSilentWaveConfigEntry,
)


_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(
    hass: HomeAssistant, entry: TheSilentWaveConfigEntry
) -> bool:
    """Set up TheSilentWave from a config entry."""
    # Fetch the configuration data from the entry.
    name = entry.data["name"]
    host = entry.data["host"]

    entry.runtime_data = coordinator = TheSilentWaveCoordinator(hass, name, host)

    # Try to do the first refresh to verify that the device is reachable.
    try:
        await coordinator.async_config_entry_first_refresh()
    except SilentWaveError as exc:
        _LOGGER.debug("Failed to communicate with device: %s", exc)
        raise ConfigEntryNotReady(f"Cannot connect to device at {host}") from exc

    # Register the sensor entity.
    hass.data.setdefault("thesilentwave", {})
    hass.data["thesilentwave"][entry.entry_id] = coordinator

    # Add the sensor entity to Home Assistant.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: TheSilentWaveConfigEntry
) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok and entry.entry_id in hass.data.get("thesilentwave", {}):
        hass.data["thesilentwave"].pop(entry.entry_id)

    return unload_ok
