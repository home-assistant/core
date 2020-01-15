"""Config flow for NEW_NAME."""
import logging

from homeassistant import config_entries
from homeassistant.helpers import config_entry_oauth2_flow

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class OAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle NEW_NAME OAuth2 authentication."""

    DOMAIN = DOMAIN
    # TODO Pick one from config_entries.CONN_CLASS_*
    CONNECTION_CLASS = config_entries.CONN_CLASS_UNKNOWN

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)
