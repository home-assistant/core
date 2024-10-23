"""WebRTC container classes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RTCIceServer:
    """RTC Ice Server.

    See https://www.w3.org/TR/webrtc/#rtciceserver-dictionary
    """

    urls: list[str] | str
    username: str | None = None
    credential: str | None = None

    def to_frontend_dict(self) -> dict[str, Any]:
        """Return a dict that can be used by the frontend."""

        data = {
            "urls": self.urls,
        }
        if self.username is not None:
            data["username"] = self.username
        if self.credential is not None:
            data["credential"] = self.credential
        return data


@dataclass
class RTCConfiguration:
    """RTC Configuration.

    See https://www.w3.org/TR/webrtc/#rtcconfiguration-dictionary
    """

    ice_servers: list[RTCIceServer] = field(default_factory=list)

    def to_frontend_dict(self) -> dict[str, Any]:
        """Return a dict that can be used by the frontend."""
        if not self.ice_servers:
            return {}

        return {
            "iceServers": [server.to_frontend_dict() for server in self.ice_servers]
        }


@dataclass(kw_only=True)
class WebRTCClientConfiguration:
    """WebRTC configuration for the client.

    Not part of the spec, but required to configure client.
    """

    configuration: RTCConfiguration = field(default_factory=RTCConfiguration)
    data_channel: str | None = None

    def to_frontend_dict(self) -> dict[str, Any]:
        """Return a dict that can be used by the frontend."""
        data: dict[str, Any] = {
            "configuration": self.configuration.to_frontend_dict(),
        }
        if self.data_channel is not None:
            data["dataChannel"] = self.data_channel
        return data
