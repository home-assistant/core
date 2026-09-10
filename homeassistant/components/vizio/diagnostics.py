"""Diagnostics support for Vizio."""

from dataclasses import asdict
from typing import Any

from vizaio import VizioError

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_HOST
from homeassistant.core import HomeAssistant

from .coordinator import VizioConfigEntry

TO_REDACT = {
    CONF_ACCESS_TOKEN,
    CONF_HOST,
    "esn",
    "serial_number",
    # Device-cased keys inside SystemVersions.raw
    "ESN",
    "SERIAL NUMBER",
    "unique_id",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: VizioConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data.device_coordinator
    device = coordinator.device

    try:
        versions: dict[str, Any] | None = asdict(await device.get_versions())
    except VizioError:
        versions = None

    return async_redact_data(
        {
            "entry": {
                "data": dict(entry.data),
                "options": dict(entry.options),
                "unique_id": entry.unique_id,
            },
            "device_profile": {
                "name": device.profile.name,
                "max_volume": device.profile.max_volume,
                "requires_auth": device.profile.requires_auth,
                "has_battery": device.profile.has_battery,
                "has_inputs": device.profile.has_inputs,
                "has_apps": device.profile.has_apps,
            },
            "data": asdict(coordinator.data),
            "versions": versions,
        },
        TO_REDACT,
    )
