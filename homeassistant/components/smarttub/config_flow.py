"""Config flow to configure the SmartTub integration."""
import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, CONF_SCAN_INTERVAL
from homeassistant.core import callback

from .api import validate_credentials
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN  # pylint: disable=unused-import

DATA_SCHEMA = vol.Schema(
    {vol.Required(CONF_EMAIL): str, vol.Required(CONF_PASSWORD): str}
)


_LOGGER = logging.getLogger(__name__)


class SmartTubConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """SmartTub configuration flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)

    async def async_step_import(self, import_info):
        """Set the config entry up from yaml."""
        return await self.async_step_user(import_info)

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_EMAIL])
            self._abort_if_unique_id_configured()

            errors = await self._validate_credentials(user_input)

            if not errors:
                return self.async_create_entry(
                    title=user_input[CONF_EMAIL], data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def _validate_credentials(self, data):
        errors = {}
        if not await validate_credentials(
            self.hass, data[CONF_EMAIL], data[CONF_PASSWORD]
        ):
            errors["base"] = "invalid_auth"
        return errors


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_SCAN_INTERVAL,
                        default=self.config_entry.options.get(
                            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL,
                        ),
                    ): int,
                }
            ),
        )
