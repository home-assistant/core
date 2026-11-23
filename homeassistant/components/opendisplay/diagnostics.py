"""Diagnostics support for OpenDisplay."""

import dataclasses
from typing import Any

from opendisplay import GlobalConfig

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import OpenDisplayConfigEntry

TO_REDACT = {
    "ssid",
    "password",
    "server_url",
    "serial_number",
    "friendly_name",
    "device_location",
    "device_id",
    "custom_string_1",
    "custom_string_2",
    "custom_string_3",
    "encryption_key",
    "findmy_config_raw",
    "length_prefixed_packets",
    # Raw bytes of config packets the library does not recognise: unknown
    # content, so never expose it.
    "unparsed_tail",
}

DRIVE_DATA = (
    "display_modes",
    "display_luts",
    "display_calibrations",
    "display_panels",
)


def _asdict(obj: Any) -> Any:
    """Recursively convert a dataclass to a dict, encoding bytes as hex strings."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: _asdict(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
    if isinstance(obj, bytes):
        return obj.hex()
    if isinstance(obj, (list, tuple)):
        return [_asdict(item) for item in obj]
    return obj


def _device_config(config: GlobalConfig) -> dict[str, Any]:
    """Return the config with the drive data the library parses, by name."""
    data = _asdict(config)
    for name in DRIVE_DATA:
        data[name] = _asdict(getattr(config, name))
    return async_redact_data(data, TO_REDACT)


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: OpenDisplayConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    runtime = entry.runtime_data
    fw = runtime.firmware

    return {
        "firmware": {
            "major": fw["major"],
            "minor": fw["minor"],
            "patch": fw["patch"],
            "sha": fw["sha"],
        },
        "is_flex": runtime.is_flex,
        "device_config": _device_config(runtime.device_config),
    }
