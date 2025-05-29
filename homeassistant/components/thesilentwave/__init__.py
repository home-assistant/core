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
from .const import DOMAIN


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

    # Add the sensor entity to Home Assistant.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: TheSilentWaveConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
