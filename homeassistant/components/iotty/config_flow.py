"""Config flow for iotty."""

import logging
from typing import override

from homeassistant.helpers import config_entry_oauth2_flow

from .const import DOMAIN


class OAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle iotty OAuth2 authentication."""

    DOMAIN = DOMAIN

    @property
    @override
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)
