"""Diagnostics support for PrusaLink."""

from collections.abc import Iterable, Mapping
from enum import Enum
from typing import Any, cast

from pyprusalink import (
    JobInfo,
    LegacyPrinterStatus,
    PrinterInfo,
    PrinterStatus,
    VersionInfo,
)

from homeassistant.core import HomeAssistant

from .coordinator import PrusaLinkConfigEntry

# The hostname, serial number, printer name and location are left out, as
# they identify the printer or the user. Status messages are left out as they
# are free text.
VERSION_KEYS = (
    "api",
    "server",
    "text",
    "firmware",
    "printer",
    "version",
    "sdk",
    "nozzle_diameter",
    "capabilities",
)
INFO_KEYS = (
    "mmu",
    "farm_mode",
    "nozzle_diameter",
    "min_extrusion_temp",
    "sd_ready",
    "active_camera",
    "network_error_chime",
)
PRINTER_KEYS = (
    "state",
    "temp_nozzle",
    "target_nozzle",
    "temp_bed",
    "target_bed",
    "axis_x",
    "axis_y",
    "axis_z",
    "flow",
    "speed",
    "fan_hotend",
    "fan_print",
)
STATUS_JOB_KEYS = ("progress", "time_printing", "time_remaining")
# The storage name and path are left out, as they are set by the user.
STORAGE_KEYS = ("read_only", "free_space")
# The file name, path and refs of the job are left out, as they are set by
# the user.
JOB_KEYS = (
    "state",
    "progress",
    "time_remaining",
    "time_printing",
    "inaccurate_estimates",
    "serial_print",
)


def _pick(data: Mapping[str, Any], keys: Iterable[str]) -> dict[str, Any]:
    """Return the keys that are reported, with enums converted to values."""
    result: dict[str, Any] = {}
    for key in keys:
        if key in data:
            value = data[key]
            result[key] = value.value if isinstance(value, Enum) else value
    return result


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: PrusaLinkConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinators = entry.runtime_data
    version = cast(VersionInfo, coordinators["version"].data)
    info = cast(PrinterInfo, coordinators["info"].data)
    status = cast(PrinterStatus, coordinators["status"].data)
    legacy_status = cast(LegacyPrinterStatus, coordinators["legacy_status"].data)
    job = cast(JobInfo | None, coordinators["job"].data_or_none)

    printer = status["printer"]
    printer_diagnostics = _pick(printer, PRINTER_KEYS)
    if (status_printer := printer.get("status_printer")) is not None:
        printer_diagnostics["status_printer_ok"] = status_printer.get("ok")
    if (status_connect := printer.get("status_connect")) is not None:
        printer_diagnostics["status_connect_ok"] = status_connect.get("ok")
    telemetry = legacy_status.get("telemetry")

    return {
        "coordinators": {
            name: {"last_update_success": coordinator.last_update_success}
            for name, coordinator in coordinators.items()
        },
        "version": _pick(version, VERSION_KEYS),
        "info": _pick(info, INFO_KEYS),
        "status": {
            "printer": printer_diagnostics,
            "job": _pick(status["job"], STATUS_JOB_KEYS) if "job" in status else None,
            "storage": (
                _pick(status["storage"], STORAGE_KEYS) if "storage" in status else None
            ),
        },
        "legacy_status": {
            "material": telemetry.get("material") if telemetry is not None else None,
        },
        # The job endpoint returns nothing when no job is running.
        "job": (
            {
                **_pick(job, JOB_KEYS),
                "has_file": job.get("file") is not None,
            }
            if job is not None
            else None
        ),
    }
