"""Data Schema for command line."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TemplateSelector,
    TextSelector,
)
from homeassistant.const import (
    CONF_COMMAND,
    CONF_DEVICE_CLASS,
    CONF_NAME,
    CONF_PAYLOAD_OFF,
    CONF_PAYLOAD_ON,
    CONF_TYPE,
    CONF_UNIQUE_ID,
    CONF_VALUE_TEMPLATE,
    CONF_COMMAND_CLOSE,
    CONF_COMMAND_OPEN,
    CONF_COMMAND_STATE,
    CONF_COMMAND_STOP,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_COMMAND_OFF,
    CONF_COMMAND_ON,
    CONF_ICON_TEMPLATE,
)

from .const import CONF_COMMAND_TIMEOUT, DEFAULT_TIMEOUT, PLATFORMS

DEFAULT_NAME = "Command Line"
DEFAULT_PAYLOAD_ON = "ON"
DEFAULT_PAYLOAD_OFF = "OFF"
CONF_JSON_ATTRIBUTES = "json_attributes"

DATA_SCHEMA_COMMON = vol.Schema(
    {
        vol.Required(CONF_TYPE): SelectSelector(
            SelectSelectorConfig(options=PLATFORMS, mode=SelectSelectorMode.LIST)
        ),
        vol.Required(CONF_NAME, default=DEFAULT_NAME): TextSelector(),
    }
)

DATA_SCHEMA_UNIQUE_ID = vol.Schema({vol.Optional(CONF_UNIQUE_ID): TextSelector()})

DATA_SCHEMA_BINARY_SENSOR = vol.Schema(
    {
        vol.Required(CONF_COMMAND): TextSelector(),
        vol.Optional(CONF_PAYLOAD_OFF, default=DEFAULT_PAYLOAD_OFF): TextSelector(),
        vol.Optional(CONF_PAYLOAD_ON, default=DEFAULT_PAYLOAD_ON): TextSelector(),
        vol.Optional(CONF_DEVICE_CLASS): SelectSelector(
            SelectSelectorConfig(
                options=[enum for enum in BinarySensorDeviceClass],
                mode=SelectSelectorMode.DROPDOWN,
            )
        ),
        vol.Optional(CONF_VALUE_TEMPLATE): TemplateSelector(),
        vol.Optional(CONF_COMMAND_TIMEOUT, default=DEFAULT_TIMEOUT): NumberSelector(
            NumberSelectorConfig(min=0, max=100, step=1, mode=NumberSelectorMode.BOX)
        ),
    }
)


DATA_SCHEMA_SENSOR = vol.Schema(
    {
        vol.Required(CONF_COMMAND): TextSelector(),
        vol.Optional(CONF_COMMAND_TIMEOUT, default=DEFAULT_TIMEOUT): NumberSelector(
            NumberSelectorConfig(min=0, max=100, step=1, mode=NumberSelectorMode.BOX)
        ),
        vol.Optional(CONF_JSON_ATTRIBUTES): SelectSelector(
            SelectSelectorConfig(options=[""], multiple=True, custom_value=True)
        ),
        vol.Optional(CONF_DEVICE_CLASS): SelectSelector(
            SelectSelectorConfig(
                options=[enum for enum in SensorDeviceClass],
                mode=SelectSelectorMode.DROPDOWN,
            )
        ),
        vol.Optional(CONF_UNIT_OF_MEASUREMENT): TextSelector(),
        vol.Optional(CONF_VALUE_TEMPLATE): TemplateSelector(),
    }
)


DATA_SCHEMA_COVER = vol.Schema(
    {
        vol.Optional(CONF_COMMAND_CLOSE, default="true"): TextSelector(),
        vol.Optional(CONF_COMMAND_OPEN, default="true"): TextSelector(),
        vol.Optional(CONF_COMMAND_STATE): TextSelector(),
        vol.Optional(CONF_COMMAND_STOP, default="true"): TextSelector(),
        vol.Optional(CONF_VALUE_TEMPLATE): TemplateSelector(),
        vol.Optional(CONF_COMMAND_TIMEOUT, default=DEFAULT_TIMEOUT): NumberSelector(
            NumberSelectorConfig(min=0, max=100, step=1, mode=NumberSelectorMode.BOX)
        ),
    }
)

DATA_SCHEMA_NOTIFY = vol.Schema(
    {
        vol.Required(CONF_COMMAND): TextSelector(),
        vol.Optional(CONF_COMMAND_TIMEOUT, default=DEFAULT_TIMEOUT): NumberSelector(
            NumberSelectorConfig(min=0, max=100, step=1, mode=NumberSelectorMode.BOX)
        ),
    }
)

DATA_SCHEMA_SWITCH = vol.Schema(
    {
        vol.Optional(CONF_COMMAND_OFF, default="true"): TextSelector(),
        vol.Optional(CONF_COMMAND_ON, default="true"): TextSelector(),
        vol.Optional(CONF_COMMAND_STATE): TextSelector(),
        vol.Optional(CONF_VALUE_TEMPLATE): TemplateSelector(),
        vol.Optional(CONF_ICON_TEMPLATE): TemplateSelector(),
        vol.Optional(CONF_COMMAND_TIMEOUT, default=DEFAULT_TIMEOUT): NumberSelector(
            NumberSelectorConfig(min=0, max=100, step=1, mode=NumberSelectorMode.BOX)
        ),
    }
)
