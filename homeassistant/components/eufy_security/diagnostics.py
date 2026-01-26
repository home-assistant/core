"""Diagnostics support for Eufy Security."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .coordinator import EufySecurityConfigEntry

TO_REDACT = {
    "email",
    "password",
    "token",
    "private_key",
    "server_public_key",
    "api_base",
    "ip_addr",
    "ip_address",
    "cover_path",
    "pic_url",
    "rtsp_username",
    "rtsp_password",
    "rtsp_credentials",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    config_entry: EufySecurityConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    api = config_entry.runtime_data.api

    cameras_data = {
        serial: {
            "name": camera.name,
            "model": camera.model,
            "serial": camera.serial,
            "station_serial": camera.station_serial,
            "hardware_version": camera.hardware_version,
            "software_version": camera.software_version,
            "has_ip_address": camera.ip_address is not None,
            "has_rtsp_credentials": bool(camera.rtsp_username and camera.rtsp_password),
            "has_thumbnail": camera.last_camera_image_url is not None,
        }
        for serial, camera in api.cameras.items()
    }

    stations_data = {
        serial: {
            "name": station.name,
            "model": station.model,
            "serial": station.serial,
        }
        for serial, station in api.stations.items()
    }

    return {
        "config_entry": async_redact_data(config_entry.as_dict(), TO_REDACT),
        "cameras": cameras_data,
        "stations": stations_data,
    }
