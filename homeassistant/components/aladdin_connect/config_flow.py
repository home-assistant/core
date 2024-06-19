"""Config flow for Aladdin Connect Genie."""

from collections.abc import Mapping
import logging
from typing import Any

import jwt

from homeassistant.config_entries import ConfigEntry, ConfigFlowResult
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_TOKEN
from homeassistant.helpers.config_entry_oauth2_flow import AbstractOAuth2FlowHandler

from .const import DOMAIN


class AladdinConnectOAuth2FlowHandler(AbstractOAuth2FlowHandler, domain=DOMAIN):
    """Config flow to handle Aladdin Connect Genie OAuth2 authentication."""

    DOMAIN = DOMAIN
    VERSION = 2
    MINOR_VERSION = 1

    reauth_entry: ConfigEntry | None = None

    async def async_step_reauth(
        self, user_input: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon API auth error or upgrade from v1 to v2."""
        self.reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: Mapping[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm")
        return await self.async_step_user()

    async def async_oauth_create_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Create an oauth config entry or update existing entry for reauth."""
        token_payload = jwt.decode(
            data[CONF_TOKEN][CONF_ACCESS_TOKEN], options={"verify_signature": False}
        )
        if not self.reauth_entry:
            await self.async_set_unique_id(token_payload["sub"])
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=token_payload["username"],
                data=data,
            )

        if self.reauth_entry.unique_id == token_payload["username"]:
            return self.async_update_reload_and_abort(
                self.reauth_entry,
                data=data,
                unique_id=token_payload["sub"],
            )
        if self.reauth_entry.unique_id == token_payload["sub"]:
            return self.async_update_reload_and_abort(self.reauth_entry, data=data)

        return self.async_abort(reason="wrong_account")

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)
