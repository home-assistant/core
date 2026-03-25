"""Helper functions for Acmeda Pulse."""

from __future__ import annotations

from typing import TYPE_CHECKING

from aiopulse import Roller

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, LOGGER

if TYPE_CHECKING:
    from . import AcmedaConfigEntry


@callback
def async_add_acmeda_entities(
    hass: HomeAssistant,
    entity_class: type,
    config_entry: AcmedaConfigEntry,
    current: set[int],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add any new entities."""
    hub = config_entry.runtime_data
    LOGGER.debug("Looking for new %s on: %s", entity_class.__name__, hub.host)

    api = hub.api.rollers

    new_items = []
    for unique_id, roller in api.items():
        if unique_id not in current:
            LOGGER.debug("New %s %s", entity_class.__name__, unique_id)
            new_item = entity_class(roller)
            current.add(unique_id)
            new_items.append(new_item)

    async_add_entities(new_items)


async def update_devices(
    hass: HomeAssistant, config_entry: ConfigEntry, api: dict[int, Roller]
) -> None:
    """Tell hass that device info has been updated."""
    dev_registry = dr.async_get(hass)

    for api_item in api.values():
        # Update Device name
        device = dev_registry.async_get_device(identifiers={(DOMAIN, api_item.id)})
        if device is not None:
            dev_registry.async_update_device(
                device.id,
                name=api_item.name,
            )
