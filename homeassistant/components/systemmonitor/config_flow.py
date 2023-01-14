"""Config flow for systemmonitor."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
import uuid

import voluptuous as vol

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import CONF_NAME, CONF_RESOURCES, CONF_TYPE, CONF_UNIQUE_ID
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
    SchemaConfigFlowHandler,
    SchemaFlowError,
    SchemaFlowFormStep,
    SchemaFlowMenuStep,
)
from homeassistant.helpers.selector import (
    ObjectSelector,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import CONF_ARG, CONF_INDEX, DOMAIN


@dataclass
class SensorConfig:
    """Description for Sensor config."""

    name: str
    mandatory_arg: bool


SENSOR_CONFIG: dict[str, SensorConfig] = {
    "disk_free": SensorConfig(name="Disk free", mandatory_arg=False),
    "disk_use": SensorConfig(name="Disk use", mandatory_arg=False),
    "disk_use_percent": SensorConfig(name="Disk use (percent)", mandatory_arg=False),
    "ipv4_address": SensorConfig(name="IPv4 address", mandatory_arg=True),
    "ipv6_address": SensorConfig(name="IPv6 address", mandatory_arg=True),
    "last_boot": SensorConfig(name="Last boot", mandatory_arg=False),
    "load_15m": SensorConfig(name="Load (15m)", mandatory_arg=False),
    "load_1m": SensorConfig(name="Load (1m)", mandatory_arg=False),
    "load_5m": SensorConfig(name="Load (5m)", mandatory_arg=False),
    "memory_free": SensorConfig(name="Memory free", mandatory_arg=False),
    "memory_use": SensorConfig(name="Memory use", mandatory_arg=False),
    "memory_use_percent": SensorConfig(
        name="Memory use (percent)", mandatory_arg=False
    ),
    "network_in": SensorConfig(name="Network in", mandatory_arg=True),
    "network_out": SensorConfig(name="Network out", mandatory_arg=True),
    "packets_in": SensorConfig(name="Packets in", mandatory_arg=True),
    "packets_out": SensorConfig(name="Packets out", mandatory_arg=True),
    "throughput_network_in": SensorConfig(
        name="Network throughput in", mandatory_arg=True
    ),
    "throughput_network_out": SensorConfig(
        name="Network throughput out", mandatory_arg=True
    ),
    "process": SensorConfig(name="Process", mandatory_arg=True),
    "processor_use": SensorConfig(name="Processor use", mandatory_arg=False),
    "processor_temperature": SensorConfig(
        name="Processor temperature", mandatory_arg=False
    ),
    "swap_free": SensorConfig(name="Swap free", mandatory_arg=False),
    "swap_use": SensorConfig(name="Swap use", mandatory_arg=False),
    "swap_use_percent": SensorConfig(name="Swap use (percent)", mandatory_arg=False),
}

TYPE_OPTIONS = [
    SelectOptionDict(value="disk_free", label="Disk free"),
    SelectOptionDict(value="disk_use", label="Disk use"),
    SelectOptionDict(value="disk_use_percent", label="Disk use (percent)"),
    SelectOptionDict(value="ipv4_address", label="IPv4 address"),
    SelectOptionDict(value="ipv6_address", label="IPv6 address"),
    SelectOptionDict(value="last_boot", label="Last boot"),
    SelectOptionDict(value="load_15m", label="Load (15m)"),
    SelectOptionDict(value="load_1m", label="Load (1m)"),
    SelectOptionDict(value="load_5m", label="Load (5m)"),
    SelectOptionDict(value="memory_free", label="Memory free"),
    SelectOptionDict(value="memory_use", label="Memory use"),
    SelectOptionDict(value="memory_use_percent", label="Memory use (percent)"),
    SelectOptionDict(value="network_in", label="Network in"),
    SelectOptionDict(value="network_out", label="Network out"),
    SelectOptionDict(value="packets_in", label="Packets in"),
    SelectOptionDict(value="packets_out", label="Packets out"),
    SelectOptionDict(value="throughput_network_in", label="Network throughput in"),
    SelectOptionDict(value="throughput_network_out", label="Network throughput out"),
    SelectOptionDict(value="process", label="Process"),
    SelectOptionDict(value="processor_use", label="Processor use"),
    SelectOptionDict(value="processor_temperature", label="Processor temperature"),
    SelectOptionDict(value="swap_free", label="Swap free"),
    SelectOptionDict(value="swap_use", label="Swap use"),
    SelectOptionDict(value="swap_use_percent", label="Swap use (percent)"),
]

SENSOR_SETUP = {
    vol.Required(CONF_TYPE): SelectSelector(
        SelectSelectorConfig(
            options=TYPE_OPTIONS,
            multiple=False,
            custom_value=False,
            mode=SelectSelectorMode.DROPDOWN,
        )
    ),
    vol.Optional(CONF_ARG): ObjectSelector(),
}


async def validate_sensor_setup(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Validate sensor input."""
    user_input[CONF_UNIQUE_ID] = str(uuid.uuid1())
    user_input[
        CONF_NAME
    ] = f"{SENSOR_CONFIG[user_input[CONF_TYPE]].name} {user_input.get(CONF_ARG, '')}".rstrip()

    if (
        SENSOR_CONFIG[user_input[CONF_TYPE]].mandatory_arg is True
        and user_input.get(CONF_ARG) is None
    ):
        raise SchemaFlowError("missing_arg")

    # Standard behavior is to merge the result with the options.
    # In this case, we want to add a sub-item so we update the options directly.
    sensors: list[dict[str, Any]] = handler.options.setdefault(SENSOR_DOMAIN, [])
    sensors.append(user_input)
    return {}


async def validate_sensor_setup_import(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Validate sensor input."""
    sensors: list[dict[str, Any]] = handler.options.setdefault(SENSOR_DOMAIN, [])

    for sensor_config in user_input[CONF_RESOURCES]:
        sensor = {}
        sensor[CONF_UNIQUE_ID] = str(uuid.uuid1())
        sensor[
            CONF_NAME
        ] = f"{SENSOR_CONFIG[sensor_config[CONF_TYPE]].name} {sensor_config.get(CONF_ARG, '')}".rstrip()

        if (
            SENSOR_CONFIG[sensor_config[CONF_TYPE]].mandatory_arg is True
            and sensor_config.get(CONF_ARG) is None
        ):
            raise SchemaFlowError("missing_arg")

        sensors.append(sensor_config)
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
    return handler.options[SENSOR_DOMAIN][idx]  # type: ignore[no-any-return]


async def validate_sensor_edit(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Update edited sensor."""
    user_input[
        CONF_NAME
    ] = f"{SENSOR_CONFIG[user_input[CONF_TYPE]].name} {user_input.get(CONF_ARG, '')}".rstrip()

    # Standard behavior is to merge the result with the options.
    # In this case, we want to add a sub-item so we update the options directly.
    idx: int = handler.flow_state["_idx"]
    handler.options[SENSOR_DOMAIN][idx].update(user_input)
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


DATA_SCHEMA_SENSOR = vol.Schema(SENSOR_SETUP)

CONFIG_FLOW = {
    "user": SchemaFlowFormStep(
        schema=DATA_SCHEMA_SENSOR,
        validate_user_input=validate_sensor_setup,
    ),
    "import": SchemaFlowFormStep(
        schema=DATA_SCHEMA_SENSOR,
        validate_user_input=validate_sensor_setup_import,
    ),
}
OPTIONS_FLOW = {
    "init": SchemaFlowMenuStep(["add_sensor", "select_edit_sensor", "remove_sensor"]),
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
        DATA_SCHEMA_SENSOR,
        suggested_values=get_edit_sensor_suggested_values,
        validate_user_input=validate_sensor_edit,
    ),
    "remove_sensor": SchemaFlowFormStep(
        get_remove_sensor_schema,
        suggested_values=None,
        validate_user_input=validate_remove_sensor,
    ),
}


class SystemmonitorConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle a config flow for Systemmonitor."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW

    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        return "Systemmonitor"
