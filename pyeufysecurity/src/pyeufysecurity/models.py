"""Data models for Eufy Security API."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any
from urllib.parse import quote as url_quote

from .exceptions import EufySecurityError

if TYPE_CHECKING:
    from .api import EufySecurityAPI

_LOGGER = logging.getLogger(__name__)


@dataclass
class Camera:
    """Representation of a Eufy Security camera."""

    _api: EufySecurityAPI = field(repr=False)
    camera_info: dict[str, Any] = field(repr=False)
    # Separate storage for event-based data (thumbnail URL, etc.)
    _event_data: dict[str, Any] = field(default_factory=dict, repr=False)
    # RTSP credentials (set from config entry options)
    rtsp_username: str | None = None
    rtsp_password: str | None = None

    @property
    def serial(self) -> str:
        """Return the camera serial number."""
        return str(self.camera_info.get("device_sn", ""))

    @property
    def name(self) -> str:
        """Return the camera name."""
        return str(self.camera_info.get("device_name", "Unknown"))

    @property
    def model(self) -> str:
        """Return the camera model."""
        return str(self.camera_info.get("device_model", "Unknown"))

    @property
    def station_serial(self) -> str:
        """Return the station serial number."""
        return str(self.camera_info.get("station_sn", ""))

    @property
    def hardware_version(self) -> str:
        """Return the hardware version."""
        return str(self.camera_info.get("main_hw_version", ""))

    @property
    def software_version(self) -> str:
        """Return the software version."""
        return str(self.camera_info.get("main_sw_version", ""))

    @property
    def ip_address(self) -> str | None:
        """Return the local IP address of the camera."""
        return self.camera_info.get("ip_addr") or None

    @property
    def last_camera_image_url(self) -> str | None:
        """Return the URL to the latest camera thumbnail from events."""
        # Try event-based thumbnail first, fall back to device info
        return self._event_data.get("pic_url") or self.camera_info.get("cover_path")

    def update_event_data(self, event_data: dict[str, Any]) -> None:
        """Update the camera with event data (thumbnail URL, etc.)."""
        self._event_data = event_data

    async def async_start_stream(self) -> str | None:
        """Start the camera stream and return the RTSP URL.

        Tries local RTSP first (if camera has RTSP enabled and credentials configured),
        then falls back to cloud streaming.
        """
        # Try local RTSP if we have an IP address and credentials
        # Eufy cameras with RTSP enabled use port 554 and path /live0
        if self.ip_address and self.rtsp_username and self.rtsp_password:
            # URL-encode credentials in case they contain special characters
            username = url_quote(self.rtsp_username, safe="")
            password = url_quote(self.rtsp_password, safe="")
            rtsp_url = f"rtsp://{username}:{password}@{self.ip_address}:554/live0"
            _LOGGER.debug(
                "Camera %s local RTSP URL: rtsp://%s:***@%s:554/live0",
                self.name,
                self.rtsp_username,
                self.ip_address,
            )
            return rtsp_url

        if self.ip_address:
            _LOGGER.debug(
                "Camera %s has IP %s but RTSP credentials not configured. "
                "Configure them in the integration options",
                self.name,
                self.ip_address,
            )

        # Fall back to cloud streaming API
        try:
            resp = await self._api.async_request(
                "post",
                "v1/web/equipment/start_stream",
                data={
                    "device_sn": self.serial,
                    "station_sn": self.station_serial,
                    "proto": 2,
                },
            )
            url = resp.get("data", {}).get("url")
            return str(url) if url else None
        except EufySecurityError as err:
            _LOGGER.warning("Failed to start stream: %s", err)
            return None

    async def async_stop_stream(self) -> None:
        """Stop the camera stream."""
        try:
            await self._api.async_request(
                "post",
                "v1/web/equipment/stop_stream",
                data={
                    "device_sn": self.serial,
                    "station_sn": self.station_serial,
                    "proto": 2,
                },
            )
        except EufySecurityError as err:
            _LOGGER.warning("Failed to stop stream: %s", err)


@dataclass
class Station:
    """Representation of a Eufy Security station/hub."""

    serial: str
    name: str
    model: str
