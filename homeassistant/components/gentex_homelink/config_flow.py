"""Config flow for homelink."""

from collections.abc import Mapping
import logging
from typing import Any, override

import jwt

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlowResult
from homeassistant.helpers.config_entry_oauth2_flow import AbstractOAuth2FlowHandler

from .const import DOMAIN
from .oauth2 import HomeLinkOAuth2Implementation

_LOGGER = logging.getLogger(__name__)


class OAuth2FlowHandler(AbstractOAuth2FlowHandler, domain=DOMAIN):
    """Config flow to handle homelink OAuth2 authentication."""

    DOMAIN = DOMAIN

    @property
    @override
    def logger(self):
        """Get the logger."""
        return _LOGGER

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Start browser-based OAuth2 authentication."""
        self.flow_impl = HomeLinkOAuth2Implementation(self.hass, DOMAIN)
        return await self.async_step_auth(user_input)

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm")
        return await self.async_step_user()

    @override
    async def async_oauth_create_entry(self, data: dict) -> ConfigFlowResult:
        """Create an oauth config entry or update existing entry for reauth."""
        try:
            sub = jwt.decode(
                data["token"]["access_token"], options={"verify_signature": False}
            )["sub"]
        except jwt.DecodeError, KeyError:
            return self.async_abort(reason="oauth_error")
        await self.async_set_unique_id(sub)
        entry_title = self.context.get("title_placeholders", {"name": "HomeLink"})[
            "name"
        ]
        if self.source == SOURCE_REAUTH:
            self._abort_if_unique_id_mismatch()
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(), data_updates=data, title=entry_title
            )
        self._abort_if_unique_id_configured()
        return self.async_create_entry(data=data, title=entry_title)
