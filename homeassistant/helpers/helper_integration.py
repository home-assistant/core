"""Helpers for helper integrations."""

from collections.abc import Callable, Collection, Coroutine
from typing import Any

from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, valid_entity_id

from . import device_registry as dr, entity_registry as er
from .deprecation import deprecated_function
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


def async_remove_helper_devices(
    hass: HomeAssistant,
    *,
    helper_config_entry_id: str,
    source_device_id: str | None,
    sweep_helper_devices: bool = False,
    keep_device_ids: Collection[str] = (),
) -> None:
    """Migrate a helper which has tried to own a device instead of just linking to it.

    In the single-config-entry device model a helper can no longer co-own the source
    device. A helper that co-owned it before the single-config-entry device was introduced
    now owns a split of it (linked by the pre-migration composite_device_id); a helper that
    declared the source device's identifiers or connections in its device_info afterwards
    now owns a fork (a separate device that copied that identity). This removes the helper's
    duplicate device(s) and relinks its entities to the source device, or detaches them when
    the source has no concrete device to hold the link.

    :param helper_config_entry_id: The config entry id of the helper being migrated.
    :param source_device_id: The device the helper should link its entities to. A concrete
        device relinks the entities to it. A pre-migration composite id and None have no
        concrete device to hold the link, so the entities are detached; in targeted mode
        a composite or None source with no matching duplicate is a no-op.
    :param sweep_helper_devices: By default only the helper's single duplicate of
        source_device_id (a split or fork) is removed. When True, every device the
        helper owns except source_device_id and keep_device_ids is removed instead -
        even when source_device_id no longer exists, in which case the helper's
        entities are left without a device. Use this to clean up devices the helper
        created but never removed itself, such as a fork left behind for each
        previously selected source device.
    :param keep_device_ids: Devices the helper legitimately owns which must not be removed.
        Only consulted when sweep_helper_devices is True.
    """
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)

    source_device = (
        device_registry.async_get(source_device_id)
        if source_device_id is not None
        else None
    )
    if source_device is None:
        # No source device (gone, or none selected). In sweep mode the helper's devices are
        # still removed, leaving its entities without a device; targeted mode has no duplicate
        # to match.
        if sweep_helper_devices:
            _sweep_helper_devices(
                device_registry,
                entity_registry,
                helper_config_entry_id,
                None,
                keep_device_ids,
            )
        return

    # source_device_id is either the pre-migration composite id (source_device is then the
    # synthesized composite) or a concrete device. Its splits, if any, share this id as
    # their composite_device_id.
    source_is_concrete = source_device_id in device_registry.devices
    composite_device_id = (
        source_device.composite_device_id if source_is_concrete else source_device_id
    )
    target_device_id = source_device_id if source_is_concrete else None

    if sweep_helper_devices:
        _sweep_helper_devices(
            device_registry,
            entity_registry,
            helper_config_entry_id,
            target_device_id,
            keep_device_ids,
        )
    else:
        _remove_duplicate_helper_device(
            device_registry,
            entity_registry,
            helper_config_entry_id,
            source_device,
            composite_device_id,
            target_device_id,
        )


def _remove_duplicate_helper_device(
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    helper_config_entry_id: str,
    source_device: dr.DeviceEntry,
    composite_device_id: str | None,
    target_device_id: str | None,
) -> None:
    """Remove the helper's single duplicate of the source device.

    The duplicate is either a split of the same pre-migration composite (linked by
    composite_device_id) or a fork that copied the source device's identifiers or
    connections into its device_info. Match on both, and only among the helper's own
    devices, so unrelated helper-owned devices are left untouched.
    """
    duplicate = next(
        (
            device
            for device in dr.async_entries_for_config_entry(
                device_registry, helper_config_entry_id
            )
            if (
                composite_device_id is not None
                and device.composite_device_id == composite_device_id
            )
            or device.identifiers & source_device.identifiers
            or device.connections & source_device.connections
        ),
        None,
    )
    if duplicate is None:
        return
    for entity in er.async_entries_for_config_entry(
        entity_registry, helper_config_entry_id
    ):
        if entity.device_id == duplicate.id:
            entity_registry.async_update_entity(
                entity.entity_id, device_id=target_device_id
            )
    device_registry.async_remove_device(duplicate.id)


def _sweep_helper_devices(
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    helper_config_entry_id: str,
    target_device_id: str | None,
    keep_device_ids: Collection[str],
) -> None:
    """Remove every device the helper owns except the target and the allow-list.

    Sweeps up devices left behind when the user repeatedly changed the source device: the
    helper's entities are relinked to the target device (except those already on a kept
    device) and the other helper-owned devices are removed.
    """
    kept_device_ids = {*keep_device_ids}
    if target_device_id is not None:
        kept_device_ids.add(target_device_id)
    for entity in er.async_entries_for_config_entry(
        entity_registry, helper_config_entry_id
    ):
        if entity.device_id not in kept_device_ids:
            entity_registry.async_update_entity(
                entity.entity_id, device_id=target_device_id
            )
    for device in dr.async_entries_for_config_entry(
        device_registry, helper_config_entry_id
    ):
        if device.id not in kept_device_ids:
            device_registry.async_remove_device(device.id)


@deprecated_function(
    "homeassistant.helpers.helper_integration.async_remove_helper_devices",
    breaks_in_ha_version="2027.8.0",
)
def async_remove_helper_config_entry_from_source_device(
    hass: HomeAssistant,
    *,
    helper_config_entry_id: str,
    source_device_id: str,
) -> None:
    """Migrate a helper which has tried to add its config entry to the source device.

    Deprecated alias of async_remove_helper_devices, kept for custom integrations.
    """
    async_remove_helper_devices(
        hass,
        helper_config_entry_id=helper_config_entry_id,
        source_device_id=source_device_id,
    )
