"""Diagnostics support for VeSync."""

from __future__ import annotations

from typing import Any

from pyvesync import VeSync

from homeassistant.components.diagnostics import REDACTED
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntry

from .const import DOMAIN, VS_MANAGER
from .entity import VeSyncBaseDevice

KEYS_TO_REDACT = {"manager", "uuid", "mac_id"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    manager: VeSync = hass.data[DOMAIN][VS_MANAGER]

    return {
        DOMAIN: {
            "bulb_count": len(manager.devices.bulbs),
            "fan_count": len(manager.devices.fans),
            "humidifers_count": len(manager.devices.humidifiers),
            "air_purifiers": len(manager.devices.air_purifiers),
            "outlets_count": len(manager.devices.outlets),
            "switch_count": len(manager.devices.switches),
            "timezone": manager.time_zone,
        },
        "devices": [_redact_device_values(device) for device in manager.devices],
    }


async def async_get_device_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry, device: DeviceEntry
) -> dict[str, Any]:
    """Return diagnostics for a device entry."""
    manager: VeSync = hass.data[DOMAIN][VS_MANAGER]
    device_dict = manager.devices
    vesync_device_id = next(iden[1] for iden in device.identifiers if iden[0] == DOMAIN)

    # Base device information, without sensitive information.
    data = _redact_device_values(device_dict[vesync_device_id])

    data["home_assistant"] = {
        "name": device.name,
        "name_by_user": device.name_by_user,
        "disabled": device.disabled,
        "disabled_by": device.disabled_by,
        "entities": [],
    }

    # Gather information how this VeSync device is represented in Home Assistant
    entity_registry = er.async_get(hass)
    hass_entities = er.async_entries_for_device(
        entity_registry,
        device_id=device.id,
        include_disabled_entities=True,
    )

    for entity_entry in hass_entities:
        state = hass.states.get(entity_entry.entity_id)
        state_dict = None
        if state:
            state_dict = dict(state.as_dict())
            # The context doesn't provide useful information in this case.
            state_dict.pop("context", None)

        data["home_assistant"]["entities"].append(
            {
                "domain": entity_entry.domain,
                "entity_id": entity_entry.entity_id,
                "entity_category": entity_entry.entity_category,
                "device_class": entity_entry.device_class,
                "original_device_class": entity_entry.original_device_class,
                "name": entity_entry.name,
                "original_name": entity_entry.original_name,
                "icon": entity_entry.icon,
                "original_icon": entity_entry.original_icon,
                "unit_of_measurement": entity_entry.unit_of_measurement,
                "state": state_dict,
                "disabled": entity_entry.disabled,
                "disabled_by": entity_entry.disabled_by,
            }
        )

    return data


def _redact_device_values(device: VeSyncBaseDevice) -> dict:
    """Rebuild and redact values of a VeSync device."""
    data = {}
    for key, item in device.__dict__.items():
        if key not in KEYS_TO_REDACT:
            data[key] = item
        else:
            data[key] = REDACTED

    return data
