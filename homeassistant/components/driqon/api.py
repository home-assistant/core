"""Async Firebase and DRIQON cloud API client."""
from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Literal, NoReturn, NotRequired, TypedDict, cast
from urllib.parse import quote, urlencode

from aiohttp import ClientError, ClientResponse, ClientSession, ClientTimeout

from .const import DEFAULT_API_URL


class Device(TypedDict):
    """A validated device returned by the DRIQON cloud API."""

    device_id: str
    device_name: NotRequired[str | None]
    device_type: NotRequired[str | None]
    firmware_version: NotRequired[str | None]
    state: NotRequired[str | None]
    status: NotRequired[str | None]
    permission: NotRequired[str]
    is_shared: NotRequired[bool]
    capabilities: NotRequired[list[Capability]]


class Capability(TypedDict):
    """A capability descriptor supplied by DRIQON."""

    name: str
    platform: str


class FirebaseAuthResponse(TypedDict):
    """Firebase Identity Toolkit sign-in response fields used by DRIQON."""

    localId: str
    refreshToken: str
    idToken: str


class FirebaseRefreshResponse(TypedDict):
    """Firebase Secure Token refresh response fields used by DRIQON."""

    user_id: NotRequired[str]
    refresh_token: NotRequired[str]
    id_token: str


class DriqonApiError(Exception):
    """Base error for sanitized API failures."""


class DriqonAuthError(DriqonApiError):
    """Credentials or a refresh token were rejected."""


class DriqonInvalidApiKeyError(DriqonApiError):
    """Firebase rejected the configured web API key."""


class DriqonAuthorizationError(DriqonApiError):
    """The account is not authorized for the requested operation."""


class DriqonNotFoundError(DriqonApiError):
    """The requested DRIQON resource does not exist or is not visible."""


class DriqonRateLimitError(DriqonApiError):
    """The service rate-limited this request."""


class DriqonInvalidResponseError(DriqonApiError):
    """The service returned an invalid response."""


def _string_key_mapping(value: object) -> Mapping[str, object] | None:
    """Narrow untrusted JSON objects to string-keyed mappings."""
    if not isinstance(value, dict) or not all(
        isinstance(key, str) for key in value
    ):
        return None
    return cast(Mapping[str, object], value)


class DriqonApi:
    """Talk to Firebase auth and the authenticated DRIQON REST API."""

    def __init__(
        self,
        session: ClientSession,
        email: str,
        *,
        api_key: str,
        api_url: str = DEFAULT_API_URL,
        refresh_token: str | None = None,
    ) -> None:
        self.session = session
        self.email = email
        self.api_key = api_key
        self.api_url = api_url.rstrip("/")
        self.refresh_token = refresh_token
        self.id_token: str | None = None
        self.local_id: str | None = None

    async def sign_in(self, password: str) -> FirebaseAuthResponse:
        """Sign in with Firebase email/password; the password is never retained."""
        url = "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword"
        payload = await self._json(
            "POST",
            f"{url}?{urlencode({'key': self.api_key})}",
            json_body={
                "email": self.email,
                "password": password,
                "returnSecureToken": True,
            },
            firebase=True,
        )
        response = _string_key_mapping(payload)
        if response is None:
            raise DriqonInvalidResponseError("Firebase returned an invalid sign-in response")
        local_id = response.get("localId")
        refresh_token = response.get("refreshToken")
        id_token = response.get("idToken")
        if not (
            isinstance(local_id, str)
            and local_id
            and isinstance(refresh_token, str)
            and refresh_token
            and isinstance(id_token, str)
            and id_token
        ):
            raise DriqonInvalidResponseError("Firebase omitted required sign-in fields")
        result: FirebaseAuthResponse = {
            "localId": local_id,
            "refreshToken": refresh_token,
            "idToken": id_token,
        }
        self.local_id = local_id
        self.refresh_token = refresh_token
        self.id_token = id_token
        return result

    async def refresh(self) -> None:
        """Refresh the short-lived Firebase ID token."""
        if not self.refresh_token:
            raise DriqonAuthError("Firebase authentication must be renewed")
        url = "https://securetoken.googleapis.com/v1/token"
        try:
            payload = await self._json(
                "POST",
                f"{url}?{urlencode({'key': self.api_key})}",
                form_body={
                    "grant_type": "refresh_token",
                    "refresh_token": self.refresh_token,
                },
                firebase=True,
            )
        except DriqonAuthError as err:
            raise DriqonAuthError("Firebase refresh token was rejected") from err
        response = _string_key_mapping(payload)
        if response is None or not isinstance(response.get("id_token"), str):
            raise DriqonInvalidResponseError("Firebase returned an invalid token response")
        self.id_token = response["id_token"]
        refresh_token = response.get("refresh_token")
        if isinstance(refresh_token, str) and refresh_token:
            self.refresh_token = refresh_token
        user_id = response.get("user_id")
        if isinstance(user_id, str):
            self.local_id = user_id

    async def request(
        self,
        method: str,
        path: str,
        *,
        json_body: Mapping[str, str | bool] | None = None,
    ) -> object:
        """Make an authenticated API request, refreshing once after HTTP 401."""
        if not self.id_token:
            await self.refresh()
        headers: dict[str, str] = {}
        headers["Authorization"] = f"Bearer {self.id_token}"
        try:
            return await self._json(
                method,
                f"{self.api_url}{path}",
                headers=headers,
                json_body=json_body,
            )
        except DriqonAuthError:
            await self.refresh()
            headers["Authorization"] = f"Bearer {self.id_token}"
            return await self._json(
                method,
                f"{self.api_url}{path}",
                headers=headers,
                json_body=json_body,
            )

    async def devices(self) -> list[Device]:
        """Return valid devices; skip malformed records without losing the rest."""
        payload = await self.request("GET", "/devices")
        if not isinstance(payload, list):
            raise DriqonInvalidResponseError("DRIQON returned an invalid device list")
        devices: list[Device] = []
        for raw_item in payload:
            item = _string_key_mapping(raw_item)
            device_id = item.get("device_id") if item is not None else None
            if not isinstance(device_id, str):
                continue
            device: Device = {"device_id": device_id}
            for key in ("device_name", "device_type", "firmware_version", "state", "status"):
                if key not in item:
                    continue
                value = item.get(key)
                if not (value is None or isinstance(value, str)):
                    continue
                if key == "device_name":
                    device["device_name"] = value
                elif key == "device_type":
                    device["device_type"] = value
                elif key == "firmware_version":
                    device["firmware_version"] = value
                elif key == "state":
                    device["state"] = value
                else:
                    device["status"] = value
            permission = item.get("permission")
            if isinstance(permission, str):
                device["permission"] = permission
            is_shared = item.get("is_shared")
            if isinstance(is_shared, bool):
                device["is_shared"] = is_shared
            capabilities = item.get("capabilities")
            if isinstance(capabilities, list):
                valid_capabilities: list[Capability] = []
                for raw_capability in capabilities:
                    capability = _string_key_mapping(raw_capability)
                    if capability is None:
                        continue
                    name = capability.get("name")
                    platform = capability.get("platform")
                    if isinstance(name, str) and isinstance(platform, str):
                        valid_capabilities.append({"name": name, "platform": platform})
                device["capabilities"] = valid_capabilities
            devices.append(device)
        return devices

    async def command(self, device_id: str, command: Literal["on", "off"]) -> None:
        """Send a state command through DRIQON's permission-checked API."""
        await self.request(
            "POST",
            f"/devices/{quote(device_id, safe='')}/command",
            json_body={"command": command},
        )

    async def _json(
        self,
        method: str,
        url: str,
        *,
        firebase: bool = False,
        json_body: Mapping[str, str | bool] | None = None,
        form_body: Mapping[str, str] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> object:
        """Perform one async HTTP exchange with sanitized status handling."""
        try:
            async with self.session.request(
                method,
                url,
                timeout=ClientTimeout(total=15),
                headers=headers,
                json=json_body,
                data=form_body,
                allow_redirects=False,
            ) as response:
                if response.status >= 300:
                    await self._raise_for_status(response, firebase=firebase)
                try:
                    return await response.json(content_type=None)
                except (ValueError, UnicodeDecodeError) as err:
                    raise DriqonInvalidResponseError("Service returned invalid JSON") from err
        except (ClientError, asyncio.TimeoutError):
            # aiohttp exceptions can contain full request URLs, including the
            # Firebase Web API key. Do not retain them in Home Assistant logs.
            raise DriqonApiError("Could not reach the service") from None

    async def _raise_for_status(
        self, response: ClientResponse, *, firebase: bool
    ) -> NoReturn:
        """Map response codes without exposing server response bodies."""
        error_code = ""
        if firebase and response.status == 400:
            try:
                payload = _string_key_mapping(await response.json(content_type=None))
                error = _string_key_mapping(payload.get("error")) if payload else None
                message = error.get("message") if error else None
                if isinstance(message, str):
                    error_code = message
            except (ValueError, AttributeError):
                pass
            if "API_KEY" in error_code:
                raise DriqonInvalidApiKeyError("Firebase rejected the web API key")
            if "TOO_MANY_ATTEMPTS" in error_code:
                raise DriqonRateLimitError("Firebase temporarily rate-limited sign-in")
            raise DriqonAuthError("Firebase rejected the account credentials")
        if response.status == 401:
            raise DriqonAuthError("Firebase authentication must be renewed")
        if response.status == 403:
            raise DriqonAuthorizationError("DRIQON denied this operation")
        if response.status == 404:
            raise DriqonNotFoundError("DRIQON resource is unavailable")
        if response.status == 429:
            raise DriqonRateLimitError("DRIQON temporarily rate-limited this request")
        raise DriqonApiError(f"Service returned HTTP {response.status}")
