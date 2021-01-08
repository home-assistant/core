"""Config flow for Neato Botvac."""
import logging
from typing import Optional

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_TOKEN
from homeassistant.helpers import config_entry_oauth2_flow

# pylint: disable=unused-import
from .const import NEATO_DOMAIN

_LOGGER = logging.getLogger(__name__)


class OAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=NEATO_DOMAIN
):
    """Config flow to handle Neato Botvac OAuth2 authentication."""

    DOMAIN = NEATO_DOMAIN
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    async def async_step_user(self, user_input: Optional[dict] = None) -> dict:
        """Create an entry for the flow."""
        current_entries = self._async_current_entries()
        if current_entries and CONF_TOKEN in current_entries[0].data:
            # Already configured
            return self.async_abort(reason="already_configured")

        return await super().async_step_user(user_input=user_input)

    async def async_step_reauth(self, data) -> dict:
        """Perform reauth upon migration of old entries."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: Optional[dict] = None
    ) -> dict:
        """Confirm reauth upon migration of old entries."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm", data_schema=vol.Schema({})
            )
        return await self.async_step_user()

    async def async_oauth_create_entry(self, data: dict) -> dict:
        """Create an entry for the flow. Update an entry if one already exist."""
        current_entries = self._async_current_entries()
        if current_entries and CONF_TOKEN not in current_entries[0].data:
            # Update entry
            self.hass.config_entries.async_update_entry(
                current_entries[0], title=self.flow_impl.name, data=data
            )
            self.hass.async_create_task(
                self.hass.config_entries.async_reload(current_entries[0].entry_id)
            )
            return self.async_abort(reason="reauth_successful")
        return self.async_create_entry(title=self.flow_impl.name, data=data)
