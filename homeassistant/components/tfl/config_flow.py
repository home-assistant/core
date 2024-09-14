"""Config flow for Transport for London integration."""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from typing import Any
from urllib.error import HTTPError

from tflwrapper import stopPoint
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig

from .common import CannotConnect, InvalidAuth, call_tfl_api
from .const import CONF_API_APP_KEY, CONF_STOP_POINTS, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_API_APP_KEY): cv.string,
    }
)
STEP_STOP_POINTS_DATA_SCHEMA = vol.Schema(
    {vol.Required(CONF_STOP_POINTS): TextSelector(TextSelectorConfig(multiple=True))}
)
RECONFIGURE_DATA_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_API_APP_KEY): cv.string,
    }
)
OPTIONS_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_STOP_POINTS): TextSelector(TextSelectorConfig(multiple=True)),
    }
)


@dataclass
class ValidationResult:
    """Define a validation result."""

    errors: dict[str, str] = field(default_factory=dict)
    description_placeholders: dict[str, str] = field(default_factory=dict)


async def validate_app_key(hass: HomeAssistant, app_key: str) -> ValidationResult:
    """Validate the user input for app_key."""

    errors: dict[str, str] = {}

    _LOGGER.debug("Validating app_key")
    try:
        stop_point_api = stopPoint(app_key)
        # Make a random, cheap, call to the API to validate the app_key
        categories = await call_tfl_api(hass, stop_point_api.getCategories)
        _LOGGER.debug("Validating app_key, got categories=%s", categories)
    except CannotConnect:
        errors["base"] = "cannot_connect"
    except InvalidAuth:
        errors["base"] = "invalid_auth"
    except Exception:  # pylint: disable=broad-except
        _LOGGER.exception("Unexpected exception")
        errors["base"] = "unknown"

    return ValidationResult(errors)


async def validate_stop_point(
    hass: HomeAssistant, app_key: str, stop_point: str
) -> ValidationResult:
    """Validate the user input for stop point."""
    errors: dict[str, str] = {}
    description_placeholders: dict[str, str] = {}

    _LOGGER.debug("Validating stop_point=%s", stop_point)

    try:
        stop_point_api = stopPoint(app_key)
        _LOGGER.debug("Validating stop_point=%s", stop_point)
        arrivals = await call_tfl_api(
            hass, stop_point_api.getStationArrivals, stop_point
        )
        _LOGGER.debug("Got for stop_point=%s, arrivals=%s", stop_point, arrivals)
    except HTTPError as exception:
        if exception.code == 404:
            errors["base"] = "invalid_stop_point"
            description_placeholders["stop_point"] = stop_point
        else:
            errors["base"] = "unknown"
    except CannotConnect:
        errors["base"] = "cannot_connect"
    except InvalidAuth:
        errors["base"] = "invalid_auth"
    except Exception:  # pylint: disable=broad-except
        _LOGGER.exception("Unexpected exception")
        errors["base"] = "unknown"

    return ValidationResult(errors, description_placeholders)


async def validate_stop_points(
    hass: HomeAssistant, app_key: str, stop_points: list[str]
) -> ValidationResult:
    """Validate the stop points."""

    for stop_point in stop_points:
        validation_result = await validate_stop_point(
            hass,
            app_key,
            stop_point,
        )
        if validation_result.errors:
            break

    return validation_result


class TfLConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Transport for London."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialise the config flow."""
        self.data: dict[str, Any] = {}
        self.options: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        validation_result = ValidationResult()
        if user_input is not None:
            validation_result = await validate_app_key(
                self.hass, user_input[CONF_API_APP_KEY]
            )

            if not validation_result.errors:
                # Input is valid, set data
                self.data = user_input
                self.options[CONF_STOP_POINTS] = []
                return await self.async_step_stop_point()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=validation_result.errors,
        )

    async def async_step_stop_point(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the stop point step."""
        validation_result = ValidationResult()
        if user_input is not None:
            app_key = self.data[CONF_API_APP_KEY]
            validation_result = await validate_stop_points(
                self.hass, app_key, user_input[CONF_STOP_POINTS]
            )

            if not validation_result.errors:
                # User input is valid, save the stop point
                self.options[CONF_STOP_POINTS].extend(user_input[CONF_STOP_POINTS])

                # Create the entry
                return self.async_create_entry(
                    title="Transport for London", data=self.data, options=self.options
                )

        return self.async_show_form(
            step_id="stop_point",
            data_schema=STEP_STOP_POINTS_DATA_SCHEMA,
            errors=validation_result.errors,
            description_placeholders=validation_result.description_placeholders,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Reconfigure step allows the app key to be updated."""
        validation_result = ValidationResult()
        config_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        assert config_entry is not None
        if user_input is not None:
            app_key = user_input.get(CONF_API_APP_KEY, "")
            validation_result = await validate_app_key(self.hass, app_key)

            if not validation_result.errors:
                # Input is valid, set data
                self.data[CONF_API_APP_KEY] = app_key
                self.hass.config_entries.async_update_entry(
                    config_entry, data=self.data
                )
                return self.async_abort(reason="reconfigure_successful")

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                RECONFIGURE_DATA_SCHEMA,
                config_entry.data if user_input is None else user_input,
            ),
            errors=validation_result.errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(OptionsFlow):
    """Handles options flow for the component."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options for the TfL component."""
        validation_result = ValidationResult()

        api_key = self.config_entry.data[CONF_API_APP_KEY]

        if user_input is not None:
            # Validate the stop points
            validation_result = await validate_stop_points(
                self.hass,
                api_key,
                user_input[CONF_STOP_POINTS],
            )
            if not validation_result.errors:
                data: dict[str, Any] = {}
                data[CONF_STOP_POINTS] = user_input[CONF_STOP_POINTS]

                # Value of data will be set on the options property of our config_entry
                # instance.
                return self.async_create_entry(
                    title="Transport for London",
                    data=data,
                )

        config = self.config_entry.options

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                OPTIONS_DATA_SCHEMA, config if user_input is None else user_input
            ),
            errors=validation_result.errors,
            description_placeholders=validation_result.description_placeholders,
        )
