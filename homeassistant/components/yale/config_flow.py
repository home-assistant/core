"""Config flow for Yale integration."""

from collections.abc import Mapping
import logging
from typing import Any

import jwt

from homeassistant.config_entries import ConfigEntry, ConfigFlowResult
from homeassistant.helpers import config_entry_oauth2_flow

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class YaleConfigFlow(config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN):
    """Handle a config flow for Yale."""

    VERSION = 1
    DOMAIN = DOMAIN
    reauth_entry: ConfigEntry | None = None

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return _LOGGER

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle configuration by re-auth."""
        self.reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_user()

    def _async_get_user_id_from_access_token(self, encoded: str) -> str:
        """Get user ID from access token."""
        decoded = jwt.decode(
            encoded,
            "",
            verify=False,
            options={"verify_signature": False},
            algorithms=["HS256"],
        )
        return decoded["userId"]

    async def async_oauth_create_entry(self, data: dict) -> ConfigFlowResult:
        """Create an entry for the flow."""
        user_id = self._async_get_user_id_from_access_token(
            data["token"]["access_token"]
        )
        if entry := self.reauth_entry:
            if entry.unique_id != user_id:
                return self.async_abort(reason="reauth_invalid_user")
            return self.async_update_reload_and_abort(entry, data=data)
        await self.async_set_unique_id(user_id)
        self._abort_if_unique_id_configured()
        return await super().async_oauth_create_entry(data)
