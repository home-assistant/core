"""Config flow for Gardena integration."""
from collections import OrderedDict
import logging

from gardena.smart_system import SmartSystem

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.const import (
    CONF_CLIENT_ID,
    CONF_EMAIL,
    CONF_ID,
    CONF_PASSWORD,
)
import homeassistant.helpers.config_validation as cv

from .const import (
    DOMAIN,
    CONF_MOWER_DURATION,
    CONF_SMART_IRRIGATION_DURATION,
    CONF_SMART_WATERING_DURATION,
    DEFAULT_MOWER_DURATION,
    DEFAULT_SMART_IRRIGATION_DURATION,
    DEFAULT_SMART_WATERING_DURATION,
)


_LOGGER = logging.getLogger(__name__)


DEFAULT_OPTIONS = {
    CONF_MOWER_DURATION: DEFAULT_MOWER_DURATION,
    CONF_SMART_IRRIGATION_DURATION: DEFAULT_SMART_IRRIGATION_DURATION,
    CONF_SMART_WATERING_DURATION: DEFAULT_SMART_WATERING_DURATION,
}


class GardenaSmartSystemConfigFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Gardena."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_PUSH

    async def _show_setup_form(self, errors=None):
        """Show the setup form to the user."""
        errors = {}

        fields = OrderedDict()
        fields[vol.Required(CONF_EMAIL)] = str
        fields[vol.Required(CONF_PASSWORD)] = str
        fields[vol.Required(CONF_CLIENT_ID)] = str

        return self.async_show_form(
            step_id="user", data_schema=vol.Schema(fields), errors=errors
        )

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if user_input is None:
            return await self._show_setup_form()

        errors = {}
        try:
            await self.hass.async_add_executor_job(
                try_connection,
                user_input[CONF_EMAIL],
                user_input[CONF_PASSWORD],
                user_input[CONF_CLIENT_ID])
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
            return await self._show_setup_form(errors)

        unique_id = user_input[CONF_CLIENT_ID]

        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title="",
            data={
                CONF_ID: unique_id,
                CONF_EMAIL: user_input[CONF_EMAIL],
                CONF_PASSWORD: user_input[CONF_PASSWORD],
                CONF_CLIENT_ID: user_input[CONF_CLIENT_ID],
            })

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return GardenaSmartSystemOptionsFlowHandler(config_entry)


class GardenaSmartSystemOptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        """Initialize Gardena Smart Sytem options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        return await self.async_step_user()

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}
        if user_input is not None:
            # TODO: Validate options (min, max values)
            return self.async_create_entry(title="", data=user_input)

        fields = OrderedDict()
        fields[vol.Optional(
            CONF_MOWER_DURATION,
            default=self.config_entry.options.get(
                CONF_MOWER_DURATION, DEFAULT_MOWER_DURATION))] = cv.positive_int
        fields[vol.Optional(
            CONF_SMART_IRRIGATION_DURATION,
            default=self.config_entry.options.get(
                CONF_SMART_IRRIGATION_DURATION, DEFAULT_SMART_IRRIGATION_DURATION))] = cv.positive_int
        fields[vol.Optional(
            CONF_SMART_WATERING_DURATION,
            default=self.config_entry.options.get(
                CONF_SMART_WATERING_DURATION, DEFAULT_SMART_WATERING_DURATION))] = cv.positive_int

        return self.async_show_form(step_id="user", data_schema=vol.Schema(fields), errors=errors)


def try_connection(email, password, client_id):
    _LOGGER.debug("Trying to connect to Gardena during setup")
    smart_system = SmartSystem(email=email, password=password, client_id=client_id)
    smart_system.authenticate()
    smart_system.update_locations()
    _LOGGER.debug("Successfully connected to Gardena during setup")
