"""Config flow for Aladdin Connect Genie."""

from collections.abc import Mapping
import logging
from typing import Any

import jwt
import voluptuous as vol

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlowResult
from homeassistant.helpers import config_entry_oauth2_flow

from .const import CONFIG_FLOW_MINOR_VERSION, CONFIG_FLOW_VERSION, DOMAIN


class OAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle Aladdin Connect Genie OAuth2 authentication."""

    DOMAIN = DOMAIN
    VERSION = CONFIG_FLOW_VERSION
    MINOR_VERSION = CONFIG_FLOW_MINOR_VERSION

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Check we have the cloud integration set up."""
        if "cloud" not in self.hass.config.components:
            return self.async_abort(
                reason="cloud_not_enabled",
                description_placeholders={"default_config": "default_config"},
            )
        return await super().async_step_user(user_input)

    async def async_step_reauth(
        self, user_input: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon API auth error or upgrade from v1 to v2."""
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
        # Extract the user ID from the JWT token's 'sub' field
        token = jwt.decode(
            data["token"]["access_token"], options={"verify_signature": False}
        )
        user_id = token["sub"]
        await self.async_set_unique_id(user_id)

        if self.source == SOURCE_REAUTH:
            self._abort_if_unique_id_mismatch(reason="wrong_account")
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(), data=data
            )

        self._abort_if_unique_id_configured()
        return self.async_create_entry(title="Aladdin Connect", data=data)

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)
