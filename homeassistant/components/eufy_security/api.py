"""API client for Eufy Security.

Based on python-eufy-security library by keshavdv/FuzzyMistborn.
Inlined and maintained as part of Home Assistant integration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import logging
from typing import Any

from aiohttp import ClientError, ClientSession

_LOGGER = logging.getLogger(__name__)

API_BASE = "https://mysecurity.eufylife.com/api/v1"

# Error code mapping from Eufy API
ERROR_CODES: dict[int, type[Exception]] = {}


class EufySecurityError(Exception):
    """Base exception for Eufy Security errors."""


class InvalidCredentialsError(EufySecurityError):
    """Exception for invalid credentials."""


class RequestError(EufySecurityError):
    """Exception for request errors."""


class CannotConnectError(EufySecurityError):
    """Exception for connection failures."""


# Map error code 26006 to InvalidCredentialsError
ERROR_CODES[26006] = InvalidCredentialsError


def _raise_on_error(data: dict[str, Any]) -> None:
    """Raise appropriate error based on response code."""
    code = data.get("code", 0)
    if code == 0:
        return
    error_class = ERROR_CODES.get(code, EufySecurityError)
    raise error_class(data.get("msg", f"Unknown error (code {code})"))


@dataclass
class Camera:
    """Representation of a Eufy Security camera."""

    _api: EufySecurityAPI = field(repr=False)
    camera_info: dict[str, Any] = field(repr=False)

    @property
    def serial(self) -> str:
        """Return the camera serial number."""
        return self.camera_info.get("device_sn", "")

    @property
    def name(self) -> str:
        """Return the camera name."""
        return self.camera_info.get("device_name", "Unknown")

    @property
    def model(self) -> str:
        """Return the camera model."""
        return self.camera_info.get("device_model", "Unknown")

    @property
    def station_serial(self) -> str:
        """Return the station serial number."""
        return self.camera_info.get("station_sn", "")

    @property
    def hardware_version(self) -> str:
        """Return the hardware version."""
        return self.camera_info.get("main_hw_version", "")

    @property
    def software_version(self) -> str:
        """Return the software version."""
        return self.camera_info.get("main_sw_version", "")

    @property
    def last_camera_image_url(self) -> str | None:
        """Return the URL to the latest camera thumbnail."""
        return self.camera_info.get("cover_path")

    async def async_start_stream(self) -> str | None:
        """Start the camera stream and return the RTSP URL."""
        try:
            resp = await self._api.async_request(
                "post",
                "web/equipment/start_stream",
                json={
                    "device_sn": self.serial,
                    "station_sn": self.station_serial,
                    "proto": 2,
                },
            )
            return resp.get("data", {}).get("url")
        except EufySecurityError as err:
            _LOGGER.warning("Failed to start stream: %s", err)
            return None

    async def async_stop_stream(self) -> None:
        """Stop the camera stream."""
        try:
            await self._api.async_request(
                "post",
                "web/equipment/stop_stream",
                json={
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


class EufySecurityAPI:
    """API client for Eufy Security."""

    def __init__(self, session: ClientSession, email: str, password: str) -> None:
        """Initialize the API client."""
        self._session = session
        self._email = email
        self._password = password
        self._api_base = API_BASE
        self._token: str | None = None
        self._token_expiration: datetime | None = None
        self._retry_on_401 = False
        self.cameras: dict[str, Camera] = {}
        self.stations: dict[str, Station] = {}

    async def async_authenticate(self) -> None:
        """Authenticate and get an access token."""
        try:
            auth_resp = await self.async_request(
                "post",
                "passport/login",
                json={"email": self._email, "password": self._password},
                skip_auth=True,
            )
        except ClientError as err:
            raise CannotConnectError(f"Connection error: {err}") from err

        self._retry_on_401 = False
        data = auth_resp.get("data", {})
        self._token = data.get("auth_token")

        if not self._token:
            raise InvalidCredentialsError("No auth token received")

        # Set token expiration
        expires_at = data.get("token_expires_at")
        if expires_at:
            self._token_expiration = datetime.fromtimestamp(expires_at)

        # Switch to domain-specific API if provided
        domain = data.get("domain")
        if domain:
            self._api_base = f"https://{domain}/v1"
            _LOGGER.info("Switching to API base: %s", self._api_base)

    async def async_update_device_info(self) -> None:
        """Get the latest device info."""
        # Get devices/cameras
        devices_resp = await self.async_request("post", "app/get_devs_list")

        device_data = devices_resp.get("data")
        if not device_data:
            return

        for device_info in device_data:
            device_sn = device_info.get("device_sn")
            if not device_sn:
                continue

            if device_sn in self.cameras:
                # Update existing camera
                self.cameras[device_sn].camera_info = device_info
            else:
                # Create new camera
                self.cameras[device_sn] = Camera(
                    _api=self,
                    camera_info=device_info,
                )

        # Get stations/hubs
        try:
            stations_resp = await self.async_request("post", "app/get_hub_list")
            for station_data in stations_resp.get("data", []):
                station = Station(
                    serial=station_data.get("station_sn", ""),
                    name=station_data.get("station_name", "Unknown"),
                    model=station_data.get("station_model", "Unknown"),
                )
                self.stations[station.serial] = station
        except EufySecurityError:
            # Stations list may not be available for all accounts
            pass

    async def async_request(
        self,
        method: str,
        endpoint: str,
        *,
        headers: dict[str, str] | None = None,
        json: dict[str, Any] | None = None,
        skip_auth: bool = False,
    ) -> dict[str, Any]:
        """Make a request to the API."""
        # Check token expiration and refresh if needed
        if (
            not skip_auth
            and self._token_expiration
            and datetime.now() >= self._token_expiration
        ):
            _LOGGER.info("Access token expired; fetching a new one")
            self._token = None
            self._token_expiration = None
            await self.async_authenticate()

        url = f"{self._api_base}/{endpoint}"

        if headers is None:
            headers = {}
        if self._token and not skip_auth:
            headers["x-auth-token"] = self._token

        try:
            async with self._session.request(
                method, url, headers=headers, json=json
            ) as resp:
                # Check for non-JSON response (blocked/rate limited)
                content_type = resp.headers.get("Content-Type", "")
                if "application/json" not in content_type:
                    text = await resp.text()
                    _LOGGER.debug("Non-JSON response from %s: %s", endpoint, text[:200])
                    raise CannotConnectError(
                        f"Unexpected response type from {endpoint}: {content_type}"
                    )

                resp.raise_for_status()
                data: dict[str, Any] = await resp.json(content_type=None)

                if not data:
                    raise RequestError(f"No response from {endpoint}")

                _raise_on_error(data)
                return data

        except ClientError as err:
            error_str = str(err)
            if "401" in error_str:
                if self._retry_on_401:
                    raise InvalidCredentialsError(
                        "Authentication failed after retry"
                    ) from err

                self._retry_on_401 = True
                _LOGGER.info("Got 401, attempting re-authentication")
                await self.async_authenticate()
                return await self.async_request(
                    method, endpoint, headers=headers, json=json
                )
            raise CannotConnectError(f"Request error: {err}") from err


async def async_login(
    email: str, password: str, session: ClientSession
) -> EufySecurityAPI:
    """Login and return an authenticated API client."""
    api = EufySecurityAPI(session, email, password)
    await api.async_authenticate()
    await api.async_update_device_info()
    return api
