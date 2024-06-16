"""Provides useful helpers for dealing with devices."""

from homeassistant.core import HomeAssistant, callback

from . import device_registry as dr, entity_registry as er


@callback
def async_entity_id_to_device_id(
    hass: HomeAssistant,
    entity_id: str,
) -> str | None:
    """Resolve the device id to the entity id."""

    ent_reg = er.async_get(hass)
    if ((entity := ent_reg.async_get(entity_id)) is not None) and (
        entity.device_id is not None
    ):
        return entity.device_id
    return None


@callback
async def async_device_info_to_link(
    hass: HomeAssistant,
    device_id: str | None = None,
    entity_id: str | None = None,
) -> dr.DeviceInfo | None:
    """DeviceInfo with the information to link a device in a config entry in the Link category.

    It can directly receive a device ID or an entity ID to be extracted from the device.
    """

    dev_reg = dr.async_get(hass)

    if device_id is None and entity_id is not None:
        device_id = async_entity_id_to_device_id(hass, entity_id=entity_id)

    if (
        device_id is not None
        and (device := dev_reg.async_get(device_id=device_id)) is not None
    ):
        return dr.DeviceInfo(
            identifiers=device.identifiers,
            connections=device.connections,
        )

    return None


@callback
async def async_remove_stale_device_links_helpers(
    hass: HomeAssistant,
    entry_id: str,
    source_entity_id: str | None = None,
    device_id: str | None = None,
) -> None:
    """Remove obsolete devices from helper config entries that inherit from source entity.

    This can receive an entity ID from which the correct device ID will be extracted or it
    can directly receive a device ID to be kept in the config entry.
    Without both entity ID and device ID arguments removes all device bindings from the config
    entry.
    """

    if device_id is None and source_entity_id is not None:
        device_id = async_entity_id_to_device_id(hass, entity_id=source_entity_id)

    dev_reg = dr.async_get(hass)
    # Removes all devices from the config entry that are not the same as the current device
    for device in dev_reg.devices.get_devices_for_config_entry_id(entry_id):
        if device.id == device_id:
            continue
        dev_reg.async_update_device(device.id, remove_config_entry_id=entry_id)
