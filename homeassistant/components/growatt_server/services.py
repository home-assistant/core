"""Service handlers for Growatt Server integration."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr

from .const import (
    BATT_MODE_BATTERY_FIRST,
    BATT_MODE_GRID_FIRST,
    BATT_MODE_LOAD_FIRST,
    DOMAIN,
)

if TYPE_CHECKING:
    from .coordinator import GrowattCoordinator


def _get_coordinators(
    hass: HomeAssistant, device_type: str
) -> dict[str, GrowattCoordinator]:
    """Get all coordinators of a given device type with V1 API."""
    coordinators: dict[str, GrowattCoordinator] = {}

    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.state != ConfigEntryState.LOADED:
            continue

        for coord in entry.runtime_data.devices.values():
            if coord.device_type == device_type and coord.api_version == "v1":
                coordinators[coord.device_id] = coord

    return coordinators


def _get_coordinator(
    hass: HomeAssistant, device_id: str, device_type: str
) -> GrowattCoordinator:
    """Get coordinator by device registry ID and device type."""
    coordinators = _get_coordinators(hass, device_type)

    if not coordinators:
        raise ServiceValidationError(
            f"No {device_type.upper()} devices with token authentication are configured. "
            f"Services require {device_type.upper()} devices with V1 API access."
        )

    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get(device_id)

    if not device_entry:
        raise ServiceValidationError(f"Device '{device_id}' not found")

    serial_number = None
    for identifier in device_entry.identifiers:
        if identifier[0] == DOMAIN:
            serial_number = identifier[1]
            break

    if not serial_number:
        raise ServiceValidationError(f"Device '{device_id}' is not a Growatt device")

    if serial_number not in coordinators:
        raise ServiceValidationError(
            f"{device_type.upper()} device '{serial_number}' not found or not configured for services"
        )

    return coordinators[serial_number]


def _extract_period_overrides(
    call_data: dict[str, Any], periods: list[dict]
) -> list[dict]:
    """Merge period overrides from a service call into the current period list."""
    result = list(periods)
    for i in range(1, 4):
        override: dict[str, Any] = {}
        start = call_data.get(f"period_{i}_start")
        end = call_data.get(f"period_{i}_end")
        enabled = call_data.get(f"period_{i}_enabled")
        if start is not None:
            override["start_time"] = start
        if end is not None:
            override["end_time"] = end
        if enabled is not None:
            override["enabled"] = enabled
        if override and i <= len(result):
            result[i - 1] = {**result[i - 1], **override}
    return result


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register services for Growatt Server integration."""

    async def handle_update_time_segment(call: ServiceCall) -> None:
        """Handle update_time_segment service call."""
        segment_id: int = int(call.data["segment_id"])
        batt_mode_str: str = call.data["batt_mode"]
        start_time_str: str = call.data["start_time"]
        end_time_str: str = call.data["end_time"]
        enabled: bool = call.data["enabled"]
        device_id: str = call.data["device_id"]

        if not 1 <= segment_id <= 9:
            raise ServiceValidationError(
                f"segment_id must be between 1 and 9, got {segment_id}"
            )

        valid_modes = {
            "load_first": BATT_MODE_LOAD_FIRST,
            "battery_first": BATT_MODE_BATTERY_FIRST,
            "grid_first": BATT_MODE_GRID_FIRST,
        }
        if batt_mode_str not in valid_modes:
            raise ServiceValidationError(
                f"batt_mode must be one of {list(valid_modes.keys())}, got '{batt_mode_str}'"
            )
        batt_mode: int = valid_modes[batt_mode_str]

        try:
            start_parts = start_time_str.split(":")
            start_time = datetime.strptime(
                f"{start_parts[0]}:{start_parts[1]}", "%H:%M"
            ).time()
        except (ValueError, IndexError) as err:
            raise ServiceValidationError(
                "start_time must be in HH:MM or HH:MM:SS format"
            ) from err

        try:
            end_parts = end_time_str.split(":")
            end_time = datetime.strptime(
                f"{end_parts[0]}:{end_parts[1]}", "%H:%M"
            ).time()
        except (ValueError, IndexError) as err:
            raise ServiceValidationError(
                "end_time must be in HH:MM or HH:MM:SS format"
            ) from err

        coordinator: GrowattCoordinator = _get_coordinator(hass, device_id, "min")
        await coordinator.update_time_segment(
            segment_id, batt_mode, start_time, end_time, enabled
        )

    async def handle_read_time_segments(call: ServiceCall) -> dict[str, Any]:
        """Handle read_time_segments service call."""
        coordinator: GrowattCoordinator = _get_coordinator(
            hass, call.data["device_id"], "min"
        )
        time_segments: list[dict[str, Any]] = await coordinator.read_time_segments()
        return {"time_segments": time_segments}

    async def handle_write_ac_charge_times(call: ServiceCall) -> None:
        """Handle write_ac_charge_times service call for SPH devices."""
        coordinator: GrowattCoordinator = _get_coordinator(
            hass, call.data["device_id"], "sph"
        )
        current = await coordinator.read_ac_charge_times()
        periods = _extract_period_overrides(
            call.data, current.get("periods", [{}, {}, {}])
        )
        await coordinator.update_ac_charge_times(
            int(call.data["charge_power"]),
            int(call.data["charge_stop_soc"]),
            call.data["mains_enabled"],
            periods,
        )

    async def handle_write_ac_discharge_times(call: ServiceCall) -> None:
        """Handle write_ac_discharge_times service call for SPH devices."""
        coordinator: GrowattCoordinator = _get_coordinator(
            hass, call.data["device_id"], "sph"
        )
        current = await coordinator.read_ac_discharge_times()
        periods = _extract_period_overrides(
            call.data, current.get("periods", [{}, {}, {}])
        )
        await coordinator.update_ac_discharge_times(
            int(call.data["discharge_power"]),
            int(call.data["discharge_stop_soc"]),
            periods,
        )

    async def handle_read_ac_charge_times(call: ServiceCall) -> dict[str, Any]:
        """Handle read_ac_charge_times service call for SPH devices."""
        coordinator: GrowattCoordinator = _get_coordinator(
            hass, call.data["device_id"], "sph"
        )
        return await coordinator.read_ac_charge_times()

    async def handle_read_ac_discharge_times(call: ServiceCall) -> dict[str, Any]:
        """Handle read_ac_discharge_times service call for SPH devices."""
        coordinator: GrowattCoordinator = _get_coordinator(
            hass, call.data["device_id"], "sph"
        )
        return await coordinator.read_ac_discharge_times()

    # Register services without schema - services.yaml will provide UI definition
    # Schema validation happens in the handler functions
    hass.services.async_register(
        DOMAIN,
        "update_time_segment",
        handle_update_time_segment,
        supports_response=SupportsResponse.NONE,
    )

    hass.services.async_register(
        DOMAIN,
        "read_time_segments",
        handle_read_time_segments,
        supports_response=SupportsResponse.ONLY,
    )

    hass.services.async_register(
        DOMAIN,
        "write_ac_charge_times",
        handle_write_ac_charge_times,
        supports_response=SupportsResponse.NONE,
    )

    hass.services.async_register(
        DOMAIN,
        "write_ac_discharge_times",
        handle_write_ac_discharge_times,
        supports_response=SupportsResponse.NONE,
    )

    hass.services.async_register(
        DOMAIN,
        "read_ac_charge_times",
        handle_read_ac_charge_times,
        supports_response=SupportsResponse.ONLY,
    )

    hass.services.async_register(
        DOMAIN,
        "read_ac_discharge_times",
        handle_read_ac_discharge_times,
        supports_response=SupportsResponse.ONLY,
    )
