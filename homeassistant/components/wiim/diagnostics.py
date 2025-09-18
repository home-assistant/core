# homeassistant/components/wiim/diagnostics.py
"""Diagnostics support for WiiM integration."""

from __future__ import annotations

from typing import Any

from wiim.wiim_device import WiimDevice

from homeassistant.core import HomeAssistant

from . import WiimConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: WiimConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    wiim_device: WiimDevice = entry.runtime_data

    diag_data: dict[str, Any] = {
        "entry_data": dict(entry.data),
        "device_udn": wiim_device.udn,
        "device_name": wiim_device.name,
        "model_name": wiim_device.model_name,
        "manufacturer": wiim_device._manufacturer,  # noqa: SLF001
        "firmware_version": wiim_device.firmware_version,
        "ip_address": wiim_device.ip_address,
        "http_api_url": wiim_device.http_api_url,
        "is_available_sdk": wiim_device.available,
        "upnp_device_info": (
            {
                "device_type": (
                    wiim_device.upnp_device.device_type
                    if wiim_device.upnp_device
                    else None
                ),
                "presentation_url": (
                    wiim_device.upnp_device.presentation_url
                    if wiim_device.upnp_device
                    else None
                ),
                "device_url_desc_xml": (
                    wiim_device.upnp_device.device_url
                    if wiim_device.upnp_device
                    else None
                ),
                "services": (
                    [s.service_id for s in wiim_device.upnp_device.services.values()]
                    if wiim_device.upnp_device
                    else []
                ),
            }
            if wiim_device.upnp_device
            else "UPnP Device object not fully initialized"
        ),
        "current_media_player_state": {
            "volume": wiim_device.volume,
            "is_muted": wiim_device.is_muted,
            "playing_status": (
                wiim_device.playing_status.value if wiim_device.playing_status else None
            ),
            "current_track_info": wiim_device.current_track_info,
            "play_mode": wiim_device.play_mode if wiim_device.play_mode else None,
            "loop_mode": wiim_device.loop_mode.value if wiim_device.loop_mode else None,
            "equalizer_mode": (
                wiim_device.equalizer_mode.value if wiim_device.equalizer_mode else None
            ),
            "current_position_sec": wiim_device.current_position,
            "current_track_duration_sec": wiim_device.current_track_duration,
            "next_track_uri": wiim_device.next_track_uri,
        },
        "http_device_properties_raw": (
            dict(wiim_device._device_info_properties)  # noqa: SLF001
            if wiim_device._device_info_properties  # noqa: SLF001
            else None
        ),
        "http_player_properties_raw": (
            dict(wiim_device._player_properties)  # noqa: SLF001
            if wiim_device._player_properties  # noqa: SLF001
            else None
        ),
    }

    if wiim_device.av_transport:
        diag_data["upnp_av_transport_state"] = {
            s.name: s.value for s in wiim_device.av_transport.state_variables.values()
        }
    if wiim_device.rendering_control:
        diag_data["upnp_rendering_control_state"] = {
            s.name: s.value
            for s in wiim_device.rendering_control.state_variables.values()
        }
    if wiim_device.play_queue_service:
        diag_data["upnp_play_queue_state"] = {
            s.name: s.value
            for s in wiim_device.play_queue_service.state_variables.values()
        }

    return diag_data
