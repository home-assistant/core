"""Config flow to configure the Meteo-France integration."""
import logging

from meteofrance.client import meteofranceClient, meteofranceError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_MONITORED_CONDITIONS

from .const import CONF_CITY, SENSOR_TYPES
from .const import DOMAIN  # pylint: disable=unused-import

_LOGGER = logging.getLogger(__name__)


class MeteoFranceFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Meteo-France config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize Meteo-France config flow."""

    def _configuration_exists(self, city_name: str) -> bool:
        """Return True if city_name exists in configuration."""
        for entry in self._async_current_entries():
            if entry.data[CONF_CITY] == city_name:
                return True
        return False

    async def _show_setup_form(self, user_input=None, errors=None):
        """Show the setup form to the user."""

        if user_input is None:
            user_input = {}

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_CITY, default=user_input.get(CONF_CITY, "")): str}
            ),
            errors=errors or {},
        )

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""
        errors = {}

        if user_input is None:
            return await self._show_setup_form(user_input, None)

        city = user_input[CONF_CITY]
        monitored_conditions = user_input.get(
            CONF_MONITORED_CONDITIONS, list(SENSOR_TYPES)
        )
        if self._configuration_exists(city):
            errors[CONF_CITY] = "city_exists"
            return await self._show_setup_form(user_input, errors)

        try:
            await self.hass.async_add_executor_job(meteofranceClient, city)
        except meteofranceError as exp:
            _LOGGER.error(
                "Unexpected error when creating the meteofrance proxy: %s", exp
            )
            errors["base"] = "unknown"
            return await self._show_setup_form(user_input, errors)

        return self.async_create_entry(
            title=city,
            data={CONF_CITY: city, CONF_MONITORED_CONDITIONS: monitored_conditions},
        )

    async def async_step_import(self, user_input):
        """Import a config entry."""
        if self._configuration_exists(user_input[CONF_CITY]):
            return self.async_abort(reason="city_exists")

        return await self.async_step_user(user_input)
