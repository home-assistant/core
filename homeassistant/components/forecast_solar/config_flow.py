"""Config flow for Forecast.Solar integration."""
from __future__ import annotations

import re
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv

from .const import (
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
    CONF_LOCATION_ZONE,
    CONF_MANUAL_LOCATION,
    CONF_MODULES_POWER,
    DOMAIN,
)

RE_API_KEY = re.compile(r"^[a-zA-Z0-9]{16}$")


class ForecastSolarFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Forecast.Solar."""

    VERSION = 2

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> ForecastSolarOptionFlowHandler:
        """Get the options flow for this handler."""
        return ForecastSolarOptionFlowHandler(config_entry)

    def __init__(self):
        self.flow_data = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by the user."""

        if user_input is not None:
            self.flow_data.update(user_input)
            if user_input.get(CONF_LOCATION_CHOICE) == CONF_HOME_LOCATION:
                return await self.async_step_declination()
            elif user_input.get(CONF_LOCATION_CHOICE) == CONF_MANUAL_LOCATION:
                return await self.async_step_manual_location()
            elif user_input.get(CONF_LOCATION_CHOICE) == CONF_LOCATION_ZONE:
                return await self.async_step_zone_location()

        # Check if valid angle sensors exist.
        angle_sensors = [
            sensor
            for sensor in self.hass.states.async_entity_ids("sensor")
            if self.hass.states.get(sensor).attributes.get("unit_of_measurement")
            in ["°", "degrees", "deg", "degree"]
        ]
        has_angle_sensors = bool(angle_sensors)

        # Construct the choices for azimuth and declination based on the existence of valid sensors.
        azimuth_choices = {CONF_FIXED: "Fixed Azimuth"}
        declination_choices = {CONF_FIXED: "Fixed Declination"}

        if has_angle_sensors:
            azimuth_choices[CONF_ADJ] = "Adjustable Azimuth with a Sensor"
            declination_choices[CONF_ADJ] = "Adjustable Declination with a Sensor"
        location_choice_schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=self.hass.config.location_name): str,
                vol.Required(CONF_LOCATION_CHOICE): vol.In(
                    {
                        CONF_HOME_LOCATION: "Use My Home Location",
                        CONF_LOCATION_ZONE: "Select a Zone",
                        CONF_MANUAL_LOCATION: "Input Latitude & Longitude Manually",
                    }
                ),
                vol.Required(CONF_AZIMUTH_CHOICE): vol.In(azimuth_choices),
                vol.Required(CONF_DECLINATION_CHOICE): vol.In(declination_choices),
            }
        )

        location_choice_schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=self.hass.config.location_name): str,
                vol.Required(CONF_LOCATION_CHOICE): vol.In(
                    {
                        CONF_HOME_LOCATION: "Use My Home Location",
                        CONF_LOCATION_ZONE: "Select a Zone",
                        CONF_MANUAL_LOCATION: "Input Latitude & Longitude Manually",
                    }
                ),
                vol.Required(CONF_AZIMUTH_CHOICE): vol.In(
                    {
                        CONF_FIXED: "Fixed Azimuth",
                        CONF_ADJ: "Adjustable Azimuth with a Sensor",
                    }
                ),
                vol.Required(CONF_DECLINATION_CHOICE): vol.In(
                    {
                        CONF_FIXED: "Fixed Declination",
                        CONF_ADJ: "Adjustable Declination with a Sensor",
                    }
                ),
            }
        )

        return self.async_show_form(step_id="user", data_schema=location_choice_schema)

    async def async_step_zone_location(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the zone location step."""
        zones = await self.hass.async_add_executor_job(
            self.hass.states.entity_ids, "zone"
        )

        if user_input is not None:
            previous_input = self.flow_data
            self.flow_data = {**previous_input, **user_input}
            # Proceed to the next step with the selected zone.
            return await self.async_step_declination()
        return self.async_show_form(
            step_id="zone_location",
            data_schema=vol.Schema({vol.Required(CONF_LOCATION_ZONE): vol.In(zones)}),
        )

    async def async_step_manual_location(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle manual location input."""

        if user_input is not None:
            previous_input = self.flow_data
            self.flow_data = {**previous_input, **user_input}
            # Proceed to the next step with the manually inputted data.
            return await self.async_step_declination()
        manual_location_schema = vol.Schema(
            {
                vol.Required(CONF_LATITUDE): cv.latitude,
                vol.Required(CONF_LONGITUDE): cv.longitude,
            }
        )

        return self.async_show_form(
            step_id="manual_location", data_schema=manual_location_schema
        )

    async def async_step_declination(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the declination step."""
        errors = {}
        previous_input = self.flow_data
        angle_sensors = [
            sensor
            for sensor in self.hass.states.async_entity_ids("sensor")
            if self.hass.states.get(sensor).attributes.get("unit_of_measurement")
            in ["°", "degrees", "deg", "degree"]
        ]

        if previous_input.get(CONF_DECLINATION_CHOICE) == CONF_ADJ:
            declination_schema = vol.Schema(
                {vol.Required(CONF_DECLINATION_SENSOR): vol.In(angle_sensors)}
            )
        else:
            declination_schema = vol.Schema(
                {
                    vol.Required(CONF_DECLINATION, default=25): vol.All(
                        vol.Coerce(int), vol.Range(min=0, max=90)
                    )
                }
            )
        if user_input is not None:
            self.flow_data = {**previous_input, **user_input}
            # Proceed to the next step
            return await self.async_step_azimuth()
        return self.async_show_form(
            step_id="declination", data_schema=declination_schema, errors=errors
        )

    async def async_step_azimuth(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the azimuth step."""
        errors = {}
        previous_input = self.flow_data
        angle_sensors = [
            sensor
            for sensor in self.hass.states.async_entity_ids("sensor")
            if self.hass.states.get(sensor).attributes.get("unit_of_measurement")
            in ["°", "degrees", "deg", "degree"]
        ]

        if previous_input.get(CONF_AZIMUTH_CHOICE) == CONF_ADJ:
            azimuth_schema = vol.Schema(
                {vol.Required(CONF_AZIMUTH_SENSOR): vol.In(angle_sensors)}
            )
        else:
            azimuth_schema = vol.Schema(
                {
                    vol.Required(CONF_AZIMUTH, default=180): vol.All(
                        vol.Coerce(int), vol.Range(min=0, max=360)
                    ),
                }
            )
        if user_input is not None:
            self.flow_data = {**previous_input, **user_input}
            # Proceed to the next step
            return await self.async_step_wattage()
        return self.async_show_form(
            step_id="azimuth", data_schema=azimuth_schema, errors=errors
        )

    async def async_step_wattage(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the wattage step."""

        if user_input is not None:
            previous_input = self.flow_data
            return self.async_create_entry(
                title=previous_input[CONF_NAME],
                data={
                    CONF_HOME_LOCATION: previous_input.get(CONF_HOME_LOCATION),
                    CONF_LOCATION_ZONE: previous_input.get(CONF_LOCATION_ZONE),
                    CONF_LATITUDE: previous_input.get(CONF_LATITUDE),
                    CONF_LONGITUDE: previous_input.get(CONF_LONGITUDE),
                },
                options={
                    CONF_DECLINATION: previous_input.get(CONF_DECLINATION),
                    CONF_DECLINATION_SENSOR: previous_input.get(
                        CONF_DECLINATION_SENSOR
                    ),
                    CONF_AZIMUTH: previous_input.get(CONF_AZIMUTH),
                    CONF_AZIMUTH_SENSOR: previous_input.get(CONF_AZIMUTH_SENSOR),
                    CONF_MODULES_POWER: user_input.get(CONF_MODULES_POWER),
                },
            )
        return self.async_show_form(
            step_id="wattage",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_MODULES_POWER): vol.Coerce(int),
                }
            ),
        )


class ForecastSolarOptionFlowHandler(OptionsFlow):
    """Handle options."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        errors = {}
        if user_input is not None:
            if (api_key := user_input.get(CONF_API_KEY)) and RE_API_KEY.match(
                api_key
            ) is None:
                errors[CONF_API_KEY] = "invalid_api_key"
            else:
                return self.async_create_entry(
                    title="", data=user_input | {CONF_API_KEY: api_key or None}
                )
        # Check if the declination and azimuth sensors are set.
        declination_sensor = self.config_entry.options.get(CONF_DECLINATION_SENSOR)
        azimuth_sensor = self.config_entry.options.get(CONF_AZIMUTH_SENSOR)

        # Generate the schema dynamically based on the sensor values.
        options_schema = {
            vol.Optional(
                CONF_API_KEY,
                description={
                    "suggested_value": self.config_entry.options.get(CONF_API_KEY, "")
                },
            ): str,
            vol.Required(
                CONF_MODULES_POWER,
                default=self.config_entry.options[CONF_MODULES_POWER],
            ): vol.Coerce(int),
            vol.Optional(
                CONF_DAMPING_MORNING,
                default=self.config_entry.options.get(CONF_DAMPING_MORNING, 0.0),
            ): vol.Coerce(float),
            vol.Optional(
                CONF_DAMPING_EVENING,
                default=self.config_entry.options.get(CONF_DAMPING_EVENING, 0.0),
            ): vol.Coerce(float),
            vol.Optional(
                CONF_INVERTER_SIZE,
                description={
                    "suggested_value": self.config_entry.options.get(CONF_INVERTER_SIZE)
                },
            ): vol.Coerce(int),
        }
        angle_sensors = [
            sensor
            for sensor in self.hass.states.async_entity_ids("sensor")
            if self.hass.states.get(sensor).attributes.get("unit_of_measurement")
            in ["°", "degrees", "deg", "degree"]
        ]
        declination_sensors = angle_sensors.copy()

        if declination_sensor and declination_sensor in angle_sensors:
            declination_sensors.remove(declination_sensor)
            declination_sensors.insert(0, declination_sensor)

        if azimuth_sensor and azimuth_sensor in angle_sensors:
            angle_sensors.remove(azimuth_sensor)
            angle_sensors.insert(0, azimuth_sensor)

        if declination_sensor:
            options_schema[vol.Required(CONF_DECLINATION_SENSOR)] = vol.In(
                declination_sensors
            )
        else:
            options_schema[
                vol.Required(
                    CONF_DECLINATION,
                    default=self.config_entry.options[CONF_DECLINATION],
                )
            ] = vol.All(vol.Coerce(int), vol.Range(min=0, max=90))
        if azimuth_sensor:
            options_schema[vol.Required(CONF_AZIMUTH_SENSOR)] = vol.In(angle_sensors)
        else:
            options_schema[
                vol.Required(
                    CONF_AZIMUTH, default=self.config_entry.options.get(CONF_AZIMUTH)
                )
            ] = vol.All(vol.Coerce(int), vol.Range(min=0, max=360))
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(options_schema),
            errors=errors,
        )
