"""Config flow for fitbit."""

import logging
from typing import Any

from fitbit.exceptions import HTTPException

from homeassistant.const import CONF_TOKEN
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_entry_oauth2_flow

from . import api
from .const import DOMAIN, OAUTH_SCOPES

_LOGGER = logging.getLogger(__name__)


class OAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle fitbit OAuth2 authentication."""

    DOMAIN = DOMAIN

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    @property
    def extra_authorize_data(self) -> dict[str, str]:
        """Extra data that needs to be appended to the authorize url."""
        return {
            "scope": " ".join(OAUTH_SCOPES),
            "prompt": "consent",
        }

    async def async_oauth_create_entry(self, data: dict[str, Any]) -> FlowResult:
        """Create an entry for the flow, or update existing entry."""

        client = api.ConfigFlowFitbitApi(self.hass, data[CONF_TOKEN])
        try:
            profile = await client.async_get_user_profile()
        except HTTPException as err:
            _LOGGER.error("Failed to fetch user profile for Fitbit API: %s", err)
            return self.async_abort(reason="cannot_connect")

        await self.async_set_unique_id(profile.encoded_id)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title=profile.full_name, data=data)

    async def async_step_import(self, data: dict[str, Any]) -> FlowResult:
        """Handle import from YAML."""
        return await self.async_oauth_create_entry(data)
