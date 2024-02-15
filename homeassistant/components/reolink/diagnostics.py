"""Diagnostics support for Reolink."""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from . import ReolinkData
from .const import DOMAIN


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    reolink_data: ReolinkData = hass.data[DOMAIN][config_entry.entry_id]
    host = reolink_data.host
    api = host.api

    IPC_cam: dict[int, dict[str, Any]] = {}
    for ch in api.channels:
        IPC_cam[ch] = {}
        IPC_cam[ch]["model"] = api.camera_model(ch)
        IPC_cam[ch]["firmware version"] = api.camera_sw_version(ch)

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
        "capabilities": api.capabilities,
        "api versions": api.checked_api_versions,
        "abilities": api.abilities,
    }
