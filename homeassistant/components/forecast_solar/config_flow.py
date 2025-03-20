"""Config flow for Forecast.Solar integration."""

from __future__ import annotations

import re
from typing import Any

import voluptuous as vol

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    UnitOfEnergy,
)
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv, entity_registry as er

from .const import (
    CONF_AZIMUTH,
    CONF_DAMPING_EVENING,
    CONF_DAMPING_MORNING,
    CONF_DECLINATION,
    CONF_INVERTER_SIZE,
    CONF_MODULES_POWER,
    CONF_SEND_ACTUALS,
    CONF_TODAY_ENERGY_GENERATION_ENTITY_ID,
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
        return ForecastSolarOptionFlowHandler()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        if user_input is not None:
            return self.async_create_entry(
                title=user_input[CONF_NAME],
                data={
                    CONF_LATITUDE: user_input[CONF_LATITUDE],
                    CONF_LONGITUDE: user_input[CONF_LONGITUDE],
                },
                options={
                    CONF_AZIMUTH: user_input[CONF_AZIMUTH],
                    CONF_DECLINATION: user_input[CONF_DECLINATION],
                    CONF_MODULES_POWER: user_input[CONF_MODULES_POWER],
                },
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_NAME, default=self.hass.config.location_name
                    ): str,
                    vol.Required(
                        CONF_LATITUDE, default=self.hass.config.latitude
                    ): cv.latitude,
                    vol.Required(
                        CONF_LONGITUDE, default=self.hass.config.longitude
                    ): cv.longitude,
                    vol.Required(CONF_DECLINATION, default=25): vol.All(
                        vol.Coerce(int), vol.Range(min=0, max=90)
                    ),
                    vol.Required(CONF_AZIMUTH, default=180): vol.All(
                        vol.Coerce(int), vol.Range(min=0, max=360)
                    ),
                    vol.Required(CONF_MODULES_POWER): vol.All(
                        vol.Coerce(int), vol.Range(min=1)
                    ),
                }
            ),
        )


class ForecastSolarOptionFlowHandler(OptionsFlow):
    """Handle options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        errors = {}
        if user_input is not None:
            # Validate API key
            if (api_key := user_input.get(CONF_API_KEY)) and RE_API_KEY.match(
                api_key
            ) is None:
                errors[CONF_API_KEY] = "invalid_api_key"

            # Validate CONF_TODAY_ENERGY_GENERATION_ENTITY_ID
            entity_id = user_input.get(CONF_TODAY_ENERGY_GENERATION_ENTITY_ID)
            if entity_id:
                entity_registry = er.async_get(self.hass)
                entity_entry = entity_registry.async_get(entity_id)
                if not entity_entry:
                    errors[CONF_TODAY_ENERGY_GENERATION_ENTITY_ID] = "entity_not_found"
                elif entity_entry.original_device_class != SensorDeviceClass.ENERGY:
                    errors[CONF_TODAY_ENERGY_GENERATION_ENTITY_ID] = (
                        f"invalid device class. Needs to be Energy, currently: {entity_entry.original_device_class}"
                    )
                elif entity_entry.unit_of_measurement != UnitOfEnergy.KILO_WATT_HOUR:
                    errors[CONF_TODAY_ENERGY_GENERATION_ENTITY_ID] = (
                        f"invalid unit needs to be kWh, currently: {entity_entry.unit_of_measurement}"
                    )
                elif (
                    not entity_entry.capabilities
                    or entity_entry.capabilities.get("state_class")
                    != "total_increasing"
                ):
                    state_class = (
                        entity_entry.capabilities.get("state_class")
                        if entity_entry.capabilities
                        else None
                    )
                    errors[CONF_TODAY_ENERGY_GENERATION_ENTITY_ID] = (
                        f"invalid_state_class. Needs to be total_increasing, currently: {state_class}"
                    )
            # If no errors, save the options
            if not errors:
                return self.async_create_entry(
                    title="", data=user_input | {CONF_API_KEY: api_key or None}
                )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_API_KEY,
                        description={
                            "suggested_value": self.config_entry.options.get(
                                CONF_API_KEY, ""
                            )
                        },
                    ): str,
                    vol.Required(
                        CONF_DECLINATION,
                        default=self.config_entry.options[CONF_DECLINATION],
                    ): vol.All(vol.Coerce(int), vol.Range(min=0, max=90)),
                    vol.Required(
                        CONF_AZIMUTH,
                        default=self.config_entry.options.get(CONF_AZIMUTH),
                    ): vol.All(vol.Coerce(int), vol.Range(min=-0, max=360)),
                    vol.Required(
                        CONF_MODULES_POWER,
                        default=self.config_entry.options[CONF_MODULES_POWER],
                    ): vol.All(vol.Coerce(int), vol.Range(min=1)),
                    vol.Optional(
                        CONF_DAMPING_MORNING,
                        default=self.config_entry.options.get(
                            CONF_DAMPING_MORNING, 0.0
                        ),
                    ): vol.Coerce(float),
                    vol.Optional(
                        CONF_DAMPING_EVENING,
                        default=self.config_entry.options.get(
                            CONF_DAMPING_EVENING, 0.0
                        ),
                    ): vol.Coerce(float),
                    vol.Optional(
                        CONF_INVERTER_SIZE,
                        description={
                            "suggested_value": self.config_entry.options.get(
                                CONF_INVERTER_SIZE
                            )
                        },
                    ): vol.Coerce(int),
                    vol.Optional(
                        CONF_SEND_ACTUALS,
                        description={
                            "suggested_value": self.config_entry.options.get(
                                CONF_SEND_ACTUALS, False
                            )
                        },
                    ): vol.Coerce(bool),
                    vol.Optional(
                        CONF_TODAY_ENERGY_GENERATION_ENTITY_ID,
                        description={
                            "suggested_value": self.config_entry.options.get(
                                CONF_TODAY_ENERGY_GENERATION_ENTITY_ID, False
                            )
                        },
                    ): str,
                }
            ),
            errors=errors,
        )
