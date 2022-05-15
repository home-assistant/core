"""Data Schema for command line."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import (
    CONF_COMMAND,
    CONF_COMMAND_CLOSE,
    CONF_COMMAND_OFF,
    CONF_COMMAND_ON,
    CONF_COMMAND_OPEN,
    CONF_COMMAND_STATE,
    CONF_COMMAND_STOP,
    CONF_DEVICE_CLASS,
    CONF_ICON_TEMPLATE,
    CONF_NAME,
    CONF_PAYLOAD_OFF,
    CONF_PAYLOAD_ON,
    CONF_PLATFORM,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_VALUE_TEMPLATE,
    Platform,
)
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TemplateSelector,
    TextSelector,
)

from .const import CONF_COMMAND_TIMEOUT, DEFAULT_TIMEOUT

DEFAULT_NAME = "Command Line"
DEFAULT_PAYLOAD_ON = "ON"
DEFAULT_PAYLOAD_OFF = "OFF"
CONF_JSON_ATTRIBUTES = "json_attributes"

SELECT_PLATFORMS = [
    SelectOptionDict(label="Binary Sensor", value=Platform.BINARY_SENSOR),
    SelectOptionDict(label="Cover", value=Platform.COVER),
    SelectOptionDict(label="Notify", value=Platform.NOTIFY),
    SelectOptionDict(label="Sensor", value=Platform.SENSOR),
    SelectOptionDict(label="Switch", value=Platform.SWITCH),
]

DATA_SCHEMA_COMMON = vol.Schema(
    {
        vol.Required(CONF_PLATFORM): SelectSelector(
            SelectSelectorConfig(options=SELECT_PLATFORMS, mode=SelectSelectorMode.LIST)
        ),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): TextSelector(),
    }
)

DATA_SCHEMA_BINARY_SENSOR = vol.Schema(
    {
        vol.Required(CONF_COMMAND): TextSelector(),
        vol.Optional(CONF_PAYLOAD_OFF, default=DEFAULT_PAYLOAD_OFF): TextSelector(),
        vol.Optional(CONF_PAYLOAD_ON, default=DEFAULT_PAYLOAD_ON): TextSelector(),
        vol.Optional(CONF_DEVICE_CLASS): SelectSelector(
            SelectSelectorConfig(
                options=list(BinarySensorDeviceClass),
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
                options=list(SensorDeviceClass),
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
