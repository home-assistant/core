"""The AirVisual Pro integration."""

import asyncio
from contextlib import suppress

from pyairvisual.node import NodeProError, NodeSamba

from homeassistant.const import (
    CONF_IP_ADDRESS,
    CONF_PASSWORD,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .coordinator import (
    AirVisualProConfigEntry,
    AirVisualProCoordinator,
    AirVisualProData,
)

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(
    hass: HomeAssistant, entry: AirVisualProConfigEntry
) -> None:
    """Set up AirVisual Pro from a config entry."""
    node = NodeSamba(entry.data[CONF_IP_ADDRESS], entry.data[CONF_PASSWORD])

    try:
        await node.async_connect()
    except NodeProError as err:
        raise ConfigEntryNotReady from err

    coordinator = AirVisualProCoordinator(hass, entry, node)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = AirVisualProData(coordinator=coordinator, node=node)

    async def async_shutdown(_: Event) -> None:
        """Define an event handler to disconnect from the websocket."""
        if coordinator.reload_task:
            with suppress(asyncio.CancelledError):
                coordinator.reload_task.cancel()
        await node.async_disconnect()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_shutdown)
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(
    hass: HomeAssistant, entry: AirVisualProConfigEntry
) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
    await entry.runtime_data.node.async_disconnect()
