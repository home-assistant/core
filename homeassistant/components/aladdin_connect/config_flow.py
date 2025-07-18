"""Config flow for Aladdin Connect Genie."""

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlowResult
from homeassistant.helpers import config_entry_oauth2_flow

from .const import CONFIG_FLOW_MINOR_VERSION, CONFIG_FLOW_VERSION, DOMAIN


class OAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle Aladdin Connect Genie OAuth2 authentication."""

    DOMAIN = DOMAIN
    VERSION = CONFIG_FLOW_VERSION
    MINOR_VERSION = CONFIG_FLOW_MINOR_VERSION

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
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=vol.Schema({}),
            )
        return await self.async_step_user()

    async def async_oauth_create_entry(self, data: dict) -> ConfigFlowResult:
        """Create an oauth config entry or update existing entry for reauth."""
        if self.reauth_entry:
            return self.async_update_reload_and_abort(
                self.reauth_entry,
                data=data,
            )
        return await super().async_oauth_create_entry(data)

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)
