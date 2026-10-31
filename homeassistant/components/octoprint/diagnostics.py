"""Diagnostics support for OctoPrint."""

from typing import Any

from pyoctoprintapi import OctoprintJobInfo, OctoprintPrinterInfo

from homeassistant.const import CONF_PATH, CONF_PORT, CONF_SSL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant

from .coordinator import OctoprintConfigEntry


def _job_to_dict(job: OctoprintJobInfo) -> dict[str, Any]:
    """Return the non-sensitive job information."""
    return {
        "state": job.state,
        "error": job.error,
        "progress": {
            "completion": job.progress.completion,
            "print_time": job.progress.print_time,
            "print_time_left": job.progress.print_time_left,
        },
        "job": {
            "completion": job.job.completion,
            "estimated_print_time": job.job.estimated_print_time,
            "file": {
                "origin": job.job.file.origin,
                "size": job.job.file.size,
            },
        },
    }


def _printer_to_dict(printer: OctoprintPrinterInfo) -> dict[str, Any]:
    """Return the printer information."""
    flags = printer.state.flags
    return {
        "state": {
            "text": printer.state.text,
            "flags": {
                "cancelling": flags.cancelling,
                "closed_or_error": flags.closed_or_error,
                "error": flags.error,
                "finishing": flags.finishing,
                "operational": flags.operational,
                "paused": flags.paused,
                "pausing": flags.pausing,
                "printing": flags.printing,
                "ready": flags.ready,
                "resuming": flags.resuming,
                "sd_ready": flags.sd_ready,
            },
        },
        "has_heated_bed": printer.has_heated_bed,
        "temperatures": [
            {
                "name": temperature.name,
                "actual": temperature.actual_temp,
                "target": temperature.target_temp,
                "offset": temperature.offset,
            }
            for temperature in printer.temperatures
        ],
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: OctoprintConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    job: OctoprintJobInfo | None = coordinator.data["job"]
    printer: OctoprintPrinterInfo | None = coordinator.data["printer"]
    return {
        "config_entry": {
            key: entry.data[key]
            for key in (CONF_SSL, CONF_VERIFY_SSL, CONF_PORT, CONF_PATH)
        },
        "job": _job_to_dict(job) if job is not None else None,
        "printer": _printer_to_dict(printer) if printer is not None else None,
    }
