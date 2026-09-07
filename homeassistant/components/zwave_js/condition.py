"""Offer Z-Wave JS automation conditions."""

import abc
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Unpack, override

import voluptuous as vol
from zwave_js_server.const import CommandClass
from zwave_js_server.model.node import Node as ZwaveNode

from homeassistant.const import ATTR_DEVICE_ID, CONF_OPTIONS
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.automation import move_top_level_schema_fields_to_options
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
_CONDITION_VALUE_SCHEMA = vol.Any(bool, int, float, dict, cv.string)

_BASE_SCHEMA_DICT: dict[vol.Marker, Any] = {
    vol.Required(ATTR_DEVICE_ID): vol.All(cv.ensure_list, [cv.string]),
    vol.Required(ATTR_BEHAVIOR, default=BEHAVIOR_ANY): vol.In(
        [BEHAVIOR_ANY, BEHAVIOR_ALL]
    ),
}

_NODE_STATUS_OPTIONS_SCHEMA_DICT: dict[vol.Marker, Any] = {
    **_BASE_SCHEMA_DICT,
    vol.Required(CONF_STATUS): vol.In(NODE_STATUSES),
}

_VALUE_OPTIONS_SCHEMA_DICT: dict[vol.Marker, Any] = {
    **_BASE_SCHEMA_DICT,
    vol.Required(ATTR_COMMAND_CLASS): COMMAND_CLASS_SCHEMA,
    vol.Required(ATTR_PROPERTY): vol.Any(vol.Coerce(int), cv.string),
    vol.Optional(ATTR_ENDPOINT): vol.Coerce(int),
    vol.Optional(ATTR_PROPERTY_KEY): vol.Any(vol.Coerce(int), cv.string),
    vol.Required(ATTR_VALUE): _CONDITION_VALUE_SCHEMA,
}

_CONFIG_PARAMETER_OPTIONS_SCHEMA_DICT: dict[vol.Marker, Any] = {
    **_BASE_SCHEMA_DICT,
    vol.Required(ATTR_CONFIG_PARAMETER): vol.Coerce(int),
    vol.Optional(ATTR_CONFIG_PARAMETER_BITMASK): vol.Any(
        vol.Coerce(int), BITMASK_SCHEMA
    ),
    vol.Optional(ATTR_ENDPOINT, default=0): vol.Coerce(int),
    vol.Required(ATTR_VALUE): _CONDITION_VALUE_SCHEMA,
}


def _condition_schema(options_schema_dict: dict[vol.Marker, Any]) -> vol.Schema:
    """Return the condition schema for an options schema dict."""
    return vol.Schema({vol.Required(CONF_OPTIONS, default={}): options_schema_dict})


@dataclass(slots=True)
class _ResolvedNodes:
    """Z-Wave nodes resolved from the targeted devices."""

    nodes: set[ZwaveNode] = field(default_factory=set)
    unresolved: int = 0


@callback
def _async_resolve_nodes(
    hass: HomeAssistant, device_ids: Iterable[str]
) -> _ResolvedNodes:
    """Resolve targeted device IDs to Z-Wave nodes."""
    dev_reg = dr.async_get(hass)
    resolved = _ResolvedNodes()
    for device_id in set(device_ids):
        try:
            node = async_get_node_from_device_id(hass, device_id, dev_reg)
        except ValueError:
            resolved.unresolved += 1
        else:
            resolved.nodes.add(node)
    return resolved


class _ZwaveNodeCondition(Condition):
    """Base for conditions evaluated per Z-Wave node."""

    options_schema_dict: dict[vol.Marker, Any]
    _schema: vol.Schema

    @classmethod
    @override
    async def async_validate_complete_config(
        cls, hass: HomeAssistant, complete_config: ConfigType
    ) -> ConfigType:
        """Validate complete config."""
        complete_config = move_top_level_schema_fields_to_options(
            complete_config, cls.options_schema_dict
        )
        return await super().async_validate_complete_config(hass, complete_config)

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

        resolved = _async_resolve_nodes(hass, device_ids)
        if not resolved.nodes:
            raise vol.Invalid("No nodes found for the given devices")
        cls._validate_nodes(resolved.nodes, config[CONF_OPTIONS])
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
        resolved = _async_resolve_nodes(self._hass, self._options[ATTR_DEVICE_ID])
        if not resolved.nodes:
            return False
        behavior_all = self._options[ATTR_BEHAVIOR] == BEHAVIOR_ALL
        if behavior_all and resolved.unresolved:
            return False
        combine: Callable[[Iterable[object]], bool] = all if behavior_all else any
        return combine(self._node_matches(node) for node in resolved.nodes)


class NodeStatusCondition(_ZwaveNodeCondition):
    """Test the status of Z-Wave nodes."""

    options_schema_dict = _NODE_STATUS_OPTIONS_SCHEMA_DICT
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
            except vol.Invalid:
                continue
            return
        raise vol.Invalid(f"No targeted node has {cls._value_description(options)}")

    @override
    def _node_matches(self, node: ZwaveNode) -> bool:
        try:
            value = get_zwave_value_from_config(node, self._value_config(self._options))
        except vol.Invalid:
            return False
        return value_matches_state(value, self._options[ATTR_VALUE])


class ValueCondition(_ZwaveValueCondition):
    """Test a Z-Wave value."""

    options_schema_dict = _VALUE_OPTIONS_SCHEMA_DICT
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

    options_schema_dict = _CONFIG_PARAMETER_OPTIONS_SCHEMA_DICT
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
