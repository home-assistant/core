"""Provide models for the Z-Wave integration."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from awesomeversion import AwesomeVersion
from zwave_js_server.const import LogLevel
from zwave_js_server.model.node import Node as ZwaveNode
from zwave_js_server.model.value import (
    ConfigurationValue as ZwaveConfigurationValue,
    Value as ZwaveValue,
    get_value_id_str,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, Platform
from homeassistant.helpers.entity import EntityDescription

if TYPE_CHECKING:
    from _typeshed import DataclassInstance
    from zwave_js_server.client import Client as ZwaveClient

    from . import DriverEvents


@dataclass
class ZwaveJSData:
    """Data for zwave_js runtime data."""

    client: ZwaveClient
    driver_events: DriverEvents
    old_server_log_level: LogLevel | None = None


type ZwaveJSConfigEntry = ConfigEntry[ZwaveJSData]


@dataclass
class ZwaveValueID:
    """Class to represent a value ID."""

    property_: str | int
    command_class: int
    endpoint: int | None = None
    property_key: str | int | None = None


class ValueType(StrEnum):
    """Enum with all value types."""

    ANY = "any"
    BOOLEAN = "boolean"
    NUMBER = "number"
    STRING = "string"


class DataclassMustHaveAtLeastOne:
    """A dataclass that must have at least one input parameter that is not None."""

    def __post_init__(self: DataclassInstance) -> None:
        """Post dataclass initialization."""
        if all(val is None for val in asdict(self).values()):
            raise ValueError("At least one input parameter must not be None")


@dataclass
class FirmwareVersionRange(DataclassMustHaveAtLeastOne):
    """Firmware version range dictionary."""

    min: str | None = None
    max: str | None = None
    min_ver: AwesomeVersion | None = field(default=None, init=False)
    max_ver: AwesomeVersion | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        """Post dataclass initialization."""
        super().__post_init__()
        if self.min:
            self.min_ver = AwesomeVersion(self.min)
        if self.max:
            self.max_ver = AwesomeVersion(self.max)


@dataclass
class PlatformZwaveDiscoveryInfo:
    """Info discovered from (primary) ZWave Value to create entity."""

    # node to which the value(s) belongs
    node: ZwaveNode
    # the value object itself for primary value
    primary_value: ZwaveValue
    # bool to specify whether state is assumed and events should be fired on value
    # update
    assumed_state: bool
    # the home assistant platform for which an entity should be created
    platform: Platform
    # additional values that need to be watched by entity
    additional_value_ids_to_watch: set[str]


@dataclass
class ZwaveDiscoveryInfo(PlatformZwaveDiscoveryInfo):
    """Info discovered from (primary) ZWave Value to create entity."""

    # helper data to use in platform setup
    platform_data: Any = None
    # data template to use in platform logic
    platform_data_template: BaseDiscoverySchemaDataTemplate | None = None
    # hint for the platform about this discovered entity
    platform_hint: str | None = ""
    # bool to specify whether entity should be enabled by default
    entity_registry_enabled_default: bool = True
    # the entity category for the discovered entity
    entity_category: EntityCategory | None = None


@dataclass
class ZWaveValueDiscoverySchema(DataclassMustHaveAtLeastOne):
    """Z-Wave Value discovery schema.

    The Z-Wave Value must match these conditions.
    Use the Z-Wave specifications to find out the values for these parameters:
    https://github.com/zwave-js/specs/tree/master
    """

    # [optional] the value's command class must match ANY of these values
    command_class: set[int] | None = None
    # [optional] the value's endpoint must match ANY of these values
    endpoint: set[int] | None = None
    # [optional] the value's property must match ANY of these values
    property: set[str | int] | None = None
    # [optional] the value's property name must match ANY of these values
    property_name: set[str] | None = None
    # [optional] the value's property key must match ANY of these values
    property_key: set[str | int | None] | None = None
    # [optional] the value's property key must NOT match ANY of these values
    not_property_key: set[str | int | None] | None = None
    # [optional] the value's metadata_type must match ANY of these values
    type: set[str] | None = None
    # [optional] the value's metadata_readable must match this value
    readable: bool | None = None
    # [optional] the value's metadata_writeable must match this value
    writeable: bool | None = None
    # [optional] the value's states map must include ANY of these key/value pairs
    any_available_states: set[tuple[int, str]] | None = None
    # [optional] the value's states map must include ANY of these keys
    any_available_states_keys: set[int] | None = None
    # [optional] the value's cc specific map must include ANY of these key/value pairs
    any_available_cc_specific: set[tuple[Any, Any]] | None = None
    # [optional] the value's value must match this value
    value: Any | None = None
    # [optional] the value's metadata_stateful must match this value
    stateful: bool | None = None


@dataclass
class NewZWaveDiscoverySchema:
    """Z-Wave discovery schema.

    The Z-Wave node and it's (primary) value for an entity must match these conditions.
    Use the Z-Wave specifications to find out the values for these parameters:
    https://github.com/zwave-js/node-zwave-js/tree/master/specs
    """

    # specify the hass platform for which this scheme applies (e.g. light, sensor)
    platform: Platform
    # platform-specific entity description
    entity_description: EntityDescription
    # entity class to use to instantiate the entity
    entity_class: type
    # primary value belonging to this discovery scheme
    primary_value: ZWaveValueDiscoverySchema
    # [optional] template to generate platform specific data to use in setup
    data_template: BaseDiscoverySchemaDataTemplate | None = None
    # [optional] the node's manufacturer_id must match ANY of these values
    manufacturer_id: set[int] | None = None
    # [optional] the node's product_id must match ANY of these values
    product_id: set[int] | None = None
    # [optional] the node's product_type must match ANY of these values
    product_type: set[int] | None = None
    # [optional] the node's firmware_version must be within this range
    firmware_version_range: FirmwareVersionRange | None = None
    # [optional] the node's firmware_version must match ANY of these values
    firmware_version: set[str] | None = None
    # [optional] the node's basic device class must match ANY of these values
    device_class_basic: set[str | int] | None = None
    # [optional] the node's generic device class must match ANY of these values
    device_class_generic: set[str | int] | None = None
    # [optional] the node's specific device class must match ANY of these values
    device_class_specific: set[str | int] | None = None
    # [optional] additional values that ALL need to be present
    # on the node for this scheme to pass
    required_values: list[ZWaveValueDiscoverySchema] | None = None
    # [optional] additional values that MAY NOT be present
    # on the node for this scheme to pass
    absent_values: list[ZWaveValueDiscoverySchema] | None = None
    # [optional] bool to specify if this primary value may be discovered
    # by multiple platforms
    allow_multi: bool = False
    # [optional] bool to specify whether state is assumed
    # and events should be fired on value update
    assumed_state: bool = False


@dataclass
class BaseDiscoverySchemaDataTemplate:
    """Base class for discovery schema data templates."""

    static_data: Any | None = None

    def resolve_data(self, value: ZwaveValue) -> Any:
        """Resolve helper class data for a discovered value.

        Can optionally be implemented by subclasses if input data needs to be
        transformed once discovered Value is available.
        """
        return {}

    def values_to_watch(self, resolved_data: Any) -> Iterable[ZwaveValue | None]:
        """Return list of all ZwaveValues resolved by helper that should be watched.

        Should be implemented by subclasses only if there are values to watch.
        """
        return []

    def value_ids_to_watch(self, resolved_data: Any) -> set[str]:
        """Return list of all Value IDs resolved by helper that should be watched.

        Not to be overwritten by subclasses.
        """
        return {val.value_id for val in self.values_to_watch(resolved_data) if val}

    @staticmethod
    def _get_value_from_id(
        node: ZwaveNode, value_id_obj: ZwaveValueID
    ) -> ZwaveValue | ZwaveConfigurationValue | None:
        """Get a ZwaveValue from a node using a ZwaveValueDict."""
        value_id = get_value_id_str(
            node,
            value_id_obj.command_class,
            value_id_obj.property_,
            endpoint=value_id_obj.endpoint,
            property_key=value_id_obj.property_key,
        )
        return node.values.get(value_id)
