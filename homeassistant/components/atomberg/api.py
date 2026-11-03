"""Client for the Atomberg Home public cloud API."""

import asyncio
from dataclasses import dataclass
import json
import time
from typing import Any, Self

from aiohttp import ClientError, ClientSession, ClientTimeout

API_URL = "https://api.developer.atomberg-iot.com"
REQUEST_TIMEOUT = ClientTimeout(total=30)
ACCESS_TOKEN_LIFETIME = 23 * 60 * 60

DEVICE_TYPE_FAN = "fan"
DEVICE_TYPE_WATER_PURIFIER = "water_purifier"
DEVICE_TYPE_LOCK = "lock"

COMMAND_POWER = "power"
COMMAND_SPEED = "speed"
COMMAND_SLEEP = "sleep"
COMMAND_TIMER = "timer"
COMMAND_LED = "led"
COMMAND_BRIGHTNESS = "brightness"
COMMAND_LIGHT_MODE = "light_mode"

COMMAND_MODE = "mode"
COMMAND_FALLBACK_MODE = "fallback_mode"
COMMAND_TDS_THRESHOLD = "tds_threshold"
COMMAND_IDLE_SLEEP = "idle_sleep"
COMMAND_SLEEP_WINDOW = "sleep_mode"
COMMAND_START_UTC = "start_utc"
COMMAND_STOP_UTC = "stop_utc"

DEFAULT_FAN_COMMANDS = frozenset({COMMAND_POWER, COMMAND_SPEED})


class AtombergError(Exception):
    """Base error for the Atomberg API."""


class AtombergConnectionError(AtombergError):
    """Error talking to the Atomberg API."""


class AtombergAuthError(AtombergError):
    """The API key or refresh token was rejected."""


@dataclass(frozen=True, slots=True)
class AtombergDevice:
    """A device registered to the Atomberg account."""

    device_id: str
    name: str
    model: str | None
    series: str | None
    color: str | None
    device_type: str
    supported_commands: frozenset[str]

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> Self:
        """Build a device from an entry of ``get_list_of_devices``."""
        commands = frozenset(
            command["command"] for command in data.get("supported_commands") or []
        )
        device_type = data.get("device_type", DEVICE_TYPE_FAN)
        return cls(
            device_id=data["device_id"],
            name=data["name"],
            model=data.get("model"),
            series=data.get("series"),
            color=data.get("color"),
            device_type=device_type,
            supported_commands=commands
            or (
                DEFAULT_FAN_COMMANDS if device_type == DEVICE_TYPE_FAN else frozenset()
            ),
        )


def parse_state(device: AtombergDevice, data: dict[str, Any]) -> dict[str, Any]:
    """Map an entry of ``get_device_state`` to the keys used by the integration."""
    if device.device_type in (DEVICE_TYPE_WATER_PURIFIER, DEVICE_TYPE_LOCK):
        return {**data, "is_online": data.get("is_online", True)}
    return {
        "is_online": data.get("is_online", True),
        COMMAND_POWER: data.get("power", False),
        COMMAND_SPEED: data.get("last_recorded_speed"),
        COMMAND_SLEEP: data.get("sleep_mode", False),
        COMMAND_LED: data.get("led", False),
        COMMAND_BRIGHTNESS: data.get("last_recorded_brightness"),
        COMMAND_LIGHT_MODE: data.get("last_recorded_color"),
        "timer_hours": data.get("timer_hours"),
    }


class AtombergClient:
    """Async client for the Atomberg Home public API."""

    def __init__(
        self, session: ClientSession, api_key: str, refresh_token: str
    ) -> None:
        """Initialize the client."""
        self._session = session
        self._api_key = api_key
        self._refresh_token = refresh_token
        self._access_token: str | None = None
        self._access_token_expires = 0.0
        self._token_lock = asyncio.Lock()

    async def async_get_devices(self) -> list[AtombergDevice]:
        """Return all devices on the account."""
        message = await self._async_authorized_request("GET", "/v1/get_list_of_devices")
        try:
            return [
                AtombergDevice.from_api(device) for device in message["devices_list"]
            ]
        except (KeyError, TypeError) as err:
            raise AtombergError("Unexpected device list response") from err

    async def async_get_states(self) -> dict[str, dict[str, Any]]:
        """Return the raw state of every device, keyed by device ID, in one call."""
        message = await self._async_authorized_request(
            "GET", "/v1/get_device_state", params={"device_id": "all"}
        )
        try:
            return {state["device_id"]: state for state in message["device_state"]}
        except (KeyError, TypeError) as err:
            raise AtombergError("Unexpected device state response") from err

    async def async_send_command(self, device_id: str, command: dict[str, Any]) -> None:
        """Send a command to a device."""
        await self._async_authorized_request(
            "POST",
            "/v1/send_command",
            json_body={"device_id": device_id, "command": command},
        )

    async def async_get_guest_pin(
        self, device_id: str, start_time: int | None = None, end_time: int | None = None
    ) -> dict[str, Any]:
        """Generate a temporary guest PIN for a lock."""
        body: dict[str, Any] = {"device_id": device_id}
        if start_time is not None and end_time is not None:
            body["start_time"] = start_time
            body["end_time"] = end_time
        message = await self._async_authorized_request(
            "POST", "/v1/get_lock_dynamic_pin", json_body=body
        )
        try:
            return message["data"]
        except (KeyError, TypeError) as err:
            raise AtombergError("Unexpected guest PIN response") from err

    async def _async_get_access_token(self) -> str:
        async with self._token_lock:
            if self._access_token and time.monotonic() < self._access_token_expires:
                return self._access_token
            message = await self._async_request(
                "GET",
                "/v1/get_access_token",
                bearer=self._refresh_token,
                auth_error_statuses=(401, 403),
            )
            try:
                self._access_token = message["access_token"]
            except (KeyError, TypeError) as err:
                raise AtombergError("Unexpected access token response") from err
            self._access_token_expires = time.monotonic() + ACCESS_TOKEN_LIFETIME
            return self._access_token

    async def _async_authorized_request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> Any:
        token = await self._async_get_access_token()
        try:
            return await self._async_request(
                method, path, bearer=token, params=params, json_body=json_body
            )
        except AtombergAuthError:
            self._access_token = None
        token = await self._async_get_access_token()
        return await self._async_request(
            method, path, bearer=token, params=params, json_body=json_body
        )

    async def _async_request(
        self,
        method: str,
        path: str,
        *,
        bearer: str,
        params: dict[str, str] | None = None,
        json_body: dict[str, Any] | None = None,
        auth_error_statuses: tuple[int, ...] = (401,),
    ) -> Any:
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {bearer}",
            "x-api-key": self._api_key,
        }
        try:
            async with self._session.request(
                method,
                f"{API_URL}{path}",
                headers=headers,
                params=params,
                json=json_body,
                timeout=REQUEST_TIMEOUT,
            ) as response:
                status = response.status
                body = await response.text()
        except (ClientError, TimeoutError) as err:
            raise AtombergConnectionError(str(err)) from err

        if status in auth_error_statuses:
            raise AtombergAuthError(f"HTTP {status}")
        if status >= 400:
            raise AtombergConnectionError(f"HTTP {status}: {body[:200]}")

        try:
            data = json.loads(body)
        except ValueError as err:
            raise AtombergError("Response was not valid JSON") from err
        if not isinstance(data, dict) or data.get("status") != "Success":
            raise AtombergError(f"API reported failure: {body[:200]}")
        return data.get("message")
