"""Diagnostics support for DLNA DMR."""

from typing import Any

from async_upnp_client.profiles.dlna import DmrDevice

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import async_get_platforms

from .const import (
    CONF_BROWSE_UNFILTERED,
    CONF_CALLBACK_URL_OVERRIDE,
    CONF_LISTEN_PORT,
    CONF_POLL_AVAILABILITY,
    DOMAIN,
)
from .media_player import DlnaDmrEntity


def _device_diagnostics(device: DmrDevice) -> dict[str, Any]:
    """Return diagnostics for a connected DMR device."""
    profile_device = device.profile_device
    return {
        "manufacturer": profile_device.manufacturer,
        "model_name": profile_device.model_name,
        "model_number": profile_device.model_number,
        "model_description": profile_device.model_description,
        "device_type": profile_device.device_type,
        "services": {
            service.service_type: sorted(service.actions)
            for service in profile_device.all_services
        },
        "sink_protocol_info": device.sink_protocol_info,
        "transport_state": device.transport_state,
        "valid_play_modes": sorted(device.valid_play_modes),
        "has_volume_level": device.has_volume_level,
        "has_volume_mute": device.has_volume_mute,
        "has_presets": device.has_presets,
        "has_play_media": device.has_play_media,
        "has_next_transport_uri": device.has_next_transport_uri,
        "can_play": device.can_play,
        "can_pause": device.can_pause,
        "can_stop": device.can_stop,
        "can_previous": device.can_previous,
        "can_next": device.can_next,
        "can_seek_rel_time": device.can_seek_rel_time,
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    # The entity is not added to the platform when it is disabled
    entity = next(
        (
            entity
            for platform in async_get_platforms(hass, DOMAIN)
            if platform.config_entry is not None
            and platform.config_entry.entry_id == entry.entry_id
            for entity in platform.entities.values()
            if isinstance(entity, DlnaDmrEntity)
        ),
        None,
    )
    device = entity.device if entity else None
    return {
        "device_type": entry.data[CONF_TYPE],
        "options": {
            CONF_LISTEN_PORT: entry.options.get(CONF_LISTEN_PORT),
            CONF_POLL_AVAILABILITY: entry.options.get(CONF_POLL_AVAILABILITY, False),
            CONF_BROWSE_UNFILTERED: entry.options.get(CONF_BROWSE_UNFILTERED, False),
            "callback_url_override_set": bool(
                entry.options.get(CONF_CALLBACK_URL_OVERRIDE)
            ),
        },
        "available": entity.available if entity else None,
        "state": entity.state if entity else None,
        "supported_features": entity.supported_features if entity else None,
        "device": _device_diagnostics(device) if device else None,
    }
