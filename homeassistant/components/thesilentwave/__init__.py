"""The Silent Wave integration."""

import logging

from homeassistant.config_entries import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv

from pysilentwave.exceptions import SilentWaveError

from .coordinator import TheSilentWaveCoordinator


_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry):
    """Fetch the configuration data from the entry."""

    # Fetch the configuration data from the entry.
    name = entry.data.get("name", "TheSilentWave")
    host = entry.data.get("host", "")
    scan_interval = 10  # Fixed scan interval

    # Create the coordinator with scan_interval.
    coordinator = TheSilentWaveCoordinator(hass, name, host, scan_interval)

    # Try to do the first refresh to verify that the device is reachable.
    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady:
        # Just log a simple error without including the long exception chain.
        _LOGGER.error("Failed to connect to device at %s", host)
        raise
    except SilentWaveError as exc:
        raise ConfigEntryNotReady("Failed to communicate with device") from exc

    # Register the sensor entity.
    hass.data.setdefault("thesilentwave", {})
    hass.data["thesilentwave"][entry.entry_id] = coordinator

    # Set runtime data.
    entry.runtime_data = {"coordinator": coordinator}

    # Add the sensor entity to Home Assistant.
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])

    return True


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, ["sensor"])

    if unload_ok and entry.entry_id in hass.data.get("thesilentwave", {}):
        hass.data["thesilentwave"].pop(entry.entry_id)

    return unload_ok
