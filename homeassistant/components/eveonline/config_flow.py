"""Config flow for the Eve Online integration."""

from __future__ import annotations

import logging
from typing import Any

import jwt

from homeassistant.config_entries import ConfigFlowResult
from homeassistant.helpers.config_entry_oauth2_flow import AbstractOAuth2FlowHandler

from .const import CONF_CHARACTER_ID, CONF_CHARACTER_NAME, DOMAIN, SCOPES

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
        """Create an entry for the flow."""
        try:
            token = data["token"]["access_token"]
            character_info = _decode_eve_jwt(token)
        except ValueError, KeyError, jwt.DecodeError:
            return self.async_abort(reason="oauth_error")

        await self.async_set_unique_id(str(character_info[CONF_CHARACTER_ID]))
        self._abort_if_unique_id_configured()

        data[CONF_CHARACTER_ID] = character_info[CONF_CHARACTER_ID]
        data[CONF_CHARACTER_NAME] = character_info[CONF_CHARACTER_NAME]

        return self.async_create_entry(
            title=character_info[CONF_CHARACTER_NAME],
            data=data,
        )


def _decode_eve_jwt(token: str) -> dict[str, Any]:
    """Decode an Eve SSO JWT to extract character info."""
    decoded = jwt.decode(token, options={"verify_signature": False})
    sub = decoded.get("sub", "")
    sub_parts = sub.split(":")
    if len(sub_parts) != 3 or sub_parts[0] != "CHARACTER" or sub_parts[1] != "EVE":
        raise ValueError(sub)
    return {
        CONF_CHARACTER_ID: int(sub_parts[2]),
        CONF_CHARACTER_NAME: decoded.get("name", "Unknown"),
    }
