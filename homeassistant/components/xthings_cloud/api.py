"""Xthings Cloud API client."""

from __future__ import annotations

from typing import Any

import aiohttp

from .const import (
    API_BRITE_BRIGHTNESS_URL,
    API_BRITE_COLOR_URL,
    API_BRITE_OFF_URL,
    API_BRITE_ON_URL,
    API_CAMERA_WEBRTC_URL,
    API_DEVICE_STATUS_URL,
    API_DEVICES_URL,
    API_FRP_HTTP_URL,
    API_LOGIN_URL,
    API_LOCK_LOCK_URL,
    API_LOCK_UNLOCK_URL,
    API_PLUG_OFF_URL,
    API_PLUG_ON_URL,
    API_REFRESH_TOKEN_URL,
    API_SWITCH_BRIGHTNESS_URL,
    API_SWITCH_OFF_URL,
    API_SWITCH_ON_URL,
    LOGGER,
)


class XthingsCloudApiError(Exception):
    """API call error."""

    def __init__(self, message: str, code: int = 0) -> None:
        super().__init__(message)
        self.code = code


class XthingsCloudAuthError(XthingsCloudApiError):
    """Authentication error."""


class XthingsCloudApiClient:
    """Xthings Cloud API client."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        token: str | None = None,
    ) -> None:
        self._session = session
        self._token = token

    @property
    def token(self) -> str | None:
        return self._token

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._token:
            headers["x-token"] = self._token
        return headers

    async def _async_request(
        self,
        method: str,
        url: str,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Send request and parse {"code": ..., "data": ...} response."""
        if headers is None:
            headers = self._headers()
        LOGGER.debug("API request: %s %s, body=%s", method, url, json)
        try:
            resp = await self._session.request(method, url, json=json, headers=headers)
            resp.raise_for_status()
            result = await resp.json()
        except aiohttp.ClientError as err:
            LOGGER.error("API request failed: %s %s, error=%s", method, url, err)
            raise XthingsCloudApiError(f"Request failed: {err}") from err

        code = result.get("code")
        LOGGER.debug("API response: %s %s, code=%s, data=%s", method, url, code, result.get("data"))

        if code == 200:
            return result.get("data", {})

        # Auth errors requiring re-login
        if code in (20001, 20011, 20012, 21022):
            LOGGER.warning("API auth error: %s %s, code=%s", method, url, code)
            raise XthingsCloudAuthError(f"Auth failed (code={code})", code=code)

        LOGGER.error("API error: %s %s, code=%s", method, url, code)
        raise XthingsCloudApiError(f"API error (code={code})", code=code)

    async def async_login(
        self, email: str, password: str,
        client_id: str | None = None,
        verification_code: str | None = None,
    ) -> dict[str, Any]:
        """Login and obtain token. Returns 2fa flag if verification required."""
        payload: dict[str, Any] = {"email": email, "password": password}
        if client_id:
            payload["client_id"] = client_id
        if verification_code:
            payload["code"] = verification_code
        data = await self._async_request(
            "POST", API_LOGIN_URL, json=payload,
            headers={"Content-Type": "application/json"},
        )
        # 2FA required: server sent verification code
        if data.get("2fa"):
            return {"2fa": data["2fa"]}
        self._token = data["token"]
        return {
            "token": data["token"],
            "refresh_token": data.get("refresh_token", ""),
            "client_id": data.get("client_id", ""),
        }

    async def async_refresh_token(self, refresh_token: str) -> dict[str, Any]:
        """Refresh token using refresh_token."""
        data = await self._async_request(
            "POST", API_REFRESH_TOKEN_URL,
            json={"refresh_token": refresh_token},
            headers={"Content-Type": "application/json"},
        )
        self._token = data["token"]
        return {
            "token": data["token"],
            "refresh_token": data.get("refresh_token", ""),
        }

    async def async_get_devices(self) -> list[dict[str, Any]]:
        """Get device list."""
        data = await self._async_request("POST", API_DEVICES_URL)
        return data.get("devices", [])

    async def async_get_device_status(self, device_id: str) -> dict[str, Any]:
        """Get single device status."""
        return await self._async_request(
            "POST", API_DEVICE_STATUS_URL, json={"id": device_id}
        )

    async def async_lock_lock(self, device_id: str) -> dict[str, Any]:
        """Lock the device."""
        return await self._async_request(
            "POST", API_LOCK_LOCK_URL, json={"uuid": device_id}
        )

    async def async_lock_unlock(self, device_id: str) -> dict[str, Any]:
        """Unlock the device."""
        return await self._async_request(
            "POST", API_LOCK_UNLOCK_URL, json={"uuid": device_id}
        )

    async def async_get_camera_webrtc(self, device_id: str) -> dict[str, Any]:
        """Get camera KVS WebRTC credentials."""
        return await self._async_request(
            "POST", API_CAMERA_WEBRTC_URL, json={"uuid": device_id}
        )

    async def async_brite_on(self, device_id: str) -> dict[str, Any]:
        """Turn on light."""
        return await self._async_request(
            "POST", API_BRITE_ON_URL, json={"uuid": device_id}
        )

    async def async_brite_off(self, device_id: str) -> dict[str, Any]:
        """Turn off light."""
        return await self._async_request(
            "POST", API_BRITE_OFF_URL, json={"uuid": device_id}
        )

    async def async_brite_brightness(
        self, device_id: str, brightness: int
    ) -> dict[str, Any]:
        """Set light brightness."""
        return await self._async_request(
            "POST", API_BRITE_BRIGHTNESS_URL,
            json={"uuid": device_id, "brightness": brightness},
        )

    async def async_brite_color(
        self, device_id: str, color: dict[str, Any]
    ) -> dict[str, Any]:
        """Set light color."""
        return await self._async_request(
            "POST", API_BRITE_COLOR_URL,
            json={"uuid": device_id, "color": color},
        )

    async def async_switch_on(self, device_id: str) -> dict[str, Any]:
        """Turn on switch."""
        return await self._async_request(
            "POST", API_SWITCH_ON_URL, json={"uuid": device_id}
        )

    async def async_switch_off(self, device_id: str) -> dict[str, Any]:
        """Turn off switch."""
        return await self._async_request(
            "POST", API_SWITCH_OFF_URL, json={"uuid": device_id}
        )

    async def async_switch_brightness(
        self, device_id: str, brightness: int
    ) -> dict[str, Any]:
        """Set switch brightness."""
        return await self._async_request(
            "POST", API_SWITCH_BRIGHTNESS_URL,
            json={"uuid": device_id, "brightness": brightness},
        )

    async def async_plug_on(self, device_id: str) -> dict[str, Any]:
        """Turn on plug."""
        return await self._async_request(
            "POST", API_PLUG_ON_URL, json={"uuid": device_id}
        )

    async def async_plug_off(self, device_id: str) -> dict[str, Any]:
        """Turn off plug."""
        return await self._async_request(
            "POST", API_PLUG_OFF_URL, json={"uuid": device_id}
        )

    async def async_get_frp_config(self, client_id: str) -> dict[str, Any]:
        """Get FRP remote access configuration."""
        return await self._async_request(
            "POST", API_FRP_HTTP_URL, json={"uuid": client_id}
        )
