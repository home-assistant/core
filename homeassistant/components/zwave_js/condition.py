"""Offer Z-Wave JS automation conditions."""

import abc
from collections.abc import Callable, Iterable
from typing import TYPE_CHECKING, Any, Unpack, override

import probatio
from zwave_js_server.const import CommandClass
from zwave_js_server.model.node import Node as ZwaveNode

from homeassistant.const import ATTR_DEVICE_ID, CONF_OPTIONS
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.condition import (
    ATTR_BEHAVIOR,
    BEHAVIOR_ALL,
    BEHAVIOR_ANY,
    Condition,
    ConditionCheckParams,
    ConditionConfig,
)
from homeassistant.helpers.typing import ConfigType

from .config_validation import BITMASK_SCHEMA, COMMAND_CLASS_SCHEMA
from .const import (
    ATTR_COMMAND_CLASS,
    ATTR_CONFIG_PARAMETER,
    ATTR_CONFIG_PARAMETER_BITMASK,
    ATTR_ENDPOINT,
    ATTR_PROPERTY,
    ATTR_PROPERTY_KEY,
    ATTR_VALUE,
    NODE_STATUSES,
)
from .helpers import (
    async_bypass_dynamic_config_validation,
    async_get_node_from_device_id,
    get_zwave_value_from_config,
    node_status_matches,
    value_matches_state,
)

CONF_STATUS = "status"

# Conditions compare against state labels, so strings must be kept as given
_CONDITION_VALUE_SCHEMA = probatio.Any(bool, int, float, dict, cv.string)

_BASE_SCHEMA_DICT: dict[probatio.Marker, Any] = {
    probatio.Required(ATTR_DEVICE_ID): probatio.All(cv.ensure_list, [cv.string]),
    probatio.Required(ATTR_BEHAVIOR, default=BEHAVIOR_ANY): probatio.In(
        [BEHAVIOR_ANY, BEHAVIOR_ALL]
    ),
}

_NODE_STATUS_OPTIONS_SCHEMA_DICT: dict[probatio.Marker, Any] = {
    **_BASE_SCHEMA_DICT,
    probatio.Required(CONF_STATUS): probatio.In(NODE_STATUSES),
}

_VALUE_OPTIONS_SCHEMA_DICT: dict[probatio.Marker, Any] = {
    **_BASE_SCHEMA_DICT,
    probatio.Required(ATTR_COMMAND_CLASS): COMMAND_CLASS_SCHEMA,
    probatio.Required(ATTR_PROPERTY): probatio.Any(probatio.Coerce(int), cv.string),
    probatio.Optional(ATTR_ENDPOINT): probatio.Coerce(int),
    probatio.Optional(ATTR_PROPERTY_KEY): probatio.Any(probatio.Coerce(int), cv.string),
    probatio.Required(ATTR_VALUE): _CONDITION_VALUE_SCHEMA,
}

_CONFIG_PARAMETER_OPTIONS_SCHEMA_DICT: dict[probatio.Marker, Any] = {
    **_BASE_SCHEMA_DICT,
    probatio.Required(ATTR_CONFIG_PARAMETER): probatio.Coerce(int),
    probatio.Optional(ATTR_CONFIG_PARAMETER_BITMASK): probatio.Any(
        probatio.Coerce(int), BITMASK_SCHEMA
    ),
    probatio.Optional(ATTR_ENDPOINT, default=0): probatio.Coerce(int),
    probatio.Required(ATTR_VALUE): _CONDITION_VALUE_SCHEMA,
}


def _condition_schema(
    options_schema_dict: dict[probatio.Marker, Any],
) -> probatio.Schema:
    """Return the condition schema for an options schema dict."""
    return probatio.Schema(
        {probatio.Required(CONF_OPTIONS, default={}): options_schema_dict}
    )


@callback
def _async_resolve_nodes(
    hass: HomeAssistant, device_ids: Iterable[str]
) -> set[ZwaveNode]:
    """Resolve targeted device IDs to Z-Wave nodes, skipping any that don't resolve."""
    nodes: set[ZwaveNode] = set()
    for device_id in set(device_ids):
        try:
            nodes.add(async_get_node_from_device_id(hass, device_id))
        except ValueError:
            continue
    return nodes


class _ZwaveNodeCondition(Condition):
    """Base for conditions evaluated per Z-Wave node."""

    _schema: probatio.Schema

    @classmethod
    @override
    async def async_validate_config(
        cls, hass: HomeAssistant, config: ConfigType
    ) -> ConfigType:
        """Validate config."""
        config = cls._schema(config)
        device_ids = config[CONF_OPTIONS][ATTR_DEVICE_ID]
        if async_bypass_dynamic_config_validation(hass, {ATTR_DEVICE_ID: device_ids}):
            return config

        nodes = _async_resolve_nodes(hass, device_ids)
        if not nodes:
            raise probatio.Invalid("No nodes found for the given devices")
        cls._validate_nodes(nodes, config[CONF_OPTIONS])
        return config

    @classmethod
    def _validate_nodes(cls, nodes: set[ZwaveNode], options: dict[str, Any]) -> None:
        """Validate the options against the resolved nodes."""

    def __init__(self, hass: HomeAssistant, config: ConditionConfig) -> None:
        """Initialize condition."""
        super().__init__(hass, config)
        if TYPE_CHECKING:
            assert config.options is not None
        self._options = config.options

    @abc.abstractmethod
    def _node_matches(self, node: ZwaveNode) -> bool:
        """Return whether a node satisfies the condition."""

    @override
    def _async_check(self, **kwargs: Unpack[ConditionCheckParams]) -> bool:
        """Test the condition against all targeted nodes."""
        nodes = _async_resolve_nodes(self._hass, self._options[ATTR_DEVICE_ID])
        combine: Callable[[Iterable[object]], bool] = (
            all if self._options[ATTR_BEHAVIOR] == BEHAVIOR_ALL else any
        )
        return combine(self._node_matches(node) for node in nodes)


class NodeStatusCondition(_ZwaveNodeCondition):
    """Test the status of Z-Wave nodes."""

    _schema = _condition_schema(_NODE_STATUS_OPTIONS_SCHEMA_DICT)

    @override
    def _node_matches(self, node: ZwaveNode) -> bool:
        return node_status_matches(node, self._options[CONF_STATUS])


class _ZwaveValueCondition(_ZwaveNodeCondition):
    """Base for conditions comparing a Z-Wave value."""

    @classmethod
    @abc.abstractmethod
    def _value_config(cls, options: dict[str, Any]) -> dict[str, Any]:
        """Return the value lookup config for get_zwave_value_from_config."""

    @classmethod
    @abc.abstractmethod
    def _value_description(cls, options: dict[str, Any]) -> str:
        """Return a human readable description of the looked up value."""

    @classmethod
    @override
    def _validate_nodes(cls, nodes: set[ZwaveNode], options: dict[str, Any]) -> None:
        value_config = cls._value_config(options)
        for node in nodes:
            try:
                get_zwave_value_from_config(node, value_config)
            except probatio.Invalid:
                continue
            return
        raise probatio.Invalid(
            f"No targeted node has {cls._value_description(options)}"
        )

    @override
    def _node_matches(self, node: ZwaveNode) -> bool:
        try:
            value = get_zwave_value_from_config(node, self._value_config(self._options))
        except probatio.Invalid:
            return False
        return value_matches_state(value, self._options[ATTR_VALUE])


class ValueCondition(_ZwaveValueCondition):
    """Test a Z-Wave value."""

    _schema = _condition_schema(_VALUE_OPTIONS_SCHEMA_DICT)

    @classmethod
    @override
    def _value_config(cls, options: dict[str, Any]) -> dict[str, Any]:
        return {
            ATTR_COMMAND_CLASS: options[ATTR_COMMAND_CLASS],
            ATTR_PROPERTY: options[ATTR_PROPERTY],
            ATTR_ENDPOINT: options.get(ATTR_ENDPOINT),
            ATTR_PROPERTY_KEY: options.get(ATTR_PROPERTY_KEY),
        }

    @classmethod
    @override
    def _value_description(cls, options: dict[str, Any]) -> str:
        command_class = CommandClass(options[ATTR_COMMAND_CLASS])
        return f"value {command_class.name}-{options[ATTR_PROPERTY]}"


class ConfigParameterCondition(_ZwaveValueCondition):
    """Test a Z-Wave configuration parameter."""

    _schema = _condition_schema(_CONFIG_PARAMETER_OPTIONS_SCHEMA_DICT)

    @classmethod
    @override
    def _value_config(cls, options: dict[str, Any]) -> dict[str, Any]:
        return {
            ATTR_COMMAND_CLASS: CommandClass.CONFIGURATION,
            ATTR_PROPERTY: options[ATTR_CONFIG_PARAMETER],
            ATTR_PROPERTY_KEY: options.get(ATTR_CONFIG_PARAMETER_BITMASK),
            ATTR_ENDPOINT: options[ATTR_ENDPOINT],
        }

    @classmethod
    @override
    def _value_description(cls, options: dict[str, Any]) -> str:
        return f"configuration parameter {options[ATTR_CONFIG_PARAMETER]}"


CONDITIONS: dict[str, type[Condition]] = {
    "node_status": NodeStatusCondition,
    "config_parameter": ConfigParameterCondition,
    "value": ValueCondition,
}


async def async_get_conditions(hass: HomeAssistant) -> dict[str, type[Condition]]:
    """Return the Z-Wave JS conditions."""
    return CONDITIONS
