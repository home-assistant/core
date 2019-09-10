"""Config flow to configure ecobee."""
import voluptuous as vol
from copy import copy

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY
from homeassistant.core import callback

from . import CONF_HOLD_TEMP, DOMAIN, ECOBEE_CONFIG_FILE


@config_entries.HANDLERS.register(DOMAIN)
class EcobeeFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle an ecobee config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return EcobeeOptionsFlowHandler(config_entry)

    def __init__(self):
        """Initialize the ecobee flow."""
        self._ecobee = None

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        return await self.async_step_init(user_input)

    async def async_step_init(self, user_input=None):
        """Handle a flow start."""
        errors = {}

        if self._async_current_entries():
            """Config entry currently exists, only one allowed."""
            return self.async_abort(reason="one_instance_only")

        if user_input is not None:
            """Use the user-supplied API key to attempt to obtain a PIN from ecobee."""
            from pyecobee import Ecobee

            config = {CONF_API_KEY: user_input[CONF_API_KEY]}

            self._ecobee = Ecobee(config=config)

            await self.hass.async_add_executor_job(self._ecobee.request_pin())

            if self._ecobee.pin is None:
                """Obtaining the PIN failed. Maybe the wrong API key?"""
                errors["base"] = "pin_request_failed"
            else:
                """Move to the next step of the flow."""
                return await self.async_step_authorize()

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): str}),
            errors=errors,
        )

    async def async_step_authorize(self, user_input=None):
        """Present the user with the PIN so that the app can be authorized on ecobee.com."""
        errors = {}

        if user_input is not None:
            """Attempt to obtain tokens from ecobee and finish the flow."""
            await self.hass.async_add_executor_job(self._ecobee.request_tokens())
            if len(self._ecobee.refresh_token) > 0:
                """Refresh token obtained; create the config entry."""
                return self.async_create_entry(title=DOMAIN, data=self._ecobee.config)
            else:
                errors["base"] = "token_request_failed"

        return self.async_show_form(
            step_id="authorize",
            errors=errors,
            description_placeholders={"pin": self._ecobee.pin},
        )

    async def async_step_import(self, import_data):
        """Import ecobee config from an existing ecobee.conf file.

        This flow is triggered by `async_setup` if no existing entry exists
        and if ecobee.conf exists, allowing pre-config-flow ecobee component
        users an easy migration path to using a config entry.

        We will attempt to validate the credentials found in ecobee.conf
        and create an entry if valid. Otherwise, we will abort and the user
        will need to redo the authorization process via the config flow.
        """
        config_file = self.hass.config.path(ECOBEE_CONFIG_FILE)

        from pyecobee import Ecobee

        self._ecobee = Ecobee(config_filename=config_file)

        if len(self._ecobee.refresh_token) > 0:
            """Refresh token loaded from existing config, attempt refresh to validate it."""
            await self.hass.async_add_executor_job(self._ecobee.refresh_tokens())
            if self._ecobee.pin is None:
                return self.async_create_entry(title=DOMAIN, data=self._ecobee.config)
            else:
                self.async_abort(reason="refresh_token_expired")
        else:
            self.async_abort(reason="credentials_not_found")


class EcobeeOptionsFlowHandler(config_entries.OptionsFlow):
    """Manage ecobee options."""

    def __init__(self, config_entry):
        """Initialize ecobee options flow."""
        self.config_entry = config_entry
        self.options = copy(config_entry.options)

    async def async_step_init(self, user_input=None):
        """Handle an options flow start."""
        return await self.async_step_ecobee_options()

    async def async_step_ecobee_options(self, user_input=None):
        """Manage the ecobee options."""
        if user_input is not None:
            self.options[CONF_HOLD_TEMP] = user_input[CONF_HOLD_TEMP]
            return self.async_create_entry(title="", data=self.options)

        return self.async_show_form(
            step_id="ecobee_options",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_HOLD_TEMP,
                        default=self.config_entry.options[CONF_HOLD_TEMP],
                    ): bool
                }
            ),
        )
