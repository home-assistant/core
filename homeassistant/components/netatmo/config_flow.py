"""Config flow for Netatmo."""
import logging

from homeassistant import config_entries
from homeassistant.helpers import config_entry_oauth2_flow

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class NetatmoFlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle Netatmo OAuth2 authentication."""

    DOMAIN = DOMAIN
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    @property
    def extra_authorize_data(self) -> dict:
        """Extra data that needs to be appended to the authorize url."""
        return {
            "scope": (
                " ".join(
                    [
                        "read_station",
                        "read_camera",
                        "access_camera",
                        "write_camera",
                        "read_presence",
                        "access_presence",
                        "read_homecoach",
                        "read_smokedetector",
                        "read_thermostat",
                        "write_thermostat",
                    ]
                )
            )
        }

    async def async_step_user(self, user_input=None):
        """Handle a flow start."""
        if self.hass.config_entries.async_entries(DOMAIN):
            return self.async_abort(reason="already_setup")

        return await super().async_step_user(user_input)

    async def async_step_homekit(self, homekit_info):
        """Handle HomeKit discovery."""
        return await self.async_step_user()
