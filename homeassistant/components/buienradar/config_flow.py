"""Config flow for buienradar2 integration."""
import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_INCLUDE, CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

from .const import (
    CAMERA_DIM_MAX,
    CAMERA_DIM_MIN,
    CONF_CAMERA,
    CONF_COUNTRY,
    CONF_DELTA,
    CONF_DIMENSION,
    CONF_FORECAST,
    CONF_SENSOR,
    CONF_TIMEFRAME,
    CONF_WEATHER,
    DOMAIN,
    HOME_LOCATION_NAME,
    SUPPORTED_COUNTRY_CODES,
)

_LOGGER = logging.getLogger(__name__)


@callback
def configured_instances(hass):
    """Return a set of configured SimpliSafe instances."""
    entries = []
    for entry in hass.config_entries.async_entries(DOMAIN):
        entries.append(
            f"{entry.data.get(CONF_LATITUDE)}-{entry.data.get(CONF_LONGITUDE)}"
        )
    return set(entries)


class BuienradarFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for buienradar2."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Init MetFlowHandler."""
        self._errors = {}

        self._weather = False
        self._camera = False
        self._sensor = False

        self._name = None
        self._latitude = None
        self._longitude = None

        self._weatherdata = {}
        self._cameradata = {}
        self._sensordata = {}

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        self._errors = {}

        if user_input is not None:
            if (
                f"{user_input.get(CONF_LATITUDE)}-{user_input.get(CONF_LONGITUDE)}"
                not in configured_instances(self.hass)
            ):
                self._name = user_input[CONF_NAME]

                self._weather = user_input[CONF_WEATHER]
                self._camera = user_input[CONF_CAMERA]
                self._sensor = user_input[CONF_SENSOR]

                self._latitude = user_input[CONF_LATITUDE]
                self._longitude = user_input[CONF_LONGITUDE]

                if self._weather:
                    return await self.async_step_setup_weather()
                if self._camera:
                    return await self.async_step_setup_camera()
                if self._sensor:
                    return await self.async_step_setup_sensor()

                self._errors["base"] = "empty_selection"
            else:
                self._errors[CONF_NAME] = "name_exists"

        return await self._show_config_form(
            name=HOME_LOCATION_NAME,
            latitude=self.hass.config.latitude,
            longitude=self.hass.config.longitude,
        )

    async def async_step_setup_weather(self, user_input=None):
        """Handle step to configure weather platform."""
        self._errors = {}

        if user_input is not None:
            self._weatherdata = user_input

            if self._camera:
                return await self.async_step_setup_camera()
            if self._sensor:
                return await self.async_step_setup_sensor()

            return await self._configure()

        return self.async_show_form(
            step_id="setup_weather",
            data_schema=vol.Schema({vol.Required(CONF_FORECAST, default=True): bool}),
            errors=self._errors,
        )

    async def async_step_setup_camera(self, user_input=None):
        """Handle step to configure camera platform."""
        self._errors = {}

        if user_input is not None:
            self._cameradata = user_input

            if self._sensor:
                return await self.async_step_setup_sensor()

            return await self._configure()

        return self.async_show_form(
            step_id="setup_camera",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DIMENSION, default=512): vol.All(
                        vol.Coerce(int),
                        vol.Range(min=CAMERA_DIM_MIN, max=CAMERA_DIM_MAX),
                    ),
                    vol.Required(CONF_DELTA, default=600.0): vol.All(
                        vol.Coerce(int), vol.Range(min=0)
                    ),
                    vol.Required(CONF_COUNTRY, default="NL"): vol.All(
                        vol.Coerce(str), vol.In(SUPPORTED_COUNTRY_CODES)
                    ),
                }
            ),
            errors=self._errors,
        )

    async def async_step_setup_sensor(self, user_input=None):
        """Handle step to configure sensor platform."""
        self._errors = {}

        if user_input is not None:
            self._sensordata = user_input

            return await self._configure()

        return self.async_show_form(
            step_id="setup_sensor",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_TIMEFRAME, default=60): vol.All(
                        vol.Coerce(int), vol.Range(min=5, max=120)
                    ),
                }
            ),
            errors=self._errors,
        )

    async def _show_config_form(
        self, name=None, latitude=None, longitude=None, elevation=None
    ):
        """Show the configuration form to edit location data."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default=name): str,
                    vol.Required(CONF_LATITUDE, default=latitude): cv.latitude,
                    vol.Required(CONF_LONGITUDE, default=longitude): cv.longitude,
                    vol.Required(CONF_WEATHER, default=False): bool,
                    vol.Required(CONF_CAMERA, default=False): bool,
                    vol.Required(CONF_SENSOR, default=False): bool,
                }
            ),
            errors=self._errors,
        )

    async def _configure(self):
        data = {
            CONF_NAME: self._name,
            CONF_LATITUDE: self._latitude,
            CONF_LONGITUDE: self._longitude,
            CONF_WEATHER: self._weatherdata,
            CONF_CAMERA: self._cameradata,
            CONF_SENSOR: self._sensordata,
        }

        data[CONF_WEATHER][CONF_INCLUDE] = self._weather
        data[CONF_CAMERA][CONF_INCLUDE] = self._camera
        data[CONF_SENSOR][CONF_INCLUDE] = self._sensor

        return self.async_create_entry(title=self._name, data=data)
