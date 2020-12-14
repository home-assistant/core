"""Config flow for Neato Botvac."""
import logging

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import config_entry_oauth2_flow

# pylint: disable=unused-import
from .const import NEATO_DOMAIN

DOCS_URL = "https://www.home-assistant.io/integrations/neato"

_LOGGER = logging.getLogger(__name__)


class OAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=NEATO_DOMAIN
):
    """Config flow to handle Neato Botvac OAuth2 authentication."""

    VERSION = 2
    DOMAIN = NEATO_DOMAIN
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    async def async_step_user(self, user_input=None) -> dict:
        """Create an entry for the flow."""
        current_entries = self._async_current_entries()
        if current_entries and current_entries[0].version == self.VERSION:
            return self.async_abort(reason="already_configured")

        return await super().async_step_user(user_input=user_input)

    async def async_step_reauth(self, config_entry: ConfigEntry) -> dict:
        """Perform reauth upon migration of old entries."""
        # self.hass.config_entries.async_remove(config_entry.unique_id)
        return self.async_show_form(step_id="user")

    async def async_oauth_create_entry(self, data: dict) -> dict:
        """Create an entry for the flow. Update an entry if one already exist."""
        current_entries = self._async_current_entries()
        if current_entries and current_entries[0].version == 1:
            self.hass.config_entries.async_update_entry(
                current_entries[0], title=self.flow_impl.name, data=data
            )
            # TODO: how to update the entry version?
            return self.async_abort(reason="entry_updated")
        return self.async_create_entry(title=self.flow_impl.name, data=data)
