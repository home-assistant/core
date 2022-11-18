"""Adds config flow for Scrape integration."""
from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.components.rest import create_rest_data_from_config
from homeassistant.components.rest.data import DEFAULT_TIMEOUT
from homeassistant.components.rest.schema import DEFAULT_METHOD, METHODS
from homeassistant.components.sensor import (
    CONF_STATE_CLASS,
    SensorDeviceClass,
    SensorStateClass,
)
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
    CONF_UNIT_OF_MEASUREMENT,
    CONF_USERNAME,
    CONF_VALUE_TEMPLATE,
    CONF_VERIFY_SSL,
    HTTP_BASIC_AUTHENTICATION,
    HTTP_DIGEST_AUTHENTICATION,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.core import async_get_hass
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaConfigFlowHandler,
    SchemaFlowError,
    SchemaFlowFormStep,
    SchemaFlowMenuStep,
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

SENSOR_SETUP_OPT = {
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
            options=[TEMP_CELSIUS, TEMP_FAHRENHEIT],
            custom_value=True,
            mode=SelectSelectorMode.DROPDOWN,
        )
    ),
}

SENSOR_SETUP = {
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): TextSelector(),
}


def validate_rest_setup(user_input: dict[str, Any]) -> dict[str, Any]:
    """Validate rest setup."""
    hass = async_get_hass()
    rest_config: dict[str, Any] = COMBINED_SCHEMA(user_input)
    try:
        rest = create_rest_data_from_config(hass, rest_config)
        asyncio.run_coroutine_threadsafe(rest.async_update(), hass.loop)
    except Exception as err:
        raise SchemaFlowError("resource_error") from err
    return user_input


def validate_sensor_setup(user_input: dict[str, Any]) -> dict[str, Any]:
    """Validate sensor setup."""
    return {"sensors": [user_input]}


DATA_SCHEMA_RESOURCE = vol.Schema(RESOURCE_SETUP)
DATA_SCHEMA_SENSOR = vol.Schema({**SENSOR_SETUP, **SENSOR_SETUP_OPT})
DATA_SCHEMA_SENSOR_OPT = vol.Schema(SENSOR_SETUP_OPT)

CONFIG_FLOW: dict[str, SchemaFlowFormStep | SchemaFlowMenuStep] = {
    "user": SchemaFlowFormStep(
        schema=DATA_SCHEMA_RESOURCE,
        next_step=lambda _: "sensor",
        validate_user_input=validate_rest_setup,
    ),
    "sensor": SchemaFlowFormStep(
        schema=DATA_SCHEMA_SENSOR,
        validate_user_input=validate_sensor_setup,
    ),
}


class ScrapeConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle a config flow for Scrape."""

    config_flow = CONFIG_FLOW

    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        return options[CONF_RESOURCE]

    def async_config_flow_finished(self, options: Mapping[str, Any]) -> None:
        """Check for duplicate records."""
        data: dict[str, Any] = dict(options)
        self._async_abort_entries_match(data)
