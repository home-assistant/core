"""Diagnostics support for Tuya."""

from __future__ import annotations

from contextlib import suppress
import json
from typing import Any, cast

from tuya_sharing import CustomerDevice

from homeassistant.components.diagnostics import REDACTED
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.util import dt as dt_util

from . import TuyaConfigEntry
from .const import DOMAIN, DPCode


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: TuyaConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return _async_get_diagnostics(hass, entry)


async def async_get_device_diagnostics(
    hass: HomeAssistant, entry: TuyaConfigEntry, device: DeviceEntry
) -> dict[str, Any]:
    """Return diagnostics for a device entry."""
    return _async_get_diagnostics(hass, entry, device)


@callback
def _async_get_diagnostics(
    hass: HomeAssistant,
    entry: TuyaConfigEntry,
    device: DeviceEntry | None = None,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    hass_data = entry.runtime_data

    mqtt_connected = None
    if hass_data.manager.mq.client:
        mqtt_connected = hass_data.manager.mq.client.is_connected()

    data = {
        "endpoint": hass_data.manager.customer_api.endpoint,
        "terminal_id": hass_data.manager.terminal_id,
        "mqtt_connected": mqtt_connected,
        "disabled_by": entry.disabled_by,
        "disabled_polling": entry.pref_disable_polling,
    }

    if device:
        tuya_device_id = next(iter(device.identifiers))[1]
        data |= _async_device_as_dict(
            hass, hass_data.manager.device_map[tuya_device_id]
        )
    else:
        data.update(
            devices=[
                _async_device_as_dict(hass, device)
                for device in hass_data.manager.device_map.values()
            ]
        )

    return data


@callback
def _async_device_as_dict(
    hass: HomeAssistant, device: CustomerDevice
) -> dict[str, Any]:
    """Represent a Tuya device as a dictionary."""

    # Base device information, without sensitive information.
    data = {
        "id": device.id,
        "name": device.name,
        "category": device.category,
        "product_id": device.product_id,
        "product_name": device.product_name,
        "online": device.online,
        "sub": device.sub,
        "time_zone": device.time_zone,
        "active_time": dt_util.utc_from_timestamp(device.active_time).isoformat(),
        "create_time": dt_util.utc_from_timestamp(device.create_time).isoformat(),
        "update_time": dt_util.utc_from_timestamp(device.update_time).isoformat(),
        "function": {},
        "status_range": {},
        "status": {},
        "home_assistant": {},
        "set_up": device.set_up,
        "support_local": device.support_local,
    }

    # Gather Tuya states
    for dpcode, value in device.status.items():
        # These statuses may contain sensitive information, redact these..
        if dpcode in {DPCode.ALARM_MESSAGE, DPCode.MOVEMENT_DETECT_PIC}:
            data["status"][dpcode] = REDACTED
            continue

        with suppress(ValueError, TypeError):
            value = json.loads(value)
        data["status"][dpcode] = value

    # Gather Tuya functions
    for function in device.function.values():
        value = function.values
        with suppress(ValueError, TypeError, AttributeError):
            value = json.loads(cast(str, function.values))

        data["function"][function.code] = {
            "type": function.type,
            "value": value,
        }

    # Gather Tuya status ranges
    for status_range in device.status_range.values():
        value = status_range.values
        with suppress(ValueError, TypeError, AttributeError):
            value = json.loads(status_range.values)

        data["status_range"][status_range.code] = {
            "type": status_range.type,
            "value": value,
        }

    # Gather information how this Tuya device is represented in Home Assistant
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)
    hass_device = device_registry.async_get_device(identifiers={(DOMAIN, device.id)})
    if hass_device:
        data["home_assistant"] = {
            "name": hass_device.name,
            "name_by_user": hass_device.name_by_user,
            "disabled": hass_device.disabled,
            "disabled_by": hass_device.disabled_by,
            "entities": [],
        }

        hass_entities = er.async_entries_for_device(
            entity_registry,
            device_id=hass_device.id,
            include_disabled_entities=True,
        )

        for entity_entry in hass_entities:
            state = hass.states.get(entity_entry.entity_id)
            state_dict: dict[str, Any] | None = None
            if state:
                state_dict = dict(state.as_dict())

                # Redact the `entity_picture` attribute as it contains a token.
                if "entity_picture" in state_dict["attributes"]:
                    state_dict["attributes"] = {
                        **state_dict["attributes"],
                        "entity_picture": REDACTED,
                    }

                # The context doesn't provide useful information in this case.
                state_dict.pop("context", None)

            data["home_assistant"]["entities"].append(
                {
                    "disabled": entity_entry.disabled,
                    "disabled_by": entity_entry.disabled_by,
                    "entity_category": entity_entry.entity_category,
                    "device_class": entity_entry.device_class,
                    "original_device_class": entity_entry.original_device_class,
                    "icon": entity_entry.icon,
                    "original_icon": entity_entry.original_icon,
                    "unit_of_measurement": entity_entry.unit_of_measurement,
                    "state": state_dict,
                }
            )

    return data
