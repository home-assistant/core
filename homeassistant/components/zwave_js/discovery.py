"""Map Z-Wave nodes and values to Home Assistant entities."""

from __future__ import annotations

from collections.abc import Generator
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any, cast

from awesomeversion import AwesomeVersion
from zwave_js_server.const import (
    CURRENT_STATE_PROPERTY,
    CURRENT_VALUE_PROPERTY,
    TARGET_STATE_PROPERTY,
    TARGET_VALUE_PROPERTY,
    CommandClass,
)
from zwave_js_server.const.command_class.barrier_operator import (
    SIGNALING_STATE_PROPERTY,
)
from zwave_js_server.const.command_class.color_switch import CURRENT_COLOR_PROPERTY
from zwave_js_server.const.command_class.humidity_control import (
    HUMIDITY_CONTROL_MODE_PROPERTY,
)
from zwave_js_server.const.command_class.lock import (
    CURRENT_MODE_PROPERTY,
    DOOR_STATUS_PROPERTY,
    LOCKED_PROPERTY,
)
from zwave_js_server.const.command_class.meter import (
    RESET_PROPERTY as RESET_METER_PROPERTY,
    VALUE_PROPERTY,
)
from zwave_js_server.const.command_class.protection import LOCAL_PROPERTY, RF_PROPERTY
from zwave_js_server.const.command_class.sound_switch import (
    DEFAULT_TONE_ID_PROPERTY,
    DEFAULT_VOLUME_PROPERTY,
    TONE_ID_PROPERTY,
)
from zwave_js_server.const.command_class.thermostat import (
    THERMOSTAT_CURRENT_TEMP_PROPERTY,
    THERMOSTAT_FAN_MODE_PROPERTY,
    THERMOSTAT_MODE_PROPERTY,
    THERMOSTAT_SETPOINT_PROPERTY,
)
from zwave_js_server.exceptions import UnknownValueData
from zwave_js_server.model.node import Node as ZwaveNode
from zwave_js_server.model.value import (
    ConfigurationValue,
    ConfigurationValueType,
    Value as ZwaveValue,
)

from homeassistant.const import EntityCategory, Platform
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceEntry

from .const import COVER_POSITION_PROPERTY_KEYS, COVER_TILT_PROPERTY_KEYS, LOGGER
from .discovery_data_template import (
    BaseDiscoverySchemaDataTemplate,
    ConfigurableFanValueMappingDataTemplate,
    CoverTiltDataTemplate,
    DynamicCurrentTempClimateDataTemplate,
    FanValueMapping,
    FixedFanValueMappingDataTemplate,
    NumericSensorDataTemplate,
)
from .helpers import ZwaveValueID

if TYPE_CHECKING:
    from _typeshed import DataclassInstance


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
class ZwaveDiscoveryInfo:
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
    # helper data to use in platform setup
    platform_data: Any
    # additional values that need to be watched by entity
    additional_value_ids_to_watch: set[str]
    # hint for the platform about this discovered entity
    platform_hint: str | None = ""
    # data template to use in platform logic
    platform_data_template: BaseDiscoverySchemaDataTemplate | None = None
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
    # [optional] the value's value must match this value
    value: Any | None = None
    # [optional] the value's metadata_stateful must match this value
    stateful: bool | None = None


@dataclass
class ZWaveDiscoverySchema:
    """Z-Wave discovery schema.

    The Z-Wave node and it's (primary) value for an entity must match these conditions.
    Use the Z-Wave specifications to find out the values for these parameters:
    https://github.com/zwave-js/specs/tree/master
    """

    # specify the hass platform for which this scheme applies (e.g. light, sensor)
    platform: Platform
    # primary value belonging to this discovery scheme
    primary_value: ZWaveValueDiscoverySchema
    # [optional] hint for platform
    hint: str | None = None
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
    # [optional] the node's generic device class must match ANY of these values
    device_class_generic: set[str] | None = None
    # [optional] the node's specific device class must match ANY of these values
    device_class_specific: set[str] | None = None
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
    # [optional] bool to specify whether entity should be enabled by default
    entity_registry_enabled_default: bool = True
    # [optional] the entity category for the discovered entity
    entity_category: EntityCategory | None = None


DOOR_LOCK_CURRENT_MODE_SCHEMA = ZWaveValueDiscoverySchema(
    command_class={CommandClass.DOOR_LOCK},
    property={CURRENT_MODE_PROPERTY},
    type={ValueType.NUMBER},
)

SWITCH_MULTILEVEL_CURRENT_VALUE_SCHEMA = ZWaveValueDiscoverySchema(
    command_class={CommandClass.SWITCH_MULTILEVEL},
    property={CURRENT_VALUE_PROPERTY},
    type={ValueType.NUMBER},
)

SWITCH_MULTILEVEL_TARGET_VALUE_SCHEMA = ZWaveValueDiscoverySchema(
    command_class={CommandClass.SWITCH_MULTILEVEL},
    property={TARGET_VALUE_PROPERTY},
    type={ValueType.NUMBER},
)

SWITCH_BINARY_CURRENT_VALUE_SCHEMA = ZWaveValueDiscoverySchema(
    command_class={CommandClass.SWITCH_BINARY}, property={CURRENT_VALUE_PROPERTY}
)

SIREN_TONE_SCHEMA = ZWaveValueDiscoverySchema(
    command_class={CommandClass.SOUND_SWITCH},
    property={TONE_ID_PROPERTY},
    type={ValueType.NUMBER},
)

WINDOW_COVERING_COVER_CURRENT_VALUE_SCHEMA = ZWaveValueDiscoverySchema(
    command_class={CommandClass.WINDOW_COVERING},
    property={CURRENT_VALUE_PROPERTY},
    property_key=COVER_POSITION_PROPERTY_KEYS,
)

WINDOW_COVERING_SLAT_CURRENT_VALUE_SCHEMA = ZWaveValueDiscoverySchema(
    command_class={CommandClass.WINDOW_COVERING},
    property={CURRENT_VALUE_PROPERTY},
    property_key=COVER_TILT_PROPERTY_KEYS,
)

# For device class mapping see:
# https://github.com/zwave-js/node-zwave-js/blob/master/packages/config/config/deviceClasses.json
DISCOVERY_SCHEMAS = [
    # ====== START OF DEVICE SPECIFIC MAPPING SCHEMAS =======
    # Honeywell 39358 In-Wall Fan Control using switch multilevel CC
    ZWaveDiscoverySchema(
        platform=Platform.FAN,
        hint="has_fan_value_mapping",
        manufacturer_id={0x0039},
        product_id={0x3131},
        product_type={0x4944},
        primary_value=SWITCH_MULTILEVEL_CURRENT_VALUE_SCHEMA,
        required_values=[SWITCH_MULTILEVEL_TARGET_VALUE_SCHEMA],
        data_template=FixedFanValueMappingDataTemplate(
            FanValueMapping(speeds=[(1, 32), (33, 66), (67, 99)]),
        ),
    ),
    # GE/Jasco - In-Wall Smart Fan Control - 12730 / ZW4002
    ZWaveDiscoverySchema(
        platform=Platform.FAN,
        hint="has_fan_value_mapping",
        manufacturer_id={0x0063},
        product_id={0x3034},
        product_type={0x4944},
        primary_value=SWITCH_MULTILEVEL_CURRENT_VALUE_SCHEMA,
        data_template=FixedFanValueMappingDataTemplate(
            FanValueMapping(speeds=[(1, 33), (34, 67), (68, 99)]),
        ),
    ),
    # GE/Jasco - In-Wall Smart Fan Control - 14287 / 55258 / ZW4002
    ZWaveDiscoverySchema(
        platform=Platform.FAN,
        hint="has_fan_value_mapping",
        manufacturer_id={0x0063},
        product_id={0x3131, 0x3337},
        product_type={0x4944},
        primary_value=SWITCH_MULTILEVEL_CURRENT_VALUE_SCHEMA,
        data_template=FixedFanValueMappingDataTemplate(
            FanValueMapping(speeds=[(1, 32), (33, 66), (67, 99)]),
        ),
    ),
    # GE/Jasco - In-Wall Smart Fan Control - 14314 / ZW4002
    ZWaveDiscoverySchema(
        platform=Platform.FAN,
        manufacturer_id={0x0063},
        product_id={0x3138},
        product_type={0x4944},
        primary_value=SWITCH_MULTILEVEL_CURRENT_VALUE_SCHEMA,
    ),
    # Leviton ZW4SF fan controllers using switch multilevel CC
    ZWaveDiscoverySchema(
        platform=Platform.FAN,
        hint="has_fan_value_mapping",
        manufacturer_id={0x001D},
        product_id={0x0002},
        product_type={0x0038},
        primary_value=SWITCH_MULTILEVEL_CURRENT_VALUE_SCHEMA,
        data_template=FixedFanValueMappingDataTemplate(
            FanValueMapping(speeds=[(1, 25), (26, 50), (51, 75), (76, 99)]),
        ),
    ),
    # Inovelli LZW36 light / fan controller combo using switch multilevel CC
    # The fan is endpoint 2, the light is endpoint 1.
    ZWaveDiscoverySchema(
        platform=Platform.FAN,
        hint="has_fan_value_mapping",
        manufacturer_id={0x031E},
        product_id={0x0001},
        product_type={0x000E},
        primary_value=ZWaveValueDiscoverySchema(
            command_class={CommandClass.SWITCH_MULTILEVEL},
            endpoint={2},
            property={CURRENT_VALUE_PROPERTY},
            type={ValueType.NUMBER},
        ),
        data_template=FixedFanValueMappingDataTemplate(
            FanValueMapping(
                presets={1: "breeze"}, speeds=[(2, 33), (34, 66), (67, 99)]
            ),
        ),
    ),
    # HomeSeer HS-FC200+
    ZWaveDiscoverySchema(
        platform=Platform.FAN,
        hint="has_fan_value_mapping",
        manufacturer_id={0x000C},
        product_id={0x0001},
        product_type={0x0203},
        primary_value=SWITCH_MULTILEVEL_CURRENT_VALUE_SCHEMA,
        data_template=ConfigurableFanValueMappingDataTemplate(
            configuration_option=ZwaveValueID(
                property_=5, command_class=CommandClass.CONFIGURATION, endpoint=0
            ),
            configuration_value_to_fan_value_mapping={
                0: FanValueMapping(speeds=[(1, 33), (34, 66), (67, 99)]),
                1: FanValueMapping(speeds=[(1, 24), (25, 49), (50, 74), (75, 99)]),
            },
        ),
    ),
    # Fibaro Shutter Fibaro FGR222
    ZWaveDiscoverySchema(
        platform=Platform.COVER,
        hint="shutter_tilt",
        manufacturer_id={0x010F},
        product_id={0x1000, 0x1001},
        product_type={0x0301, 0x0302},
        primary_value=SWITCH_MULTILEVEL_CURRENT_VALUE_SCHEMA,
        data_template=CoverTiltDataTemplate(
            current_tilt_value_id=ZwaveValueID(
                property_="fibaro",
                command_class=CommandClass.MANUFACTURER_PROPRIETARY,
                endpoint=0,
                property_key="venetianBlindsTilt",
            ),
            target_tilt_value_id=ZwaveValueID(
                property_="fibaro",
                command_class=CommandClass.MANUFACTURER_PROPRIETARY,
                endpoint=0,
                property_key="venetianBlindsTilt",
            ),
        ),
        required_values=[
            ZWaveValueDiscoverySchema(
                command_class={CommandClass.MANUFACTURER_PROPRIETARY},
                property={"fibaro"},
                property_key={"venetianBlindsTilt"},
            )
        ],
    ),
    # Fibaro Shutter Fibaro FGR223
    # Combine both switch_multilevel endpoints into shutter_tilt
    # if operating mode (151) is set to venetian blind (2)
    ZWaveDiscoverySchema(
        platform=Platform.COVER,
        hint="shutter_tilt",
        manufacturer_id={0x010F},
        product_id={0x1000, 0x1001},
        product_type={0x0303},
        primary_value=ZWaveValueDiscoverySchema(
            command_class={CommandClass.SWITCH_MULTILEVEL},
            property={CURRENT_VALUE_PROPERTY},
            endpoint={1},
            type={ValueType.NUMBER},
        ),
        data_template=CoverTiltDataTemplate(
            current_tilt_value_id=ZwaveValueID(
                property_=CURRENT_VALUE_PROPERTY,
                command_class=CommandClass.SWITCH_MULTILEVEL,
                endpoint=2,
            ),
            target_tilt_value_id=ZwaveValueID(
                property_=TARGET_VALUE_PROPERTY,
                command_class=CommandClass.SWITCH_MULTILEVEL,
                endpoint=2,
            ),
        ),
        required_values=[
            ZWaveValueDiscoverySchema(
                command_class={CommandClass.CONFIGURATION},
                property={151},
                endpoint={0},
                value={2},
            )
        ],
    ),
    # Fibaro Shutter Fibaro FGR223
    # Disable endpoint 2 (slat),
    # as these are either combined with endpoint one as shutter_tilt
    # or it has no practical function.
    # CC: Switch_Multilevel
    ZWaveDiscoverySchema(
        platform=Platform.COVER,
        hint="shutter",
        manufacturer_id={0x010F},
        product_id={0x1000, 0x1001},
        product_type={0x0303},
        primary_value=ZWaveValueDiscoverySchema(
            command_class={CommandClass.SWITCH_MULTILEVEL},
            property={CURRENT_VALUE_PROPERTY},
            endpoint={2},
            type={ValueType.NUMBER},
        ),
        entity_registry_enabled_default=False,
    ),
    # Fibaro Nice BiDi-ZWave (IBT4ZWAVE)
    ZWaveDiscoverySchema(
        platform=Platform.COVER,
        hint="gate",
        manufacturer_id={0x0441},
        product_id={0x1000},
        product_type={0x2400},
        primary_value=SWITCH_MULTILEVEL_CURRENT_VALUE_SCHEMA,
        required_values=[SWITCH_MULTILEVEL_TARGET_VALUE_SCHEMA],
    ),
    # Shelly Qubino Wave Shutter QNSH-001P10
    # Combine both switch_multilevel endpoints into shutter_tilt
    # if operating mode (71) is set to venetian blind (1)
    ZWaveDiscoverySchema(
        platform=Platform.COVER,
        hint="shutter_tilt",
        manufacturer_id={0x0460},
        product_id={0x0082},
        product_type={0x0003},
        primary_value=ZWaveValueDiscoverySchema(
            command_class={CommandClass.SWITCH_MULTILEVEL},
            property={CURRENT_VALUE_PROPERTY},
            endpoint={1},
            type={ValueType.NUMBER},
        ),
        data_template=CoverTiltDataTemplate(
            current_tilt_value_id=ZwaveValueID(
                property_=CURRENT_VALUE_PROPERTY,
                command_class=CommandClass.SWITCH_MULTILEVEL,
                endpoint=2,
            ),
            target_tilt_value_id=ZwaveValueID(
                property_=TARGET_VALUE_PROPERTY,
                command_class=CommandClass.SWITCH_MULTILEVEL,
                endpoint=2,
            ),
        ),
        required_values=[
            ZWaveValueDiscoverySchema(
                command_class={CommandClass.CONFIGURATION},
                property={71},
                endpoint={0},
                value={1},
            )
        ],
    ),
    # Shelly Qubino Wave Shutter QNSH-001P10
    # Disable endpoint 2 (slat),
    # as these are either combined with endpoint one as shutter_tilt
    # or it has no practical function.
    # CC: Switch_Multilevel
    ZWaveDiscoverySchema(
        platform=Platform.COVER,
        hint="shutter",
        manufacturer_id={0x0460},
        product_id={0x0082},
        product_type={0x0003},
        primary_value=ZWaveValueDiscoverySchema(
            command_class={CommandClass.SWITCH_MULTILEVEL},
            property={CURRENT_VALUE_PROPERTY},
            endpoint={2},
            type={ValueType.NUMBER},
        ),
        entity_registry_enabled_default=False,
    ),
    # Qubino flush shutter
    ZWaveDiscoverySchema(
        platform=Platform.COVER,
        hint="shutter",
        manufacturer_id={0x0159},
        product_id={0x0052, 0x0053},
        product_type={0x0003},
        primary_value=SWITCH_MULTILEVEL_CURRENT_VALUE_SCHEMA,
    ),
    # Graber/Bali/Spring Fashion Covers
    ZWaveDiscoverySchema(
        platform=Platform.COVER,
        hint="blind",
        manufacturer_id={0x026E},
        product_id={0x5A31},
        product_type={0x4353},
        primary_value=SWITCH_MULTILEVEL_CURRENT_VALUE_SCHEMA,
    ),
    # iBlinds v2 window blind motor
    ZWaveDiscoverySchema(
        platform=Platform.COVER,
        hint="blind",
        manufacturer_id={0x0287},
        product_id={0x000D},
        product_type={0x0003},
        primary_value=SWITCH_MULTILEVEL_CURRENT_VALUE_SCHEMA,
    ),
    # Merten 507801 Connect Roller Shutter
    ZWaveDiscoverySchema(
        platform=Platform.COVER,
        hint="shutter",
        manufacturer_id={0x007A},
        product_id={0x0001},
        product_type={0x8003},
        primary_value=ZWaveValueDiscoverySchema(
            command_class={CommandClass.SWITCH_MULTILEVEL},
            property={CURRENT_VALUE_PROPERTY},
            endpoint={0, 1},
            type={ValueType.NUMBER},
        ),
        assumed_state=True,
    ),
    # Merten 507801 Connect Roller Shutter.
    # Disable endpoint 2, as it has no practical function. CC: Switch_Multilevel
    ZWaveDiscoverySchema(
        platform=Platform.COVER,
        hint="shutter",
        manufacturer_id={0x007A},
        product_id={0x0001},
        product_type={0x8003},
        primary_value=ZWaveValueDiscoverySchema(
            command_class={CommandClass.SWITCH_MULTILEVEL},
            property={CURRENT_VALUE_PROPERTY},
            endpoint={2},
            type={ValueType.NUMBER},
        ),
        assumed_state=True,
        entity_registry_enabled_default=False,
    ),
    # Merten 507801 Connect Roller Shutter.
    # Disable endpoint 2, as it has no practical function. CC: Protection
    ZWaveDiscoverySchema(
        platform=Platform.SELECT,
        manufacturer_id={0x007A},
        product_id={0x0001},
        product_type={0x8003},
        primary_value=ZWaveValueDiscoverySchema(
            command_class={CommandClass.PROTECTION},
            property={LOCAL_PROPERTY, RF_PROPERTY},
            endpoint={2},
            type={ValueType.NUMBER},
        ),
        entity_registry_enabled_default=False,
    ),
    # ZVIDAR Z-CM-V01 (SmartWings/Deyi WM25L/V Z-Wave Motor for Roller Shade)
    ZWaveDiscoverySchema(
        platform=Platform.COVER,
        hint="shade",
        manufacturer_id={0x045A},
        product_id={0x0507},
        product_type={0x0904},
        primary_value=SWITCH_MULTILEVEL_CURRENT_VALUE_SCHEMA,
    ),
    # Vision Security ZL7432 In Wall Dual Relay Switch
    ZWaveDiscoverySchema(
        platform=Platform.SWITCH,
        manufacturer_id={0x0109},
        product_id={0x1711, 0x1717},
        product_type={0x2017},
        primary_value=SWITCH_BINARY_CURRENT_VALUE_SCHEMA,
        assumed_state=True,
    ),
    # Heatit Z-TRM6
    ZWaveDiscoverySchema(
        platform=Platform.CLIMATE,
        hint="dynamic_current_temp",
        manufacturer_id={0x019B},
        product_id={0x3001},
        product_type={0x0030},
        primary_value=ZWaveValueDiscoverySchema(
            command_class={CommandClass.THERMOSTAT_MODE},
            property={THERMOSTAT_MODE_PROPERTY},
            type={ValueType.NUMBER},
        ),
        data_template=DynamicCurrentTempClimateDataTemplate(
            lookup_table={
                # Floor sensor
                "Floor": ZwaveValueID(
                    property_=THERMOSTAT_CURRENT_TEMP_PROPERTY,
                    command_class=CommandClass.SENSOR_MULTILEVEL,
                    endpoint=4,
                ),
                # Internal sensor
                "Internal": ZwaveValueID(
                    property_=THERMOSTAT_CURRENT_TEMP_PROPERTY,
                    command_class=CommandClass.SENSOR_MULTILEVEL,
                    endpoint=2,
                ),
                # Internal with limit by floor sensor
                "Internal with floor limit": ZwaveValueID(
                    property_=THERMOSTAT_CURRENT_TEMP_PROPERTY,
                    command_class=CommandClass.SENSOR_MULTILEVEL,
                    endpoint=2,
                ),
                # External sensor (connected to device)
                "External": ZwaveValueID(
                    property_=THERMOSTAT_CURRENT_TEMP_PROPERTY,
                    command_class=CommandClass.SENSOR_MULTILEVEL,
                    endpoint=3,
                ),
                # External sensor (connected to device) with limit by floor sensor (2x sensors)
                "External with floor limit": ZwaveValueID(
                    property_=THERMOSTAT_CURRENT_TEMP_PROPERTY,
                    command_class=CommandClass.SENSOR_MULTILEVEL,
                    endpoint=3,
                ),
                # PWER - Power regulator mode (no sensor used).
                # This mode is not supported by the climate entity.
                # Heating is set by adjusting parameter 25.
                # P25: Set % of time the relay should be active when using PWER mode.
                # (30-minute duty cycle)
                # Use the air temperature as current temperature in the climate entity
                # as we have nothing else.
                "Power regulator": ZwaveValueID(
                    property_=THERMOSTAT_CURRENT_TEMP_PROPERTY,
                    command_class=CommandClass.SENSOR_MULTILEVEL,
                    endpoint=2,
                ),
            },
            dependent_value=ZwaveValueID(
                property_=2, command_class=CommandClass.CONFIGURATION, endpoint=0
            ),
        ),
    ),
    # Heatit Z-TRM3
    ZWaveDiscoverySchema(
        platform=Platform.CLIMATE,
        hint="dynamic_current_temp",
        manufacturer_id={0x019B},
        product_id={0x0203},
        product_type={0x0003},
        primary_value=ZWaveValueDiscoverySchema(
            command_class={CommandClass.THERMOSTAT_MODE},
            property={THERMOSTAT_MODE_PROPERTY},
            type={ValueType.NUMBER},
        ),
        data_template=DynamicCurrentTempClimateDataTemplate(
            lookup_table={
                # Internal Sensor
                "A": ZwaveValueID(
                    property_=THERMOSTAT_CURRENT_TEMP_PROPERTY,
                    command_class=CommandClass.SENSOR_MULTILEVEL,
                    endpoint=2,
                ),
                "AF": ZwaveValueID(
                    property_=THERMOSTAT_CURRENT_TEMP_PROPERTY,
                    command_class=CommandClass.SENSOR_MULTILEVEL,
                    endpoint=2,
                ),
                # External Sensor
                "A2": ZwaveValueID(
                    property_=THERMOSTAT_CURRENT_TEMP_PROPERTY,
                    command_class=CommandClass.SENSOR_MULTILEVEL,
                    endpoint=3,
                ),
                "A2F": ZwaveValueID(
                    property_=THERMOSTAT_CURRENT_TEMP_PROPERTY,
                    command_class=CommandClass.SENSOR_MULTILEVEL,
                    endpoint=3,
                ),
                # Floor sensor
                "F": ZwaveValueID(
                    property_=THERMOSTAT_CURRENT_TEMP_PROPERTY,
                    command_class=CommandClass.SENSOR_MULTILEVEL,
                    endpoint=4,
                ),
            },
            dependent_value=ZwaveValueID(
                property_=2, command_class=CommandClass.CONFIGURATION, endpoint=0
            ),
        ),
    ),
    # Heatit Z-TRM2fx
    ZWaveDiscoverySchema(
        platform=Platform.CLIMATE,
        hint="dynamic_current_temp",
        manufacturer_id={0x019B},
        product_id={0x0202},
        product_type={0x0003},
        firmware_version_range=FirmwareVersionRange(min="3.0"),
        primary_value=ZWaveValueDiscoverySchema(
            command_class={CommandClass.THERMOSTAT_MODE},
            property={THERMOSTAT_MODE_PROPERTY},
            type={ValueType.NUMBER},
        ),
        data_template=DynamicCurrentTempClimateDataTemplate(
            lookup_table={
                # External Sensor
                "A2": ZwaveValueID(
                    property_=THERMOSTAT_CURRENT_TEMP_PROPERTY,
                    command_class=CommandClass.SENSOR_MULTILEVEL,
                    endpoint=2,
                ),
                "A2F": ZwaveValueID(
                    property_=THERMOSTAT_CURRENT_TEMP_PROPERTY,
                    command_class=CommandClass.SENSOR_MULTILEVEL,
                    endpoint=2,
                ),
                # Floor sensor
                "F": ZwaveValueID(
                    property_=THERMOSTAT_CURRENT_TEMP_PROPERTY,
                    command_class=CommandClass.SENSOR_MULTILEVEL,
                    endpoint=3,
                ),
            },
            dependent_value=ZwaveValueID(
                property_=2, command_class=CommandClass.CONFIGURATION, endpoint=0
            ),
        ),
    ),
    # FortrezZ SSA1/SSA2/SSA3
    ZWaveDiscoverySchema(
        platform=Platform.SELECT,
        hint="multilevel_switch",
        manufacturer_id={0x0084},
        product_id={0x0107, 0x0108, 0x010B, 0x0205},
        product_type={0x0311, 0x0313, 0x0331, 0x0341, 0x0343},
        primary_value=SWITCH_MULTILEVEL_CURRENT_VALUE_SCHEMA,
        data_template=BaseDiscoverySchemaDataTemplate(
            {
                0: "Off",
                33: "Strobe ONLY",
                66: "Siren ONLY",
                99: "Siren & Strobe FULL Alarm",
            },
        ),
    ),
    # HomeSeer HSM-200 v1
    ZWaveDiscoverySchema(
        platform=Platform.LIGHT,
        hint="black_is_off",
        manufacturer_id={0x001E},
        product_id={0x0001},
        product_type={0x0004},
        primary_value=ZWaveValueDiscoverySchema(
            command_class={CommandClass.SWITCH_COLOR},
            property={CURRENT_COLOR_PROPERTY},
            property_key={None},
        ),
        absent_values=[SWITCH_MULTILEVEL_CURRENT_VALUE_SCHEMA],
    ),
    # Logic Group ZDB5100
    ZWaveDiscoverySchema(
        platform=Platform.LIGHT,
        hint="black_is_off",
        manufacturer_id={0x0234},
        product_id={0x0121},
        product_type={0x0003},
        primary_value=ZWaveValueDiscoverySchema(
            command_class={CommandClass.SWITCH_COLOR},
            property={CURRENT_COLOR_PROPERTY},
            property_key={None},
        ),
    ),
    # ====== START OF GENERIC MAPPING SCHEMAS =======
    # locks
    # Door Lock CC
    ZWaveDiscoverySchema(
        platform=Platform.LOCK,
        primary_value=DOOR_LOCK_CURRENT_MODE_SCHEMA,
        allow_multi=True,
    ),
    ZWaveDiscoverySchema(
        platform=Platform.SELECT,
        primary_value=DOOR_LOCK_CURRENT_MODE_SCHEMA,
        hint="door_lock",
    ),
    # Only discover the Lock CC if the Door Lock CC isn't also present on the node
    ZWaveDiscoverySchema(
        platform=Platform.LOCK,
        primary_value=ZWaveValueDiscoverySchema(
            command_class={CommandClass.LOCK},
            property={LOCKED_PROPERTY},
            type={ValueType.BOOLEAN},
        ),
        absent_values=[DOOR_LOCK_CURRENT_MODE_SCHEMA],
    ),
    # door lock door status
    ZWaveDiscoverySchema(
        platform=Platform.BINARY_SENSOR,
        hint="property",
        primary_value=ZWaveValueDiscoverySchema(
            command_class={
                CommandClass.LOCK,
                CommandClass.DOOR_LOCK,
            },
            property={DOOR_STATUS_PROPERTY},
            type={ValueType.ANY},
        ),
    ),
    # thermostat fan
    ZWaveDiscoverySchema(
        platform=Platform.FAN,
        hint="thermostat_fan",
        primary_value=ZWaveValueDiscoverySchema(
            command_class={CommandClass.THERMOSTAT_FAN_MODE},
            property={THERMOSTAT_FAN_MODE_PROPERTY},
            type={ValueType.NUMBER},
        ),
        entity_registry_enabled_default=False,
    ),
    # humidifier
    # hygrostats supporting mode (and optional setpoint)
    ZWaveDiscoverySchema(
        platform=Platform.HUMIDIFIER,
        primary_value=ZWaveValueDiscoverySchema(
            command_class={CommandClass.HUMIDITY_CONTROL_MODE},
            property={HUMIDITY_CONTROL_MODE_PROPERTY},
            type={ValueType.NUMBER},
        ),
    ),
    # climate
    # thermostats supporting mode (and optional setpoint)
    ZWaveDiscoverySchema(
        platform=Platform.CLIMATE,
        primary_value=ZWaveValueDiscoverySchema(
            command_class={CommandClass.THERMOSTAT_MODE},
            property={THERMOSTAT_MODE_PROPERTY},
            type={ValueType.NUMBER},
        ),
    ),
    # thermostats supporting setpoint only (and thus not mode)
    ZWaveDiscoverySchema(
        platform=Platform.CLIMATE,
        primary_value=ZWaveValueDiscoverySchema(
            command_class={CommandClass.THERMOSTAT_SETPOINT},
            property={THERMOSTAT_SETPOINT_PROPERTY},
            type={ValueType.NUMBER},
        ),
        absent_values=[  # mode must not be present to prevent dupes
            ZWaveValueDiscoverySchema(
                command_class={CommandClass.THERMOSTAT_MODE},
                property={THERMOSTAT_MODE_PROPERTY},
                type={ValueType.NUMBER},
            ),
        ],
    ),
    # binary sensors
    # When CC is Sensor Binary and device class generic is Binary Sensor, entity should
    # be enabled by default
    ZWaveDiscoverySchema(
        platform=Platform.BINARY_SENSOR,
        hint="boolean",
        device_class_generic={"Binary Sensor"},
        primary_value=ZWaveValueDiscoverySchema(
            command_class={CommandClass.SENSOR_BINARY},
            type={ValueType.BOOLEAN},
        ),
    ),
    # Legacy binary sensors are phased out (replaced by notification sensors)
    # Disable by default to not confuse users
    ZWaveDiscoverySchema(
        platform=Platform.BINARY_SENSOR,
        hint="boolean",
        primary_value=ZWaveValueDiscoverySchema(
            command_class={CommandClass.SENSOR_BINARY},
            type={ValueType.BOOLEAN},
        ),
        entity_registry_enabled_default=False,
    ),
    ZWaveDiscoverySchema(
        platform=Platform.BINARY_SENSOR,
        hint="boolean",
        primary_value=ZWaveValueDiscoverySchema(
            command_class={
                CommandClass.BATTERY,
                CommandClass.SENSOR_ALARM,
            },
            type={ValueType.BOOLEAN},
        ),
    ),
    # binary sensor for Indicator CC
    ZWaveDiscoverySchema(
        platform=Platform.BINARY_SENSOR,
        hint="boolean",
        primary_value=ZWaveValueDiscoverySchema(
            command_class={CommandClass.INDICATOR},
            type={ValueType.BOOLEAN},
            readable=True,
            writeable=False,
        ),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # generic text sensors
    ZWaveDiscoverySchema(
        platform=Platform.SENSOR,
        hint="string_sensor",
        primary_value=ZWaveValueDiscoverySchema(
            command_class={CommandClass.SENSOR_ALARM},
            type={ValueType.STRING},
        ),
    ),
    # generic numeric sensors
    ZWaveDiscoverySchema(
        platform=Platform.SENSOR,
        hint="numeric_sensor",
        primary_value=ZWaveValueDiscoverySchema(
            command_class={
                CommandClass.BATTERY,
                CommandClass.ENERGY_PRODUCTION,
                CommandClass.SENSOR_ALARM,
                CommandClass.SENSOR_MULTILEVEL,
            },
            type={ValueType.NUMBER},
        ),
        data_template=NumericSensorDataTemplate(),
    ),
    ZWaveDiscoverySchema(
        platform=Platform.SENSOR,
        hint="numeric_sensor",
        primary_value=ZWaveValueDiscoverySchema(
            command_class={CommandClass.INDICATOR},
            type={ValueType.NUMBER},
            readable=True,
            writeable=False,
        ),
        data_template=NumericSensorDataTemplate(),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # Meter sensors for Meter CC
    ZWaveDiscoverySchema(
        platform=Platform.SENSOR,
        hint="meter",
        primary_value=ZWaveValueDiscoverySchema(
            command_class={
                CommandClass.METER,
            },
            type={ValueType.NUMBER},
            property={VALUE_PROPERTY},
        ),
        data_template=NumericSensorDataTemplate(),
    ),
    # number for Indicator CC (exclude property keys 3-5)
    ZWaveDiscoverySchema(
        platform=Platform.NUMBER,
        primary_value=ZWaveValueDiscoverySchema(
            command_class={CommandClass.INDICATOR},
            type={ValueType.NUMBER},
            not_property_key={3, 4, 5},
            readable=True,
            writeable=True,
        ),
        entity_category=EntityCategory.CONFIG,
    ),
    # button for Indicator CC
    ZWaveDiscoverySchema(
        platform=Platform.BUTTON,
        primary_value=ZWaveValueDiscoverySchema(
            command_class={CommandClass.INDICATOR},
            type={ValueType.BOOLEAN},
            readable=False,
            writeable=True,
        ),
        entity_category=EntityCategory.CONFIG,
    ),
    # binary switches
    ZWaveDiscoverySchema(
        platform=Platform.SWITCH,
        primary_value=SWITCH_BINARY_CURRENT_VALUE_SCHEMA,
    ),
    # switch for Indicator CC
    ZWaveDiscoverySchema(
        platform=Platform.SWITCH,
        hint="indicator",
        primary_value=ZWaveValueDiscoverySchema(
            command_class={CommandClass.INDICATOR},
            type={ValueType.BOOLEAN},
            readable=True,
            writeable=True,
        ),
        entity_category=EntityCategory.CONFIG,
    ),
    # binary switch
    # barrier operator signaling states
    ZWaveDiscoverySchema(
        platform=Platform.SWITCH,
        hint="barrier_event_signaling_state",
        primary_value=ZWaveValueDiscoverySchema(
            command_class={CommandClass.BARRIER_OPERATOR},
            property={SIGNALING_STATE_PROPERTY},
            type={ValueType.NUMBER},
        ),
    ),
    # cover
    # window coverings
    ZWaveDiscoverySchema(
        platform=Platform.COVER,
        hint="window_covering",
        primary_value=WINDOW_COVERING_COVER_CURRENT_VALUE_SCHEMA,
    ),
    ZWaveDiscoverySchema(
        platform=Platform.COVER,
        hint="window_covering",
        primary_value=WINDOW_COVERING_SLAT_CURRENT_VALUE_SCHEMA,
        absent_values=[WINDOW_COVERING_COVER_CURRENT_VALUE_SCHEMA],
    ),
    ZWaveDiscoverySchema(
        platform=Platform.COVER,
        hint="multilevel_switch",
        device_class_generic={"Multilevel Switch"},
        device_class_specific={
            "Motor Control Class A",
            "Motor Control Class B",
            "Motor Control Class C",
            "Multiposition Motor",
        },
        primary_value=SWITCH_MULTILEVEL_CURRENT_VALUE_SCHEMA,
        absent_values=[
            WINDOW_COVERING_COVER_CURRENT_VALUE_SCHEMA,
            WINDOW_COVERING_SLAT_CURRENT_VALUE_SCHEMA,
        ],
    ),
    # cover
    # motorized barriers
    ZWaveDiscoverySchema(
        platform=Platform.COVER,
        hint="motorized_barrier",
        primary_value=ZWaveValueDiscoverySchema(
            command_class={CommandClass.BARRIER_OPERATOR},
            property={CURRENT_STATE_PROPERTY},
            type={ValueType.NUMBER},
        ),
        required_values=[
            ZWaveValueDiscoverySchema(
                command_class={CommandClass.BARRIER_OPERATOR},
                property={TARGET_STATE_PROPERTY},
                type={ValueType.NUMBER},
            ),
        ],
    ),
    # fan
    ZWaveDiscoverySchema(
        platform=Platform.FAN,
        hint="fan",
        device_class_generic={"Multilevel Switch"},
        device_class_specific={"Fan Switch"},
        primary_value=SWITCH_MULTILEVEL_CURRENT_VALUE_SCHEMA,
        required_values=[SWITCH_MULTILEVEL_TARGET_VALUE_SCHEMA],
    ),
    # number platform
    # valve control for thermostats
    ZWaveDiscoverySchema(
        platform=Platform.NUMBER,
        hint="Valve control",
        device_class_generic={"Thermostat"},
        primary_value=SWITCH_MULTILEVEL_CURRENT_VALUE_SCHEMA,
    ),
    # lights
    # primary value is the currentValue (brightness)
    # catch any device with multilevel CC as light
    # NOTE: keep this at the bottom of the discovery scheme,
    # to handle all others that need the multilevel CC first
    ZWaveDiscoverySchema(
        platform=Platform.LIGHT,
        primary_value=SWITCH_MULTILEVEL_CURRENT_VALUE_SCHEMA,
    ),
    # light for Basic CC with target
    ZWaveDiscoverySchema(
        platform=Platform.LIGHT,
        primary_value=ZWaveValueDiscoverySchema(
            command_class={CommandClass.BASIC},
            type={ValueType.NUMBER},
            property={CURRENT_VALUE_PROPERTY},
        ),
        required_values=[
            ZWaveValueDiscoverySchema(
                command_class={CommandClass.BASIC},
                type={ValueType.NUMBER},
                property={TARGET_VALUE_PROPERTY},
            )
        ],
    ),
    # sensor for Basic CC without target
    ZWaveDiscoverySchema(
        platform=Platform.SENSOR,
        hint="numeric_sensor",
        primary_value=ZWaveValueDiscoverySchema(
            command_class={CommandClass.BASIC},
            type={ValueType.NUMBER},
            property={CURRENT_VALUE_PROPERTY},
        ),
        absent_values=[
            ZWaveValueDiscoverySchema(
                command_class={CommandClass.BASIC},
                type={ValueType.NUMBER},
                property={TARGET_VALUE_PROPERTY},
            )
        ],
    ),
    # sirens
    ZWaveDiscoverySchema(
        platform=Platform.SIREN,
        primary_value=SIREN_TONE_SCHEMA,
    ),
    # select
    # siren default tone
    ZWaveDiscoverySchema(
        platform=Platform.SELECT,
        hint="Default tone",
        primary_value=ZWaveValueDiscoverySchema(
            command_class={CommandClass.SOUND_SWITCH},
            property={DEFAULT_TONE_ID_PROPERTY},
            type={ValueType.NUMBER},
        ),
        required_values=[SIREN_TONE_SCHEMA],
    ),
    # number
    # siren default volume
    ZWaveDiscoverySchema(
        platform=Platform.NUMBER,
        hint="volume",
        primary_value=ZWaveValueDiscoverySchema(
            command_class={CommandClass.SOUND_SWITCH},
            property={DEFAULT_VOLUME_PROPERTY},
            type={ValueType.NUMBER},
        ),
        required_values=[SIREN_TONE_SCHEMA],
    ),
    # select
    # protection CC
    ZWaveDiscoverySchema(
        platform=Platform.SELECT,
        primary_value=ZWaveValueDiscoverySchema(
            command_class={CommandClass.PROTECTION},
            property={LOCAL_PROPERTY, RF_PROPERTY},
            type={ValueType.NUMBER},
        ),
    ),
    # button
    # Notification CC idle
    ZWaveDiscoverySchema(
        platform=Platform.BUTTON,
        hint="notification idle",
        primary_value=ZWaveValueDiscoverySchema(
            command_class={CommandClass.NOTIFICATION},
            type={ValueType.NUMBER},
            any_available_states={(0, "idle")},
        ),
        allow_multi=True,
    ),
    # event
    # stateful = False
    ZWaveDiscoverySchema(
        platform=Platform.EVENT,
        hint="stateless",
        primary_value=ZWaveValueDiscoverySchema(
            stateful=False,
        ),
    ),
    # button
    # Meter CC idle
    ZWaveDiscoverySchema(
        platform=Platform.BUTTON,
        hint="meter reset",
        primary_value=ZWaveValueDiscoverySchema(
            command_class={CommandClass.METER},
            property={RESET_METER_PROPERTY},
            type={ValueType.BOOLEAN},
        ),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ZWaveDiscoverySchema(
        platform=Platform.BINARY_SENSOR,
        hint="notification",
        primary_value=ZWaveValueDiscoverySchema(
            command_class={
                CommandClass.NOTIFICATION,
            },
            type={ValueType.NUMBER},
        ),
        # set allow-multi to true because some of the notification sensors
        # can not be mapped to a binary sensor and must be handled as a regular sensor
        allow_multi=True,
    ),
    # alarmType, alarmLevel (Notification CC)
    ZWaveDiscoverySchema(
        platform=Platform.SENSOR,
        hint="notification_alarm",
        primary_value=ZWaveValueDiscoverySchema(
            command_class={
                CommandClass.NOTIFICATION,
            },
            property={"alarmType", "alarmLevel"},
            type={ValueType.NUMBER},
        ),
        entity_registry_enabled_default=False,
    ),
    # fallback sensors within Notification CC
    ZWaveDiscoverySchema(
        platform=Platform.SENSOR,
        hint="notification",
        primary_value=ZWaveValueDiscoverySchema(
            command_class={
                CommandClass.NOTIFICATION,
            },
            type={ValueType.NUMBER},
        ),
    ),
]


@callback
def async_discover_node_values(
    node: ZwaveNode, device: DeviceEntry, discovered_value_ids: dict[str, set[str]]
) -> Generator[ZwaveDiscoveryInfo]:
    """Run discovery on ZWave node and return matching (primary) values."""
    for value in node.values.values():
        # We don't need to rediscover an already processed value_id
        if value.value_id not in discovered_value_ids[device.id]:
            yield from async_discover_single_value(value, device, discovered_value_ids)


@callback
def async_discover_single_value(
    value: ZwaveValue, device: DeviceEntry, discovered_value_ids: dict[str, set[str]]
) -> Generator[ZwaveDiscoveryInfo]:
    """Run discovery on a single ZWave value and return matching schema info."""
    for schema in DISCOVERY_SCHEMAS:
        # abort if attribute(s) already discovered
        if value.value_id in discovered_value_ids[device.id]:
            continue

        # check manufacturer_id, product_id, product_type
        if (
            (
                schema.manufacturer_id is not None
                and value.node.manufacturer_id not in schema.manufacturer_id
            )
            or (
                schema.product_id is not None
                and value.node.product_id not in schema.product_id
            )
            or (
                schema.product_type is not None
                and value.node.product_type not in schema.product_type
            )
        ):
            continue

        # check firmware_version_range
        if schema.firmware_version_range is not None and (
            (
                schema.firmware_version_range.min is not None
                and schema.firmware_version_range.min_ver
                > AwesomeVersion(value.node.firmware_version)
            )
            or (
                schema.firmware_version_range.max is not None
                and schema.firmware_version_range.max_ver
                < AwesomeVersion(value.node.firmware_version)
            )
        ):
            continue

        # check device_class_generic
        if schema.device_class_generic and (
            not value.node.device_class
            or not any(
                value.node.device_class.generic.label == val
                for val in schema.device_class_generic
            )
        ):
            continue

        # check device_class_specific
        if schema.device_class_specific and (
            not value.node.device_class
            or not any(
                value.node.device_class.specific.label == val
                for val in schema.device_class_specific
            )
        ):
            continue

        # check primary value
        if not check_value(value, schema.primary_value):
            continue

        # check additional required values
        if schema.required_values is not None and not all(
            any(check_value(val, val_scheme) for val in value.node.values.values())
            for val_scheme in schema.required_values
        ):
            continue

        # check for values that may not be present
        if schema.absent_values is not None and any(
            any(check_value(val, val_scheme) for val in value.node.values.values())
            for val_scheme in schema.absent_values
        ):
            continue

        # resolve helper data from template
        resolved_data = None
        additional_value_ids_to_watch = set()
        if schema.data_template:
            try:
                resolved_data = schema.data_template.resolve_data(value)
            except UnknownValueData as err:
                LOGGER.error(
                    "Discovery for value %s on device '%s' (%s) will be skipped: %s",
                    value,
                    device.name_by_user or device.name,
                    value.node,
                    err,
                )
                continue
            additional_value_ids_to_watch = schema.data_template.value_ids_to_watch(
                resolved_data
            )

        # all checks passed, this value belongs to an entity
        yield ZwaveDiscoveryInfo(
            node=value.node,
            primary_value=value,
            assumed_state=schema.assumed_state,
            platform=schema.platform,
            platform_hint=schema.hint,
            platform_data_template=schema.data_template,
            platform_data=resolved_data,
            additional_value_ids_to_watch=additional_value_ids_to_watch,
            entity_registry_enabled_default=schema.entity_registry_enabled_default,
            entity_category=schema.entity_category,
        )

        # prevent re-discovery of the (primary) value if not allowed
        if not schema.allow_multi:
            discovered_value_ids[device.id].add(value.value_id)

    # prevent re-discovery of the (primary) value after all schemas have been checked
    discovered_value_ids[device.id].add(value.value_id)

    if value.command_class == CommandClass.CONFIGURATION:
        yield from async_discover_single_configuration_value(
            cast(ConfigurationValue, value)
        )


@callback
def async_discover_single_configuration_value(
    value: ConfigurationValue,
) -> Generator[ZwaveDiscoveryInfo]:
    """Run discovery on single Z-Wave configuration value and return schema matches."""
    if value.metadata.writeable and value.metadata.readable:
        if value.configuration_value_type == ConfigurationValueType.ENUMERATED:
            yield ZwaveDiscoveryInfo(
                node=value.node,
                primary_value=value,
                assumed_state=False,
                platform=Platform.SELECT,
                platform_hint="config_parameter",
                platform_data=None,
                additional_value_ids_to_watch=set(),
                entity_registry_enabled_default=False,
            )
        elif value.configuration_value_type in (
            ConfigurationValueType.RANGE,
            ConfigurationValueType.MANUAL_ENTRY,
        ):
            yield ZwaveDiscoveryInfo(
                node=value.node,
                primary_value=value,
                assumed_state=False,
                platform=Platform.NUMBER,
                platform_hint="config_parameter",
                platform_data=None,
                additional_value_ids_to_watch=set(),
                entity_registry_enabled_default=False,
            )
        elif value.configuration_value_type == ConfigurationValueType.BOOLEAN:
            yield ZwaveDiscoveryInfo(
                node=value.node,
                primary_value=value,
                assumed_state=False,
                platform=Platform.SWITCH,
                platform_hint="config_parameter",
                platform_data=None,
                additional_value_ids_to_watch=set(),
                entity_registry_enabled_default=False,
            )
    elif not value.metadata.writeable and value.metadata.readable:
        if value.configuration_value_type == ConfigurationValueType.BOOLEAN:
            yield ZwaveDiscoveryInfo(
                node=value.node,
                primary_value=value,
                assumed_state=False,
                platform=Platform.BINARY_SENSOR,
                platform_hint="config_parameter",
                platform_data=None,
                additional_value_ids_to_watch=set(),
                entity_registry_enabled_default=False,
            )
        else:
            yield ZwaveDiscoveryInfo(
                node=value.node,
                primary_value=value,
                assumed_state=False,
                platform=Platform.SENSOR,
                platform_hint="config_parameter",
                platform_data=None,
                additional_value_ids_to_watch=set(),
                entity_registry_enabled_default=False,
            )


@callback
def check_value(value: ZwaveValue, schema: ZWaveValueDiscoverySchema) -> bool:
    """Check if value matches scheme."""
    # check command_class
    if (
        schema.command_class is not None
        and value.command_class not in schema.command_class
    ):
        return False
    # check endpoint
    if schema.endpoint is not None and value.endpoint not in schema.endpoint:
        return False
    # check property
    if schema.property is not None and value.property_ not in schema.property:
        return False
    # check property_name
    if (
        schema.property_name is not None
        and value.property_name not in schema.property_name
    ):
        return False
    # check property_key
    if (
        schema.property_key is not None
        and value.property_key not in schema.property_key
    ):
        return False
    # check property_key against not_property_key set
    if (
        schema.not_property_key is not None
        and value.property_key in schema.not_property_key
    ):
        return False
    # check metadata_type
    if schema.type is not None and value.metadata.type not in schema.type:
        return False
    # check metadata_readable
    if schema.readable is not None and value.metadata.readable != schema.readable:
        return False
    # check metadata_writeable
    if schema.writeable is not None and value.metadata.writeable != schema.writeable:
        return False
    # check available states
    if (
        schema.any_available_states is not None
        and value.metadata.states is not None
        and not any(
            str(key) in value.metadata.states and value.metadata.states[str(key)] == val
            for key, val in schema.any_available_states
        )
    ):
        return False
    # check value
    if schema.value is not None and value.value not in schema.value:
        return False
    # check metadata_stateful
    if schema.stateful is not None and value.metadata.stateful != schema.stateful:
        return False
    return True
