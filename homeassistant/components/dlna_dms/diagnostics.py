"""Diagnostics support for DLNA DMS."""

from typing import TYPE_CHECKING, Any

from async_upnp_client.profiles.dlna import DmsDevice

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .dms import get_domain_data


def _device_diagnostics(device: DmsDevice) -> dict[str, Any]:
    """Return diagnostics for a connected DMS device."""
    profile_device = device.profile_device
    return {
        "manufacturer": profile_device.manufacturer,
        "model_name": profile_device.model_name,
        "model_number": profile_device.model_number,
        "model_description": profile_device.model_description,
        "device_type": profile_device.device_type,
        "services": {
            service.service_type: sorted(service.actions)
            for service in profile_device.services.values()
        },
        "search_capabilities": device.search_capabilities,
        "sort_capabilities": device.sort_capabilities,
        "source_protocol_info": device.source_protocol_info,
        "system_update_id": device.system_update_id,
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    if TYPE_CHECKING:
        assert entry.unique_id
    source = get_domain_data(hass).devices[entry.unique_id]
    device = source.device
    return {
        "available": source.available,
        "device": _device_diagnostics(device) if device else None,
    }
