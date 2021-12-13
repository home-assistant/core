"""Provides helpers for Z-Wave JS device automations."""
from __future__ import annotations

from typing import cast

import voluptuous as vol
from zwave_js_server.const import ConfigurationValueType
from zwave_js_server.model.node import Node
from zwave_js_server.model.value import ConfigurationValue

NODE_STATUSES = ["asleep", "awake", "dead", "alive"]

CONF_SUBTYPE = "subtype"
CONF_VALUE_ID = "value_id"

VALUE_ID_REGEX = r"([0-9]+-[0-9]+-[0-9]+-).+"


def get_config_parameter_value_schema(node: Node, value_id: str) -> vol.Schema | None:
    """Get the extra fields schema for a config parameter value."""
    config_value = cast(ConfigurationValue, node.values[value_id])
    min_ = config_value.metadata.min
    max_ = config_value.metadata.max

    if config_value.configuration_value_type in (
        ConfigurationValueType.RANGE,
        ConfigurationValueType.MANUAL_ENTRY,
    ):
        return vol.All(vol.Coerce(int), vol.Range(min=min_, max=max_))

    if config_value.configuration_value_type == ConfigurationValueType.ENUMERATED:
        return vol.In({int(k): v for k, v in config_value.metadata.states.items()})

    return None
