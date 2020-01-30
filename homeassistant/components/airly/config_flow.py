"""Adds config flow for Airly."""
from airly import Airly
from airly.exceptions import AirlyError
import async_timeout
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from .const import (  # pylint:disable=unused-import
    DEFAULT_NAME,
    DOMAIN,
    NO_AIRLY_SENSORS,
)


class AirlyFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Airly."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize."""
        self._errors = {}

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        self._errors = {}

        websession = async_get_clientsession(self.hass)

        if user_input is not None:
            await self.async_set_unique_id(
                f"{user_input[CONF_LATITUDE]}-{user_input[CONF_LONGITUDE]}"
            )
            self._abort_if_unique_id_configured()
            api_key_valid = await self._test_api_key(websession, user_input["api_key"])
            if not api_key_valid:
                self._errors["base"] = "auth"
            else:
                location_valid = await self._test_location(
                    websession,
                    user_input["api_key"],
                    user_input["latitude"],
                    user_input["longitude"],
                )
                if not location_valid:
                    self._errors["base"] = "wrong_location"

            if not self._errors:
                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input
                )

        return self._show_config_form(
            name=DEFAULT_NAME,
            api_key="",
            latitude=self.hass.config.latitude,
            longitude=self.hass.config.longitude,
        )

    def _show_config_form(self, name=None, api_key=None, latitude=None, longitude=None):
        """Show the configuration form to edit data."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY, default=api_key): str,
                    vol.Optional(
                        CONF_LATITUDE, default=self.hass.config.latitude
                    ): cv.latitude,
                    vol.Optional(
                        CONF_LONGITUDE, default=self.hass.config.longitude
                    ): cv.longitude,
                    vol.Optional(CONF_NAME, default=name): str,
                }
            ),
            errors=self._errors,
        )

    async def _test_api_key(self, client, api_key):
        """Return true if api_key is valid."""

        with async_timeout.timeout(10):
            airly = Airly(api_key, client)
            measurements = airly.create_measurements_session_point(
                latitude=52.24131, longitude=20.99101
            )
            try:
                await measurements.update()
            except AirlyError:
                return False
            return True

    async def _test_location(self, client, api_key, latitude, longitude):
        """Return true if location is valid."""

        with async_timeout.timeout(10):
            airly = Airly(api_key, client)
            measurements = airly.create_measurements_session_point(
                latitude=latitude, longitude=longitude
            )

            await measurements.update()
        current = measurements.current
        if current["indexes"][0]["description"] == NO_AIRLY_SENSORS:
            return False
        return True
