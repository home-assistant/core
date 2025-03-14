"""Diagnostics support for HomeKit Controller."""

from __future__ import annotations

from typing import Any

from aiohomekit.model.characteristics.characteristic_types import CharacteristicsTypes

from homeassistant.components.diagnostics import REDACTED, async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntry

from .connection import HKDevice
from .const import KNOWN_DEVICES

REDACTED_CHARACTERISTICS = [
    CharacteristicsTypes.SERIAL_NUMBER,
]

REDACTED_CONFIG_ENTRY_KEYS = [
    "AccessoryIP",
    "iOSDeviceLTSK",
]

REDACTED_STATE = ["access_token", "entity_picture"]


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
def _async_get_diagnostics_for_device(
    hass: HomeAssistant, device: DeviceEntry
) -> dict[str, Any]:
    data: dict[str, Any] = {}

    data["name"] = device.name
    data["model"] = device.model
    data["manfacturer"] = device.manufacturer
    data["sw_version"] = device.sw_version
    data["hw_version"] = device.hw_version

    entities = data["entities"] = []

    hass_entities = er.async_entries_for_device(
        er.async_get(hass),
        device_id=device.id,
        include_disabled_entities=True,
    )

    hass_entities.sort(key=lambda entry: entry.original_name or "")

    for entity_entry in hass_entities:
        state = hass.states.get(entity_entry.entity_id)
        state_dict = None
        if state:
            state_dict = async_redact_data(state.as_dict(), REDACTED_STATE)
            state_dict.pop("context", None)

        entities.append(
            {
                "original_name": entity_entry.original_name,
                "original_device_class": entity_entry.original_device_class,
                "entity_category": entity_entry.entity_category,
                "original_icon": entity_entry.original_icon,
                "icon": entity_entry.icon,
                "unit_of_measurement": entity_entry.unit_of_measurement,
                "device_class": entity_entry.device_class,
                "disabled": entity_entry.disabled,
                "disabled_by": entity_entry.disabled_by,
                "state": state_dict,
            }
        )

    return data


@callback
def _async_get_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry, device: DeviceEntry | None = None
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    hkid = entry.data["AccessoryPairingID"]
    connection: HKDevice = hass.data[KNOWN_DEVICES][hkid]

    data: dict[str, Any] = {
        "config-entry": {
            "title": entry.title,
            "version": entry.version,
            "data": async_redact_data(entry.data, REDACTED_CONFIG_ENTRY_KEYS),
        }
    }

    # This is the raw data as returned by homekit
    # It is roughly equivalent to what is in .storage/homekit_controller-entity-map
    # But it also has the latest values seen by the polling or events
    data["entity-map"] = accessories = connection.entity_map.serialize()
    data["config-num"] = connection.config_num

    # It contains serial numbers, which we should strip out
    for accessory in accessories:
        for service in accessory.get("services", []):
            for char in service.get("characteristics", []):
                if char["type"] in REDACTED_CHARACTERISTICS:
                    char["value"] = REDACTED

    if device:
        data["device"] = _async_get_diagnostics_for_device(hass, device)
    else:
        device_registry = dr.async_get(hass)

        devices = data["devices"] = []
        for device_id in connection.devices.values():
            if not (device := device_registry.async_get(device_id)):
                continue
            devices.append(_async_get_diagnostics_for_device(hass, device))

    return data
