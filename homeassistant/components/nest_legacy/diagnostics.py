"""Provides diagnostics for Nest."""

from __future__ import annotations

import dataclasses
from typing import Any

from aiohttp import ClientError
from google.protobuf.json_format import MessageToDict
from google.protobuf.message import Message

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceEntry

from .const import CONF_COOKIES, CONF_ISSUE_TOKEN
from .coordinator import NestConfigEntry
from .pynest.exceptions import PynestException
from .pynest.models import NestDevice, NestHeatLink

TO_REDACT = [
    CONF_ACCESS_TOKEN,
    CONF_COOKIES,
    CONF_ISSUE_TOKEN,
    "access_token",
    "address_lines",
    "aux_primary_fabric_id",
    "city",
    "country",
    "email",
    "emergency_contact_description",
    "emergency_contact_phone",
    "ifj_primary_fabric_id",
    "latitude",
    "location",
    "longitude",
    "mac_address",
    "name",
    "parameters",
    "pairing_token",
    "postal_code",
    "profile_image_url",
    "service_config",
    "sunrise",
    "sunset",
    "temp_c",
    "thread_ip_address",
    "thread_mac_address",
    "time_zone",
    "topaz_hush_key",
    "user",
    "userid",
    "wifi_mac_address",
    "zip",
    "cookie",
    "issuetoken",
    "title",
    "phone_numbers",
]


def _convert_protobuf_to_dict(data: Any) -> Any:
    """Convert protobuf messages to dicts recursively."""
    if isinstance(data, Message):
        return MessageToDict(data, preserving_proto_field_name=True)
    if isinstance(data, dict):
        return {k: _convert_protobuf_to_dict(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_convert_protobuf_to_dict(item) for item in data]
    return data


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: NestConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data

    # Ensure we have the latest data for diagnostics
    try:
        if coordinator.client.is_expired():
            await coordinator.async_reauthenticate()
    except (ClientError, TimeoutError, PynestException, HomeAssistantError) as e:
        return {"error": f"Authentication failed during diagnostics: {e}"}

    processed_data = {
        key: dataclasses.asdict(value)
        for key, value in coordinator.data.items()
        if value
    }

    raw_api_data = _convert_protobuf_to_dict(coordinator.get_raw_data_for_diagnostics())

    data: dict[str, Any] = {
        "config_entry": entry.as_dict(),
        "processed_data": processed_data,
        "raw_api_data": raw_api_data,
    }

    return async_redact_data(data, TO_REDACT)


async def async_get_device_diagnostics(
    hass: HomeAssistant, entry: NestConfigEntry, device: DeviceEntry
) -> dict[str, Any]:
    """Return diagnostics for a device entry."""
    coordinator = entry.runtime_data
    identifier = next(iter(device.identifiers))
    serial_number = identifier[1]

    device_data = coordinator.data.get(serial_number)
    if not isinstance(device_data, NestDevice):
        return {"error": "Device not found in coordinator data"}

    raw_data = coordinator.get_raw_data_for_diagnostics()
    device_raw_data = raw_data.get(device_data.object_key)

    # For Heat Links, fall back to associated thermostat data if available
    if (
        not device_raw_data
        and isinstance(device_data, NestHeatLink)
        and device_data.associated_thermostat_object_key
    ):
        device_raw_data = raw_data.get(device_data.associated_thermostat_object_key)

    device_raw_data = _convert_protobuf_to_dict(device_raw_data)

    data: dict[str, Any] = {
        "device_entry": {
            "name": device.name,
            "model": device.model,
            "sw_version": device.sw_version,
            "hw_version": device.hw_version,
            "manufacturer": device.manufacturer,
        },
        "processed_data": dataclasses.asdict(device_data),
        "raw_data": device_raw_data,
    }

    return async_redact_data(data, TO_REDACT)
