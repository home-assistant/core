"""Config flow for Forecast.Solar integration."""

from __future__ import annotations

import re
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv

from .const import (
    AZIMUTH_MAX,
    AZIMUTH_MIN,
    CONF_ADJ,
    CONF_AZIMUTH,
    CONF_AZIMUTH_CHOICE,
    CONF_AZIMUTH_SENSOR,
    CONF_DAMPING_EVENING,
    CONF_DAMPING_MORNING,
    CONF_DECLINATION,
    CONF_DECLINATION_CHOICE,
    CONF_DECLINATION_SENSOR,
    CONF_FIXED,
    CONF_HOME_LOCATION,
    CONF_INVERTER_SIZE,
    CONF_LOCATION_CHOICE,
    CONF_MANUAL_LOCATION,
    CONF_MODULES_POWER,
    DECLINATION_MAX,
    DECLINATION_MIN,
    DOMAIN,
)

RE_API_KEY = re.compile(r"^[a-zA-Z0-9]{16}$")

_ANGLE_UNITS: frozenset[str] = frozenset({"°", "degrees", "deg", "degree"})


def _get_angle_sensor_ids(hass: HomeAssistant) -> list[str]:
    """Get entity IDs of sensors that report angle units."""
    return [
        state.entity_id
        for entity_id in hass.states.async_entity_ids("sensor")
        if (state := hass.states.get(entity_id)) is not None
        and state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) in _ANGLE_UNITS
    ]


class ForecastSolarFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Forecast.Solar."""

    VERSION = 3

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> ForecastSolarOptionFlowHandler:
        """Get the options flow for this handler."""
        return ForecastSolarOptionFlowHandler()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        if user_input is not None:
            return self.async_create_entry(title=user_input[CONF_NAME], data={})

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_NAME, default=self.hass.config.location_name): str}
            ),
        )


class ForecastSolarOptionFlowHandler(OptionsFlowWithReload):
    """Handle options for Forecast.Solar."""

    def __init__(self) -> None:
        """Initialize the options flow."""
        self._flow_data: dict[str, Any] = {}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage top-level options and routing choices.

        Top-level options are wattage, damping, API key, inverter size, and choice
        fields for location, quadrant, and declination.
        """
        errors: dict[str, str] = {}

        angle_sensors = _get_angle_sensor_ids(self.hass)
        has_sensors = bool(angle_sensors)

        azimuth_choices: dict[str, str] = {CONF_FIXED: "Enter a fixed value"}
        declination_choices: dict[str, str] = {CONF_FIXED: "Enter a fixed value"}
        if has_sensors:
            azimuth_choices[CONF_ADJ] = "Read from a sensor"
            declination_choices[CONF_ADJ] = "Read from a sensor"

        if user_input is not None:
            api_key = user_input.get(CONF_API_KEY) or None
            if api_key and RE_API_KEY.match(api_key) is None:
                errors[CONF_API_KEY] = "invalid_api_key"
            else:
                self._flow_data = {**user_input, CONF_API_KEY: api_key}
                location_choice = user_input.get(CONF_LOCATION_CHOICE)
                if location_choice == CONF_HOME_LOCATION:
                    self._flow_data[CONF_LATITUDE] = self.hass.config.latitude
                    self._flow_data[CONF_LONGITUDE] = self.hass.config.longitude
                    return await self.async_step_azimuth()
                # CONF_MANUAL_LOCATION
                return await self.async_step_location_manual()

        # Determine defaults from current options so the form is
        # pre-populated when the user opens the options panel.
        current = self.config_entry.options
        existing_azimuth_choice = (
            CONF_ADJ if current.get(CONF_AZIMUTH_SENSOR) else CONF_FIXED
        )
        existing_declination_choice = (
            CONF_ADJ if current.get(CONF_DECLINATION_SENSOR) else CONF_FIXED
        )
        existing_location_choice = (
            CONF_MANUAL_LOCATION if CONF_LATITUDE in current else CONF_HOME_LOCATION
        )

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_LOCATION_CHOICE,
                    default=existing_location_choice,
                ): vol.In(
                    {
                        CONF_HOME_LOCATION: "Use my Home Assistant home location",
                        CONF_MANUAL_LOCATION: "Enter coordinates manually",
                    }
                ),
                vol.Required(
                    CONF_AZIMUTH_CHOICE,
                    default=existing_azimuth_choice,
                ): vol.In(azimuth_choices),
                vol.Required(
                    CONF_DECLINATION_CHOICE,
                    default=existing_declination_choice,
                ): vol.In(declination_choices),
                vol.Required(
                    CONF_MODULES_POWER,
                    default=current.get(CONF_MODULES_POWER),
                ): vol.Coerce(int),
                vol.Optional(
                    CONF_API_KEY,
                    description={"suggested_value": current.get(CONF_API_KEY, "")},
                ): str,
                vol.Optional(
                    CONF_INVERTER_SIZE,
                    description={"suggested_value": current.get(CONF_INVERTER_SIZE)},
                ): vol.Coerce(int),
                vol.Optional(
                    CONF_DAMPING_MORNING,
                    default=current.get(CONF_DAMPING_MORNING, 0.0),
                ): vol.Coerce(float),
                vol.Optional(
                    CONF_DAMPING_EVENING,
                    default=current.get(CONF_DAMPING_EVENING, 0.0),
                ): vol.Coerce(float),
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)

    async def async_step_location_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 2a: set manual location (only if user chose this option)."""
        if user_input is not None:
            self._flow_data.update(user_input)
            return await self.async_step_azimuth()

        return self.async_show_form(
            step_id="location_manual",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_LATITUDE,
                        default=self.config_entry.options.get(
                            CONF_LATITUDE, self.hass.config.latitude
                        ),
                    ): cv.latitude,
                    vol.Required(
                        CONF_LONGITUDE,
                        default=self.config_entry.options.get(
                            CONF_LONGITUDE, self.hass.config.longitude
                        ),
                    ): cv.longitude,
                }
            ),
        )

    async def async_step_azimuth(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 3: route azimuth to fixed or sensor screen."""
        if self._flow_data.get(CONF_AZIMUTH_CHOICE) == CONF_ADJ:
            return await self.async_step_azimuth_sensor(user_input)
        return await self.async_step_azimuth_manual(user_input)

    async def async_step_azimuth_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a fixed azimuth value."""
        if user_input is not None:
            self._flow_data.update(user_input)
            # Ensure no leftover sensor value from a previous configuration.
            self._flow_data.pop(CONF_AZIMUTH_SENSOR, None)
            return await self.async_step_declination()

        return self.async_show_form(
            step_id="azimuth_manual",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_AZIMUTH,
                        default=self.config_entry.options.get(CONF_AZIMUTH, 180),
                    ): vol.All(
                        vol.Coerce(int),
                        vol.Range(min=AZIMUTH_MIN, max=AZIMUTH_MAX),
                    ),
                }
            ),
        )

    async def async_step_azimuth_sensor(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle sensor-based azimuth selection."""
        if user_input is not None:
            self._flow_data.update(user_input)
            # Ensure no leftover manual value from a previous configuration.
            self._flow_data.pop(CONF_AZIMUTH, None)
            return await self.async_step_declination()

        # Pre-select the previously saved sensor if it still exists.
        angle_sensors = _get_angle_sensor_ids(self.hass)
        current_sensor = self.config_entry.options.get(CONF_AZIMUTH_SENSOR)

        return self.async_show_form(
            step_id="azimuth_sensor",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_AZIMUTH_SENSOR,
                        default=current_sensor
                        if angle_sensors and current_sensor in angle_sensors
                        else None,
                    ): vol.In(angle_sensors),
                }
            ),
        )

    async def async_step_declination(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 4: route declination to fixed or sensor screen."""
        if self._flow_data.get(CONF_DECLINATION_CHOICE) == CONF_ADJ:
            return await self.async_step_declination_sensor(user_input)
        return await self.async_step_declination_manual(user_input)

    async def async_step_declination_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a fixed declination value."""
        if user_input is not None:
            self._flow_data.update(user_input)
            self._flow_data.pop(CONF_DECLINATION_SENSOR, None)
            return self._async_create_entry()

        return self.async_show_form(
            step_id="declination_manual",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_DECLINATION,
                        default=self.config_entry.options.get(CONF_DECLINATION, 25),
                    ): vol.All(
                        vol.Coerce(int),
                        vol.Range(min=DECLINATION_MIN, max=DECLINATION_MAX),
                    ),
                }
            ),
        )

    async def async_step_declination_sensor(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle sensor-based declination selection."""
        if user_input is not None:
            self._flow_data.update(user_input)
            self._flow_data.pop(CONF_DECLINATION, None)
            return self._async_create_entry()

        angle_sensors = _get_angle_sensor_ids(self.hass)
        current_sensor = self.config_entry.options.get(CONF_DECLINATION_SENSOR)

        return self.async_show_form(
            step_id="declination_sensor",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_DECLINATION_SENSOR,
                        default=current_sensor
                        if angle_sensors and current_sensor in angle_sensors
                        else None,
                    ): vol.In(angle_sensors),
                }
            ),
        )

    def _async_create_entry(self) -> ConfigFlowResult:
        """Persist the collected options, dropping any None values."""
        options = {
            CONF_API_KEY: self._flow_data.get(CONF_API_KEY),
            CONF_LATITUDE: self._flow_data.get(CONF_LATITUDE),
            CONF_LONGITUDE: self._flow_data.get(CONF_LONGITUDE),
            CONF_MODULES_POWER: self._flow_data.get(CONF_MODULES_POWER),
            CONF_DAMPING_MORNING: self._flow_data.get(CONF_DAMPING_MORNING),
            CONF_DAMPING_EVENING: self._flow_data.get(CONF_DAMPING_EVENING),
            CONF_INVERTER_SIZE: self._flow_data.get(CONF_INVERTER_SIZE),
            CONF_AZIMUTH: self._flow_data.get(CONF_AZIMUTH),
            CONF_AZIMUTH_SENSOR: self._flow_data.get(CONF_AZIMUTH_SENSOR),
            CONF_DECLINATION: self._flow_data.get(CONF_DECLINATION),
            CONF_DECLINATION_SENSOR: self._flow_data.get(CONF_DECLINATION_SENSOR),
        }
        return self.async_create_entry(
            title="",
            data={k: v for k, v in options.items() if v is not None},
        )
