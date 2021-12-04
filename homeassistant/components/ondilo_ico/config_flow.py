"""Config flow for Ondilo ICO."""
import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import callback
from homeassistant.helpers import config_entry_oauth2_flow

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN
from .oauth_impl import OndiloOauth2Implementation


class OAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle Ondilo ICO OAuth2 authentication."""

    DOMAIN = DOMAIN

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return OndiloOptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        await self.async_set_unique_id(DOMAIN)

        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        self.async_register_implementation(
            self.hass,
            OndiloOauth2Implementation(self.hass),
        )

        return await super().async_step_user(user_input)

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    @property
    def extra_authorize_data(self) -> dict:
        """Extra data that needs to be appended to the authorize url."""
        return {"scope": "api"}


class OndiloOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Ondilo options."""

    def __init__(self, config_entry):
        """Initialize Ondilo options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=self.config_entry.options.get(
                            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                        ),
                    ): vol.All(vol.Coerce(int), vol.Range(min=2))
                }
            ),
        )
