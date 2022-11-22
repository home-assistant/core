"""Adds config flow for Scrape integration."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any
import uuid

import voluptuous as vol

from homeassistant.components.rest import create_rest_data_from_config
from homeassistant.components.rest.data import DEFAULT_TIMEOUT
from homeassistant.components.rest.schema import DEFAULT_METHOD, METHODS
from homeassistant.components.sensor import (
    CONF_STATE_CLASS,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ATTRIBUTE,
    CONF_AUTHENTICATION,
    CONF_DEVICE_CLASS,
    CONF_HEADERS,
    CONF_METHOD,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_RESOURCE,
    CONF_TIMEOUT,
    CONF_UNIQUE_ID,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_USERNAME,
    CONF_VALUE_TEMPLATE,
    CONF_VERIFY_SSL,
    HTTP_BASIC_AUTHENTICATION,
    HTTP_DIGEST_AUTHENTICATION,
    UnitOfTemperature,
)
from homeassistant.core import async_get_hass, callback
from homeassistant.data_entry_flow import FlowResult, schema_with_suggested_values
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
    SchemaConfigFlowHandler,
    SchemaFlowError,
    SchemaFlowFormStep,
    SchemaFlowMenuStep,
    SchemaOptionsFlowHandler,
)
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    ObjectSelector,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TemplateSelector,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from . import COMBINED_SCHEMA
from .const import CONF_INDEX, CONF_SELECT, DEFAULT_NAME, DEFAULT_VERIFY_SSL, DOMAIN

RESOURCE_SETUP = {
    vol.Required(CONF_RESOURCE): TextSelector(
        TextSelectorConfig(type=TextSelectorType.URL)
    ),
    vol.Optional(CONF_METHOD, default=DEFAULT_METHOD): SelectSelector(
        SelectSelectorConfig(options=METHODS, mode=SelectSelectorMode.DROPDOWN)
    ),
    vol.Optional(CONF_AUTHENTICATION): SelectSelector(
        SelectSelectorConfig(
            options=[HTTP_BASIC_AUTHENTICATION, HTTP_DIGEST_AUTHENTICATION],
            mode=SelectSelectorMode.DROPDOWN,
        )
    ),
    vol.Optional(CONF_USERNAME): TextSelector(),
    vol.Optional(CONF_PASSWORD): TextSelector(
        TextSelectorConfig(type=TextSelectorType.PASSWORD)
    ),
    vol.Optional(CONF_HEADERS): ObjectSelector(),
    vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): BooleanSelector(),
    vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): NumberSelector(
        NumberSelectorConfig(min=0, step=1, mode=NumberSelectorMode.BOX)
    ),
}

SENSOR_SETUP = {
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): TextSelector(),
    vol.Required(CONF_SELECT): TextSelector(),
    vol.Optional(CONF_INDEX, default=0): NumberSelector(
        NumberSelectorConfig(min=0, step=1, mode=NumberSelectorMode.BOX)
    ),
    vol.Optional(CONF_ATTRIBUTE): TextSelector(),
    vol.Optional(CONF_VALUE_TEMPLATE): TemplateSelector(),
    vol.Optional(CONF_DEVICE_CLASS): SelectSelector(
        SelectSelectorConfig(
            options=[cls.value for cls in SensorDeviceClass],
            mode=SelectSelectorMode.DROPDOWN,
        )
    ),
    vol.Optional(CONF_STATE_CLASS): SelectSelector(
        SelectSelectorConfig(
            options=[cls.value for cls in SensorStateClass],
            mode=SelectSelectorMode.DROPDOWN,
        )
    ),
    vol.Optional(CONF_UNIT_OF_MEASUREMENT): SelectSelector(
        SelectSelectorConfig(
            options=[cls.value for cls in UnitOfTemperature],
            custom_value=True,
            mode=SelectSelectorMode.DROPDOWN,
        )
    ),
}


def validate_rest_setup(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Validate rest setup."""
    hass = async_get_hass()
    rest_config: dict[str, Any] = COMBINED_SCHEMA(user_input)
    try:
        create_rest_data_from_config(hass, rest_config)
    except Exception as err:
        raise SchemaFlowError("resource_error") from err
    return user_input


def validate_sensor(user_input: dict[str, Any]) -> dict[str, Any]:
    """Validate sensor."""
    user_input[CONF_INDEX] = int(user_input[CONF_INDEX])
    if not user_input.get(CONF_UNIQUE_ID):  # Only applies to new sensors
        user_input[CONF_UNIQUE_ID] = str(uuid.uuid1())
    return user_input


def validate_sensor_setup(user_input: dict[str, Any]) -> dict[str, Any]:
    """Validate sensor setup."""
    return {"sensor": [validate_sensor(user_input)]}


DATA_SCHEMA_RESOURCE = vol.Schema(RESOURCE_SETUP)
DATA_SCHEMA_SENSOR = vol.Schema(SENSOR_SETUP)

CONFIG_FLOW = {
    "user": SchemaFlowFormStep(
        schema=DATA_SCHEMA_RESOURCE,
        next_step="sensor",
        validate_user_input=validate_rest_setup,
    ),
    "sensor": SchemaFlowFormStep(
        schema=DATA_SCHEMA_SENSOR,
        validate_user_input=validate_sensor_setup,
    ),
}
OPTIONS_FLOW = {
    "init": SchemaFlowMenuStep(["resource", "add_sensor", "select_edit_sensor"]),
    "resource": SchemaFlowFormStep(
        DATA_SCHEMA_RESOURCE,
        validate_user_input=validate_rest_setup,
    ),
}


class ScrapeConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle a config flow for Scrape."""

    config_flow = CONFIG_FLOW

    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        return options[CONF_RESOURCE]

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> ScrapeOptionsFlowHandler:
        """Options callback for Scrape."""
        return ScrapeOptionsFlowHandler(
            config_entry,
            OPTIONS_FLOW,
            ScrapeConfigFlowHandler.async_options_flow_finished,
        )


class ScrapeOptionsFlowHandler(SchemaOptionsFlowHandler):
    """Handle an options flow for Scrape."""

    # `init` and `resource` steps are managed via OPTIONS_FLOW

    _sensor_index: int

    async def async_step_add_sensor(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Add a new sensor."""
        if user_input is not None:
            user_input = validate_sensor(user_input)
            sensors: list[dict[str, Any]] = self.config_entry.options["sensor"]
            sensors.append(user_input)
            return self.async_create_entry(data=self.config_entry.options)

        return self.async_show_form(
            step_id="add_sensor",
            data_schema=DATA_SCHEMA_SENSOR,
        )

    async def async_step_select_edit_sensor(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Select a sensor to edit."""
        if user_input is not None:
            self._sensor_index = int(user_input[CONF_INDEX])
            return await self.async_step_edit_sensor()

        sensors: list[dict[str, Any]] = self.config_entry.options["sensor"]
        return self.async_show_form(
            step_id="select_edit_sensor",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_INDEX): vol.In(
                        {
                            str(index): config[CONF_NAME]
                            for index, config in enumerate(sensors)
                        },
                    )
                }
            ),
        )

    async def async_step_edit_sensor(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Edit a sensor."""
        sensors: list[dict[str, Any]] = self.config_entry.options["sensor"]
        if user_input is not None:
            sensors[self._sensor_index] = validate_sensor(user_input)
            return self.async_create_entry(data=self.config_entry.options)

        return self.async_show_form(
            step_id="edit_sensor",
            data_schema=schema_with_suggested_values(
                DATA_SCHEMA_SENSOR,
                sensors[self._sensor_index],
                self.show_advanced_options,
            ),
        )
