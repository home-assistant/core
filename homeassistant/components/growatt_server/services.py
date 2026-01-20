"""Service handlers for Growatt Server integration."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
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


async def async_register_services(hass: HomeAssistant) -> None:
    """Register services for Growatt Server integration."""

    def get_min_coordinators() -> dict[str, GrowattCoordinator]:
        """Get all MIN coordinators with V1 API from loaded config entries."""
        min_coordinators: dict[str, GrowattCoordinator] = {}

        for entry in hass.config_entries.async_entries(DOMAIN):
            if entry.state != ConfigEntryState.LOADED:
                continue

            # Add MIN coordinators from this entry
            for coord in entry.runtime_data.devices.values():
                if coord.device_type == "min" and coord.api_version == "v1":
                    min_coordinators[coord.device_id] = coord

        return min_coordinators

    def get_coordinator(device_id: str) -> GrowattCoordinator:
        """Get coordinator by device_id.

        Args:
            device_id: Device registry ID (not serial number)
        """
        # Get current coordinators (they may have changed since service registration)
        min_coordinators = get_min_coordinators()

        if not min_coordinators:
            raise ServiceValidationError(
                "No MIN devices with token authentication are configured. "
                "Services require MIN devices with V1 API access."
            )

        # Device registry ID provided - map to serial number
        device_registry = dr.async_get(hass)
        device_entry = device_registry.async_get(device_id)

        if not device_entry:
            raise ServiceValidationError(f"Device '{device_id}' not found")

        # Extract serial number from device identifiers
        serial_number = None
        for identifier in device_entry.identifiers:
            if identifier[0] == DOMAIN:
                serial_number = identifier[1]
                break

        if not serial_number:
            raise ServiceValidationError(
                f"Device '{device_id}' is not a Growatt device"
            )

        # Find coordinator by serial number
        if serial_number not in min_coordinators:
            raise ServiceValidationError(
                f"MIN device '{serial_number}' not found or not configured for services"
            )

        return min_coordinators[serial_number]

    async def handle_update_time_segment(call: ServiceCall) -> None:
        """Handle update_time_segment service call."""
        segment_id: int = int(call.data["segment_id"])
        batt_mode_str: str = call.data["batt_mode"]
        start_time_str: str = call.data["start_time"]
        end_time_str: str = call.data["end_time"]
        enabled: bool = call.data["enabled"]
        device_id: str = call.data["device_id"]

        # Validate segment_id range
        if not 1 <= segment_id <= 9:
            raise ServiceValidationError(
                f"segment_id must be between 1 and 9, got {segment_id}"
            )

        # Validate and convert batt_mode string to integer
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

        # Convert time strings to datetime.time objects
        # UI time selector sends HH:MM:SS, but we only need HH:MM (strip seconds)
        try:
            # Take only HH:MM part (ignore seconds if present)
            start_parts = start_time_str.split(":")
            start_time_hhmm = f"{start_parts[0]}:{start_parts[1]}"
            start_time = datetime.strptime(start_time_hhmm, "%H:%M").time()
        except (ValueError, IndexError) as err:
            raise ServiceValidationError(
                "start_time must be in HH:MM or HH:MM:SS format"
            ) from err

        try:
            # Take only HH:MM part (ignore seconds if present)
            end_parts = end_time_str.split(":")
            end_time_hhmm = f"{end_parts[0]}:{end_parts[1]}"
            end_time = datetime.strptime(end_time_hhmm, "%H:%M").time()
        except (ValueError, IndexError) as err:
            raise ServiceValidationError(
                "end_time must be in HH:MM or HH:MM:SS format"
            ) from err

        # Get the appropriate MIN coordinator
        coordinator: GrowattCoordinator = get_coordinator(device_id)

        await coordinator.update_time_segment(
            segment_id,
            batt_mode,
            start_time,
            end_time,
            enabled,
        )

    async def handle_read_time_segments(call: ServiceCall) -> dict[str, Any]:
        """Handle read_time_segments service call."""
        device_id: str = call.data["device_id"]

        # Get the appropriate MIN coordinator
        coordinator: GrowattCoordinator = get_coordinator(device_id)

        time_segments: list[dict[str, Any]] = await coordinator.read_time_segments()

        return {"time_segments": time_segments}

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
