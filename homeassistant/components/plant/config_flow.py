"""Config flow for Plant."""
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
import homeassistant.helpers.config_validation as cv

from .const import (
    BATTERY_SENSOR,
    BRIGHTNESS_SENSOR,
    CONDUCTIVITY_SENSOR,
    CONF_CHECK_DAYS,
    CONF_MAX_CONDUCTIVITY,
    CONF_MAX_MOISTURE,
    CONF_MIN_BATTERY_LEVEL,
    CONF_MIN_CONDUCTIVITY,
    CONF_MIN_MOISTURE,
    DEFAULT_CHECK_DAYS,
    DEFAULT_MAX_CONDUCTIVITY,
    DEFAULT_MAX_MOISTURE,
    DEFAULT_MIN_BATTERY_LEVEL,
    DEFAULT_MIN_CONDUCTIVITY,
    DEFAULT_MIN_MOISTURE,
    DOMAIN,
    MOISTURE_SENSOR,
    PLANT_NAME,
    SENSORS,
    TEMPERATURE_SENSOR,
)

sensor_datatype = {
    MOISTURE_SENSOR: cv.positive_int,
    BATTERY_SENSOR: cv.positive_int,
    CONDUCTIVITY_SENSOR: cv.positive_int,
    BRIGHTNESS_SENSOR: cv.positive_int,
    TEMPERATURE_SENSOR: vol.Coerce(float),
}

default_sensor_values = {
    CONF_MIN_BATTERY_LEVEL: DEFAULT_MIN_BATTERY_LEVEL,
    CONF_MIN_MOISTURE: DEFAULT_MIN_MOISTURE,
    CONF_MAX_MOISTURE: DEFAULT_MAX_MOISTURE,
    CONF_MIN_CONDUCTIVITY: DEFAULT_MIN_CONDUCTIVITY,
    CONF_MAX_CONDUCTIVITY: DEFAULT_MAX_CONDUCTIVITY,
}


class PlantConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Plant config flow."""

    # The schema version of the entries that it creates
    # Home Assistant will call your migrate method if the version changes
    VERSION = 1

    def __init__(self) -> None:
        """Initialise plant flow."""
        self.data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Render first step."""
        if user_input is None:
            return await self._show_plant_name_form({})

        self.data[PLANT_NAME] = user_input[PLANT_NAME]
        return await self._show_sensors_form({})

    async def async_step_sensors(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Render sensor step."""
        if user_input is None:
            return await self._show_plant_name_form({})

        self.data[SENSORS] = user_input

        return await self._show_limits_form({})

    async def _show_plant_name_form(
        self, user_input: dict[str, Any] | None
    ) -> FlowResult:
        default = ""
        if user_input is not None:
            default = user_input.get(PLANT_NAME, "")
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(PLANT_NAME, default=default): str}),
        )

    async def _show_sensors_form(self, user_input: dict[str, Any] | None) -> FlowResult:
        if user_input is None:
            user_input = {}
        return self.async_show_form(
            step_id="sensors",
            data_schema=vol.Schema(
                {
                    vol.Optional(MOISTURE_SENSOR): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain=["sensor", "number", "input_number"]
                        ),
                    ),
                    vol.Optional(BATTERY_SENSOR): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain=["sensor", "number", "input_number"]
                        ),
                    ),
                    vol.Optional(TEMPERATURE_SENSOR): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain=["sensor", "number", "input_number"]
                        ),
                    ),
                    vol.Optional(CONDUCTIVITY_SENSOR): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain=["sensor", "number", "input_number"]
                        ),
                    ),
                    vol.Optional(BRIGHTNESS_SENSOR): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain=["sensor", "number", "input_number"]
                        ),
                    ),
                }
            ),
        )

    async def _show_limits_form(self, user_input: dict[str, Any] | None) -> FlowResult:
        if user_input is None:
            user_input = {}
        schemas = {}
        for sensor_type in (
            MOISTURE_SENSOR,
            TEMPERATURE_SENSOR,
            CONDUCTIVITY_SENSOR,
            BRIGHTNESS_SENSOR,
        ):
            if sensor_type in self.data[SENSORS]:
                min_var = f"min_{sensor_type}"
                max_var = f"max_{sensor_type}"
                min_default = user_input.get(
                    min_var, default_sensor_values.get(min_var)
                )
                max_default = user_input.get(
                    max_var, default_sensor_values.get(max_var)
                )
                schemas[vol.Optional(min_var, default=min_default)] = sensor_datatype[
                    sensor_type
                ]
                schemas[vol.Optional(max_var, default=max_default)] = sensor_datatype[
                    sensor_type
                ]
        if BATTERY_SENSOR in self.data[SENSORS]:
            schemas[
                vol.Optional(CONF_MIN_BATTERY_LEVEL, default=DEFAULT_MIN_BATTERY_LEVEL)
            ] = cv.positive_int

        if BRIGHTNESS_SENSOR in self.data[SENSORS]:
            schemas[
                vol.Optional(CONF_CHECK_DAYS, default=DEFAULT_CHECK_DAYS)
            ] = cv.positive_int

        return self.async_show_form(step_id="limits", data_schema=vol.Schema(schemas))

    async def async_step_limits(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """asd."""
        if user_input is None:
            user_input = {}
        return self.async_create_entry(
            title=self.data[PLANT_NAME], data={"sensors": self.data, **user_input}
        )
