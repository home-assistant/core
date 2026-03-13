"""The vitrea integration."""

from __future__ import annotations

import logging

from vitreaclient import VitreaClient

from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .coordinator import VitreaCoordinator
from .models import VitreaConfigEntry

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
        # Store coordinator as runtime data
        entry.runtime_data = coordinator

        # Set up platforms (this registers the entity add callbacks)
        await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

        # Perform first refresh to discover entities
        # This ensures callbacks are attached before status request is sent
        # triggers the coordinator to fetch initial data (with _async_update_data)
        await coordinator.async_config_entry_first_refresh()

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

    return True


async def async_unload_entry(hass: HomeAssistant, entry: VitreaConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)

    # Clean up coordinator
    if unload_ok and hasattr(entry, "runtime_data"):
        await entry.runtime_data.async_shutdown()

    return unload_ok
