"""Config flow for Ondilo ICO."""

import logging
from typing import Any

from homeassistant.config_entries import ConfigFlowResult
from homeassistant.helpers.config_entry_oauth2_flow import AbstractOAuth2FlowHandler

from .const import DOMAIN
from .oauth_impl import OndiloOauth2Implementation


class OndiloIcoOAuth2FlowHandler(AbstractOAuth2FlowHandler, domain=DOMAIN):
    """Config flow to handle Ondilo ICO OAuth2 authentication."""

    DOMAIN = DOMAIN

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        await self.async_set_unique_id(DOMAIN)

        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        self.async_register_implementation(
            self.hass,
            OndiloOauth2Implementation(self.hass),
        )

        return await super().async_step_user(user_input)

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    @property
    def extra_authorize_data(self) -> dict:
        """Extra data that needs to be appended to the authorize url."""
        return {"scope": "api"}
