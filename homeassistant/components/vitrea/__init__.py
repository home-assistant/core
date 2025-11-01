"""The vitrea integration."""

from __future__ import annotations

import logging

from vitreaclient import VitreaClient

from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady

from .coordinator import VitreaCoordinator
from .models import VitreaConfigEntry, VitreaRuntimeData

_LOGGER = logging.getLogger(__name__)

# List the platforms that you want to support
_PLATFORMS = [Platform.COVER]


async def async_setup_entry(hass: HomeAssistant, entry: VitreaConfigEntry) -> bool:
    """Set up vitrea from a config entry."""
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    _LOGGER.debug(
        "Connecting to Vitrea box at %s:%s with config: %s", host, port, entry.data
    )
    client = VitreaClient(host, port)
    coordinator = VitreaCoordinator(hass, client, entry)
    try:
        await coordinator.async_setup()
        # Initialize runtime data with the client and coordinator
        entry.runtime_data = VitreaRuntimeData(
            client=client, coordinator=coordinator, hass=hass
        )

        # Set up platforms
        await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)
        # After platforms are set up, trigger status request
        await coordinator.async_platforms_ready()
        _LOGGER.info("Vitrea integration setup complete")

    except ConnectionError as ex:
        # Connection failed - device may be offline or unreachable
        raise ConfigEntryNotReady(
            f"Failed to connect to Vitrea at {host}:{port}"
        ) from ex
    except TimeoutError as ex:
        # Connection timeout - device may be slow to respond
        raise ConfigEntryNotReady(
            f"Timeout connecting to Vitrea at {host}:{port}"
        ) from ex
    except Exception as ex:
        # Unexpected error during setup
        _LOGGER.exception("Unexpected error setting up Vitrea integration")
        raise ConfigEntryError(f"Unknown error connecting to Vitrea: {ex}") from ex

    return True


async def async_unload_entry(hass: HomeAssistant, entry: VitreaConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)

    # Clean up coordinator
    if unload_ok and hasattr(entry, "runtime_data"):
        await entry.runtime_data.coordinator.async_shutdown()

    return unload_ok
