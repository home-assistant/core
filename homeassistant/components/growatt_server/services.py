"""Service handlers for Growatt Server integration."""

from __future__ import annotations

from datetime import datetime, time
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
            translation_domain=DOMAIN,
            translation_key="no_devices_configured",
            translation_placeholders={"device_type": device_type.upper()},
        )

    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get(device_id)

    if not device_entry:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="device_not_found",
            translation_placeholders={"device_id": device_id},
        )

    serial_number = None
    for identifier in device_entry.identifiers:
        if identifier[0] == DOMAIN:
            serial_number = identifier[1]
            break

    if not serial_number:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="device_not_growatt",
            translation_placeholders={"device_id": device_id},
        )

    if serial_number not in coordinators:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="device_not_configured",
            translation_placeholders={
                "device_type": device_type.upper(),
                "serial_number": serial_number,
            },
        )

    return coordinators[serial_number]


def _parse_time_str(
    time_str: str,
    translation_key: str,
    translation_placeholders: dict[str, str] | None = None,
) -> time:
    """Parse a time string (HH:MM or HH:MM:SS) to a datetime.time object."""
    parts = time_str.split(":")
    if len(parts) not in (2, 3):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key=translation_key,
            translation_placeholders=translation_placeholders or {},
        )
    try:
        return datetime.strptime(f"{parts[0]}:{parts[1]}", "%H:%M").time()
    except (ValueError, IndexError) as err:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key=translation_key,
            translation_placeholders=translation_placeholders or {},
        ) from err


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
                translation_domain=DOMAIN,
                translation_key="invalid_segment_id",
                translation_placeholders={"segment_id": str(segment_id)},
            )

        valid_modes = {
            "load_first": BATT_MODE_LOAD_FIRST,
            "battery_first": BATT_MODE_BATTERY_FIRST,
            "grid_first": BATT_MODE_GRID_FIRST,
        }
        if batt_mode_str not in valid_modes:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_batt_mode",
                translation_placeholders={
                    "batt_mode": batt_mode_str,
                    "allowed_modes": ", ".join(valid_modes),
                },
            )
        batt_mode: int = valid_modes[batt_mode_str]

        start_time = _parse_time_str(start_time_str, "invalid_time_format_start_time")
        end_time = _parse_time_str(end_time_str, "invalid_time_format_end_time")

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
        # Read current settings first — the SPH API requires all 3 periods in
        # every write call. Any period not supplied by the caller is filled in
        # from the cache so existing settings are not overwritten with zeros.
        current = await coordinator.read_ac_charge_times()

        charge_power: int = int(call.data.get("charge_power", current["charge_power"]))
        charge_stop_soc: int = int(
            call.data.get("charge_stop_soc", current["charge_stop_soc"])
        )
        mains_enabled: bool = call.data.get("mains_enabled", current["mains_enabled"])

        if not 0 <= charge_power <= 100:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_charge_power",
                translation_placeholders={"value": str(charge_power)},
            )
        if not 0 <= charge_stop_soc <= 100:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_charge_stop_soc",
                translation_placeholders={"value": str(charge_stop_soc)},
            )

        periods = []
        for i in range(1, 4):
            cached = current["periods"][i - 1]
            start = _parse_time_str(
                call.data.get(f"period_{i}_start", cached["start_time"]),
                "invalid_time_format_period_start",
                {"period": str(i)},
            )
            end = _parse_time_str(
                call.data.get(f"period_{i}_end", cached["end_time"]),
                "invalid_time_format_period_end",
                {"period": str(i)},
            )
            enabled: bool = call.data.get(f"period_{i}_enabled", cached["enabled"])
            periods.append({"start_time": start, "end_time": end, "enabled": enabled})

        await coordinator.update_ac_charge_times(
            charge_power, charge_stop_soc, mains_enabled, periods
        )

    async def handle_write_ac_discharge_times(call: ServiceCall) -> None:
        """Handle write_ac_discharge_times service call for SPH devices."""
        coordinator: GrowattCoordinator = _get_coordinator(
            hass, call.data["device_id"], "sph"
        )
        # Read current settings first — same read-merge-write pattern as charge.
        current = await coordinator.read_ac_discharge_times()

        discharge_power: int = int(
            call.data.get("discharge_power", current["discharge_power"])
        )
        discharge_stop_soc: int = int(
            call.data.get("discharge_stop_soc", current["discharge_stop_soc"])
        )

        if not 0 <= discharge_power <= 100:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_discharge_power",
                translation_placeholders={"value": str(discharge_power)},
            )
        if not 0 <= discharge_stop_soc <= 100:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_discharge_stop_soc",
                translation_placeholders={"value": str(discharge_stop_soc)},
            )

        periods = []
        for i in range(1, 4):
            cached = current["periods"][i - 1]
            start = _parse_time_str(
                call.data.get(f"period_{i}_start", cached["start_time"]),
                "invalid_time_format_period_start",
                {"period": str(i)},
            )
            end = _parse_time_str(
                call.data.get(f"period_{i}_end", cached["end_time"]),
                "invalid_time_format_period_end",
                {"period": str(i)},
            )
            enabled: bool = call.data.get(f"period_{i}_enabled", cached["enabled"])
            periods.append({"start_time": start, "end_time": end, "enabled": enabled})

        await coordinator.update_ac_discharge_times(
            discharge_power, discharge_stop_soc, periods
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
