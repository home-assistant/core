"""Helpers for helper integrations."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any

from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, valid_entity_id

from . import device_registry as dr, entity_registry as er
from .event import async_track_entity_registry_updated_event


def async_handle_source_entity_changes(
    hass: HomeAssistant,
    *,
    helper_config_entry_id: str,
    set_source_entity_id_or_uuid: Callable[[str], None],
    source_device_id: str | None,
    source_entity_id_or_uuid: str,
    source_entity_removed: Callable[[], Coroutine[Any, Any, None]],
) -> CALLBACK_TYPE:
    """Handle changes to a helper entity's source entity.

    The following changes are handled:
    - Entity removal: If the source entity is removed, the helper config entry
      is removed, and the helper entity is cleaned up.
    - Entity ID changed: If the source entity's entity ID changes and the source
      entity is identified by an entity ID, the set_source_entity_id_or_uuid is
      called. If the source entity is identified by a UUID, the helper config entry
      is reloaded.
    - Source entity moved to another device: The helper entity is updated to link
      to the new device, and the helper config entry removed from the old device
      and added to the new device. Then the helper config entry is reloaded.
    - Source entity removed from the device: The helper entity is updated to link
      to no device, and the helper config entry removed from the old device. Then
      the helper config entry is reloaded.

    :param set_source_entity_id_or_uuid: A function which updates the source entity
        ID or UUID, e.g., in the helper config entry options.
    :param source_entity_removed: A function which is called when the source entity
        is removed. This can be used to clean up any resources related to the source
        entity or ask the user to select a new source entity.
    """

    async def async_registry_updated(
        event: Event[er.EventEntityRegistryUpdatedData],
    ) -> None:
        """Handle entity registry update."""
        nonlocal source_device_id

        data = event.data
        if data["action"] == "remove":
            await source_entity_removed()

        if data["action"] != "update":
            return

        if "entity_id" in data["changes"]:
            # Entity_id changed, update or reload the config entry
            if valid_entity_id(source_entity_id_or_uuid):
                # If the entity is pointed to by an entity ID, update the entry
                set_source_entity_id_or_uuid(data["entity_id"])
            else:
                await hass.config_entries.async_reload(helper_config_entry_id)

        if not source_device_id or "device_id" not in data["changes"]:
            return

        # Handle the source entity being moved to a different device or removed
        # from the device
        if (
            not (source_entity_entry := entity_registry.async_get(data["entity_id"]))
            or not device_registry.async_get(source_device_id)
            or source_entity_entry.device_id == source_device_id
        ):
            # No need to do any cleanup
            return

        # The source entity has been moved to a different device, update the helper
        # entities to link to the new device and the helper device to include the
        # helper config entry
        for helper_entity in entity_registry.entities.get_entries_for_config_entry_id(
            helper_config_entry_id
        ):
            # Update the helper entity to link to the new device (or no device)
            entity_registry.async_update_entity(
                helper_entity.entity_id, device_id=source_entity_entry.device_id
            )

        if source_entity_entry.device_id is not None:
            device_registry.async_update_device(
                source_entity_entry.device_id,
                add_config_entry_id=helper_config_entry_id,
            )

        device_registry.async_update_device(
            source_device_id, remove_config_entry_id=helper_config_entry_id
        )
        source_device_id = source_entity_entry.device_id

        # Reload the config entry so the helper entity is recreated with
        # correct device info
        await hass.config_entries.async_reload(helper_config_entry_id)

    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)
    source_entity_id = er.async_validate_entity_id(
        entity_registry, source_entity_id_or_uuid
    )
    return async_track_entity_registry_updated_event(
        hass, source_entity_id, async_registry_updated
    )
