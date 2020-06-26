"""Config flow for Smappee."""
import logging

from homeassistant import config_entries
from homeassistant.helpers import config_entry_oauth2_flow

from .const import DOMAIN  # pylint: disable=unused-import

_LOGGER = logging.getLogger(__name__)


class SmappeeFlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle Smappee OAuth2 authentication."""

    DOMAIN = DOMAIN
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)
