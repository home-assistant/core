"""Diagnostics support for Govee lights local."""

from typing import Any

from govee_local_api import GoveeDevice, GoveeLightFeatures

from homeassistant.core import HomeAssistant

from .coordinator import GoveeLocalConfigEntry


def _device_diagnostics(device: GoveeDevice) -> dict[str, Any]:
    """Return diagnostics for a single device without identifying data."""
    capabilities = device.capabilities
    return {
        "sku": device.sku,
        "is_manual": device.is_manual,
        "on": device.on,
        "brightness": device.brightness,
        "rgb_color": device.rgb_color,
        "temperature_color": device.temperature_color,
        "capabilities": {
            "features": [
                feature.name
                for feature in GoveeLightFeatures
                if feature in capabilities.features
            ],
            "segments_count": capabilities.segments_count,
            "temperature_range": capabilities.temperature_range._asdict(),
            "scenes": capabilities.available_scenes,
        },
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: GoveeLocalConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return {
        "devices": [
            _device_diagnostics(device) for device in entry.runtime_data.devices
        ]
    }
