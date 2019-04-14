"""Config flow to configure component."""
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_USERNAME,\
    CONF_PASSWORD
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN


@config_entries.HANDLERS.register(DOMAIN)
class Nhc2FlowHandler(config_entries.ConfigFlow):
    """Config flow for NHC2 platform."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    def __init__(self):
        """Init NHC2FlowHandler."""
        self._errors = {}

    async def async_step_import(self, user_input):
        """Import a config entry."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        return self.async_create_entry(
            title="configuration.yaml", data=user_input
        )

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        self._errors = {}

        if user_input is not None:
            if user_input[CONF_USERNAME] not in\
                    self.hass.config_entries.async_entries(DOMAIN):
                return self.async_create_entry(
                    title=user_input[CONF_USERNAME],
                    data=user_input,
                )

            self._errors[CONF_USERNAME] = 'name_exists'

        # default location is set hass configuration
        return await self._show_config_form(
            host=None,
            port=8883,
            username=None,
            password=None)

    async def _show_config_form(self, host=None, port=None,
                                username=None,
                                password=None):
        """Show the configuration form to edit NHC2 data."""
        return self.async_show_form(
            step_id='user',
            data_schema=vol.Schema({
                vol.Required(CONF_HOST, default=host): str,
                vol.Required(CONF_PORT, default=port): cv.port,
                vol.Required(CONF_USERNAME, default=username): str,
                vol.Required(CONF_PASSWORD, default=password): str
            }),
            errors=self._errors,
        )
