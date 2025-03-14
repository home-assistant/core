"""Diagnostics support for Reolink."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from .util import ReolinkConfigEntry, ReolinkData


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ReolinkConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    reolink_data: ReolinkData = config_entry.runtime_data
    host = reolink_data.host
    api = host.api

    IPC_cam: dict[int, dict[str, Any]] = {}
    for ch in api.channels:
        IPC_cam[ch] = {}
        IPC_cam[ch]["model"] = api.camera_model(ch)
        IPC_cam[ch]["hardware version"] = api.camera_hardware_version(ch)
        IPC_cam[ch]["firmware version"] = api.camera_sw_version(ch)
        IPC_cam[ch]["encoding main"] = await api.get_encoding(ch)

    chimes: dict[int, dict[str, Any]] = {}
    for chime in api.chime_list:
        chimes[chime.dev_id] = {}
        chimes[chime.dev_id]["channel"] = chime.channel
        chimes[chime.dev_id]["name"] = chime.name
        chimes[chime.dev_id]["online"] = chime.online
        chimes[chime.dev_id]["event_types"] = chime.chime_event_types

    return {
        "model": api.model,
        "hardware version": api.hardware_version,
        "firmware version": api.sw_version,
        "HTTPS": api.use_https,
        "HTTP(S) port": api.port,
        "WiFi connection": api.wifi_connection,
        "WiFi signal": api.wifi_signal,
        "RTMP enabled": api.rtmp_enabled,
        "RTSP enabled": api.rtsp_enabled,
        "ONVIF enabled": api.onvif_enabled,
        "event connection": host.event_connection,
        "stream protocol": api.protocol,
        "channels": api.channels,
        "stream channels": api.stream_channels,
        "IPC cams": IPC_cam,
        "Chimes": chimes,
        "capabilities": api.capabilities,
        "cmd list": host.update_cmd,
        "firmware ch list": host.firmware_ch_list,
        "api versions": api.checked_api_versions,
        "abilities": api.abilities,
        "BC_abilities": api.baichuan.abilities,
    }
