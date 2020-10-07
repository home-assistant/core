"""Config flow utilities."""
from collections import OrderedDict
import logging

from pyvesync import VeSync
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@callback
def configured_instances(hass):
    """Return already configured instances."""
    return hass.config_entries.async_entries(DOMAIN)


@config_entries.HANDLERS.register(DOMAIN)
class VeSyncFlowHandler(config_entries.ConfigFlow):
    """Handle a config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Instantiate config flow."""
        self._username = None
        self._password = None
        self.data_schema = OrderedDict()
        self.data_schema[vol.Required(CONF_USERNAME)] = str
        self.data_schema[vol.Required(CONF_PASSWORD)] = str

    @callback
    def _show_form(self, errors=None):
        """Show form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(self.data_schema),
            errors=errors if errors else {},
        )

    async def async_step_import(self, import_config):
        """Handle external yaml configuration."""
        return await self.async_step_user(import_config)

    async def async_step_user(self, user_input=None):
        """Handle a flow start."""
        if configured_instances(self.hass):
            return self.async_abort(reason="single_instance_allowed")

        if not user_input:
            return self._show_form()

        self._username = user_input[CONF_USERNAME]
        self._password = user_input[CONF_PASSWORD]

        manager = VeSync(self._username, self._password)
        login = await self.hass.async_add_executor_job(manager.login)
        if not login:
            return self._show_form(errors={"base": "invalid_auth"})

        return self.async_create_entry(
            title=self._username,
            data={CONF_USERNAME: self._username, CONF_PASSWORD: self._password},
        )
