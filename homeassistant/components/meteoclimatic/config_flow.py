"""Config flow to configure the Meteoclimatic integration."""

import logging

from meteoclimatic import MeteoclimaticClient
from meteoclimatic.exceptions import MeteoclimaticError, StationNotFound
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow

from .const import CONF_STATION_CODE, DOMAIN

_LOGGER = logging.getLogger(__name__)


class MeteoclimaticFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a Meteoclimatic config flow."""

    VERSION = 1

    def _show_setup_form(self, user_input=None, errors=None):
        """Show the setup form to the user."""
        if user_input is None:
            user_input = {}

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_STATION_CODE, default=user_input.get(CONF_STATION_CODE, "")
                    ): str
                }
            ),
            errors=errors or {},
        )

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""
        errors = {}

        if user_input is None:
            return self._show_setup_form(user_input, errors)

        station_code = user_input[CONF_STATION_CODE]
        client = MeteoclimaticClient()

        try:
            weather = await self.hass.async_add_executor_job(
                client.weather_at_station, station_code
            )
        except StationNotFound as exp:
            _LOGGER.error("Station not found: %s", exp)
            errors["base"] = "not_found"
            return self._show_setup_form(user_input, errors)
        except MeteoclimaticError as exp:
            _LOGGER.error("Error when obtaining Meteoclimatic weather: %s", exp)
            return self.async_abort(reason="unknown")

        # Check if already configured
        await self.async_set_unique_id(station_code, raise_on_progress=False)

        return self.async_create_entry(
            title=weather.station.name, data={CONF_STATION_CODE: station_code}
        )
