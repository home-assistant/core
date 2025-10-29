"""Config flow for Level Lock with OTP-enhanced OAuth2."""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import suppress
from http import HTTPStatus
import logging
import re
import time
from typing import Any

from aiohttp import ClientError, ClientResponseError
import voluptuous as vol
from yarl import URL

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlowResult
from homeassistant.helpers import aiohttp_client, config_entry_oauth2_flow

from .const import (
    CONF_OAUTH2_BASE_URL,
    CONF_PARTNER_BASE_URL,
    DEFAULT_OAUTH2_BASE_URL,
    DEFAULT_PARTNER_BASE_URL,
    DOMAIN,
    OAUTH2_GRANT_PERMISSIONS_ACCEPT_PATH,
    OAUTH2_OTP_CONFIRM_PATH,
    OAUTH2_TOKEN_EXCHANGE_PATH,
    PARTNER_OTP_START_PATH,
)

# Regex patterns for extracting request_uuid from HTML
REQUEST_UUID_PATTERN_DOUBLE_QUOTES = r'name="request_uuid"[^>]*value="([^"]+)"'
REQUEST_UUID_PATTERN_REVERSE_ORDER = r'value="([^"]+)"[^>]*name="request_uuid"'
REQUEST_UUID_PATTERN_SINGLE_QUOTES = r"name='request_uuid'[^>]*value='([^']+)'"


def validate_and_format_otp_code(code: str) -> str:
    """Validate and format OTP code to ABCD-1234 format.

    Args:
        code: Raw user input code

    Returns:
        Formatted code in ABCD-1234 format

    Raises:
        vol.Invalid: If code format is invalid
    """
    # Strip whitespace, remove all dashes, and convert to uppercase
    code_cleaned = code.strip().replace("-", "").upper()

    # Validate: must be exactly 8 characters (4 letters + 4 digits)
    if len(code_cleaned) != 8:
        raise vol.Invalid("invalid_code_format")

    # Validate first 4 characters are letters
    if not code_cleaned[:4].isalpha():
        raise vol.Invalid("invalid_code_format")

    # Validate last 4 characters are digits
    if not code_cleaned[4:].isdigit():
        raise vol.Invalid("invalid_code_format")

    # Return formatted code with dash
    return f"{code_cleaned[:4]}-{code_cleaned[4:]}"


class OAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle Level Lock OAuth2 authentication with OTP."""

    DOMAIN = DOMAIN

    def __init__(self) -> None:
        """Initialize flow state."""
        super().__init__()
        self._user_id: str | None = None
        self._request_uuid: str | None = None
        self._authorization_code: str | None = None
        self._oauth2_base_url: str = DEFAULT_OAUTH2_BASE_URL
        self._partner_base_url: str = DEFAULT_PARTNER_BASE_URL

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    @property
    def extra_authorize_data(self) -> dict[str, Any]:
        """Append Level Lock scopes."""
        return {"scope": "all"}

    def _build_oauth2_url(self, path: str) -> str:
        """Build an OAuth2 URL by appending path to the base URL."""
        return f"{self._oauth2_base_url}{path}"

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect user identifier and optional base URLs."""
        # Defaults from existing runtime config if present
        existing = self.hass.data.get(DOMAIN) or {}
        default_oauth2 = existing.get(CONF_OAUTH2_BASE_URL, DEFAULT_OAUTH2_BASE_URL)
        default_partner = existing.get(CONF_PARTNER_BASE_URL, DEFAULT_PARTNER_BASE_URL)

        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required("user_id"): str,
                        vol.Optional(CONF_OAUTH2_BASE_URL, default=default_oauth2): str,
                        vol.Optional(
                            CONF_PARTNER_BASE_URL, default=default_partner
                        ): str,
                    }
                ),
            )

        self._user_id = user_input["user_id"].strip()
        self._oauth2_base_url = user_input.get(
            CONF_OAUTH2_BASE_URL, default_oauth2
        ).rstrip("/")
        self._partner_base_url = user_input.get(
            CONF_PARTNER_BASE_URL, default_partner
        ).rstrip("/")

        # Store for downstream providers (authorization server)
        self.hass.data.setdefault(DOMAIN, {})[CONF_OAUTH2_BASE_URL] = (
            self._oauth2_base_url
        )
        self.hass.data[DOMAIN][CONF_PARTNER_BASE_URL] = self._partner_base_url

        return await self.async_step_start()

    async def async_step_start(
        self, _: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Start OAuth2 authorize to get request_uuid and trigger OTP start."""
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

        # Select first (or only) implementation; Level Lock only needs one
        self.flow_impl = list(implementations.values())[0]

        try:
            authorize_url = await self.async_generate_authorize_url()
        except Exception as err:  # noqa: BLE001
            self.logger.error("Error generating authorize URL: %s", err)
            return self.async_abort(reason="authorize_url_timeout")

        # Call authorize endpoint (server returns HTML with hidden request_uuid)
        session = aiohttp_client.async_get_clientsession(self.hass)
        try:
            async with session.get(
                authorize_url, headers={"accept": "text/html,application/xhtml+xml"}
            ) as resp:
                if resp.status >= HTTPStatus.BAD_REQUEST:
                    self.logger.error("Authorize request failed: %s", resp.status)
                    return self.async_abort(reason="oauth_failed")
                html = await resp.text()
        except (ClientError, ClientResponseError) as err:
            self.logger.error("Error requesting authorize URL: %s", err)
            return self.async_abort(reason="oauth_failed")

        # Extract request_uuid from hidden input
        match = re.search(REQUEST_UUID_PATTERN_DOUBLE_QUOTES, html, re.IGNORECASE)
        if not match:
            # Try alternative attribute order or single quotes
            match = re.search(
                REQUEST_UUID_PATTERN_REVERSE_ORDER, html, re.IGNORECASE
            ) or re.search(REQUEST_UUID_PATTERN_SINGLE_QUOTES, html, re.IGNORECASE)
        if not match:
            self.logger.error("Missing request_uuid in authorize response HTML")
            return self.async_abort(reason="oauth_error")

        self._request_uuid = match.group(1)

        # Trigger OTP delivery via partner server
        partner_otp_start = f"{self._partner_base_url}{PARTNER_OTP_START_PATH}"
        self.logger.warning("Partner OTP Start URL: %s", partner_otp_start)
        try:
            async with session.post(
                partner_otp_start,
                json={"request_uuid": self._request_uuid, "user_id": self._user_id},
            ) as resp:
                if resp.status >= HTTPStatus.BAD_REQUEST:
                    self.logger.error("OTP start failed: %s", resp.status)
                    return self.async_abort(reason="oauth_failed")
        except (ClientError, ClientResponseError) as err:
            self.logger.error("Error starting OTP: %s", err)
            return self.async_abort(reason="oauth_failed")

        return await self.async_step_otp()

    async def async_step_otp(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Prompt for OTP and complete authentication, permissions and token exchange."""
        errors: dict[str, str] = {}

        if user_input is None:
            return self.async_show_form(
                step_id="otp",
                data_schema=vol.Schema({vol.Required("code"): str}),
            )

        assert self._request_uuid is not None
        assert self._user_id is not None

        # Validate and format the OTP code
        try:
            code = validate_and_format_otp_code(user_input["code"])
        except vol.Invalid:
            errors["code"] = "invalid_code_format"
            return self.async_show_form(
                step_id="otp",
                data_schema=vol.Schema({vol.Required("code"): str}),
                errors=errors,
            )

        session = aiohttp_client.async_get_clientsession(self.hass)

        # Confirm OTP
        otp_confirm_url = self._build_oauth2_url(OAUTH2_OTP_CONFIRM_PATH)
        self.logger.warning("OTP Confirm URL: %s", otp_confirm_url)
        try:
            async with session.post(
                otp_confirm_url,
                json={
                    "request_uuid": self._request_uuid,
                    "user_id": self._user_id,
                    "code": code,
                },
            ) as resp:
                if resp.status >= HTTPStatus.BAD_REQUEST:
                    self.logger.error("OTP confirm failed: %s", resp.status)
                    errors["base"] = "invalid_auth"
        except (ClientError, ClientResponseError) as err:
            self.logger.error("Error confirming OTP: %s", err)
            errors["base"] = "invalid_auth"

        if errors:
            return self.async_show_form(
                step_id="otp",
                data_schema=vol.Schema({vol.Required("code"): str}),
                errors=errors,
            )

        # Accept grant permissions
        grant_url = self._build_oauth2_url(OAUTH2_GRANT_PERMISSIONS_ACCEPT_PATH)
        redirect_uri_from_grant: str | None = None
        self.logger.warning("Grant URL: %s", grant_url)
        try:
            async with session.post(
                grant_url, json={"request_uuid": self._request_uuid}
            ) as resp:
                if resp.status >= HTTPStatus.BAD_REQUEST:
                    self.logger.error("Grant permissions failed: %s", resp.status)
                    return self.async_abort(reason="oauth_failed")
                data: dict[str, Any] = await resp.json()
                redirect_uri_from_grant = data.get("redirect_uri")
        except (ClientError, ClientResponseError) as err:
            self.logger.error("Error granting permissions: %s", err)
            return self.async_abort(reason="oauth_failed")

        if not redirect_uri_from_grant:
            self.logger.error("Missing redirect_uri after granting permissions")
            return self.async_abort(reason="oauth_error")

        # Extract authorization code (and state for completeness)
        parsed_redirect = URL(redirect_uri_from_grant)
        authorization_code = parsed_redirect.query.get("code")
        if not authorization_code:
            self.logger.error(
                "Missing authorization code in redirect_uri: %s",
                redirect_uri_from_grant,
            )
            return self.async_abort(reason="oauth_error")

        # Exchange code for token (PKCE: include code_verifier; include client_secret if available)
        token_url = self._build_oauth2_url(OAUTH2_TOKEN_EXCHANGE_PATH)
        self.logger.warning("Token Exchange URL: %s", token_url)
        payload: dict[str, Any] = {
            "grant_type": "authorization_code",
            "code": authorization_code,
            "redirect_uri": self.flow_impl.redirect_uri,  # type: ignore[attr-defined]
            "client_id": self.flow_impl.client_id,  # type: ignore[attr-defined]
        }
        # Add PKCE token parameters if provided by the implementation
        with suppress(Exception):
            payload.update(self.flow_impl.extra_token_resolve_data)  # type: ignore[attr-defined]

        # Some authorization servers require a client_secret even with PKCE
        client_secret: str | None = getattr(self.flow_impl, "client_secret", None)
        if client_secret:
            payload["client_secret"] = client_secret

        try:
            async with session.post(token_url, data=payload) as resp:
                if resp.status >= HTTPStatus.BAD_REQUEST:
                    self.logger.error("Token exchange failed: %s", resp.status)
                    return self.async_abort(reason="oauth_failed")
                token: dict[str, Any] = await resp.json()
        except (ClientError, ClientResponseError) as err:
            self.logger.error("Error exchanging token: %s", err)
            return self.async_abort(reason="oauth_failed")

        if "expires_in" not in token:
            self.logger.warning("Invalid token response: %s", token)
            return self.async_abort(reason="oauth_error")

        try:
            token["expires_in"] = int(token["expires_in"])
        except (ValueError, TypeError) as err:
            self.logger.warning("Error converting expires_in to int: %s", err)
            return self.async_abort(reason="oauth_error")
        token["expires_at"] = time.time() + token["expires_in"]

        # Persist tokens + options
        return await self.async_oauth_create_entry(
            {"auth_implementation": self.flow_impl.domain, "token": token}
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauth by restarting the OTP flow."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauth and continue."""
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm")
        return await self.async_step_user()

    async def async_oauth_create_entry(self, data: dict) -> ConfigFlowResult:
        """Create or update an entry and store base URLs in options."""
        options = {
            CONF_OAUTH2_BASE_URL: self._oauth2_base_url,
            CONF_PARTNER_BASE_URL: self._partner_base_url,
        }
        if self.source == SOURCE_REAUTH:
            # Update existing entry on reauth
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(), data=data, options=options
            )
        return self.async_create_entry(
            title=self.flow_impl.name, data=data, options=options
        )
