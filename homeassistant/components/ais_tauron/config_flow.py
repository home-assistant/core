"""Config flow to configure TAURON component."""

import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback

from . import TauronAmiplusSensor
from .const import CONF_METER_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)


@callback
def configured_tauron_connectoin(hass):
    """Return a set of the configured supla hosts."""
    return set(
        entry.data.get(CONF_NAME) for entry in hass.config_entries.async_entries(DOMAIN)
    )


@config_entries.HANDLERS.register(DOMAIN)
class AisTauronFlowHandler(config_entries.ConfigFlow):
    """AIS TAURON config flow."""

    VERSION = 1

    def __init__(self):
        """Initialize TAURON configuration flow."""
        pass

    async def async_step_import(self, import_config):
        """Import the supla server as config entry."""
        _LOGGER.warning("Go to async_step_user")
        return await self.async_step_init(user_input=import_config)

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        if user_input is not None:
            return await self.async_step_init(user_input=None)
        return self.async_show_form(step_id="confirm")

    async def async_step_confirm(self, user_input=None):
        """Handle a flow start."""
        errors = {}
        if user_input is not None:
            return await self.async_step_init(user_input=None)
        return self.async_show_form(step_id="confirm", errors=errors)

    async def async_step_init(self, user_input=None):
        """Handle a flow start."""
        errors = {}
        description_placeholders = {"error_info": ""}
        if user_input is not None:
            try:
                # Test the connection
                test = TauronAmiplusSensor(
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                    user_input[CONF_METER_ID],
                    "zone",
                )
                _LOGGER.info("AIS TAURON " + str(test.mode))
                if test.mode is not None:
                    """Finish config flow"""
                    return self.async_create_entry(title="eLicznik", data=user_input)
                errors = {CONF_METER_ID: "server_no_connection"}
                description_placeholders = {"error_info": str(test)}
            except Exception as e:
                errors = {CONF_METER_ID: "server_no_connection"}
                description_placeholders = {"error_info": str(e)}

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Required("energy_meter_id"): str,
                }
            ),
            errors=errors,
            description_placeholders=description_placeholders,
        )
