"""Config flow for the Eve Online integration."""

from __future__ import annotations

import base64
import binascii
from collections.abc import Mapping
import json
import logging
from typing import Any

from homeassistant.config_entries import (
    SOURCE_REAUTH,
    SOURCE_RECONFIGURE,
    ConfigFlowResult,
)
from homeassistant.helpers.config_entry_oauth2_flow import AbstractOAuth2FlowHandler

from .const import DOMAIN, SCOPES

_LOGGER = logging.getLogger(__name__)


class OAuth2FlowHandler(AbstractOAuth2FlowHandler, domain=DOMAIN):
    """Handle OAuth2 config flow for Eve Online.

    Each config entry represents one authenticated character.
    Multiple characters can be added as separate entries.
    """

    DOMAIN = DOMAIN

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return _LOGGER

    @property
    def extra_authorize_data(self) -> dict[str, Any]:
        """Extra data to include in the authorize URL."""
        return {"scope": " ".join(SCOPES)}

    async def async_oauth_create_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Create an entry for the flow.

        Decode the Eve SSO JWT access token to extract character_id and
        character_name, then create a config entry for that character.
        """
        token = data["token"]["access_token"]
        try:
            character_info = _decode_eve_jwt(token)
        except ValueError, KeyError, binascii.Error:
            return self.async_abort(reason="oauth_error")

        character_id = character_info["character_id"]
        character_name = character_info["character_name"]

        await self.async_set_unique_id(str(character_id))

        if self.source == SOURCE_REAUTH:
            self._abort_if_unique_id_mismatch(reason="reauth_account_mismatch")
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(),
                title=character_name,
                data={
                    **data,
                    "character_id": character_id,
                    "character_name": character_name,
                },
            )

        if self.source == SOURCE_RECONFIGURE:
            self._abort_if_unique_id_mismatch(reason="reconfigure_account_mismatch")
            return self.async_update_reload_and_abort(
                self._get_reconfigure_entry(),
                title=character_name,
                data={
                    **data,
                    "character_id": character_id,
                    "character_name": character_name,
                },
            )

        self._abort_if_unique_id_configured()

        data["character_id"] = character_id
        data["character_name"] = character_name

        return self.async_create_entry(
            title=character_name,
            data=data,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauth dialog."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                description_placeholders={
                    "account": self._get_reauth_entry().title,
                },
            )
        return await self.async_step_user()

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration."""
        return await self.async_step_user()


def _decode_eve_jwt(token: str) -> dict[str, Any]:
    """Decode an Eve SSO JWT token to extract character info.

    Eve SSO access tokens are JWTs with:
    - sub: "CHARACTER:EVE:<character_id>"
    - name: character name

    We only decode the payload (no signature verification needed since
    the token was just received from the SSO endpoint via HTTPS).
    """
    parts = token.split(".")
    if len(parts) != 3:
        msg = "Invalid JWT token format"
        raise ValueError(msg)

    payload = parts[1]
    padding = 4 - len(payload) % 4
    if padding != 4:
        payload += "=" * padding

    decoded = json.loads(base64.urlsafe_b64decode(payload))

    sub = decoded.get("sub", "")
    sub_parts = sub.split(":")
    if len(sub_parts) != 3 or sub_parts[0] != "CHARACTER":
        msg = f"Unexpected JWT subject format: {sub}"
        raise ValueError(msg)

    return {
        "character_id": int(sub_parts[2]),
        "character_name": decoded.get("name", "Unknown"),
    }
