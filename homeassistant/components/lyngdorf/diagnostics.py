"""Diagnostics support for the Lyngdorf integration."""

from dataclasses import asdict
from typing import Any

from lyngdorf import Trim

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.components.ssdp import async_get_discovery_info_by_st
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.service_info.ssdp import ATTR_UPNP_SERIAL

from .const import CONF_SERIAL_NUMBER, SSDP_ST
from .models import LyngdorfConfigEntry

# Reported under the integration's own names, which do not all match the
# library's spelling of the band.
_TRIMS = {
    "trim_bass": Trim.BASS,
    "trim_treble": Trim.TREBLE,
    "trim_centre": Trim.CENTER,
    "trim_height": Trim.HEIGHT,
    "trim_lfe": Trim.LFE,
    "trim_surround": Trim.SURROUND,
}

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
    volume = receiver.volume
    lipsync = receiver.lipsync
    zone_b = receiver.zone_b

    state: dict[str, Any] = {
        "connected": receiver.connected,
        "model": receiver.model.name,
        "power_on": receiver.power_on,
        "volume": volume.value if volume is not None else None,
        "mute_enabled": receiver.muted,
        "source": receiver.source,
        "available_sources": receiver.sources,
        "sound_mode": receiver.sound_mode,
        "available_sound_modes": receiver.sound_modes,
        "audio_input": receiver.audio_input,
        "available_audio_inputs": receiver.audio_inputs,
        "video_input": receiver.video_input,
        "available_video_inputs": receiver.video_inputs,
        "audio_information": receiver.audio_information,
        "video_information": receiver.video_information,
        "streaming_source": receiver.streaming_source,
        "available_stream_types": receiver.stream_types,
        "room_perfect_position": receiver.room_perfect_position,
        "available_room_perfect_positions": receiver.room_perfect_positions,
        "voicing": receiver.voicing,
        "available_voicings": receiver.voicings,
        "lipsync": lipsync.value if lipsync is not None else None,
        "zone_b_power_on": zone_b.power_on if zone_b is not None else None,
        "zone_b_volume": zone_b.volume.value if zone_b is not None else None,
        "zone_b_mute_enabled": zone_b.muted if zone_b is not None else None,
        "zone_b_source": zone_b.source if zone_b is not None else None,
        "zone_b_audio_input": zone_b.audio_input if zone_b is not None else None,
        "zone_b_streaming_source": zone_b.streaming_source
        if zone_b is not None
        else None,
    }
    trims = {name: receiver.trims.get(trim) for name, trim in _TRIMS.items()}
    state |= {
        name: control.value if control is not None else None
        for name, control in trims.items()
    }

    # Not lipsync.range: the control reads None until the device reports a
    # value, while the range is known from the model as soon as it connects.
    lipsync_range = receiver.lipsync_range
    ranges: dict[str, Any] = {
        "lipsync_range": asdict(lipsync_range) if lipsync_range is not None else None
    }
    ranges |= {
        f"{name}_range": asdict(control.range) if control is not None else None
        for name, control in trims.items()
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
