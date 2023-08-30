"""Config flow to add the integration via the UI."""
from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol

from homeassistant import data_entry_flow
from homeassistant.const import CONF_TOKEN
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

    async def async_step_oauth2(self, user_input=None) -> FlowResult:
        """Handle the config-flow for Authorization Code Grant."""
        return await super().async_step_user(user_input)

    async def async_oauth_create_entry(self, data: dict) -> FlowResult:
        """Create an entry for the flow."""
        if "amc:api" not in data[CONF_TOKEN]["scope"]:
            _LOGGER.warning(
                "The scope of your API-key is `%s`, but should be `iam:read amc:api`",
                data[CONF_TOKEN]["scope"],
            )
        return await self.async_step_finish(DOMAIN, data)

    async def async_step_finish(self, unique_id, data) -> FlowResult:
        """Complete the config entries."""
        existing_entry = await self.async_set_unique_id(unique_id)

        if existing_entry:
            self.hass.config_entries.async_update_entry(existing_entry, data=data)
            await self.hass.config_entries.async_reload(existing_entry.entry_id)
            return self.async_abort(reason="reauth_successful")

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
        _LOGGER.debug("user_input: %s", user_input)
        return await self.async_step_user()

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)
