"""The Grid Connect integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)

from .api import AuthenticationError
from .bluetooth import (
    discover_bluetooth_devices,
)  # Import the Bluetooth discovery function

_LOGGER = logging.getLogger(__name__)  # Set up the logger

# Define the platforms that this integration supports
_PLATFORMS: list[Platform] = [Platform.EVENT, Platform.BINARY_SENSOR]

# Type alias for better readability
type GridConnectConfigEntry = ConfigEntry


async def async_setup_entry(hass: HomeAssistant, entry: GridConnectConfigEntry) -> bool:
    """Set up Grid Connect from a config entry."""
    try:
        if entry.data.get("use_bluetooth"):
            devices = await discover_bluetooth_devices()
            for device in devices:
                _LOGGER.info("Processing device: %s, %s", device.name, device.address)
            # Add further processing logic as needed
        else:
            # Forward the configuration entry to the defined platforms
            await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

            entry.runtime_data = {"key": "value"}  # Replace with actual runtime data

            return True

    except AuthenticationError as err:
        raise ConfigEntryAuthFailed("Authentication failed") from err
    except ConnectionError as err:
        raise ConfigEntryNotReady("Could not connect to the device") from err
    except Exception as err:
        raise ConfigEntryError(f"Unexpected error: {err}") from err

    return False


async def async_unload_entry(
    hass: HomeAssistant, entry: GridConnectConfigEntry
) -> bool:
    """Unload a config entry."""

    # Remove the integration platforms when unloading the configuration entry
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
