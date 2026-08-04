"""Async REST client for the Agent DVR server's command.cgi API.

Endpoints used here were verified live against a production Agent DVR
7.8.0.0 server. Anything not explicitly listed below returned
``{"status": "Command not found"}`` when probed and is intentionally not
implemented rather than guessed.
"""

import asyncio
import logging
import socket
from typing import Any
from urllib.parse import urlencode

import aiohttp

_LOGGER = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 10


class AgentDVRError(Exception):
    """Generic error talking to the Agent DVR server."""


class AgentDVRConnectionError(AgentDVRError):
    """Could not reach the Agent DVR server."""


class AgentDVRAuthError(AgentDVRError):
    """Agent DVR rejected the credentials (Protect API enabled)."""


class AgentDVRCommandError(AgentDVRError):
    """Agent DVR understood the request but returned an error payload."""


class AgentDVRClient:
    """Thin wrapper around Agent DVR's command.cgi REST API."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        host: str,
        port: int,
        username: str | None = None,
        password: str | None = None,
        use_ssl: bool = False,
    ) -> None:
        """Initialize the client."""
        self._session = session
        scheme = "https" if use_ssl else "http"
        self._base_url = f"{scheme}://{host}:{port}/"
        self._username = username
        self._password = password or ""
        self._auth = aiohttp.BasicAuth(username, self._password) if username else None

    @property
    def base_url(self) -> str:
        """Base URL of the Agent DVR server, e.g. http://host:port/."""
        return self._base_url

    @property
    def username(self) -> str | None:
        """Configured username, if any."""
        return self._username

    @property
    def password(self) -> str:
        """Configured password (empty string if none)."""
        return self._password

    @property
    def auth_type(self) -> str | None:
        """Authentication scheme to hand to MjpegCamera ('basic' or None)."""
        return "basic" if self._username else None

    def media_url(self, kind: str, oid: int) -> str:
        """Build an absolute media URL (mjpeg/mp4/webm/still) for a device."""
        paths = {
            "mjpeg": "video.mjpg",
            "mp4": "video.mp4",
            "webm": "video.webm",
            "still": "grab.jpg",
        }
        return f"{self._base_url}{paths[kind]}?oid={oid}"

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> dict:
        url = self._base_url + path
        if params:
            url = f"{url}?{urlencode(params)}"
        try:
            async with asyncio.timeout(DEFAULT_TIMEOUT):
                response = await self._session.get(url, auth=self._auth)
                if response.status == 401:
                    raise AgentDVRAuthError(
                        "Agent DVR rejected the credentials (Protect API)"
                    )
                response.raise_for_status()
                data = await response.json(content_type=None)
        except TimeoutError as exc:
            raise AgentDVRConnectionError("Timed out connecting to Agent DVR") from exc
        except (aiohttp.ClientError, socket.gaierror) as exc:
            raise AgentDVRConnectionError("Error communicating with Agent DVR") from exc

        if isinstance(data, dict) and data.get("error"):
            raise AgentDVRCommandError(str(data.get("message") or data["error"]))
        return data

    async def _command(self, cmd: str, **params: Any) -> dict:
        return await self._get("command.cgi", {"cmd": cmd, **params})

    # -- server level ---------------------------------------------------

    async def get_status(self) -> dict:
        """Return server status: armed, devices, active, recording, version..."""
        return await self._command("getStatus")

    async def get_objects(self) -> dict:
        """Return the full device/location/group tree."""
        return await self._command("getObjects")

    async def get_profiles(self) -> list[dict]:
        """Return the list of configured arm/disarm profiles."""
        data = await self._command("getProfiles")
        return data.get("profiles", [])

    async def arm(self) -> None:
        """Arm the server."""
        await self._command("arm")

    async def disarm(self) -> None:
        """Disarm the server."""
        await self._command("disarm")

    async def set_active_profile(self, profile_name: str) -> None:
        """Switch the active arm/disarm profile (e.g. home/away/night)."""
        await self._command("setProfileByName", name=profile_name)

    # -- per-device -------------------------------------------------------

    async def switch_on(self, oid: int, ot: int) -> None:
        """Enable a device."""
        await self._command("switchOn", oid=oid, ot=ot)

    async def switch_off(self, oid: int, ot: int) -> None:
        """Disable a device."""
        await self._command("switchOff", oid=oid, ot=ot)

    async def record_start(self, oid: int, ot: int) -> None:
        """Start recording on a device."""
        await self._command("record", oid=oid, ot=ot)

    async def record_stop(self, oid: int, ot: int) -> None:
        """Stop recording on a device."""
        await self._command("recordStop", oid=oid, ot=ot)

    async def alerts_on(self, oid: int, ot: int) -> None:
        """Enable alerts on a device."""
        await self._command("alertOn", oid=oid, ot=ot)

    async def alerts_off(self, oid: int, ot: int) -> None:
        """Disable alerts on a device."""
        await self._command("alertOff", oid=oid, ot=ot)

    async def detector_on(self, oid: int, ot: int) -> None:
        """Enable motion detection on a device."""
        await self._command("detectorOn", oid=oid, ot=ot)

    async def detector_off(self, oid: int, ot: int) -> None:
        """Disable motion detection on a device."""
        await self._command("detectorOff", oid=oid, ot=ot)

    async def snapshot(self, oid: int, ot: int) -> None:
        """Trigger a snapshot on a device."""
        await self._command("snapshot", oid=oid, ot=ot)

    async def get_event_count(self, oid: int, ot: int, seconds: int) -> int:
        """Return the number of events for a device in the last `seconds`."""
        data = await self._get(
            "eventcounts.json", {"oid": oid, "ot": ot, "secs": seconds}
        )
        return int(data.get("count", 0))

    # -- PTZ ------------------------------------------------------------
    # Verified live: cmd=ptzpresets lists the presets configured in Agent
    # DVR for a device; cmd=ptzpreset&preset=<name> moves to one of them.
    # There is no documented raw directional (continuous move) command
    # over REST — see webrtc.py for that.

    async def get_ptz_presets(self, oid: int, ot: int) -> list[dict] | None:
        """Return [{"name": ..., "token": ...}, ...] or None if unsupported."""
        try:
            data = await self._command("ptzpresets", oid=oid, ot=ot)
        except AgentDVRCommandError:
            return None
        presets = data.get("presets")
        if not presets:
            return None
        return presets

    async def goto_ptz_preset(self, oid: int, ot: int, preset: str) -> None:
        """Move a PTZ camera to one of its configured presets."""
        await self._command("ptzpreset", oid=oid, ot=ot, preset=preset)
