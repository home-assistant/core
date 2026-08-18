"""Diagnostics support for the Lyngdorf integration."""

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.components.ssdp import async_get_discovery_info_by_st
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.service_info.ssdp import ATTR_UPNP_SERIAL

from .const import CONF_SERIAL_NUMBER, SSDP_ST
from .models import LyngdorfConfigEntry

_TRIM_NAMES = tuple(
    f"trim_{trim}" for trim in ("bass", "treble", "centre", "height", "lfe", "surround")
)
_RANGE_NAMES = ("lipsync_range", *(f"{name}_range" for name in _TRIM_NAMES))

# The serial doubles as the device MAC and as the config entry unique_id, so it
# needs redacting wherever it surfaces, including inside the UPnP description.
TO_REDACT = {
    CONF_HOST,
    CONF_SERIAL_NUMBER,
    "unique_id",
    ATTR_UPNP_SERIAL,
    "presentationURL",
    "ssdp_location",
    "ssdp_all_locations",
    "ssdp_headers",
    "ssdp_usn",
    "ssdp_udn",
}


async def _async_ssdp_description(
    hass: HomeAssistant, serial: str
) -> dict[str, Any] | None:
    """Return the UPnP description this device is currently announcing."""
    for info in await async_get_discovery_info_by_st(hass, SSDP_ST):
        if (info.upnp.get(ATTR_UPNP_SERIAL) or "").lower() == serial.lower():
            return {
                "ssdp_usn": info.ssdp_usn,
                "ssdp_st": info.ssdp_st,
                "ssdp_udn": info.ssdp_udn,
                "ssdp_server": info.ssdp_server,
                "ssdp_location": info.ssdp_location,
                "upnp": dict(info.upnp),
            }
    # Null when SSDP has not seen the device, which is worth knowing in itself.
    return None


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: LyngdorfConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    receiver = config_entry.runtime_data.receiver

    state: dict[str, Any] = {
        "connected": receiver.connected,
        "model": receiver.model.name if receiver.model else None,
        "power_on": receiver.power_on,
        "volume": receiver.volume,
        "max_volume": receiver.max_volume,
        "mute_enabled": receiver.mute_enabled,
        "source": receiver.source,
        "available_sources": receiver.available_sources,
        "sound_mode": receiver.sound_mode,
        "available_sound_modes": receiver.available_sound_modes,
        "audio_input": receiver.audio_input,
        "available_audio_inputs": receiver.available_audio_inputs,
        "video_input": receiver.video_input,
        "available_video_inputs": receiver.available_video_inputs,
        "audio_information": receiver.audio_information,
        "video_information": receiver.video_information,
        "streaming_source": receiver.streaming_source,
        "available_stream_types": receiver.available_stream_types,
        "room_perfect_position": receiver.room_perfect_position,
        "available_room_perfect_positions": receiver.available_room_perfect_positions,
        "voicing": receiver.voicing,
        "available_voicings": receiver.available_voicings,
        "lipsync": receiver.lipsync,
        "zone_b_power_on": receiver.zone_b_power_on,
        "zone_b_volume": receiver.zone_b_volume,
        "zone_b_mute_enabled": receiver.zone_b_mute_enabled,
        "zone_b_source": receiver.zone_b_source,
        "zone_b_audio_input": receiver.zone_b_audio_input,
        "zone_b_streaming_source": receiver.zone_b_streaming_source,
    }
    state |= {name: getattr(receiver, name) for name in _TRIM_NAMES}

    ranges = {
        name: asdict(value) if (value := getattr(receiver, name)) is not None else None
        for name in _RANGE_NAMES
    }

    return async_redact_data(
        {
            "entry": config_entry.as_dict(),
            "ssdp": await _async_ssdp_description(
                hass, config_entry.data[CONF_SERIAL_NUMBER]
            ),
            "state": state,
            "ranges": ranges,
        },
        TO_REDACT,
    )
