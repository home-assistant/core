"""Helper functions for webOS Smart TV."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntry

from . import WebOsClientWrapper, async_control_connect
from .const import DATA_CONFIG_ENTRY, DOMAIN, LIVE_TV_APP_ID, WEBOSTV_EXCEPTIONS


@callback
def async_get_device_entry_by_device_id(
    hass: HomeAssistant, device_id: str
) -> DeviceEntry:
    """
    Get Device Entry from Device Registry by device ID.

    Raises ValueError if device ID is invalid.
    """
    device_reg = dr.async_get(hass)
    if (device := device_reg.async_get(device_id)) is None:
        raise ValueError(f"Device {device_id} is not a valid {DOMAIN} device.")

    return device


@callback
def async_is_device_config_entry_not_loaded(
    hass: HomeAssistant, device_id: str
) -> bool:
    """Return whether device's config entries are not loaded."""
    device = async_get_device_entry_by_device_id(hass, device_id)
    return any(
        (entry := hass.config_entries.async_get_entry(entry_id))
        and entry.state != ConfigEntryState.LOADED
        for entry_id in device.config_entries
    )


@callback
def async_get_device_id_from_entity_id(hass: HomeAssistant, entity_id: str) -> str:
    """
    Get device ID from an entity ID.

    Raises ValueError if entity or device ID is invalid.
    """
    ent_reg = er.async_get(hass)
    entity_entry = ent_reg.async_get(entity_id)

    if (
        entity_entry is None
        or entity_entry.device_id is None
        or entity_entry.platform != DOMAIN
    ):
        raise ValueError(f"Entity {entity_id} is not a valid {DOMAIN} entity.")

    return entity_entry.device_id


@callback
def async_get_client_wrapper_by_device_entry(
    hass: HomeAssistant, device: DeviceEntry
) -> WebOsClientWrapper:
    """
    Get WebOsClientWrapper from Device Registry by device entry.

    Raises ValueError if client wrapper is not found.
    """
    for config_entry_id in device.config_entries:
        wrapper: WebOsClientWrapper | None
        if wrapper := hass.data[DOMAIN][DATA_CONFIG_ENTRY].get(config_entry_id):
            break

    if not wrapper:
        raise ValueError(
            f"Device {device.id} is not from an existing {DOMAIN} config entry"
        )

    return wrapper


async def async_get_sources(host: str, key: str) -> list[str]:
    """Construct sources list."""
    try:
        client = await async_control_connect(host, key)
    except WEBOSTV_EXCEPTIONS:
        return []

    sources = []
    found_live_tv = False
    for app in client.apps.values():
        sources.append(app["title"])
        if app["id"] == LIVE_TV_APP_ID:
            found_live_tv = True

    for source in client.inputs.values():
        sources.append(source["label"])
        if source["appId"] == LIVE_TV_APP_ID:
            found_live_tv = True

    if not found_live_tv:
        sources.append("Live TV")

    # Preserve order when filtering duplicates
    return list(dict.fromkeys(sources))
