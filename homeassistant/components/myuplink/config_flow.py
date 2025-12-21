"""Config flow for myUplink."""

from collections.abc import Mapping
import logging
from typing import Any

import jwt

from homeassistant.config_entries import (
    SOURCE_REAUTH,
    SOURCE_RECONFIGURE,
    ConfigFlowResult,
)
from homeassistant.helpers import config_entry_oauth2_flow

from .const import DOMAIN, OAUTH2_SCOPES


class OAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle myUplink OAuth2 authentication."""

    VERSION = 1
    MINOR_VERSION = 2
    DOMAIN = DOMAIN

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    @property
    def extra_authorize_data(self) -> dict[str, Any]:
        """Extra data that needs to be appended to the authorize url."""
        return {"scope": " ".join(OAUTH2_SCOPES)}

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: Mapping[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
            )

        return await self.async_step_user()

    async def async_step_reconfigure(
        self, user_input: Mapping[str, Any] | None = None
    ) -> ConfigFlowResult:
        """User initiated reconfiguration."""
        return await self.async_step_user()

    async def async_oauth_create_entry(self, data: dict) -> ConfigFlowResult:
        """Create or update the config entry."""

        token = jwt.decode(
            data["token"]["access_token"], options={"verify_signature": False}
        )
        uid = token["sub"]
        await self.async_set_unique_id(uid)

        if self.source == SOURCE_REAUTH:
            self._abort_if_unique_id_mismatch(reason="account_mismatch")
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(), data=data
            )
        if self.source == SOURCE_RECONFIGURE:
            self._abort_if_unique_id_mismatch(reason="account_mismatch")
            return self.async_update_reload_and_abort(
                self._get_reconfigure_entry(), data=data
            )
        self._abort_if_unique_id_configured()
        return await super().async_oauth_create_entry(data)
