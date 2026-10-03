"""Diagnostics support for Miele."""

import hashlib
from typing import TYPE_CHECKING, Any, cast

from pymiele import completed_warnings

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import AnyDeviceEntry, DeviceEntry

from .coordinator import MieleConfigEntry, MieleDataUpdateCoordinator

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


def _unknown_program_ids(
    coordinator: MieleDataUpdateCoordinator, device_id: str
) -> list[dict[str, int | str | None]]:
    """Return unknown program IDs observed in appliance state updates."""
    return [
        {
            "value_raw": program_id,
            "value_localized": value_localized,
        }
        for program_id, value_localized in sorted(
            coordinator.unknown_program_ids.get(device_id, {}).items()
        )
    ]


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: MieleConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    miele_data: dict[str, Any] = {
        "devices": redact_identifiers(
            {
                device_id: device_data.raw
                for device_id, device_data in (
                    config_entry.runtime_data.coordinator.data.devices.items()
                )
            }
        ),
        "filling_levels": redact_identifiers(
            {
                device_id: filling_level_data.raw
                for device_id, filling_level_data in (
                    config_entry.runtime_data.aux_coordinator.data.filling_levels.items()
                )
            }
        ),
        "actions": redact_identifiers(
            {
                device_id: action_data.raw
                for device_id, action_data in (
                    config_entry.runtime_data.coordinator.data.actions.items()
                )
            }
        ),
        "unknown_program_ids": redact_identifiers(
            {
                device_id: _unknown_program_ids(
                    config_entry.runtime_data.coordinator, device_id
                )
                for device_id in config_entry.runtime_data.coordinator.unknown_program_ids
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
    hass: HomeAssistant, config_entry: MieleConfigEntry, device: AnyDeviceEntry
) -> dict[str, Any]:
    """Return diagnostics for a device."""
    if TYPE_CHECKING:
        # miele does not create child devices
        assert isinstance(device, DeviceEntry)

    info = {
        "manufacturer": device.manufacturer,
        "model": device.model,
        "model_id": device.model_id,
    }

    coordinator = config_entry.runtime_data.coordinator
    aux_coordinator = config_entry.runtime_data.aux_coordinator

    device_id = cast(str, device.serial_number)
    miele_data: dict[str, Any] = {
        "devices": {
            hash_identifier(device_id): coordinator.data.devices[device_id].raw
        },
        "filling_levels": {
            hash_identifier(device_id): aux_coordinator.data.filling_levels[
                device_id
            ].raw
        },
        "actions": {
            hash_identifier(device_id): coordinator.data.actions[device_id].raw
        },
        "unknown_program_ids": _unknown_program_ids(coordinator, device_id),
    }
    miele_data["missing_code_warnings"] = (
        sorted(completed_warnings) if len(completed_warnings) > 0 else ["None"]
    )

    return {
        "info": async_redact_data(info, TO_REDACT),
        "data": async_redact_data(config_entry.data, TO_REDACT),
        "miele_data": async_redact_data(miele_data, TO_REDACT),
    }
