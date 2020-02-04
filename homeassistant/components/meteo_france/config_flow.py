"""Config flow to configure the Meteo-France integration."""
import logging

from meteofrance.client import meteofranceClient, meteofranceError
import voluptuous as vol

from homeassistant import config_entries

from .const import CONF_CITY
from .const import DOMAIN  # pylint: disable=unused-import

_LOGGER = logging.getLogger(__name__)


class MeteoFranceFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Meteo-France config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def _show_setup_form(self, user_input=None, errors=None):
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
            return self._show_setup_form(user_input, errors)

        city = user_input[CONF_CITY]  # Might be a city name or a postal code
        city_name = None

        try:
            client = await self.hass.async_add_executor_job(meteofranceClient, city)
            city_name = client.get_data()["name"]
        except meteofranceError as exp:
            _LOGGER.error(
                "Unexpected error when creating the meteofrance proxy: %s", exp
            )
            return self.async_abort(reason="unknown")

        # Check if already configured
        await self.async_set_unique_id(city_name)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(title=city_name, data={CONF_CITY: city})

    async def async_step_import(self, user_input):
        """Import a config entry."""
        return await self.async_step_user(user_input)
