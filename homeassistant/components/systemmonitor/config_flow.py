"""Config flow for systemmonitor."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import psutil
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
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import CONF_ARG, CONF_INDEX, DOMAIN, IF_ADDRS_FAMILY


@dataclass
class SensorConfig:
    """Description for Sensor config."""

    name: str
    mandatory_arg: bool
    enable_sensor: bool
    argument: str | None = None


def get_paths() -> set[str]:
    """Return all paths to mount points."""
    partitions = psutil.disk_partitions()
    paths: set[str] = set()
    for diskpart in partitions:
        paths.add(diskpart.mountpoint)
    return paths


def get_networks() -> set[str]:
    """Return all networks."""
    nics_used = set()
    addresses = psutil.net_if_addrs()
    for nic, address_list in addresses.items():
        for addr in address_list:
            if addr.family == IF_ADDRS_FAMILY["ipv4_address"]:
                nics_used.add(nic)
            if addr.family == IF_ADDRS_FAMILY["ipv6_address"]:
                nics_used.add(nic)
    return nics_used


SENSOR_CONFIG: dict[str, SensorConfig] = {
    "disk_free": SensorConfig(
        name="Disk free",
        mandatory_arg=False,
        enable_sensor=True,
        argument="disk",
    ),
    "disk_use": SensorConfig(
        name="Disk use",
        mandatory_arg=False,
        enable_sensor=True,
        argument="disk",
    ),
    "disk_use_percent": SensorConfig(
        name="Disk use (percent)",
        mandatory_arg=False,
        enable_sensor=False,
        argument="disk",
    ),
    "ipv4_address": SensorConfig(
        name="IPv4 address",
        mandatory_arg=True,
        enable_sensor=False,
        argument="network",
    ),
    "ipv6_address": SensorConfig(
        name="IPv6 address",
        mandatory_arg=True,
        enable_sensor=False,
        argument="network",
    ),
    "last_boot": SensorConfig(
        name="Last boot",
        mandatory_arg=False,
        enable_sensor=False,
    ),
    "load_15m": SensorConfig(
        name="Load (15m)",
        mandatory_arg=False,
        enable_sensor=False,
    ),
    "load_1m": SensorConfig(
        name="Load (1m)",
        mandatory_arg=False,
        enable_sensor=False,
    ),
    "load_5m": SensorConfig(
        name="Load (5m)",
        mandatory_arg=False,
        enable_sensor=False,
    ),
    "memory_free": SensorConfig(
        name="Memory free",
        mandatory_arg=False,
        enable_sensor=True,
    ),
    "memory_use": SensorConfig(
        name="Memory use",
        mandatory_arg=False,
        enable_sensor=True,
    ),
    "memory_use_percent": SensorConfig(
        name="Memory use (percent)",
        mandatory_arg=False,
        enable_sensor=False,
    ),
    "network_in": SensorConfig(
        name="Network in",
        mandatory_arg=True,
        enable_sensor=False,
        argument="network",
    ),
    "network_out": SensorConfig(
        name="Network out",
        mandatory_arg=True,
        enable_sensor=False,
        argument="network",
    ),
    "packets_in": SensorConfig(
        name="Packets in",
        mandatory_arg=True,
        enable_sensor=False,
        argument="network",
    ),
    "packets_out": SensorConfig(
        name="Packets out",
        mandatory_arg=True,
        enable_sensor=False,
        argument="network",
    ),
    "throughput_network_in": SensorConfig(
        name="Network throughput in",
        mandatory_arg=True,
        enable_sensor=False,
        argument="network",
    ),
    "throughput_network_out": SensorConfig(
        name="Network throughput out",
        mandatory_arg=True,
        enable_sensor=False,
        argument="network",
    ),
    "process": SensorConfig(
        name="Process",
        mandatory_arg=True,
        enable_sensor=False,
    ),
    "processor_use": SensorConfig(
        name="Processor use",
        mandatory_arg=False,
        enable_sensor=True,
    ),
    "processor_temperature": SensorConfig(
        name="Processor temperature",
        mandatory_arg=False,
        enable_sensor=False,
    ),
    "swap_free": SensorConfig(
        name="Swap free",
        mandatory_arg=False,
        enable_sensor=False,
    ),
    "swap_use": SensorConfig(
        name="Swap use",
        mandatory_arg=False,
        enable_sensor=False,
    ),
    "swap_use_percent": SensorConfig(
        name="Swap use (percent)",
        mandatory_arg=False,
        enable_sensor=False,
    ),
}


SENSOR_SETUP = {
    vol.Required(CONF_TYPE): SelectSelector(
        SelectSelectorConfig(
            options=list(SENSOR_CONFIG),
            multiple=False,
            custom_value=False,
            mode=SelectSelectorMode.DROPDOWN,
            translation_key="type",
        )
    ),
    vol.Optional(CONF_ARG): ObjectSelector(),
}


def get_unique_id_and_name(user_input: dict[str, Any]) -> tuple:
    """Return unique id and name."""
    unique_id = f"{SENSOR_CONFIG[user_input[CONF_TYPE]].name}-{user_input.get(CONF_ARG, '')}".rstrip()
    name = f"{SENSOR_CONFIG[user_input[CONF_TYPE]].name} {user_input.get(CONF_ARG, '')}".rstrip()

    return unique_id, name


async def validate_first_time_sensors_setup(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Validate first time setup."""
    # Standard behavior is to merge the result with the options.
    # In this case, we want to add a sub-item so we update the options directly.
    sensors: list[dict[str, Any]] = handler.options.setdefault(SENSOR_DOMAIN, [])

    paths = get_paths()
    networks = get_networks()
    for sensor_type, sensor_config in SENSOR_CONFIG.items():
        sensor: dict[str, str | None] = {}
        if sensor_type == "process":  # Can't setup "process" automatically
            continue

        if sensor_config.argument == "disk":
            for path in paths:
                sensor[CONF_TYPE] = sensor_type
                sensor[CONF_ARG] = path
                sensor[CONF_UNIQUE_ID], sensor[CONF_NAME] = get_unique_id_and_name(
                    {CONF_TYPE: sensor_type, CONF_ARG: path}
                )

                sensors.append(sensor)
            continue

        if sensor_config.argument == "network":
            for network in networks:
                sensor[CONF_TYPE] = sensor_type
                sensor[CONF_ARG] = network
                sensor[CONF_UNIQUE_ID], sensor[CONF_NAME] = get_unique_id_and_name(
                    {CONF_TYPE: sensor_type, CONF_ARG: network}
                )

                sensors.append(sensor)
            continue

        sensor[CONF_UNIQUE_ID], sensor[CONF_NAME] = get_unique_id_and_name(
            {CONF_TYPE: sensor_type, CONF_ARG: None}
        )
        sensor[CONF_TYPE] = sensor_type
        sensor[CONF_ARG] = None
        sensors.append(sensor)

    return {}


async def validate_sensor_setup(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Validate sensor input."""
    user_input[CONF_UNIQUE_ID], user_input[CONF_NAME] = get_unique_id_and_name(
        user_input
    )

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
        sensor[CONF_UNIQUE_ID], sensor[CONF_NAME] = get_unique_id_and_name(user_input)
        sensor[CONF_TYPE] = sensor_config[CONF_TYPE]
        sensor[CONF_ARG] = sensor_config[CONF_ARG]

        if (
            SENSOR_CONFIG[sensor[CONF_TYPE]].mandatory_arg is True
            and sensor.get(CONF_ARG) is None
        ):
            raise SchemaFlowError("missing_arg")

        sensors.append(sensor)
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
    _, user_input[CONF_NAME] = get_unique_id_and_name(user_input)

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
        return "System Monitor"
