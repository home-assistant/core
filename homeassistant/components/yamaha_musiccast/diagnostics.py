"""Diagnostics support for MusicCast."""

from dataclasses import asdict
from typing import Any

from aiomusiccast.features import Feature
from aiomusiccast.musiccast_data import MusicCastZoneData

from homeassistant.core import HomeAssistant

from .coordinator import MusicCastConfigEntry


def _feature_names(features: Feature) -> list[str]:
    """Return the names of the set feature flags."""
    return sorted(feature.name for feature in features if feature.name)


def _zone_diagnostics(zone: MusicCastZoneData) -> dict[str, Any]:
    """Return diagnostics for a zone."""
    return {
        **{
            key: value
            for key, value in vars(zone).items()
            if key not in ("capabilities", "range_step")
        },
        "features": _feature_names(zone.features),
        "range_step": {
            key: asdict(range_step) for key, range_step in zone.range_step.items()
        },
        "capabilities": [capability.id for capability in zone.capabilities],
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: MusicCastConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    musiccast = entry.runtime_data.musiccast
    data = musiccast.data
    return {
        "device": {
            "model_name": data.model_name,
            "system_version": data.system_version,
            "api_version": data.api_version,
            "features": _feature_names(musiccast.features),
            "capabilities": [capability.id for capability in data.capabilities],
        },
        "zones": {
            zone_id: _zone_diagnostics(zone) for zone_id, zone in data.zones.items()
        },
        "input_names": data.input_names,
        "sound_program_names": data.sound_program_names,
        "netusb": {
            "input": data.netusb_input,
            "playback": data.netusb_playback,
            "repeat": data.netusb_repeat,
            "shuffle": data.netusb_shuffle,
        },
        "tuner": {"band": data.band},
        "group": {
            "role": data.group_role,
            "server_zone": data.group_server_zone,
            "client_count": len(data.group_client_list),
        },
        "dimmer": (
            {**asdict(data.dimmer), "current": data.dimmer.dimmer_current}
            if data.dimmer
            else None
        ),
        "speaker_a": data.speaker_a,
        "speaker_b": data.speaker_b,
        "party_enable": data.party_enable,
        "alarm": {
            "on": data.alarm_on,
            "mode": data.alarm_mode,
            "volume": data.alarm_volume,
            "volume_range": data.alarm_volume_range,
            "fade_range": data.alarm_fade_range,
            "details": {
                day: {
                    key: value
                    for key, value in asdict(details).items()
                    if key != "preset_info"
                }
                for day, details in data.alarm_details.items()
            },
        },
    }
