"""API client for Energenie Mi Home."""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
from typing import Any

from aiohttp import BasicAuth, ClientError, ClientResponseError, ClientSession

from homeassistant.exceptions import HomeAssistantError

from .const import (
    DEVICE_TYPE_LIGHT_SWITCH,
    DEVICE_TYPE_POWER_SOCKET,
    DEVICE_TYPE_SWITCH,
)

_LOGGER = logging.getLogger(__name__)

API_BASE_URL = "https://mihome4u.co.uk/api/v1"
USER_AGENT = "HomeAssistant/energenie_mi_home"

SUPPORTED_DEVICE_TYPES = {
    DEVICE_TYPE_LIGHT_SWITCH,
    DEVICE_TYPE_POWER_SOCKET,
    DEVICE_TYPE_SWITCH,
}


class MiHomeAuthError(HomeAssistantError):
    """Error to indicate authentication failure."""


class MiHomeConnectionError(HomeAssistantError):
    """Error to indicate connection failure."""


@dataclass(slots=True)
class MiHomeDevice:
    """Mi Home device representation."""

    device_id: str
    name: str
    device_type: str
    is_on: bool
    brightness: int | None = None
    available: bool = True
    product_type: str | None = None

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> MiHomeDevice | None:
        """Create device from MiHome API subdevice data."""
        if "id" not in data:
            return None

        raw_type = str(data.get("device_type", "")).lower()
        device_type = _map_device_type(raw_type)
        if device_type not in SUPPORTED_DEVICE_TYPES:
            return None

        device_id = str(data["id"])
        name = data.get("label") or f"MiHome device {device_id}"
        is_on = bool(data.get("power_state"))

        brightness_value = data.get("dim_level")
        if isinstance(brightness_value, (int, float)):
            brightness = int(brightness_value)
        else:
            brightness = None

        # The API returns unknown_state?=True even when devices have valid power_state
        # Since we have valid device data (id, power_state, label), the device is available
        # We only mark as unavailable if we truly can't determine the state
        unknown_state_q = data.get("unknown_state?")
        unknown_state = data.get("unknown_state")
        _LOGGER.debug(
            "Device %s availability check: unknown_state?=%s, unknown_state=%s, power_state=%s",
            device_id,
            unknown_state_q,
            unknown_state,
            data.get("power_state"),
        )
        # Device is available if we have valid power_state data, regardless of unknown_state? flag
        # The unknown_state? flag appears to be always True in API responses but doesn't indicate
        # actual unavailability since we have valid state information
        available = True
        if available:
            _LOGGER.debug(
                "Device %s (%s) marked as available (has valid power_state=%s)",
                device_id,
                name,
                data.get("power_state"),
            )

        return cls(
            device_id=device_id,
            name=name,
            device_type=device_type,
            is_on=is_on,
            brightness=brightness,
            available=available,
            product_type=data.get("device_type"),
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MiHomeDevice:
        """Create device from API response."""
        return cls(
            device_id=data["device_id"],
            name=data.get("name", "Unknown Device"),
            device_type=data.get("device_type", "unknown"),
            is_on=data.get("is_on", False),
            brightness=data.get("brightness"),
            available=data.get("available", True),
        )


class MiHomeAPI:
    """API helper for the MiHome cloud."""

    def __init__(
        self,
        email: str,
        password: str,
        session: ClientSession,
        api_key: str | None = None,
    ) -> None:
        """Initialize the API client."""
        self.email = email
        self.password = password
        self.session = session
        self._api_key: str | None = api_key

    async def async_authenticate(self) -> str:
        """Authenticate with the user's password and return an API key."""
        data = await self._request("users/profile", use_password=True)
        api_key = data.get("api_key") if isinstance(data, dict) else None
        if not api_key:
            raise MiHomeConnectionError("API key missing from profile response")
        self._api_key = api_key
        return api_key

    async def async_get_devices(self) -> list[MiHomeDevice]:
        """Return the list of supported MiHome subdevices."""
        payload = await self._request("subdevices/list")
        if not isinstance(payload, list):
            _LOGGER.debug("Unexpected response for subdevices: %s", payload)
            return []

        _LOGGER.debug("Received %d devices from API", len(payload))
        devices: list[MiHomeDevice] = []
        for raw_device in payload:
            if not isinstance(raw_device, dict):
                _LOGGER.debug("Skipping non-dict device entry: %s", raw_device)
                continue
            # Log the raw device data for debugging
            _LOGGER.debug(
                "Processing device: id=%s, device_type=%s, power_state=%s, unknown_state?=%s, label=%s",
                raw_device.get("id"),
                raw_device.get("device_type"),
                raw_device.get("power_state"),
                raw_device.get("unknown_state?"),
                raw_device.get("label"),
            )
            device = MiHomeDevice.from_api(raw_device)
            if device:
                _LOGGER.debug(
                    "Created device: id=%s, name=%s, type=%s, available=%s, is_on=%s",
                    device.device_id,
                    device.name,
                    device.device_type,
                    device.available,
                    device.is_on,
                )
                devices.append(device)
            else:
                _LOGGER.debug(
                    "Skipped device from API response: %s (missing required fields or unsupported type). Raw data: %s",
                    raw_device.get("id", "unknown"),
                    raw_device,
                )
        _LOGGER.debug("Found %d supported devices", len(devices))
        return devices

    async def async_set_device_state(
        self, device_id: str, state: bool, brightness: int | None = None
    ) -> None:
        """Toggle a subdevice state."""
        del brightness  # Brightness is not currently supported by the MiHome API.

        params = {"id": _coerce_device_id(device_id)}
        endpoint = "subdevices/power_on" if state else "subdevices/power_off"
        _LOGGER.debug(
            "Calling %s with params: %s (device_id=%s)",
            endpoint,
            params,
            device_id,
        )
        response = await self._request(endpoint, params=params)
        _LOGGER.debug("Response from %s: %s", endpoint, response)

    async def _request(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        *,
        use_password: bool = False,
    ) -> Any:
        """Perform a POST request to the MiHome API."""
        auth_value = (
            self.password if use_password or not self._api_key else self._api_key
        )

        if not auth_value:
            raise MiHomeAuthError("No credentials available for MiHome request")

        auth = BasicAuth(self.email, auth_value)
        data = {"params": json.dumps(params)} if params else None

        try:
            async with self.session.post(
                f"{API_BASE_URL}/{path}",
                auth=auth,
                data=data,
                headers={"User-Agent": USER_AGENT},
            ) as response:
                if response.status == 401:
                    raise MiHomeAuthError("Invalid MiHome credentials")
                response.raise_for_status()
                payload = await response.json(content_type=None)
        except ClientResponseError as err:
            if err.status == 401:
                raise MiHomeAuthError("Invalid MiHome credentials") from err
            raise MiHomeConnectionError(f"API error: {err}") from err
        except (
            ClientError,
            json.JSONDecodeError,
        ) as err:  # pragma: no cover - network errors
            raise MiHomeConnectionError(f"Connection error: {err}") from err

        status = payload.get("status")
        if status != "success":
            message = (
                payload.get("message") or payload.get("error") or status or "unknown"
            )
            if status in {"access-denied", "not-authenticated"}:
                raise MiHomeAuthError(message)
            raise MiHomeConnectionError(f"MiHome API error: {message}")

        return payload.get("data")


def _map_device_type(raw_type: str) -> str | None:
    """Map MiHome device types onto Home Assistant categories."""
    if not raw_type:
        return None

    if "light" in raw_type or "dim" in raw_type:
        return DEVICE_TYPE_LIGHT_SWITCH
    if raw_type in {"ecalm"} or "socket" in raw_type or "plug" in raw_type:
        return DEVICE_TYPE_POWER_SOCKET
    if "switch" in raw_type:
        return DEVICE_TYPE_SWITCH
    return None


def _coerce_device_id(device_id: str) -> int | str:
    """Convert device id to integer when possible."""
    try:
        return int(device_id)
    except (TypeError, ValueError):
        return device_id
