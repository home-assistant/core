"""Config flow for Honeywell Lyric."""
import logging

from homeassistant import config_entries
from homeassistant.helpers import config_entry_oauth2_flow
from .const import DOMAIN, DATA_LYRIC_CONFIG


@config_entries.HANDLERS.register(DOMAIN)
class LyricFlowHandler(config_entry_oauth2_flow.AbstractOAuth2FlowHandler):
    """Handle a Lyric config flow."""

    DOMAIN = DOMAIN
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL
    VERSION = 1

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    async def async_step_user(self, code=None):
        """Handle a flow initiated by the user."""
        if self.hass.config_entries.async_entries(DOMAIN):
            return self.async_abort(reason="already_setup")

        return await super().async_step_user(self.hass.data.get(DATA_LYRIC_CONFIG))
