"""Config flow to configure the Meteo-France integration."""
import logging

from meteofrance_api.client import MeteoFranceClient
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_MODE
from homeassistant.core import callback

from .const import CONF_CITY, DOMAIN, FORECAST_MODE, FORECAST_MODE_DAILY

_LOGGER = logging.getLogger(__name__)


class MeteoFranceFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Meteo-France config flow."""

    VERSION = 1

    def __init__(self):
        """Init MeteoFranceFlowHandler."""
        self.places = []

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return MeteoFranceOptionsFlowHandler(config_entry)

    @callback
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
        latitude = user_input.get(CONF_LATITUDE)
        longitude = user_input.get(CONF_LONGITUDE)

        if not latitude:
            client = MeteoFranceClient()
            self.places = await self.hass.async_add_executor_job(
                client.search_places, city
            )
            _LOGGER.debug("Places search result: %s", self.places)
            if not self.places:
                errors[CONF_CITY] = "empty"
                return self._show_setup_form(user_input, errors)

            return await self.async_step_cities()

        # Check if already configured
        await self.async_set_unique_id(f"{latitude}, {longitude}")
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=city,
            data={CONF_LATITUDE: latitude, CONF_LONGITUDE: longitude},
        )

    async def async_step_import(self, user_input):
        """Import a config entry."""
        return await self.async_step_user(user_input)

    async def async_step_cities(self, user_input=None):
        """Step where the user choose the city from the API search results."""
        if not user_input:
            if len(self.places) > 1 and self.source != SOURCE_IMPORT:
                places_for_form = {}
                for place in self.places:
                    places_for_form[_build_place_key(place)] = f"{place}"

                return self.async_show_form(
                    step_id="cities",
                    data_schema=vol.Schema(
                        {
                            vol.Required(CONF_CITY): vol.All(
                                vol.Coerce(str), vol.In(places_for_form)
                            )
                        }
                    ),
                )
            user_input = {CONF_CITY: _build_place_key(self.places[0])}

        city_infos = user_input[CONF_CITY].split(";")
        return await self.async_step_user(
            {
                CONF_CITY: city_infos[0],
                CONF_LATITUDE: city_infos[1],
                CONF_LONGITUDE: city_infos[2],
            }
        )


class MeteoFranceOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a option flow."""

    def __init__(self, config_entry: config_entries.ConfigEntry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Handle options flow."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        data_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_MODE,
                    default=self.config_entry.options.get(
                        CONF_MODE, FORECAST_MODE_DAILY
                    ),
                ): vol.In(FORECAST_MODE)
            }
        )
        return self.async_show_form(step_id="init", data_schema=data_schema)


def _build_place_key(place) -> str:
    return f"{place};{place.latitude};{place.longitude}"
