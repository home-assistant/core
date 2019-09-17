"""Config flow for Transmission Bittorent Client."""
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.core import callback

from . import get_api
from .const import DEFAULT_NAME, DEFAULT_PORT, DEFAULT_SCAN_INTERVAL, DOMAIN
from .errors import AuthenticationError, CannotConnect, UnknownError


class TransmissionFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a UniFi config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return TransmissionOptionsFlowHandler(config_entry)

    def __init__(self):
        """Initialize the Transmission flow."""
        self.config = {}
        self.errors = {}

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        if self.hass.config_entries.async_entries(DOMAIN):
            return self.async_abort(reason="one_instance_allowed")

        if user_input is not None:

            self.config[CONF_NAME] = user_input.pop(CONF_NAME)
            try:
                await get_api(self.hass, **user_input)
                self.config.update(user_input)
                if "options" not in self.config:
                    self.config["options"] = {CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL}
                return self.async_create_entry(
                    title=self.config[CONF_NAME], data=self.config
                )
            except AuthenticationError:
                self.errors[CONF_USERNAME] = "wrong_credentials"
                self.errors[CONF_PASSWORD] = "wrong_credentials"
            except (CannotConnect, UnknownError):
                self.errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
                    vol.Required(CONF_HOST): str,
                    vol.Optional(CONF_USERNAME): str,
                    vol.Optional(CONF_PASSWORD): str,
                    vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
                }
            ),
            errors=self.errors,
        )

    async def async_step_import(self, import_config):
        """Import from Transmission client config."""
        self.config["options"] = {
            CONF_SCAN_INTERVAL: import_config.pop(CONF_SCAN_INTERVAL).seconds
        }

        return await self.async_step_user(user_input=import_config)


class TransmissionOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Transmission client options."""

    def __init__(self, config_entry):
        """Initialize Transmission options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the Transmission options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = {
            vol.Optional(
                CONF_SCAN_INTERVAL,
                default=self.config_entry.options.get(
                    CONF_SCAN_INTERVAL,
                    self.config_entry.data["options"][CONF_SCAN_INTERVAL],
                ),
            ): int
        }

        return self.async_show_form(step_id="init", data_schema=vol.Schema(options))
