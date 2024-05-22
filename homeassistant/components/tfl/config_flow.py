"""Config flow for Transport for London integration."""
from __future__ import annotations

from copy import deepcopy
import logging
from typing import Any
from urllib.error import HTTPError, URLError

from tflwrapper import stopPoint
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig

from .config_helper import config_from_entry
from .const import CONF_API_APP_KEY, CONF_STOP_POINTS, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_API_APP_KEY, default=""): cv.string,
    }
)
STEP_STOP_POINT_DATA_SCHEMA = vol.Schema(
    {vol.Required(CONF_STOP_POINTS): TextSelector(TextSelectorConfig(multiple=True))}
)


async def validate_app_key(hass: HomeAssistant, app_key: str) -> None:
    """Validate the user input for app_key."""

    _LOGGER.debug("Validating app_key")
    stop_point_api = stopPoint(app_key)
    # Make a random, cheap, call to the API to validate the app_key
    try:
        categories = await hass.async_add_executor_job(stop_point_api.getCategories)
        _LOGGER.debug("Validating app_key, got categories=%s", categories)
    except HTTPError as exception:
        # TfL's API returns a 429 if you pass an invalid app_key, but we also check
        # for other reasonable error codes in case their behaviour changes
        error_code = exception.code
        if error_code in (429, 401, 403):
            raise InvalidAuth from exception

        raise
    except URLError as exception:
        raise CannotConnect from exception


async def validate_stop_point(
    hass: HomeAssistant, app_key: str, stop_point: str
) -> None:
    """Validate the user input for stop point."""

    _LOGGER.debug("Validating stop_point=%s", stop_point)

    try:
        stop_point_api = stopPoint(app_key)
        _LOGGER.debug("Validating stop_point=%s", stop_point)
        arrivals = await hass.async_add_executor_job(
            stop_point_api.getStationArrivals, stop_point
        )
        _LOGGER.debug("Got for stop_point=%s, arrivals=%s", stop_point, arrivals)
    except HTTPError as exception:
        # TfL's API returns a 429 if you pass an invalid app_key, but we also check
        # for other reasonable error codes in case their behaviour changes
        error_code = exception.code
        if error_code in (429, 401, 403):
            raise InvalidAuth from exception

        if error_code == 404:
            raise ValueError from exception

        raise
    except URLError as exception:
        raise CannotConnect from exception


async def validate_stop_points(hass: HomeAssistant, app_key: str, stop_points):
    """Validate the stop points."""
    errors: dict[str, str] = {}
    description_placeholders: dict[str, str] = {}
    for stop_point in stop_points:
        try:
            await validate_stop_point(
                hass,
                app_key,
                stop_point,
            )
        except CannotConnect:
            errors["base"] = "cannot_connect"
            break
        except InvalidAuth:
            errors["base"] = "invalid_auth"
            break
        except ValueError:
            errors["base"] = "invalid_stop_point"
            description_placeholders["stop_point"] = stop_point
            break
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
            break

    return errors, description_placeholders


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Transport for London."""

    VERSION = 1
    data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                await validate_app_key(self.hass, user_input[CONF_API_APP_KEY])
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                # Input is valid, set data
                self.data = user_input
                self.data[CONF_STOP_POINTS] = []
                return await self.async_step_stop_point()

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_stop_point(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the stop point step."""
        errors: dict[str, str] = {}
        description_placeholders: dict[str, str] = {}
        if user_input is not None:
            app_key = self.data[CONF_API_APP_KEY]
            errors, description_placeholders = await validate_stop_points(
                self.hass, app_key, user_input[CONF_STOP_POINTS]
            )

            if not errors:
                # User input is valid, save the stop point
                self.data[CONF_STOP_POINTS].extend(user_input[CONF_STOP_POINTS])

                return self.async_create_entry(
                    title="Transport for London", data=self.data
                )

        return self.async_show_form(
            step_id="stop_point",
            data_schema=STEP_STOP_POINT_DATA_SCHEMA,
            errors=errors,
            description_placeholders=description_placeholders,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handles options flow for the component."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options for the TfL component."""
        errors: dict[str, str] = {}
        description_placeholders: dict[str, str] = {}

        if user_input is not None:
            # Validate the app key
            try:
                await validate_app_key(self.hass, user_input[CONF_API_APP_KEY])
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                # Validate the stop points
                errors, description_placeholders = await validate_stop_points(
                    self.hass,
                    user_input[CONF_API_APP_KEY],
                    user_input[CONF_STOP_POINTS],
                )
                if not errors:
                    data: dict[str, Any] = {}
                    data[CONF_API_APP_KEY] = user_input[CONF_API_APP_KEY]
                    data[CONF_STOP_POINTS] = user_input[CONF_STOP_POINTS]

                    # Value of data will be set on the options property of our config_entry
                    # instance.
                    return self.async_create_entry(
                        title="Transport for London",
                        data=data,
                    )

        config = config_from_entry(self.config_entry)
        api_key = deepcopy(config[CONF_API_APP_KEY])
        all_stops = deepcopy(config[CONF_STOP_POINTS])

        options_schema = vol.Schema(
            {
                vol.Optional(CONF_API_APP_KEY, default=api_key): cv.string,
                vol.Required(CONF_STOP_POINTS, default=all_stops): TextSelector(
                    TextSelectorConfig(multiple=True)
                ),
            }
        )
        return self.async_show_form(
            step_id="init",
            data_schema=options_schema,
            errors=errors,
            description_placeholders=description_placeholders,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
