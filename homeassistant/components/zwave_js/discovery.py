"""Map Z-Wave nodes and values to Home Assistant entities."""

from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, List, Optional

from zwave_js_server.const import CommandClass
from zwave_js_server.model.node import Node as ZwaveNode
from zwave_js_server.model.value import Value as ZwaveValue


@dataclass
class ZwaveDiscoveryInfo:
    """Info discovered from (primary) ZWave Value to create entity."""

    node: ZwaveNode  # node to which the value(s) belongs
    primary_value: ZwaveValue  # the value object itself for primary value
    platform: str  # the home assistant platform for which an entity should be created
    platform_hint: str = ""  # hint for the platform about this discovered entity

    @property
    def discovery_id(self):
        """Return a unique discovery id for this info."""
        # NOTE: we do not use the value_id here because list values get a different value id
        return f"{self.node.node_id}.{self.primary_value.property_}"


@dataclass
class ZWaveDiscoverySchema:
    """Z-Wave discovery schema.

    The (primary) value for an entity must match these conditions.
    """

    # specify the hass platform for which this scheme applies (e.g. light, sensor)
    platform: str
    # [optional] hint for platform
    hint: Optional[str]
    # [optional] the node's basic device class must match ANY of these values
    device_class_basic: List[str] = field(default_factory=list)
    # [optional] the node's generic device class must match ANY of these values
    device_class_generic: List[str] = field(default_factory=list)
    # [optional] the node's specific device class must match ANY of these values
    device_class_specific: List[str] = field(default_factory=list)
    # [optional] the value's command class must match ANY of these values
    command_class: List[int] = field(default_factory=list)
    # [optional] the value's endpoint must match ANY of these values
    endpoint: List[int] = field(default_factory=list)
    # [optional] the value's property must match ANY of these values
    property: List[str] = field(default_factory=list)
    # [optional] the value's metadata_type must match ANY of these values
    type: List[str] = field(default_factory=list)


DISCOVERY_SCHEMAS = [
    # generic text sensors
    ZWaveDiscoverySchema(
        platform="sensor",
        hint="string_sensor",
        command_class=[
            CommandClass.ALARM,
            CommandClass.SENSOR_ALARM,
            CommandClass.INDICATOR,
            CommandClass.NOTIFICATION,
        ],
        type=["string"],
    ),
    # generic numeric sensors
    ZWaveDiscoverySchema(
        platform="sensor",
        hint="numeric_sensor",
        command_class=[
            CommandClass.SENSOR_MULTILEVEL,
            CommandClass.METER,
            CommandClass.ALARM,
            CommandClass.SENSOR_ALARM,
            CommandClass.INDICATOR,
            CommandClass.BATTERY,
            CommandClass.NOTIFICATION,
            CommandClass.BASIC,
        ],
        type=["number"],
    ),
]


async def async_discover_values(node: ZwaveNode) -> AsyncGenerator[ZwaveDiscoveryInfo, None]:
    """Run discovery on ZWave node and return matching (primary) values."""
    for value in node.values.values():
        disc_val = await async_discover_value(value)
        if disc_val:
            yield disc_val


async def async_discover_value(value: ZwaveValue) -> Optional[ZwaveDiscoveryInfo]:
    """Run discovery on Z-Wave value and return ZwaveDiscoveryInfo if match found."""
    for schema in DISCOVERY_SCHEMAS:
        # check device_class_basic
        if not compare_value(schema.device_class_basic, value.node.device_class.basic):
            continue
        # check device_class_generic
        if not compare_value(schema.device_class_generic, value.node.device_class.generic):
            continue
        # check device_class_specific
        if not compare_value(schema.device_class_specific, value.node.device_class.specific):
            continue
        # check command_class
        if not compare_value(schema.command_class, value.command_class):
            continue
        # check endpoint
        if not compare_value(schema.endpoint, value.endpoint):
            continue
        # check property
        if not compare_value(schema.property, value.property_):
            continue
        # check metadata_type
        if not compare_value(schema.type, value.metadata.type):
            continue
        # all checks passed, this value belongs to an entity
        return ZwaveDiscoveryInfo(
            node=value.node,
            primary_value=value,
            platform=schema.platform,
            platform_hint=schema.hint,
        )


def compare_value(schema_value: List[Any], zwave_value: Any) -> bool:
    """Return if value matches schema."""
    if not schema_value:
        return True
    return zwave_value in schema_value
