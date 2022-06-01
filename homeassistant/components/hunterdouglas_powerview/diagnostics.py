"""Diagnostics support for Powerview Hunter Douglas."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntry

from .const import (
    COORDINATOR,
    DEVICE_INFO,
    DEVICE_MAC_ADDRESS,
    DEVICE_SERIAL_NUMBER,
    DOMAIN,
    PV_HUB_ADDRESS,
)
from .coordinator import PowerviewShadeUpdateCoordinator

REDACT_CONFIG = {
    CONF_HOST,
    DEVICE_MAC_ADDRESS,
    DEVICE_SERIAL_NUMBER,
    PV_HUB_ADDRESS,
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return _async_get_diagnostics(hass, entry)


async def async_get_device_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry, device: DeviceEntry
) -> dict[str, Any]:
    """Return diagnostics for a device entry."""
    return _async_get_diagnostics(hass, entry, device)


@callback
def _async_get_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
    device: DeviceEntry | None = None,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    pv_data = hass.data[DOMAIN][entry.entry_id]
    coordinator: PowerviewShadeUpdateCoordinator = pv_data[COORDINATOR]
    shade_data = coordinator.data.get_all_raw_data()
    hub_info = async_redact_data(pv_data[DEVICE_INFO], REDACT_CONFIG)

    data = {"hub_info": hub_info, "shade_data": shade_data}

    if device:
        data["device_info"] = _async_device_as_dict(hass, device)
        # try to match on name to restrict to shade if we can
        # otherwise just return all shade data
        # shade name is unique in powerview
        for shade in shade_data:
            if shade_data[shade]["name_unicode"] == device.name:
                data["shade_data"] = shade_data[shade]

    else:
        device_registry = dr.async_get(hass)
        data.update(
            device_info=[
                _async_device_as_dict(hass, device)
                for device in dr.async_entries_for_config_entry(
                    device_registry, entry.entry_id
                )
            ],
        )

    return data


@callback
def _async_device_as_dict(hass: HomeAssistant, device: DeviceEntry) -> dict[str, Any]:
    """Represent a Powerview device as a dictionary."""

    # Gather information how this device is represented in Home Assistant
    entity_registry = er.async_get(hass)
    data: dict[str, Any] = {
        "id": device.id,
        "firmware": device.sw_version,
        "model": device.model,
        "name": device.name,
        "name_by_user": device.name_by_user,
        "disabled": device.disabled,
        "disabled_by": device.disabled_by,
        "entities": [],
    }

    entities = er.async_entries_for_device(
        entity_registry,
        device_id=device.id,
        include_disabled_entities=True,
    )

    for entity_entry in entities:
        state = hass.states.get(entity_entry.entity_id)
        state_dict = None
        if state:
            state_dict = dict(state.as_dict())
            state_dict.pop("context", None)

        data["entities"].append(
            {
                "device_class": entity_entry.device_class,
                "disabled_by": entity_entry.disabled_by,
                "disabled": entity_entry.disabled,
                "entity_category": entity_entry.entity_category,
                "entity_id": entity_entry.entity_id,
                "icon": entity_entry.icon,
                "original_device_class": entity_entry.original_device_class,
                "original_icon": entity_entry.original_icon,
                "state": state_dict,
                "unit_of_measurement": entity_entry.unit_of_measurement,
            }
        )

    return data
