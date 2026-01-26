"""Config flow for Level Lock using OAuth2 Device Code Flow."""

from __future__ import annotations

import asyncio
import base64
from collections.abc import Mapping
import hashlib
from http import HTTPStatus
import logging
import re
import secrets
import time
from typing import Any

from aiohttp import ClientError, ClientResponseError
import voluptuous as vol

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlowResult
from homeassistant.helpers import aiohttp_client, config_entry_oauth2_flow

from .const import (
    CONF_CONTACT_INFO,
    CONF_PARTNER_BASE_URL,
    DEFAULT_PARTNER_BASE_URL,
    DEVICE_CODE_INITIATE_PATH,
    DEVICE_CODE_POLL_PATH,
    DOMAIN,
)


class OAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle Level Lock OAuth2 Device Code Flow authentication."""

    DOMAIN = DOMAIN

    def __init__(self) -> None:
        """Initialize flow state."""
        super().__init__()
        self._device_code: str | None = None
        self._user_code: str | None = None
        self._code_verifier: str | None = None
        self._partner_base_url: str = DEFAULT_PARTNER_BASE_URL
        self._poll_interval: int = 5
        self._contact_info: str | None = None
        self._delivery_method: str = "email"

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    @property
    def extra_authorize_data(self) -> dict[str, Any]:
        """Append Level Lock scopes."""
        return {"scope": "all"}

    def _build_partner_url(self, path: str) -> str:
        """Build a partner server URL by appending path to the base URL."""
        return f"{self._partner_base_url}{path}"

    def _detect_contact_type(self, contact: str) -> tuple[str, str]:
        """Detect if contact is email or phone and return (delivery_method, normalized_contact)."""
        contact = contact.strip()
        if "@" in contact and re.match(r"^[^@]+@[^@]+\.[^@]+$", contact):
            return "email", contact
        phone = re.sub(r"[^\d+]", "", contact)
        if phone and (phone.startswith("+") or len(phone) >= 10):
            return "sms", phone
        return "email", contact

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect user credentials."""
        implementations = await config_entry_oauth2_flow.async_get_implementations(
            self.hass, self.DOMAIN
        )
        if not implementations:
            if (
                self.DOMAIN
                in await config_entry_oauth2_flow.async_get_application_credentials(  # type: ignore[attr-defined]
                    self.hass
                )
            ):
                return self.async_abort(reason="missing_credentials")
            return self.async_abort(reason="missing_configuration")

        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_CONTACT_INFO): str,
                    }
                ),
            )

        self._partner_base_url = DEFAULT_PARTNER_BASE_URL.rstrip("/")

        contact_info = user_input[CONF_CONTACT_INFO]
        self._delivery_method, self._contact_info = self._detect_contact_type(
            contact_info
        )
        new_unique_id = self._contact_info.lower()

        if self.source == SOURCE_REAUTH:
            if self.unique_id != new_unique_id:
                return self.async_abort(reason="wrong_account")
        else:
            await self.async_set_unique_id(new_unique_id)
            self._abort_if_unique_id_configured()

        self.hass.data.setdefault(DOMAIN, {})[CONF_PARTNER_BASE_URL] = (
            self._partner_base_url
        )

        return await self.async_step_initiate()

    async def async_step_initiate(
        self, _: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Initiate device code flow and get user code."""
        implementations = await config_entry_oauth2_flow.async_get_implementations(
            self.hass, self.DOMAIN
        )
        if not implementations:
            if (
                self.DOMAIN
                in await config_entry_oauth2_flow.async_get_application_credentials(  # type: ignore[attr-defined]
                    self.hass
                )
            ):
                return self.async_abort(reason="missing_credentials")
            return self.async_abort(reason="missing_configuration")

        self.flow_impl = list(implementations.values())[0]

        session = aiohttp_client.async_get_clientsession(self.hass)
        initiate_url = self._build_partner_url(DEVICE_CODE_INITIATE_PATH)

        try:
            code_verifier, code_challenge = self._generate_pkce_pair()
            self._code_verifier = code_verifier

            payload = {
                "client_id": self.flow_impl.client_id,  # type: ignore[attr-defined]
                "code_challenge": code_challenge,
                "code_challenge_method": "S256",
                "scope": "all",
                "delivery_method": self._delivery_method,
            }
            if self._contact_info:
                if self._delivery_method == "email":
                    payload["email"] = self._contact_info
                else:
                    payload["phone_number"] = self._contact_info

            async with session.post(initiate_url, json=payload) as resp:
                if resp.status >= HTTPStatus.BAD_REQUEST:
                    self.logger.error("Device code initiation failed: %s", resp.status)
                    return self.async_abort(reason="oauth_failed")
                data = await resp.json()

            self.logger.warning("Device code initiation response: %s", data)
            self._device_code = data.get("device_code")
            self._user_code = data.get("user_code")
            self._poll_interval = data.get("interval", 5)

            if not self._device_code or not self._user_code:
                self.logger.error("Missing device_code or user_code in response")
                return self.async_abort(reason="oauth_error")

        except (ClientError, ClientResponseError) as err:
            self.logger.error("Error initiating device code: %s", err)
            return self.async_abort(reason="oauth_failed")

        return await self.async_step_verify()

    async def async_step_verify(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Display user code and wait for mobile app verification."""
        if user_input is None:
            if not self._user_code:
                self.logger.error("User code not available for display")
                return self.async_abort(reason="oauth_error")

            return self.async_show_form(
                step_id="verify",
                data_schema=vol.Schema({}),
                description_placeholders={"user_code": self._user_code},
            )

        return await self.async_step_poll()

    async def async_step_poll(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Poll for authorization completion."""
        assert self._device_code is not None
        assert self._code_verifier is not None

        session = aiohttp_client.async_get_clientsession(self.hass)
        poll_url = self._build_partner_url(DEVICE_CODE_POLL_PATH)

        max_attempts = 60
        for attempt in range(max_attempts):
            if attempt > 0:
                await asyncio.sleep(self._poll_interval)

            try:
                payload = {
                    "client_id": self.flow_impl.client_id,  # type: ignore[attr-defined]
                    "device_code": self._device_code,
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                    "code_verifier": self._code_verifier,
                }

                async with session.post(poll_url, json=payload) as resp:
                    data = await resp.json()

                if data.get("error"):
                    error = data["error"]
                    if error == "authorization_pending":
                        continue
                    if error in ("expired_token", "invalid_grant"):
                        self.logger.error("Device code expired or invalid: %s", error)
                        return self.async_abort(reason="oauth_timeout")
                    self.logger.error("Token poll error: %s", error)
                    return self.async_abort(reason="oauth_failed")

                if data.get("access_token"):
                    token = {
                        "access_token": data["access_token"],
                        "token_type": data.get("token_type", "Bearer"),
                        "expires_in": data.get("expires_in", 3600),
                        "refresh_token": data.get("refresh_token"),
                        "code_verifier": self._code_verifier,
                    }
                    token["expires_at"] = time.time() + 10

                    return await self.async_oauth_create_entry(
                        {"auth_implementation": self.flow_impl.domain, "token": token}
                    )

            except (ClientError, ClientResponseError) as err:
                self.logger.error("Error polling for token: %s", err)
                return self.async_abort(reason="oauth_failed")

        self.logger.error("Token polling timed out after %d attempts", max_attempts)
        return self.async_abort(reason="oauth_timeout")

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauth by restarting the device code flow."""
        reauth_entry = self._get_reauth_entry()
        if reauth_entry.unique_id:
            await self.async_set_unique_id(reauth_entry.unique_id)
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauth and continue."""
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm")
        return await self.async_step_user()

    async def async_oauth_create_entry(self, data: dict) -> ConfigFlowResult:
        """Create or update an entry and store partner base URL in options."""
        options = {
            CONF_PARTNER_BASE_URL: self._partner_base_url,
        }
        if self.source == SOURCE_REAUTH:
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(), data=data, options=options
            )
        return self.async_create_entry(
            title=self.flow_impl.name, data=data, options=options
        )

    def _generate_pkce_pair(self) -> tuple[str, str]:
        """Generate PKCE code_verifier and code_challenge pair."""
        code_verifier = (
            base64.urlsafe_b64encode(secrets.token_bytes(32))
            .decode("utf-8")
            .rstrip("=")
        )
        code_challenge_bytes = hashlib.sha256(code_verifier.encode("utf-8")).digest()
        code_challenge = (
            base64.urlsafe_b64encode(code_challenge_bytes).decode("utf-8").rstrip("=")
        )

        return code_verifier, code_challenge
