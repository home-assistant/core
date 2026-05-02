"""
WJG XM-3820 Camera Bridge für Home Assistant
=============================================
Unterstützt:
  - Livestream via RTSP / MJPEG
  - Snapshot (still image)
  - Aufnahme Start/Stop via HTTP API oder XM SDK
  - Dateiliste / SD-Karten-Zugriff
  - Bewegungserkennung (Sensor)
  - PTZ-Steuerung (falls verfügbar)
"""
from __future__ import annotations

import logging
from typing import Final

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .coordinator import WJGCameraCoordinator

_LOGGER = logging.getLogger(__name__)

DOMAIN: Final = "wjg_camera"
MANUFACTURER: Final = "WJG / Tenganda"
MODEL: Final = "XM-3820"

CONF_RTSP_PORT: Final = "rtsp_port"
CONF_RTSP_PATH: Final = "rtsp_path"
CONF_SNAPSHOT_PATH: Final = "snapshot_path"
CONF_PROTOCOL: Final = "protocol"
CONF_HTTP_RETRIES: Final = "http_retries"

PROTOCOL_RTSP: Final = "rtsp"
PROTOCOL_HTTP: Final = "http_only"
PROTOCOL_XM: Final = "xm_sdk"
PROTOCOL_ONVIF: Final = "onvif"

DEFAULT_RTSP_PORT: Final = 554
DEFAULT_HTTP_PORT: Final = 80
DEFAULT_XM_PORT: Final = 34567
DEFAULT_ONVIF_PORT: Final = 8899
DEFAULT_USERNAME: Final = "admin"
DEFAULT_PASSWORD: Final = ""
DEFAULT_HTTP_RETRIES: Final = 1

# Standard RTSP-Pfad für XM-basierte Kameras
DEFAULT_RTSP_PATH: Final = (
    "/user=admin&password=&channel=1&stream=0.sdp?real_stream"
)
DEFAULT_SNAPSHOT_PATH: Final = "/webcapture.jpg?command=snap&channel=1"

PLATFORMS: list[Platform] = [
    Platform.CAMERA,
    Platform.SWITCH,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.SENSOR,
]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Integration einrichten aus Config-Entry."""
    coordinator = WJGCameraCoordinator(hass, entry)

    try:
        await coordinator.async_setup()
    except Exception as err:
        _LOGGER.error(
            "Fehler beim Verbinden mit der Kamera %s: %s",
            entry.data.get(CONF_HOST),
            err,
        )
        raise ConfigEntryNotReady(f"Kamera nicht erreichbar: {err}") from err

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _LOGGER.info(
        "WJG XM-3820 Bridge erfolgreich eingerichtet: %s",
        entry.data.get(CONF_HOST)
    )
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Integration entladen."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator: WJGCameraCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_shutdown()
    return unload_ok

async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Integration neu laden."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
