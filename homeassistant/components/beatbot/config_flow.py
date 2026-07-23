"""Config flow for the Beatbot integration using OAuth2 with PKCE."""

import base64
import binascii
from collections.abc import Mapping
import json
import logging
from typing import Any, override

from beatbot_cloud.const import (
    OAUTH2_AUTHORIZE_URL,
    OAUTH2_CLIENT_ID,
    OAUTH2_SCOPE,
    OAUTH2_TOKEN_URL,
    REGION_API_BASE_URL,
)
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow

from .iot.const import DOMAIN

_LOGGER = logging.getLogger(__name__)


def _decode_access_token(access_token: str) -> dict[str, Any] | None:
    """Decode a JWT access token without signature checks.

    Returns the claims dict, or None if the token is not a decodable JWT.
    Used to pull the `sub` (config entry unique id) and the custom `region`
    claim (selects the resource API base URL) from the token.
    """
    try:
        payload = access_token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload))
    except (
        binascii.Error,
        IndexError,
        json.JSONDecodeError,
        UnicodeDecodeError,
        ValueError,
    ):
        return None
    return claims if isinstance(claims, dict) else None


class BeatbotOAuth2Implementation(
    config_entry_oauth2_flow.LocalOAuth2ImplementationWithPkce
):
    """Local OAuth2 implementation for Beatbot using HA's built-in PKCE support."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the Beatbot OAuth2 implementation."""
        super().__init__(
            hass,
            DOMAIN,
            OAUTH2_CLIENT_ID,
            OAUTH2_AUTHORIZE_URL,
            OAUTH2_TOKEN_URL,
        )

    @property
    @override
    def name(self) -> str:
        """Return the OAuth2 implementation name."""
        return "Beatbot"

    @property
    @override
    def extra_authorize_data(self) -> dict:
        """Append the Beatbot scope on top of the PKCE challenge injected by the base class."""
        data: dict = {"scope": OAUTH2_SCOPE}
        data.update(super().extra_authorize_data)
        return data


class BeatbotConfigFlow(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Handle a config flow for Beatbot via OAuth2 + PKCE."""

    DOMAIN = DOMAIN
    VERSION = 1

    @property
    @override
    def logger(self) -> logging.Logger:
        """Return the flow logger."""
        return _LOGGER

    async def _async_register_implementation(self) -> None:
        """Register the local OAuth2 implementation for this domain if missing."""
        implementations = await config_entry_oauth2_flow.async_get_implementations(
            self.hass, DOMAIN
        )
        if DOMAIN not in implementations:
            config_entry_oauth2_flow.async_register_implementation(
                self.hass, DOMAIN, BeatbotOAuth2Implementation(self.hass)
            )

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Start the flow by registering the implementation and picking it."""
        await self._async_register_implementation()
        return await self.async_step_pick_implementation(user_input)

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> config_entries.ConfigFlowResult:
        """Perform reauth upon an authentication failure."""
        await self._async_register_implementation()
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=vol.Schema({}),
            )
        return await self.async_step_pick_implementation()

    @override
    async def async_oauth_create_entry(
        self, data: dict
    ) -> config_entries.ConfigFlowResult:
        """Create the config entry, using the JWT `sub` as unique id.

        Also extracts the custom `region` claim and stores it on the entry so
        the API client can pick the resource base URL per region. A missing or
        unrecognized region aborts the flow — there is no fallback region, so
        traffic is never silently routed to the wrong backend.
        """
        access_token = (data.get("token") or {}).get("access_token")
        if access_token and (claims := _decode_access_token(access_token)):
            if sub := claims.get("sub"):
                await self.async_set_unique_id(str(sub))
            if region := claims.get("region"):
                data["region"] = str(region)
        if self.source == SOURCE_REAUTH:
            # Verify the account matches before rejecting its region, so a
            # reauth with the wrong account still surfaces unique_id_mismatch.
            self._abort_if_unique_id_mismatch()
            if data.get("region") not in REGION_API_BASE_URL:
                return self.async_abort(reason="unknown_region")
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(),
                data_updates=data,
            )
        if data.get("region") not in REGION_API_BASE_URL:
            return self.async_abort(reason="unknown_region")
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title="Beatbot", data=data)
