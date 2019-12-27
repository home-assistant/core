"""Config flow to configure Met component."""
import logging

from metno import MetWeatherData
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_ELEVATION, CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import HomeAssistantType

from .const import (
    API_URL,
    CONF_FORECAST,
    CONF_TRACK_HOME,
    DEFAULT_FORECAST,
    HOME_LOCATION_NAME,
)
from .const import DOMAIN  # pylint: disable=unused-import

_LOGGER = logging.getLogger(__name__)


class MetFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Met component."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize the config flow."""

    def _configuration_exists(
        self, name: str, latitude: float, longitude: float
    ) -> bool:
        """Return True if the coordinates, name or track_home exists in configuration."""
        for entry in self._async_current_entries():
            if (
                entry.data.get(CONF_LATITUDE) == latitude
                and entry.data.get(CONF_LONGITUDE) == longitude
            ) or entry.data.get(CONF_NAME) == name:
                return True
        return False

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is None:
            return await self._show_setup_form(self.hass, user_input, errors)

        name = user_input.get(
            CONF_NAME, self.hass.config.location_name or HOME_LOCATION_NAME
        )
        latitude = user_input.get(CONF_LATITUDE, self.hass.config.latitude)
        longitude = user_input.get(CONF_LONGITUDE, self.hass.config.longitude)
        elevation = user_input.get(CONF_ELEVATION, self.hass.config.elevation or 0)
        forecast = user_input.get(CONF_FORECAST, DEFAULT_FORECAST)

        if None in (latitude, longitude):
            _LOGGER.error("Latitude or longitude not set in Home Assistant config")
            errors["base"] = "coordinates_not_set"
            return await self._show_setup_form(self.hass, user_input, errors)

        if self._configuration_exists(name, latitude, longitude):
            errors["base"] = "already_configured"
            return await self._show_setup_form(self.hass, user_input, errors)

        coordinates = {
            "lat": str(latitude),
            "lon": str(longitude),
            "msl": str(elevation),
        }
        weather_data = MetWeatherData(
            coordinates, async_get_clientsession(self.hass), API_URL
        )
        if not await weather_data.fetching_data():
            errors["base"] = "unknown"
            return await self._show_setup_form(self.hass, user_input, errors)

        return self.async_create_entry(
            title=name,
            data={
                CONF_ELEVATION: elevation,
                CONF_FORECAST: forecast,
                CONF_LATITUDE: latitude,
                CONF_LONGITUDE: longitude,
                CONF_NAME: name,
            },
        )

    async def _show_setup_form(
        self, hass: HomeAssistantType, user_input=None, errors=None
    ):
        """Show the setup form to the user."""

        if user_input is None:
            user_input = {}

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_NAME,
                        default=user_input.get(
                            CONF_NAME, hass.config.location_name or HOME_LOCATION_NAME
                        ),
                    ): str,
                    vol.Required(
                        CONF_LATITUDE,
                        default=user_input.get(CONF_LATITUDE, hass.config.latitude),
                    ): cv.latitude,
                    vol.Required(
                        CONF_LONGITUDE,
                        default=user_input.get(CONF_LONGITUDE, hass.config.longitude),
                    ): cv.longitude,
                    vol.Required(
                        CONF_ELEVATION,
                        default=user_input.get(
                            CONF_ELEVATION, hass.config.elevation or 0
                        ),
                    ): int,
                    vol.Required(
                        CONF_FORECAST,
                        default=user_input.get(CONF_FORECAST, DEFAULT_FORECAST),
                    ): int,
                }
            ),
            errors=errors or {},
        )

    async def async_step_onboarding(self, data=None):
        """Handle a flow initialized by onboarding."""
        return self.async_create_entry(
            title=HOME_LOCATION_NAME, data={CONF_TRACK_HOME: True}
        )
