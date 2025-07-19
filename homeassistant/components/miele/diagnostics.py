"""Diagnostics support for Miele."""

from __future__ import annotations

import hashlib
from typing import Any, cast

from pymiele import completed_warnings

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from .coordinator import MieleConfigEntry

TO_REDACT = {"access_token", "refresh_token", "fabNumber"}


def hash_identifier(key: str) -> str:
    """Hash the identifier string."""
    return f"**REDACTED_{hashlib.sha256(key.encode()).hexdigest()[:16]}"


def redact_identifiers(in_data: dict[str, Any]) -> dict[str, Any]:
    """Redact identifiers from the data."""
    out_data = {}
    for key, value in in_data.items():
        out_data[hash_identifier(key)] = value
    return out_data


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: MieleConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    miele_data: dict[str, Any] = {
        "devices": redact_identifiers(
            {
                device_id: device_data.raw
                for device_id, device_data in config_entry.runtime_data.data.devices.items()
            }
        ),
        "actions": redact_identifiers(
            {
                device_id: action_data.raw
                for device_id, action_data in config_entry.runtime_data.data.actions.items()
            }
        ),
    }
    miele_data["missing_code_warnings"] = (
        sorted(completed_warnings) if len(completed_warnings) > 0 else ["None"]
    )

    return {
        "config_entry_data": async_redact_data(dict(config_entry.data), TO_REDACT),
        "miele_data": async_redact_data(miele_data, TO_REDACT),
    }


async def async_get_device_diagnostics(
    hass: HomeAssistant, config_entry: MieleConfigEntry, device: DeviceEntry
) -> dict[str, Any]:
    """Return diagnostics for a device."""
    info = {
        "manufacturer": device.manufacturer,
        "model": device.model,
    }

    coordinator = config_entry.runtime_data

    device_id = cast(str, device.serial_number)
    miele_data: dict[str, Any] = {
        "devices": {
            hash_identifier(device_id): coordinator.data.devices[device_id].raw
        },
        "actions": {
            hash_identifier(device_id): coordinator.data.actions[device_id].raw
        },
        "programs": "Not implemented",
    }
    miele_data["missing_code_warnings"] = (
        sorted(completed_warnings) if len(completed_warnings) > 0 else ["None"]
    )

    return {
        "info": async_redact_data(info, TO_REDACT),
        "data": async_redact_data(config_entry.data, TO_REDACT),
        "miele_data": async_redact_data(miele_data, TO_REDACT),
    }
