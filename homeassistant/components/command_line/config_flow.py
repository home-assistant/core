"""Config flow for Group integration."""
from __future__ import annotations

from collections.abc import Callable, Coroutine, Mapping
from typing import Any, cast

import voluptuous as vol

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.sensor import (
    CONF_STATE_CLASS,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    CONF_COMMAND,
    CONF_COMMAND_CLOSE,
    CONF_COMMAND_OFF,
    CONF_COMMAND_ON,
    CONF_COMMAND_OPEN,
    CONF_COMMAND_STATE,
    CONF_COMMAND_STOP,
    CONF_DEVICE_CLASS,
    CONF_NAME,
    CONF_PAYLOAD_OFF,
    CONF_PAYLOAD_ON,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_VALUE_TEMPLATE,
    Platform,
    UnitOfTemperature,
)
from homeassistant.core import callback
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
    SchemaConfigFlowHandler,
    SchemaFlowFormStep,
    SchemaFlowMenuStep,
)
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    ObjectSelector,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)

from . import CONF_JSON_ATTRIBUTES, DEFAULT_PAYLOAD_OFF, DEFAULT_PAYLOAD_ON
from .const import CONF_COMMAND_TIMEOUT, DEFAULT_TIMEOUT, DOMAIN

NONE_SENTINEL = "none"

PLATFORMS = [
    "binary_sensor",
    "cover",
    "notify",
    "sensor",
    "switch",
]

DEFAULT_CONFIG_SCHEMA = vol.Schema({vol.Required(CONF_NAME): TextSelector()})
BINARY_SENSOR_OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_COMMAND): TextSelector(),
        vol.Optional(CONF_PAYLOAD_OFF, default=DEFAULT_PAYLOAD_OFF): TextSelector(),
        vol.Optional(CONF_PAYLOAD_ON, default=DEFAULT_PAYLOAD_ON): TextSelector(),
        vol.Required(CONF_DEVICE_CLASS): SelectSelector(
            SelectSelectorConfig(
                options=[NONE_SENTINEL]
                + sorted([cls.value for cls in BinarySensorDeviceClass]),
                mode=SelectSelectorMode.DROPDOWN,
                translation_key="binary_sensor_device_class",
            )
        ),
        vol.Optional(CONF_VALUE_TEMPLATE): ObjectSelector(),
        vol.Optional(CONF_COMMAND_TIMEOUT, default=DEFAULT_TIMEOUT): NumberSelector(
            NumberSelectorConfig(min=0, step=1, mode=NumberSelectorMode.BOX)
        ),
    }
)
COVER_OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_COMMAND_CLOSE, default="true"): TextSelector(),
        vol.Optional(CONF_COMMAND_OPEN, default="true"): TextSelector(),
        vol.Optional(CONF_COMMAND_STATE): TextSelector(),
        vol.Optional(CONF_COMMAND_STOP, default="true"): TextSelector(),
        vol.Optional(CONF_VALUE_TEMPLATE): ObjectSelector(),
        vol.Optional(CONF_COMMAND_TIMEOUT, default=DEFAULT_TIMEOUT): NumberSelector(
            NumberSelectorConfig(min=0, step=1, mode=NumberSelectorMode.BOX)
        ),
    }
)
NOTIFY_OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_COMMAND): TextSelector(),
        vol.Optional(CONF_COMMAND_TIMEOUT, default=DEFAULT_TIMEOUT): NumberSelector(
            NumberSelectorConfig(min=0, step=1, mode=NumberSelectorMode.BOX)
        ),
    }
)
SENSOR_OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_COMMAND): TextSelector(),
        vol.Optional(CONF_COMMAND_TIMEOUT, default=DEFAULT_TIMEOUT): NumberSelector(
            NumberSelectorConfig(min=0, step=1, mode=NumberSelectorMode.BOX)
        ),
        vol.Required(CONF_JSON_ATTRIBUTES): SelectSelector(
            SelectSelectorConfig(
                options=[NONE_SENTINEL],
                custom_value=True,
                mode=SelectSelectorMode.DROPDOWN,
            )
        ),
        vol.Required(CONF_UNIT_OF_MEASUREMENT): SelectSelector(
            SelectSelectorConfig(
                options=[NONE_SENTINEL]
                + sorted([cls.value for cls in UnitOfTemperature]),
                custom_value=True,
                mode=SelectSelectorMode.DROPDOWN,
                translation_key="unit_of_measurement",
            )
        ),
        vol.Optional(CONF_VALUE_TEMPLATE): ObjectSelector(),
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
                translation_key="sensor_device_class",
            )
        ),
        vol.Required(CONF_STATE_CLASS): SelectSelector(
            SelectSelectorConfig(
                options=[NONE_SENTINEL]
                + sorted([cls.value for cls in SensorStateClass]),
                mode=SelectSelectorMode.DROPDOWN,
                translation_key="state_class",
            )
        ),
    }
)
SWITCH_OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_COMMAND_OFF, default="true"): TextSelector(),
        vol.Optional(CONF_COMMAND_ON, default="true"): TextSelector(),
        vol.Optional(CONF_COMMAND_STATE): TextSelector(),
        vol.Optional(CONF_VALUE_TEMPLATE): ObjectSelector(),
        vol.Optional(CONF_COMMAND_TIMEOUT, default=DEFAULT_TIMEOUT): NumberSelector(
            NumberSelectorConfig(min=0, step=1, mode=NumberSelectorMode.BOX)
        ),
    }
)


def _strip_sentinel(options: dict[str, Any]) -> None:
    """Convert sentinel to None."""
    for key in (
        CONF_DEVICE_CLASS,
        CONF_STATE_CLASS,
        CONF_UNIT_OF_MEASUREMENT,
        CONF_JSON_ATTRIBUTES,
    ):
        if key in options and options[key] == NONE_SENTINEL:
            options.pop(key)


def add_platform(
    platform: str,
) -> Callable[
    [SchemaCommonFlowHandler, dict[str, Any]], Coroutine[Any, Any, dict[str, Any]]
]:
    """Set group type."""

    async def _set_platform(
        handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
    ) -> dict[str, Any]:
        """Add platform to user input."""
        _strip_sentinel(user_input)
        return {"platform": platform, **user_input}

    return _set_platform


async def choose_options_step(options: dict[str, Any]) -> str:
    """Return next step_id for options flow according to platform."""
    return cast(str, options["platform"])


CONFIG_FLOW = {
    "user": SchemaFlowMenuStep(PLATFORMS),
    "binary_sensor": SchemaFlowFormStep(
        DEFAULT_CONFIG_SCHEMA.extend(BINARY_SENSOR_OPTIONS_SCHEMA.schema),
        validate_user_input=add_platform(Platform.BINARY_SENSOR),
    ),
    "cover": SchemaFlowFormStep(
        DEFAULT_CONFIG_SCHEMA.extend(COVER_OPTIONS_SCHEMA.schema),
        validate_user_input=add_platform(Platform.COVER),
    ),
    "notify": SchemaFlowFormStep(
        DEFAULT_CONFIG_SCHEMA.extend(NOTIFY_OPTIONS_SCHEMA.schema),
        validate_user_input=add_platform(Platform.COVER),
    ),
    "sensor": SchemaFlowFormStep(
        DEFAULT_CONFIG_SCHEMA.extend(SENSOR_OPTIONS_SCHEMA.schema),
        validate_user_input=add_platform(Platform.SENSOR),
    ),
    "switch": SchemaFlowFormStep(
        DEFAULT_CONFIG_SCHEMA.extend(SWITCH_OPTIONS_SCHEMA.schema),
        validate_user_input=add_platform(Platform.SWITCH),
    ),
}

OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(next_step=choose_options_step),
    "binary_sensor": SchemaFlowFormStep(BINARY_SENSOR_OPTIONS_SCHEMA),
    "cover": SchemaFlowFormStep(COVER_OPTIONS_SCHEMA),
    "notify": SchemaFlowFormStep(NOTIFY_OPTIONS_SCHEMA),
    "sensor": SchemaFlowFormStep(SENSOR_OPTIONS_SCHEMA),
    "switch": SchemaFlowFormStep(SWITCH_OPTIONS_SCHEMA),
}


class CommandLineConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle a config or options flow for groups."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW

    @callback
    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        return cast(str, options["name"])
