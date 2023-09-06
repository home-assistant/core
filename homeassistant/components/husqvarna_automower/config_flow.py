"""Config flow to add the integration via the UI."""
from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol

from homeassistant import data_entry_flow
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_entry_oauth2_flow

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class HusqvarnaConfigFlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler,
    data_entry_flow.FlowHandler,
    domain=DOMAIN,
):
    """Handle a config flow."""

    DOMAIN = DOMAIN
    VERSION = 1

    async def async_oauth_create_entry(self, data: dict) -> FlowResult:
        """Create an entry for the flow."""
        return await self.async_step_finish(DOMAIN, data)

    async def async_step_finish(self, unique_id, data) -> FlowResult:
        """Complete the config entries."""
        await self.async_set_unique_id(unique_id)

        return self.async_create_entry(
            title=unique_id,
            data=data,
        )

    async def async_step_reauth(self, user_input: Mapping[str, Any]) -> FlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None) -> FlowResult:
        """Dialog that informs the user that reauth is required."""
        if user_input is None:
            _LOGGER.debug("USER INPUT NONE")
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=vol.Schema({}),
            )
        return await self.async_step_user()

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)
