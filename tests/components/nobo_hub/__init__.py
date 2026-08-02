"""Tests for the Nobø Ecohub integration."""

from unittest.mock import MagicMock

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er


def device_identifiers(
    device_registry: dr.DeviceRegistry, entry_id: str
) -> set[tuple[str, str]]:
    """Return the identifiers of all devices for the config entry."""
    identifiers: set[tuple[str, str]] = set()
    for device in dr.async_entries_for_config_entry(device_registry, entry_id):
        identifiers |= device.identifiers
    return identifiers


def entity_unique_ids(entity_registry: er.EntityRegistry, entry_id: str) -> set[str]:
    """Return the unique ids of all entities for the config entry."""
    return {
        entry.unique_id
        for entry in er.async_entries_for_config_entry(entity_registry, entry_id)
    }


def dispatch_hub_update(hub: MagicMock) -> None:
    """Fire the hub's registered push-update callbacks without awaiting.

    Mirrors pynobo dispatching a single message: call this twice in a row to
    reproduce buffered messages processed with no event-loop yield between them.
    """
    for call in hub.register_callback.call_args_list:
        call.args[0](hub)


async def fire_hub_update(hass: HomeAssistant, hub: MagicMock) -> None:
    """Fire the hub's registered push-update callbacks and wait for state to settle."""
    dispatch_hub_update(hub)
    await hass.async_block_till_done()


async def fire_hub_connection(
    hass: HomeAssistant, hub: MagicMock, connected: bool
) -> None:
    """Fire the hub's registered connection-state callbacks and wait for state to settle."""
    hub.connected = connected
    for call in hub.register_connection_callback.call_args_list:
        call.args[0](hub, connected)
    await hass.async_block_till_done()
