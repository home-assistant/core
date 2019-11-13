"""Config flow for Islamic Prayer Times integration."""
import voluptuous as vol

from homeassistant import config_entries

from homeassistant.core import callback

from .const import CONF_CALC_METHOD, DEFAULT_CALC_METHOD, DOMAIN, CALC_METHODS, NAME


class IslamicPrayerFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the Islamic Prayer config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return IslamicPrayerOptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        if self._async_current_entries():
            return self.async_abort(reason="one_instance_allowed")

        if user_input is None:
            return self.async_show_form(step_id="user")

        return self.async_create_entry(title=NAME, data=user_input)

    async def async_step_import(self, import_config):
        """Import from Transmission client config."""
        return await self.async_step_user(user_input=import_config)


class IslamicPrayerOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Islamic Prayer client options."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage options."""
        errors = {}

        if user_input is not None:
            if user_input[CONF_CALC_METHOD] in CALC_METHODS:
                return self.async_create_entry(title="", data=user_input)
            else:
                errors[CONF_CALC_METHOD] = "wrong_method"

        options = {
            vol.Optional(
                CONF_CALC_METHOD,
                default=self.config_entry.options.get(
                    CONF_CALC_METHOD, DEFAULT_CALC_METHOD
                ),
            ): str
        }

        return self.async_show_form(
            step_id="init", data_schema=vol.Schema(options), errors=errors
        )
