"""Helpers for helper integrations."""

from collections.abc import Callable, Coroutine
from typing import Any

from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, valid_entity_id

from . import device_registry as dr, entity_registry as er
from .event import async_track_entity_registry_updated_event
from .frame import ReportBehavior, report_usage


def async_handle_source_entity_changes(
    hass: HomeAssistant,
    *,
    helper_config_entry_id: str,
    set_source_entity_id_or_uuid: Callable[[str], None],
    source_device_id: str | None,
    source_entity_id_or_uuid: str,
    source_entity_removed: Callable[[], Coroutine[Any, Any, None]] | None = None,
    **kwargs: Any,
) -> CALLBACK_TYPE:
    """Handle changes to a helper entity's source entity.

    The following changes are handled:
    - Entity removal: If the source entity is removed:
      - If source_entity_removed is provided, it is called to handle the removal.
      - If source_entity_removed is not provided, The helper entity is updated to
      not link to any device.
    - Entity ID changed: If the source entity's entity ID changes and the source
      entity is identified by an entity ID, the set_source_entity_id_or_uuid is
      called. If the source entity is identified by a UUID, the helper config entry
      is reloaded.
    - Source entity moved to another device: The helper entity is updated to link
      to the new device. Then the helper config entry is reloaded.
    - Source entity removed from the device: The helper entity is updated to link
      to no device. Then the helper config entry is reloaded.

    :param set_source_entity_id_or_uuid: A function which updates the source entity
        ID or UUID, e.g., in the helper config entry options.
    :param source_entity_removed: A function which is called when the source entity
        is removed. This can be used to clean up any resources related to the source
        entity or ask the user to select a new source entity.
    """
    if "add_helper_config_entry_to_device" in kwargs:
        del kwargs["add_helper_config_entry_to_device"]
        # Adding the helper's config entry to the source device is no longer supported
        # now that a device belongs to a single config entry; the helper entities link to
        # the source device via their device_id instead.
        report_usage(
            "calls async_handle_source_entity_changes with "
            "add_helper_config_entry_to_device, which no longer has any effect",
            core_behavior=ReportBehavior.LOG,
            breaks_in_ha_version="2027.8.0",
        )
    if kwargs:
        raise TypeError(
            "async_handle_source_entity_changes() got unexpected keyword arguments "
            f"{', '.join(map(repr, kwargs))}"
        )

    async def async_registry_updated(
        event: Event[er.EventEntityRegistryUpdatedData],
    ) -> None:
        """Handle entity registry update."""
        nonlocal source_device_id

        data = event.data
        if data["action"] == "remove":
            if source_entity_removed:
                await source_entity_removed()
            else:
                for (
                    helper_entity_entry
                ) in entity_registry.entities.get_entries_for_config_entry_id(
                    helper_config_entry_id
                ):
                    # Update the helper entity to link to the new device (or no device)
                    entity_registry.async_update_entity(
                        helper_entity_entry.entity_id, device_id=None
                    )

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

        # The source entity has been moved to a different device; relink the helper
        # entities to the new device.
        for helper_entity in entity_registry.entities.get_entries_for_config_entry_id(
            helper_config_entry_id
        ):
            # Update the helper entity to link to the new device (or no device)
            entity_registry.async_update_entity(
                helper_entity.entity_id, device_id=source_entity_entry.device_id
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


def async_remove_helper_config_entry_from_source_device(
    hass: HomeAssistant,
    *,
    helper_config_entry_id: str,
    source_device_id: str,
) -> None:
    """Migrate a helper which has tried to add its config entry to the source device.

    A device belongs to a single config entry, and has been split into multiple devices
    if it was co-owned by multiple config entries. This function handles both ids a
    helper may pass as source_device_id:
    - a pre-migration composite id (the id of the device before it was split): its split
      children are known, so the helper's entities are moved onto the source-owned split
      and the helper-owned split is removed;
    - a plain source device id, with the helper owning a separate device: the helper's
      entities are moved onto the source device and the helper's device is removed.
    """
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)

    helper_entity_entries = er.async_entries_for_config_entry(
        entity_registry, helper_config_entry_id
    )

    # A pre-migration composite id resolves to the split devices it was migrated into
    # (empty for any other id). Act on those children directly instead of relying on the
    # deprecated config_entries shim and remove_config_entry_id: move the helper's entities
    # onto a source-owned split and remove the helper-owned split.
    if split_devices := device_registry.async_get_devices_for_composite_device_id(
        source_device_id
    ):
        helper_device = next(
            (
                device
                for device in split_devices
                if device.config_entry_id == helper_config_entry_id
            ),
            None,
        )
        if helper_device is None:
            return
        target_device_id = next(
            (
                device.id
                for device in split_devices
                if device.config_entry_id != helper_config_entry_id
            ),
            None,
        )
        for helper in helper_entity_entries:
            if helper.device_id == helper_device.id:
                entity_registry.async_update_entity(
                    helper.entity_id, device_id=target_device_id
                )
        device_registry.async_remove_device(helper_device.id)
        return

    # The helper owns a separate device. Move the helper's entities onto the source device,
    # then remove the helper's device.
    if not device_registry.async_get(source_device_id):
        return
    for helper_device in dr.async_entries_for_config_entry(
        device_registry, helper_config_entry_id
    ):
        for helper in helper_entity_entries:
            if helper.device_id == helper_device.id:
                entity_registry.async_update_entity(
                    helper.entity_id, device_id=source_device_id
                )
        device_registry.async_remove_device(helper_device.id)
