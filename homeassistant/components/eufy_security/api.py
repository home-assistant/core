"""API client for Eufy Security."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import logging

from aiohttp import ClientError, ClientSession

_LOGGER = logging.getLogger(__name__)

API_BASE_URL = "https://mysecurity.eufylife.com/api/v1"

# Headers that mimic the mobile app
DEFAULT_HEADERS = {
    "User-Agent": "EufySecurity/2.4.0 (iPhone; iOS 17.0; Scale/3.00)",
    "Content-Type": "application/json",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
}


class EufySecurityError(Exception):
    """Base exception for Eufy Security errors."""


class InvalidCredentialsError(EufySecurityError):
    """Exception for invalid credentials."""


class AuthenticationError(EufySecurityError):
    """Exception for authentication failures."""


class CannotConnectError(EufySecurityError):
    """Exception for connection failures."""


@dataclass
class Camera:
    """Representation of a Eufy Security camera."""

    serial: str
    name: str
    model: str
    station_serial: str
    hardware_version: str
    software_version: str
    last_camera_image_url: str | None
    _api: EufySecurityAPI

    async def async_start_stream(self) -> str | None:
        """Start the RTSP stream and return the URL."""
        return await self._api.async_start_stream(self.serial)

    async def async_stop_stream(self) -> None:
        """Stop the RTSP stream."""
        await self._api.async_stop_stream(self.serial)


@dataclass
class Station:
    """Representation of a Eufy Security station/hub."""

    serial: str
    name: str
    model: str


class EufySecurityAPI:
    """API client for Eufy Security."""

    def __init__(self, session: ClientSession) -> None:
        """Initialize the API client."""
        self._session = session
        self._token: str | None = None
        self._user_id: str | None = None
        self.cameras: dict[str, Camera] = {}
        self.stations: dict[str, Station] = {}

    async def async_authenticate(self, email: str, password: str) -> None:
        """Authenticate with the Eufy Security API."""
        url = f"{API_BASE_URL}/passport/login"
        # Hash the password as the API expects
        password_hash = hashlib.md5(password.encode()).hexdigest()
        payload = {"email": email, "password": password_hash}

        try:
            async with self._session.post(
                url, json=payload, headers=DEFAULT_HEADERS
            ) as response:
                # Check for non-JSON response (blocked/rate limited)
                content_type = response.headers.get("Content-Type", "")
                if "application/json" not in content_type:
                    text = await response.text()
                    _LOGGER.debug("Non-JSON response: %s", text[:500])
                    if response.status == 403:
                        raise CannotConnectError(
                            "Access forbidden - Eufy may be blocking API requests"
                        )
                    raise CannotConnectError(
                        f"Unexpected response type: {content_type}"
                    )

                data = await response.json()

                if response.status != 200:
                    raise CannotConnectError(
                        f"Authentication failed with status: {response.status}"
                    )

                if data.get("code") != 0:
                    error_msg = data.get("msg", "Unknown error")
                    if "invalid" in error_msg.lower() or "incorrect" in error_msg.lower():
                        raise InvalidCredentialsError(error_msg)
                    raise AuthenticationError(error_msg)

                auth_data = data.get("data", {})
                self._token = auth_data.get("auth_token")
                self._user_id = auth_data.get("user_id")

                if not self._token:
                    raise AuthenticationError("No auth token received")

        except ClientError as err:
            raise CannotConnectError(f"Connection error: {err}") from err

    async def async_update_device_info(self) -> None:
        """Update device information from the API."""
        await self._async_get_stations()
        await self._async_get_devices()

    async def _async_get_stations(self) -> None:
        """Get list of stations/hubs."""
        url = f"{API_BASE_URL}/app/get_hub_list"

        try:
            async with self._session.post(
                url, json={}, headers=self._request_headers
            ) as response:
                data = await response.json()

                if data.get("code") != 0:
                    raise EufySecurityError(
                        f"Failed to get stations: {data.get('msg')}"
                    )

                self.stations = {}
                for station_data in data.get("data", []):
                    station = Station(
                        serial=station_data.get("station_sn", ""),
                        name=station_data.get("station_name", "Unknown"),
                        model=station_data.get("station_model", "Unknown"),
                    )
                    self.stations[station.serial] = station
        except ClientError as err:
            raise EufySecurityError(f"Connection error: {err}") from err

    async def _async_get_devices(self) -> None:
        """Get list of devices/cameras."""
        url = f"{API_BASE_URL}/app/get_devs_list"

        try:
            async with self._session.post(
                url, json={}, headers=self._request_headers
            ) as response:
                data = await response.json()

                if data.get("code") != 0:
                    raise EufySecurityError(
                        f"Failed to get devices: {data.get('msg')}"
                    )

                self.cameras = {}
                for device_data in data.get("data", []):
                    # Filter for camera devices
                    device_type = device_data.get("device_type", 0)
                    # Camera device types are typically 1-31
                    if device_type > 0:
                        camera = Camera(
                            serial=device_data.get("device_sn", ""),
                            name=device_data.get("device_name", "Unknown"),
                            model=device_data.get("device_model", "Unknown"),
                            station_serial=device_data.get("station_sn", ""),
                            hardware_version=device_data.get("main_hw_version", ""),
                            software_version=device_data.get("main_sw_version", ""),
                            last_camera_image_url=device_data.get("cover_path"),
                            _api=self,
                        )
                        self.cameras[camera.serial] = camera
        except ClientError as err:
            raise EufySecurityError(f"Connection error: {err}") from err

    async def async_start_stream(self, device_serial: str) -> str | None:
        """Start RTSP stream for a device."""
        url = f"{API_BASE_URL}/web/equipment/start_stream"
        payload = {
            "device_sn": device_serial,
            "station_sn": self.cameras[device_serial].station_serial,
            "proto": 2,  # RTSP protocol
        }

        try:
            async with self._session.post(
                url, json=payload, headers=self._request_headers
            ) as response:
                data = await response.json()

                if data.get("code") != 0:
                    _LOGGER.warning("Failed to start stream: %s", data.get("msg"))
                    return None

                return data.get("data", {}).get("url")
        except ClientError as err:
            _LOGGER.warning("Failed to start stream: %s", err)
            return None

    async def async_stop_stream(self, device_serial: str) -> None:
        """Stop RTSP stream for a device."""
        url = f"{API_BASE_URL}/web/equipment/stop_stream"
        payload = {
            "device_sn": device_serial,
            "station_sn": self.cameras[device_serial].station_serial,
        }

        try:
            async with self._session.post(
                url, json=payload, headers=self._request_headers
            ) as response:
                data = await response.json()

                if data.get("code") != 0:
                    _LOGGER.warning("Failed to stop stream: %s", data.get("msg"))
        except ClientError as err:
            _LOGGER.warning("Failed to stop stream: %s", err)

    @property
    def _request_headers(self) -> dict[str, str]:
        """Return headers for API requests."""
        headers = DEFAULT_HEADERS.copy()
        if self._token:
            headers["x-auth-token"] = self._token
        return headers


async def async_login(
    email: str, password: str, session: ClientSession
) -> EufySecurityAPI:
    """Login and return an authenticated API client."""
    api = EufySecurityAPI(session)
    await api.async_authenticate(email, password)
    await api.async_update_device_info()
    return api
