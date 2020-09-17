"""Config flow for here_weather integration."""
import logging
from typing import Optional

import herepy
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_MODE,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    CONF_UNIT_SYSTEM,
    CONF_UNIT_SYSTEM_IMPERIAL,
    CONF_UNIT_SYSTEM_METRIC,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_MODES,
    DEFAULT_MODE,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    HERE_API_KEYS,
)

_LOGGER = logging.getLogger(__name__)


async def async_validate_user_input(hass: HomeAssistant, user_input: dict) -> None:
    """Validate the user_input containing coordinates."""
    await async_validate_name(hass, user_input)
    here_client = herepy.DestinationWeatherApi(user_input[CONF_API_KEY])
    await hass.async_add_executor_job(
        here_client.weather_for_coordinates,
        user_input[CONF_LATITUDE],
        user_input[CONF_LONGITUDE],
        herepy.WeatherProductType[user_input[CONF_MODE]],
    )


async def async_validate_name(hass: HomeAssistant, user_input: dict) -> None:
    """Validate the user input."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.data[CONF_NAME] == user_input[CONF_NAME]:
            raise AlreadyConfigured


class HereWeatherConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for here_weather."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry):
        """Get the options flow for this handler."""
        return HereWeatherOptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                await async_validate_user_input(self.hass, user_input)
                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input
                )
            except AlreadyConfigured:
                return self.async_abort(reason="already_configured")
            except herepy.InvalidRequestError:
                errors["base"] = "invalid_request"
            except herepy.UnauthorizedError:
                errors["base"] = "unauthorized"
        return self.async_show_form(
            step_id="user",
            data_schema=self._get_schema(user_input),
            errors=errors,
        )

    def _get_schema(self, user_input: Optional[dict]) -> vol.Schema:
        known_api_key = None
        if HERE_API_KEYS in self.hass.data:
            known_api_key = self.hass.data[HERE_API_KEYS][0]
        if user_input is not None:
            return vol.Schema(
                {
                    vol.Required(CONF_API_KEY, default=user_input[CONF_API_KEY]): str,
                    vol.Required(CONF_NAME, default=user_input[CONF_NAME]): str,
                    vol.Required(CONF_MODE, default=user_input[CONF_MODE]): vol.In(
                        CONF_MODES
                    ),
                    vol.Required(
                        CONF_LATITUDE, default=user_input[CONF_LATITUDE]
                    ): cv.latitude,
                    vol.Required(
                        CONF_LONGITUDE, default=user_input[CONF_LONGITUDE]
                    ): cv.longitude,
                }
            )
        return vol.Schema(
            {
                vol.Required(CONF_API_KEY, default=known_api_key): str,
                vol.Required(CONF_NAME, default=DOMAIN): str,
                vol.Required(CONF_MODE, default=DEFAULT_MODE): vol.In(CONF_MODES),
                vol.Required(
                    CONF_LATITUDE, default=self.hass.config.latitude
                ): cv.latitude,
                vol.Required(
                    CONF_LONGITUDE, default=self.hass.config.longitude
                ): cv.longitude,
            }
        )


class HereWeatherOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle here_weather options."""

    def __init__(self, config_entry):
        """Initialize here_weather options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the here_weather options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = {
            vol.Optional(
                CONF_SCAN_INTERVAL,
                default=self.config_entry.options.get(
                    CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                ),
            ): int,
            vol.Optional(CONF_UNIT_SYSTEM, default=self.hass.config.units.name): vol.In(
                [CONF_UNIT_SYSTEM_METRIC, CONF_UNIT_SYSTEM_IMPERIAL]
            ),
        }

        return self.async_show_form(step_id="init", data_schema=vol.Schema(options))


class AlreadyConfigured(HomeAssistantError):
    """Error to indicate the asset pair is already configured."""
