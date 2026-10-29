"""Diagnostics support for LG ThinQ."""

from typing import Any

from thinqconnect import ConnectBaseDevice
from thinqconnect.devices.connect_device import ConnectDeviceProfile

from homeassistant.const import CONF_COUNTRY
from homeassistant.core import HomeAssistant

from . import ThinqConfigEntry


def _properties(profile: ConnectDeviceProfile, device: ConnectBaseDevice) -> dict:
    """Return the capabilities and current status of each property."""
    return {
        key: {"profile": attributes, "status": device.get_status(key)}
        for key, attributes in profile.property_map.items()
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ThinqConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    devices = []
    for coordinator in entry.runtime_data.coordinators.values():
        device = coordinator.api.device
        profile = device.profiles
        locations = {}
        for location in profile.locations:
            sub_profile = profile.get_sub_profile(location)
            sub_device = device.get_sub_device(location)
            if sub_profile is not None and sub_device is not None:
                locations[location] = _properties(sub_profile, sub_device)
        devices.append(
            {
                "device_type": device.device_type,
                "model_name": device.model_name,
                "sub_id": coordinator.sub_id,
                "reportable": device.reportable,
                "connected": coordinator.device_connected,
                "last_update_success": coordinator.last_update_success,
                "properties": _properties(profile, device),
                "locations": locations,
            }
        )
    return {
        "country": entry.data[CONF_COUNTRY],
        "devices": devices,
    }
