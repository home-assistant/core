"""Diagnostics support for Apple TV."""

from typing import Any

from pyatv.const import Protocol

from homeassistant.core import HomeAssistant

from . import AppleTvConfigEntry
from .const import CONF_CREDENTIALS


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: AppleTvConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    manager = entry.runtime_data
    diagnostics: dict[str, Any] = {
        "options": dict(entry.options),
        "paired_protocols": sorted(
            Protocol(int(protocol)).name for protocol in entry.data[CONF_CREDENTIALS]
        ),
        "is_on": manager.is_on,
        "is_connecting": manager.is_connecting,
        "connected": manager.atv is not None,
    }
    if (atv := manager.atv) is not None:
        device_info = atv.device_info
        diagnostics["device_info"] = {
            "operating_system": device_info.operating_system.name,
            "version": device_info.version,
            "build_number": device_info.build_number,
            "model": device_info.model.name,
            "raw_model": device_info.raw_model,
        }
        diagnostics["features"] = {
            feature.name: info.state.name
            for feature, info in atv.features.all_features().items()
        }
    return diagnostics
