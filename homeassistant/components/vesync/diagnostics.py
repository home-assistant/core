"""Diagnostics support for VeSync."""
from __future__ import annotations

from typing import Any

from pyvesync import VeSync

from homeassistant.components.diagnostics import REDACTED
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntry

from .common import VeSyncBaseDevice
from .const import DOMAIN, VS_MANAGER

KEYS_TO_REDACT = {"manager"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    manager: VeSync = hass.data[DOMAIN][VS_MANAGER]

    data = {
        "account_id": manager.account_id,
        "bulb_count": len(manager.bulbs),
        "fan_count": len(manager.fans),
        "outlets_count": len(manager.outlets),
        "scale_count": len(manager.scales),
        "switch_count": len(manager.switches),
        "timezone": manager.time_zone,
        "disabled_by": entry.disabled_by,
        "disabled_polling": entry.pref_disable_polling,
    }

    device_dict = _build_device_dict(manager)
    data.update(
        devices=[
            _async_device_as_dict(hass, None, device) for device in device_dict.values()
        ]
    )

    return data


async def async_get_device_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry, device: DeviceEntry
) -> dict[str, Any]:
    """Return diagnostics for a device entry."""
    manager: VeSync = hass.data[DOMAIN][VS_MANAGER]

    device_dict = _build_device_dict(manager)
    vesync_device_id = next(iter(device.identifiers))[1]
    return _async_device_as_dict(hass, device, device_dict[vesync_device_id])


@callback
def _async_device_as_dict(
    hass: HomeAssistant,
    hass_device: DeviceEntry | None,
    vesync_device: VeSyncBaseDevice,
) -> dict[str, Any]:
    """Represent a VeSync device as a dictionary."""

    # Base device information, without sensitive information.
    data = _redact_device_values(vesync_device)

    if hass_device:
        data["home_assistant"] = {
            "name": hass_device.name,
            "name_by_user": hass_device.name_by_user,
            "disabled": hass_device.disabled,
            "disabled_by": hass_device.disabled_by,
            "entities": [],
        }

        # Gather information how this VeSync device is represented in Home Assistant
        entity_registry = er.async_get(hass)
        hass_entities = er.async_entries_for_device(
            entity_registry,
            device_id=hass_device.id,
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


def _build_device_dict(manager: VeSync) -> dict:
    """Build a dictionary of ALL VeSync devices."""
    device_dict = {x.cid: x for x in manager.switches}
    device_dict.update({x.cid: x for x in manager.fans})
    device_dict.update({x.cid: x for x in manager.outlets})
    device_dict.update({x.cid: x for x in manager.switches})
    return device_dict


def _redact_device_values(device: VeSyncBaseDevice) -> dict:
    """Rebuild and redact values of a VeSync device."""
    data = {}
    for key, item in device.__dict__.items():
        if key not in KEYS_TO_REDACT:
            data[key] = item
        else:
            data[key] = REDACTED

    return data
