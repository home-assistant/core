"""The TIS Control integration."""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass
import logging

from TISApi.api import TISApi

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DEVICES_DICT, DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass
class TISData:
    """TIS Control data stored in the ConfigEntry."""

    tis_api: TISApi
    listener_task: asyncio.Task | None = None


# Define the Home Assistant platforms that this integration will support.
PLATFORMS: list[Platform] = [Platform.SWITCH]

# Create a type alias for a ConfigEntry specific to this integration.
type TISConfigEntry = ConfigEntry[TISData]


async def async_setup_entry(hass: HomeAssistant, entry: TISConfigEntry) -> bool:
    """Set up TIS Control from a config entry."""
    # Get the TISApi instance from the user's entry.
    tis_api: TISApi = TISApi(
        port=int(entry.data[CONF_PORT]),
        domain=DOMAIN,
        devices_dict=DEVICES_DICT,
    )

    try:
        await tis_api.connect()
    except (ConnectionError, OSError) as e:
        # If connection fails, raise ConfigEntryNotReady
        # to prompt Home Assistant to retry setup later.
        raise ConfigEntryNotReady(
            f"Unable to connect to TIS Control on port {entry.data[CONF_PORT]}: {e}"
        ) from e

    entry.runtime_data = TISData(tis_api=tis_api)

    async def listen_for_events() -> None:
        """Listen for events from TIS."""
        try:
            # This will run forever, pulling data from the library.
            async for event in tis_api.consume_events():
                hass.bus.async_fire(f"{DOMAIN}_event", event)
        except asyncio.CancelledError:
            _LOGGER.debug("TIS event listener task cancelled")
        except Exception:
            _LOGGER.exception("Unexpected error while processing TIS event")

    # Add this listener to the HA loop as a background task.
    # async_create_background_task automatically tracks the task and ensures it is cancelled on unload.
    entry.runtime_data.listener_task = entry.async_create_background_task(
        hass, listen_for_events(), "tis_event_listener"
    )

    try:
        await tis_api.scan_devices()
    except (ConnectionError, OSError) as e:
        _LOGGER.error(
            "Connection error occurred while scanning for devices on port %d: %s",
            entry.data[CONF_PORT],
            e,
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: TISConfigEntry) -> bool:
    """Unload a config entry."""
    # Unload the platforms associated with this entry, which will remove the entities.
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    # Only disconnect the API if the platforms successfully unloaded
    if unload_ok:
        # However, we also explicitly cancel and await it to ensure it has stopped
        # before disconnecting the API.
        if (task := entry.runtime_data.listener_task) is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
            entry.runtime_data.listener_task = None

        entry.runtime_data.tis_api.disconnect()

    return unload_ok
