"""Provides useful helpers for handling devices."""

from homeassistant.core import HomeAssistant, callback

from . import device_registry as dr, entity_registry as er


@callback
def async_entity_id_to_device_id(
    hass: HomeAssistant,
    entity_id_or_uuid: str,
) -> str | None:
    """Resolve the device id to the entity id or entity uuid."""

    ent_reg = er.async_get(hass)

    entity_id = er.async_validate_entity_id(ent_reg, entity_id_or_uuid)
    if (entity := ent_reg.async_get(entity_id)) is None:
        return None

    return entity.device_id


@callback
def async_device_info_to_link_from_entity(
    hass: HomeAssistant,
    entity_id_or_uuid: str,
) -> dr.DeviceInfo | None:
    """DeviceInfo with information to link a device from an entity.

    DeviceInfo will only return information to categorize as a link.
    """

    return async_device_info_to_link_from_device_id(
        hass,
        async_entity_id_to_device_id(hass, entity_id_or_uuid),
    )


@callback
def async_device_info_to_link_from_device_id(
    hass: HomeAssistant,
    device_id: str | None,
) -> dr.DeviceInfo | None:
    """DeviceInfo with information to link a device from a device id.

    DeviceInfo will only return information to categorize as a link.
    """

    dev_reg = dr.async_get(hass)

    if device_id is None or (device := dev_reg.async_get(device_id=device_id)) is None:
        return None

    return dr.DeviceInfo(
        identifiers=device.identifiers,
        connections=device.connections,
    )


@callback
def async_remove_stale_devices_links_keep_entity_device(
    hass: HomeAssistant,
    entry_id: str,
    source_entity_id_or_uuid: str | None,
) -> None:
    """Remove entry_id from all devices except that of source_entity_id_or_uuid.

    Also moves all entities linked to the entry_id to the device of
    source_entity_id_or_uuid.
    """

    async_remove_stale_devices_links_keep_current_device(
        hass=hass,
        entry_id=entry_id,
        current_device_id=async_entity_id_to_device_id(hass, source_entity_id_or_uuid)
        if source_entity_id_or_uuid
        else None,
    )


@callback
def async_remove_stale_devices_links_keep_current_device(
    hass: HomeAssistant,
    entry_id: str,
    current_device_id: str | None,
) -> None:
    """Remove entry_id from all devices except current_device_id."""

    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)

    # Make sure all entities are linked to the correct device
    for entity in ent_reg.entities.get_entries_for_config_entry_id(entry_id):
        if entity.device_id == current_device_id:
            continue
        ent_reg.async_update_entity(entity.entity_id, device_id=current_device_id)

    # Removes all devices from the config entry that are not the same as the current device
    for device in dev_reg.devices.get_devices_for_config_entry_id(entry_id):
        if device.id == current_device_id:
            continue
        dev_reg.async_update_device(device.id, remove_config_entry_id=entry_id)
