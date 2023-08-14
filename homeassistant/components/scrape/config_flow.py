"""Adds config flow for Scrape integration."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast
import uuid

import voluptuous as vol

from homeassistant.components.rest import create_rest_data_from_config
from homeassistant.components.rest.data import DEFAULT_TIMEOUT
from homeassistant.components.rest.schema import DEFAULT_METHOD, METHODS
from homeassistant.components.sensor import (
    CONF_STATE_CLASS,
    DOMAIN as SENSOR_DOMAIN,
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
    CONF_PAYLOAD,
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
from homeassistant.core import async_get_hass
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
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
from .const import (
    CONF_ENCODING,
    CONF_INDEX,
    CONF_SELECT,
    DEFAULT_ENCODING,
    DEFAULT_NAME,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
)

RESOURCE_SETUP = {
    vol.Required(CONF_RESOURCE): TextSelector(
        TextSelectorConfig(type=TextSelectorType.URL)
    ),
    vol.Optional(CONF_METHOD, default=DEFAULT_METHOD): SelectSelector(
        SelectSelectorConfig(options=METHODS, mode=SelectSelectorMode.DROPDOWN)
    ),
    vol.Optional(CONF_PAYLOAD): ObjectSelector(),
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
    vol.Optional(CONF_ENCODING, default=DEFAULT_ENCODING): TextSelector(),
}

NONE_SENTINEL = "none"

SENSOR_SETUP = {
    vol.Required(CONF_SELECT): TextSelector(),
    vol.Optional(CONF_INDEX, default=0): NumberSelector(
        NumberSelectorConfig(min=0, step=1, mode=NumberSelectorMode.BOX)
    ),
    vol.Optional(CONF_ATTRIBUTE): TextSelector(),
    vol.Optional(CONF_VALUE_TEMPLATE): TemplateSelector(),
    vol.Required(CONF_DEVICE_CLASS): SelectSelector(
        SelectSelectorConfig(
            options=[NONE_SENTINEL]
            + sorted(
                [
                    cls.value
                    for cls in SensorDeviceClass
                    if cls != SensorDeviceClass.ENUM
                ]
            ),
            mode=SelectSelectorMode.DROPDOWN,
            translation_key="device_class",
        )
    ),
    vol.Required(CONF_STATE_CLASS): SelectSelector(
        SelectSelectorConfig(
            options=[NONE_SENTINEL] + sorted([cls.value for cls in SensorStateClass]),
            mode=SelectSelectorMode.DROPDOWN,
            translation_key="state_class",
        )
    ),
    vol.Required(CONF_UNIT_OF_MEASUREMENT): SelectSelector(
        SelectSelectorConfig(
            options=[NONE_SENTINEL] + sorted([cls.value for cls in UnitOfTemperature]),
            custom_value=True,
            mode=SelectSelectorMode.DROPDOWN,
            translation_key="unit_of_measurement",
        )
    ),
}


def _strip_sentinel(options: dict[str, Any]) -> None:
    """Convert sentinel to None."""
    for key in (CONF_DEVICE_CLASS, CONF_STATE_CLASS, CONF_UNIT_OF_MEASUREMENT):
        if options[key] == NONE_SENTINEL:
            options.pop(key)


async def validate_rest_setup(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Validate rest setup."""
    hass = async_get_hass()
    rest_config: dict[str, Any] = COMBINED_SCHEMA(user_input)
    try:
        rest = create_rest_data_from_config(hass, rest_config)
        await rest.async_update()
    except Exception as err:
        raise SchemaFlowError("resource_error") from err
    if rest.data is None:
        raise SchemaFlowError("resource_error")
    return user_input


async def validate_sensor_setup(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Validate sensor input."""
    user_input[CONF_INDEX] = int(user_input[CONF_INDEX])
    user_input[CONF_UNIQUE_ID] = str(uuid.uuid1())

    # Standard behavior is to merge the result with the options.
    # In this case, we want to add a sub-item so we update the options directly.
    sensors: list[dict[str, Any]] = handler.options.setdefault(SENSOR_DOMAIN, [])
    _strip_sentinel(user_input)
    sensors.append(user_input)
    return {}


async def validate_select_sensor(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Store sensor index in flow state."""
    handler.flow_state["_idx"] = int(user_input[CONF_INDEX])
    return {}


async def get_select_sensor_schema(handler: SchemaCommonFlowHandler) -> vol.Schema:
    """Return schema for selecting a sensor."""
    return vol.Schema(
        {
            vol.Required(CONF_INDEX): vol.In(
                {
                    str(index): config[CONF_NAME]
                    for index, config in enumerate(handler.options[SENSOR_DOMAIN])
                },
            )
        }
    )


async def get_edit_sensor_suggested_values(
    handler: SchemaCommonFlowHandler,
) -> dict[str, Any]:
    """Return suggested values for sensor editing."""
    idx: int = handler.flow_state["_idx"]
    suggested_values: dict[str, Any] = dict(handler.options[SENSOR_DOMAIN][idx])
    for key in (CONF_DEVICE_CLASS, CONF_STATE_CLASS, CONF_UNIT_OF_MEASUREMENT):
        if not suggested_values.get(key):
            suggested_values[key] = NONE_SENTINEL
    return suggested_values


async def validate_sensor_edit(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Update edited sensor."""
    user_input[CONF_INDEX] = int(user_input[CONF_INDEX])

    # Standard behavior is to merge the result with the options.
    # In this case, we want to add a sub-item so we update the options directly.
    idx: int = handler.flow_state["_idx"]
    handler.options[SENSOR_DOMAIN][idx].update(user_input)
    _strip_sentinel(handler.options[SENSOR_DOMAIN][idx])
    return {}


async def get_remove_sensor_schema(handler: SchemaCommonFlowHandler) -> vol.Schema:
    """Return schema for sensor removal."""
    return vol.Schema(
        {
            vol.Required(CONF_INDEX): cv.multi_select(
                {
                    str(index): config[CONF_NAME]
                    for index, config in enumerate(handler.options[SENSOR_DOMAIN])
                },
            )
        }
    )


async def validate_remove_sensor(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Validate remove sensor."""
    removed_indexes: set[str] = set(user_input[CONF_INDEX])

    # Standard behavior is to merge the result with the options.
    # In this case, we want to remove sub-items so we update the options directly.
    entity_registry = er.async_get(handler.parent_handler.hass)
    sensors: list[dict[str, Any]] = []
    sensor: dict[str, Any]
    for index, sensor in enumerate(handler.options[SENSOR_DOMAIN]):
        if str(index) not in removed_indexes:
            sensors.append(sensor)
        elif entity_id := entity_registry.async_get_entity_id(
            SENSOR_DOMAIN, DOMAIN, sensor[CONF_UNIQUE_ID]
        ):
            entity_registry.async_remove(entity_id)
    handler.options[SENSOR_DOMAIN] = sensors
    return {}


DATA_SCHEMA_RESOURCE = vol.Schema(RESOURCE_SETUP)
DATA_SCHEMA_EDIT_SENSOR = vol.Schema(SENSOR_SETUP)
DATA_SCHEMA_SENSOR = vol.Schema(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): TextSelector(),
        **SENSOR_SETUP,
    }
)

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
    "init": SchemaFlowMenuStep(
        ["resource", "add_sensor", "select_edit_sensor", "remove_sensor"]
    ),
    "resource": SchemaFlowFormStep(
        DATA_SCHEMA_RESOURCE,
        validate_user_input=validate_rest_setup,
    ),
    "add_sensor": SchemaFlowFormStep(
        DATA_SCHEMA_SENSOR,
        suggested_values=None,
        validate_user_input=validate_sensor_setup,
    ),
    "select_edit_sensor": SchemaFlowFormStep(
        get_select_sensor_schema,
        suggested_values=None,
        validate_user_input=validate_select_sensor,
        next_step="edit_sensor",
    ),
    "edit_sensor": SchemaFlowFormStep(
        DATA_SCHEMA_EDIT_SENSOR,
        suggested_values=get_edit_sensor_suggested_values,
        validate_user_input=validate_sensor_edit,
    ),
    "remove_sensor": SchemaFlowFormStep(
        get_remove_sensor_schema,
        suggested_values=None,
        validate_user_input=validate_remove_sensor,
    ),
}


class ScrapeConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle a config flow for Scrape."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW

    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        return cast(str, options[CONF_RESOURCE])
