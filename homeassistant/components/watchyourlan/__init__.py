"""The WatchYourLAN integration."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .coordinator import WatchYourLANUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up WatchYourLAN from a config entry."""

    # Create and store the coordinator in entry.runtime_data
    coordinator = WatchYourLANUpdateCoordinator(hass, entry.data)

    # Attempt the first refresh to validate if the integration can be set up
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:
        # Log the failure and raise ConfigEntryNotReady if it can't connect or fetch data
        _LOGGER.error("Failed to setup WatchYourLAN: %s", err)
        raise ConfigEntryNotReady from err

    entry.runtime_data = {"coordinator": coordinator}

    # If the setup is successful, forward the entry to other platforms (e.g., sensor)
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Correctly unload the sensor platform by passing "sensor" as a string
    await hass.config_entries.async_forward_entry_unload(entry, "sensor")
    return True
