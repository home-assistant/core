"""Diagnostics support for Wyoming."""

from typing import Any

from homeassistant.core import HomeAssistant

from . import SATELLITE_PLATFORMS
from .models import WyomingConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: WyomingConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    item = entry.runtime_data
    platforms = list(item.service.platforms)
    if item.device is not None:
        platforms += SATELLITE_PLATFORMS

    diagnostics: dict[str, Any] = {
        "info": item.coordinator.data.event().data,
        "last_update_success": item.coordinator.last_update_success,
        "platforms": platforms,
    }

    if (device := item.device) is not None:
        diagnostics["satellite"] = {
            "is_active": device.is_active,
            "is_muted": device.is_muted,
            "pipeline_name": device.pipeline_name,
            "noise_suppression_level": device.noise_suppression_level,
            "auto_gain": device.auto_gain,
            "volume_multiplier": device.volume_multiplier,
            "vad_sensitivity": device.vad_sensitivity,
        }

    return diagnostics
