"""Config flow for Bosch Smart Home Camera."""

import logging
from typing import Any, override

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.helpers.config_entry_oauth2_flow import AbstractOAuth2FlowHandler

from .application_credentials import OAUTH2_CLIENT_ID, OAUTH2_CLIENT_SECRET

DOMAIN = "bosch_shc_camera"


class BoschCameraFlowHandler(AbstractOAuth2FlowHandler, domain=DOMAIN):
    """Config flow handling Bosch SingleKey ID OAuth2 authentication."""

    DOMAIN = DOMAIN

    @property
    @override
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow start."""
        await async_import_client_credential(
            self.hass,
            DOMAIN,
            ClientCredential(
                OAUTH2_CLIENT_ID, OAUTH2_CLIENT_SECRET, name="Bosch SingleKey ID"
            ),
        )
        return await super().async_step_user(user_input)
