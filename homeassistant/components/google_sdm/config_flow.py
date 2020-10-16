"""Config flow for google_sdm."""
import logging

from homeassistant import config_entries
from homeassistant.helpers import config_entry_oauth2_flow

from .const import DOMAIN, OAUTH2_ACCESS_TYPE, OAUTH2_PROMPT, OAUTH2_SCOPE

_LOGGER = logging.getLogger(__name__)


class OAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle google_sdm OAuth2 authentication."""

    DOMAIN = DOMAIN
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_PUSH

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    @property
    def extra_authorize_data(self) -> dict:
        """Extra data that needs to be appended to the authorize url."""
        return {
            "scope": OAUTH2_SCOPE,
            "access_type": OAUTH2_ACCESS_TYPE,
            "prompt": OAUTH2_PROMPT,
        }
