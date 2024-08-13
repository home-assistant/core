"""Config flow for Yale integration."""

import logging

from homeassistant.helpers import config_entry_oauth2_flow

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class YaleConfigFlow(config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN):
    """Handle a config flow for Yale."""

    VERSION = 1
    DOMAIN = DOMAIN

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return _LOGGER
