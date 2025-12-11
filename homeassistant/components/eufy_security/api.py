"""API client for Eufy Security."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from aiohttp import ClientSession

_LOGGER = logging.getLogger(__name__)

API_BASE_URL = "https://mysecurity.eufylife.com/api/v1"


class EufySecurityError(Exception):
    """Base exception for Eufy Security errors."""


class InvalidCredentialsError(EufySecurityError):
    """Exception for invalid credentials."""


class AuthenticationError(EufySecurityError):
    """Exception for authentication failures."""


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
        self.cameras: dict[str, Camera] = {}
        self.stations: dict[str, Station] = {}

    async def async_authenticate(self, email: str, password: str) -> None:
        """Authenticate with the Eufy Security API."""
        url = f"{API_BASE_URL}/passport/login"
        payload = {"email": email, "password": password}

        async with self._session.post(url, json=payload) as response:
            data = await response.json()

            if response.status != 200:
                raise AuthenticationError(f"Authentication failed: {response.status}")

            if data.get("code") != 0:
                error_msg = data.get("msg", "Unknown error")
                if "invalid" in error_msg.lower() or "incorrect" in error_msg.lower():
                    raise InvalidCredentialsError(error_msg)
                raise AuthenticationError(error_msg)

            auth_data = data.get("data", {})
            self._token = auth_data.get("auth_token")

            if not self._token:
                raise AuthenticationError("No auth token received")

    async def async_update_device_info(self) -> None:
        """Update device information from the API."""
        await self._async_get_stations()
        await self._async_get_devices()

    async def _async_get_stations(self) -> None:
        """Get list of stations/hubs."""
        url = f"{API_BASE_URL}/app/get_hub_list"

        async with self._session.post(
            url, json={}, headers=self._auth_headers
        ) as response:
            data = await response.json()

            if data.get("code") != 0:
                raise EufySecurityError(f"Failed to get stations: {data.get('msg')}")

            self.stations = {}
            for station_data in data.get("data", []):
                station = Station(
                    serial=station_data.get("station_sn", ""),
                    name=station_data.get("station_name", "Unknown"),
                    model=station_data.get("station_model", "Unknown"),
                )
                self.stations[station.serial] = station

    async def _async_get_devices(self) -> None:
        """Get list of devices/cameras."""
        url = f"{API_BASE_URL}/app/get_devs_list"

        async with self._session.post(
            url, json={}, headers=self._auth_headers
        ) as response:
            data = await response.json()

            if data.get("code") != 0:
                raise EufySecurityError(f"Failed to get devices: {data.get('msg')}")

            self.cameras = {}
            for device_data in data.get("data", []):
                # Filter for camera devices
                device_type = device_data.get("device_type", 0)
                # Camera device types are typically 1-31 based on eufy documentation
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

    async def async_start_stream(self, device_serial: str) -> str | None:
        """Start RTSP stream for a device."""
        url = f"{API_BASE_URL}/web/equipment/start_stream"
        payload = {
            "device_sn": device_serial,
            "station_sn": self.cameras[device_serial].station_serial,
            "proto": 2,  # RTSP protocol
        }

        async with self._session.post(
            url, json=payload, headers=self._auth_headers
        ) as response:
            data = await response.json()

            if data.get("code") != 0:
                _LOGGER.warning("Failed to start stream: %s", data.get("msg"))
                return None

            return data.get("data", {}).get("url")

    async def async_stop_stream(self, device_serial: str) -> None:
        """Stop RTSP stream for a device."""
        url = f"{API_BASE_URL}/web/equipment/stop_stream"
        payload = {
            "device_sn": device_serial,
            "station_sn": self.cameras[device_serial].station_serial,
        }

        async with self._session.post(
            url, json=payload, headers=self._auth_headers
        ) as response:
            data = await response.json()

            if data.get("code") != 0:
                _LOGGER.warning("Failed to stop stream: %s", data.get("msg"))

    @property
    def _auth_headers(self) -> dict[str, str]:
        """Return authentication headers."""
        return {"x-auth-token": self._token or ""}


async def async_login(
    email: str, password: str, session: ClientSession
) -> EufySecurityAPI:
    """Login and return an authenticated API client."""
    api = EufySecurityAPI(session)
    await api.async_authenticate(email, password)
    await api.async_update_device_info()
    return api
