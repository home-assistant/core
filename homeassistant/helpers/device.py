"""Provides useful helpers for handling devices."""

from homeassistant.core import HomeAssistant, callback

from . import device_registry as dr, entity_registry as er
from .frame import ReportBehavior, report_usage


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
def async_entity_id_to_device(
    hass: HomeAssistant,
    entity_id_or_uuid: str,
) -> dr.DeviceEntry | None:
    """Resolve the device entry for the entity id or entity uuid."""

    if (device_id := async_entity_id_to_device_id(hass, entity_id_or_uuid)) is None:
        return None

    return dr.async_get(hass).async_get(device_id)


@callback
def async_device_info_to_link_from_entity(
    hass: HomeAssistant,
    entity_id_or_uuid: str,
) -> dr.DeviceInfo | None:
    """DeviceInfo with information to link a device from an entity.

    Deprecated, always returns None; set entity.device_entry instead.
    """
    report_usage(
        "calls async_device_info_to_link_from_entity, which is deprecated and always "
        "returns None: a device_info carrying another device's identifiers implicitly "
        "added the caller's config entry to that device, which a single-config-entry "
        "device can't represent. Set entity.device_entry = "
        "async_entity_id_to_device(hass, source_entity_id) instead",
        core_behavior=ReportBehavior.LOG,
        breaks_in_ha_version="2027.8.0",
    )
    return None


@callback
def async_device_info_to_link_from_device_id(
    hass: HomeAssistant,
    device_id: str | None,
) -> dr.DeviceInfo | None:
    """DeviceInfo with information to link a device from a device id.

    Deprecated, always returns None; set entity.device_entry instead.
    """
    report_usage(
        "calls async_device_info_to_link_from_device_id, which is deprecated and always "
        "returns None: a device_info carrying another device's identifiers implicitly "
        "added the caller's config entry to that device, which a single-config-entry "
        "device can't represent. Set entity.device_entry to the target device instead",
        core_behavior=ReportBehavior.LOG,
        breaks_in_ha_version="2027.8.0",
    )
    return None


@callback
def async_remove_stale_devices_links_keep_entity_device(
    hass: HomeAssistant,
    entry_id: str,
    source_entity_id_or_uuid: str | None,
) -> None:
    """Remove entry_id from all devices except that of source_entity_id_or_uuid.

    Deprecated, does nothing: a device belongs to a single config entry, so a helper no
    longer adds its config entry to the source device and there is no stale config entry
    link to remove. Call helper_integration.async_remove_helper_devices with
    sweep_helper_devices=True to remove devices a helper created for previously selected
    source devices.
    """
    report_usage(
        "calls async_remove_stale_devices_links_keep_entity_device, which is deprecated "
        "and does nothing: a device belongs to a single config entry, so a helper no "
        "longer adds its config entry to the source device. Call "
        "homeassistant.helpers.helper_integration.async_remove_helper_devices with "
        "sweep_helper_devices=True instead",
        core_behavior=ReportBehavior.LOG,
        breaks_in_ha_version="2027.8.0",
    )


@callback
def async_remove_stale_devices_links_keep_current_device(
    hass: HomeAssistant,
    entry_id: str,
    current_device_id: str | None,
) -> None:
    """Remove entry_id from all devices except current_device_id.

    Deprecated, does nothing: a device belongs to a single config entry, so a helper no
    longer adds its config entry to another device and there is no stale config entry link
    to remove. Call helper_integration.async_remove_helper_devices with
    sweep_helper_devices=True to remove devices a helper created for previously selected
    source devices.
    """
    report_usage(
        "calls async_remove_stale_devices_links_keep_current_device, which is deprecated "
        "and does nothing: a device belongs to a single config entry, so a helper no "
        "longer adds its config entry to another device. Call "
        "homeassistant.helpers.helper_integration.async_remove_helper_devices with "
        "sweep_helper_devices=True instead",
        core_behavior=ReportBehavior.LOG,
        breaks_in_ha_version="2027.8.0",
    )
