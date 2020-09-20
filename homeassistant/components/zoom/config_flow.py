"""Config flow for Zoom Automation."""
import logging
from typing import Any, Dict

from homeassistant import config_entries
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.helpers import config_entry_oauth2_flow

from .common import ZoomOAuth2Implementation
from .const import (
    CONF_VERIFICATION_TOKEN,
    DOMAIN,
    OAUTH2_AUTHORIZE,
    OAUTH2_TOKEN,
    ZOOM_SCHEMA,
)

_LOGGER = logging.getLogger(__name__)


class ZoomOAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle Zoom Automation OAuth2 authentication."""

    DOMAIN = DOMAIN
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return _LOGGER

    async def async_step_user(
        self, user_input: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Handle a flow start."""
        assert self.hass

        if (
            user_input is None
            and not await config_entry_oauth2_flow.async_get_implementations(
                self.hass, self.DOMAIN
            )
        ):
            return self.async_show_form(step_id="user", data_schema=ZOOM_SCHEMA)

        if user_input:
            self.async_register_implementation(
                self.hass,
                ZoomOAuth2Implementation(
                    self.hass,
                    DOMAIN,
                    user_input[CONF_CLIENT_ID],
                    user_input[CONF_CLIENT_SECRET],
                    OAUTH2_AUTHORIZE,
                    OAUTH2_TOKEN,
                    user_input.get(CONF_VERIFICATION_TOKEN),
                ),
            )

        return await super().async_step_user()

    async def async_oauth_create_entry(
        self, data: Dict[str, str] = None
    ) -> Dict[str, Any]:
        """Create an entry for the flow."""
        self.flow_impl: ZoomOAuth2Implementation
        data = {} if data is None else data
        data.update(
            {
                CONF_CLIENT_ID: self.flow_impl.client_id,
                CONF_CLIENT_SECRET: self.flow_impl.client_secret,
                CONF_VERIFICATION_TOKEN: self.flow_impl.verification_token,
            }
        )
        return self.async_create_entry(title=DOMAIN, data=data)
