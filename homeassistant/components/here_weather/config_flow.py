"""Config flow for here_weather integration."""
import logging

import herepy
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
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
    CONF_API_KEY,
    CONF_LOCATION_NAME,
    CONF_MODES,
    CONF_OPTION,
    CONF_OPTION_COORDINATES,
    CONF_OPTION_LOCATION_NAME,
    CONF_OPTION_ZIP_CODE,
    CONF_OPTIONS,
    CONF_ZIP_CODE,
    DEFAULT_MODE,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    HERE_API_KEYS,
)

_LOGGER = logging.getLogger(__name__)


def get_base_schema(hass: HomeAssistant) -> vol.Schema:
    """Get the here_weather base schema."""
    known_api_key = None
    if HERE_API_KEYS in hass.data:
        known_api_key = hass.data[HERE_API_KEYS][0]
    return vol.Schema(
        {
            vol.Required(CONF_API_KEY, default=known_api_key): str,
            vol.Optional(CONF_NAME, default=DOMAIN): str,
            vol.Optional(CONF_MODE, default=DEFAULT_MODE): vol.In(CONF_MODES),
            vol.Optional(CONF_UNIT_SYSTEM, default=hass.config.units.name): vol.In(
                [CONF_UNIT_SYSTEM_METRIC, CONF_UNIT_SYSTEM_IMPERIAL]
            ),
        }
    )


def get_coordinate_schema(hass: HomeAssistant) -> vol.Schema:
    """Get the here_weather coordinate schema."""
    schema = get_base_schema(hass)
    return schema.extend(
        {
            vol.Optional(CONF_LATITUDE, default=hass.config.latitude): cv.latitude,
            vol.Optional(CONF_LONGITUDE, default=hass.config.longitude): cv.longitude,
        }
    )


def get_zip_code_schema(hass: HomeAssistant) -> vol.Schema:
    """Get the here_weather zip_code schema."""
    schema = get_base_schema(hass)
    return schema.extend({vol.Required(CONF_ZIP_CODE): str})


def get_location_name_schema(hass: HomeAssistant) -> vol.Schema:
    """Get the here_weather location_name schema."""
    schema = get_base_schema(hass)
    return schema.extend({vol.Required(CONF_LOCATION_NAME): str})


async def async_validate_coordinate_input(
    hass: HomeAssistant, user_input: dict
) -> None:
    """Validate the user_input containing coordinates."""
    await async_validate_name(hass, user_input)
    here_client = herepy.DestinationWeatherApi(user_input[CONF_API_KEY])
    await hass.async_add_executor_job(
        here_client.weather_for_coordinates,
        user_input[CONF_LATITUDE],
        user_input[CONF_LONGITUDE],
        herepy.WeatherProductType[user_input[CONF_MODE]],
    )


async def async_validate_zip_code_input(hass: HomeAssistant, user_input: dict) -> None:
    """Validate the user_input containing a zip_code."""
    await async_validate_name(hass, user_input)
    here_client = herepy.DestinationWeatherApi(user_input[CONF_API_KEY])
    await hass.async_add_executor_job(
        here_client.weather_for_zip_code,
        user_input[CONF_ZIP_CODE],
        herepy.WeatherProductType[user_input[CONF_MODE]],
    )


async def async_validate_location_name_input(
    hass: HomeAssistant, user_input: dict
) -> None:
    """Validate the user_input containing a location_name."""
    await async_validate_name(hass, user_input)
    here_client = herepy.DestinationWeatherApi(user_input[CONF_API_KEY])
    await hass.async_add_executor_job(
        here_client.weather_for_location_name,
        user_input[CONF_LOCATION_NAME],
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
            if user_input[CONF_OPTION] == CONF_OPTION_COORDINATES:
                return await self.async_step_coordinates()
            if user_input[CONF_OPTION] == CONF_OPTION_ZIP_CODE:
                return await self.async_step_zip_code()
            if user_input[CONF_OPTION] == CONF_OPTION_LOCATION_NAME:
                return await self.async_step_location_name()
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_OPTION): vol.In(CONF_OPTIONS)}),
            errors=errors,
        )

    async def async_step_coordinates(self, user_input=None):
        """Handle set up by coordinates."""
        errors = {}
        if user_input is not None:
            try:
                await async_validate_coordinate_input(self.hass, user_input)
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
            step_id="coordinates",
            data_schema=get_coordinate_schema(self.hass),
            errors=errors,
        )

    async def async_step_zip_code(self, user_input=None):
        """Handle set up by zip_code."""
        errors = {}
        if user_input is not None:
            try:
                await async_validate_zip_code_input(self.hass, user_input)
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
            step_id="zip_code",
            data_schema=get_zip_code_schema(self.hass),
            errors=errors,
        )

    async def async_step_location_name(self, user_input=None):
        """Handle set up by location_name."""
        errors = {}
        if user_input is not None:
            try:
                await async_validate_location_name_input(self.hass, user_input)
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
            step_id="location_name",
            data_schema=get_location_name_schema(self.hass),
            errors=errors,
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
            ): int
        }

        return self.async_show_form(step_id="init", data_schema=vol.Schema(options))


class AlreadyConfigured(HomeAssistantError):
    """Error to indicate the asset pair is already configured."""
