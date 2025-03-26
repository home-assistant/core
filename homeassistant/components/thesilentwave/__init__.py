"""The Silent Wave integration."""

import logging

from .coordinator import TheSilentWaveCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config):
    """Set up the component."""
    return True


async def async_setup_entry(hass, entry):
    """Set up a sensor from a config entry."""

    # Fetch the configuration data from the entry
    name = entry.data.get("name", "TheSilentWaveSensor")
    host = entry.data.get("host", "")
    scan_interval = entry.data.get("scan_interval", 10)
    url = f"http://{host}:8080/api/status"

    # Create the coordinator with scan_interval
    coordinator = TheSilentWaveCoordinator(hass, name, url, scan_interval)
    await coordinator.async_config_entry_first_refresh()

    # Register the sensor entity
    hass.data.setdefault("thesilentwave", {})
    hass.data["thesilentwave"][entry.entry_id] = coordinator

    # Add the sensor entity to Home Assistant
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])

    return True
