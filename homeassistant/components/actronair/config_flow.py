"""Config flow for ActronAir using Device Code Flow with QR Code."""

import base64
import io
import logging
import time
from typing import Any

import aiohttp
import qrcode
import requests

from homeassistant import config_entries
from homeassistant.helpers import aiohttp_client, config_entry_oauth2_flow

from .const import CLIENT_ID, DOMAIN, OAUTH2_TOKEN, OAUTH2_USER_INFO
from .exception import FailedToRefreshToken

_LOGGER = logging.getLogger(__name__)


class ActronAirConfigFlowContext(config_entries.ConfigFlowContext):
    """ActronAir config flow context."""

    device_code: str
    poll_interval: int


class ActronAirOAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Handle a config flow for ActronAir using Device Code Flow with QR Code."""

    VERSION = 1
    domain = DOMAIN
    DOMAIN = DOMAIN

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    def __init__(self) -> None:
        """Initialize the flow."""
        super().__init__()
        self.context: ActronAirConfigFlowContext = {
            "device_code": "",
            "poll_interval": 5,
        }

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Initiate device authorization flow and show QR code."""

        if user_input is not None:
            data = await self.async_check_auth()
            if data:
                user_info = await self.async_get_user_info(data)
                if user_info["id"] is not None:
                    await self.async_set_unique_id(user_info["id"])
                    self._abort_if_unique_id_configured()
                else:
                    return self.async_abort(reason="Failed to fetch user info!")

                return self.async_create_entry(
                    title="ActronAir",
                    data={
                        "token": {
                            "access_token": data["access_token"],
                            "refresh_token": data["refresh_token"],
                            "expires_at": time.time() + data["expires_in"],
                        },
                        "auth_implementation": self.domain,
                    },
                )

        device_code_response = await self.hass.async_add_executor_job(
            self.request_device_code, CLIENT_ID
        )

        if not device_code_response:
            return self.async_abort(reason="device_code_request_failed")

        device_code = device_code_response["device_code"]
        verification_uri = device_code_response["verification_uri"]
        user_code = device_code_response["user_code"]
        verification_uri_complete = device_code_response["verification_uri_complete"]
        poll_interval = device_code_response["interval"]
        expires_in = device_code_response["expires_in"]

        _LOGGER.info(
            "Please authorize ActronAir by visiting %s and entering the code: %s",
            verification_uri,
            user_code,
        )

        # Generate QR code
        qr_img = qrcode.make(verification_uri_complete)
        buffered = io.BytesIO()
        qr_img.save(buffered, format="PNG")
        qr_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
        qr_code_data_url = f"data:image/png;base64,{qr_base64}"

        # Store context for polling task
        self.context["device_code"] = device_code
        self.context["poll_interval"] = poll_interval

        return self.async_show_form(
            step_id="user",
            description_placeholders={
                "code": user_code,
                "here": f"[here]({verification_uri_complete})",
                "qr_code_data_url": f"![Scan this QR Code]({qr_code_data_url})",
                "time": expires_in / 60,
            },
        )

    @staticmethod
    async def async_refresh_token(token: dict) -> dict:
        """Refresh an expired token."""
        session = aiohttp.ClientSession()

        try:
            async with session.post(
                OAUTH2_TOKEN,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": token["refresh_token"],
                    "client_id": CLIENT_ID,
                },
            ) as resp:
                if resp.status != 200:
                    raise FailedToRefreshToken(
                        f"Failed to refresh token: {await resp.text()}"
                    )

                new_token = await resp.json()
                return {
                    "access_token": new_token["access_token"],
                    "refresh_token": new_token.get(
                        "refresh_token", token["refresh_token"]
                    ),
                    "expires_at": time.time() + new_token["expires_in"],
                }
        finally:
            await session.close()

    def generate_qr_code(self, url: str) -> str:
        """Generate a base64-encoded QR code image from a URL."""
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill="black", back_color="white")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        return f"data:image/png;base64,{base64.b64encode(buffer.getvalue()).decode('utf-8')}"

    def request_device_code(self, client_id: str) -> dict[str, Any] | None:
        """Send a request to ActronAir to get the device code."""
        response = requests.post(
            OAUTH2_TOKEN, data={"client_id": client_id}, timeout=10
        )

        if response.status_code == 200:
            return response.json()

        _LOGGER.error("Failed to get device code: %s", response.text)
        return None

    async def async_check_auth(self) -> dict[str, Any] | None:
        """Check if the user has authorized the app."""
        session = aiohttp_client.async_get_clientsession(self.hass)
        try:
            async with session.post(
                OAUTH2_TOKEN,
                data={
                    "client_id": CLIENT_ID,
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                    "device_code": self.context["device_code"],
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            ) as resp:
                data = await resp.json()

                if resp.status == 200 and "access_token" in data:
                    _LOGGER.info("Authorization successful")
                    return data
                if resp.status == 400 and data.get("error") == "authorization_pending":
                    _LOGGER.info("Authorization pending:")
                    return None
                _LOGGER.error("Token exchange failed: %s", data)
                return None

        except aiohttp.ClientError as err:
            _LOGGER.error("Authorization check failed: %s", err)
            return None

    async def async_get_user_info(self, token: dict) -> dict[str, Any]:
        """Get user info from ActronAir."""
        session = aiohttp_client.async_get_clientsession(self.hass)
        try:
            async with session.get(
                OAUTH2_USER_INFO,
                headers={"Authorization": f"Bearer {token['access_token']}"},
            ) as resp:
                return await resp.json()
        except aiohttp.ClientError as err:
            _LOGGER.error("Failed to get user info: %s", err)
            return {}
