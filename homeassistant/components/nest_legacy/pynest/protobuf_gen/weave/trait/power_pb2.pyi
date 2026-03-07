from google.protobuf import wrappers_pb2 as _wrappers_pb2
from ...weave import common_pb2 as _common_pb2
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class PowerSourceTrait(_message.Message):
    __slots__ = ("type", "assessedVoltage", "assessedCurrent", "assessedFrequency", "condition", "status", "present")
    class PowerSourceCondition(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        POWER_SOURCE_CONDITION_UNSPECIFIED: _ClassVar[PowerSourceTrait.PowerSourceCondition]
        POWER_SOURCE_CONDITION_NOMINAL: _ClassVar[PowerSourceTrait.PowerSourceCondition]
        POWER_SOURCE_CONDITION_CRITICAL: _ClassVar[PowerSourceTrait.PowerSourceCondition]
    POWER_SOURCE_CONDITION_UNSPECIFIED: PowerSourceTrait.PowerSourceCondition
    POWER_SOURCE_CONDITION_NOMINAL: PowerSourceTrait.PowerSourceCondition
    POWER_SOURCE_CONDITION_CRITICAL: PowerSourceTrait.PowerSourceCondition
    class PowerSourceStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        POWER_SOURCE_STATUS_UNSPECIFIED: _ClassVar[PowerSourceTrait.PowerSourceStatus]
        POWER_SOURCE_STATUS_ACTIVE: _ClassVar[PowerSourceTrait.PowerSourceStatus]
        POWER_SOURCE_STATUS_STANDBY: _ClassVar[PowerSourceTrait.PowerSourceStatus]
        POWER_SOURCE_STATUS_INACTIVE: _ClassVar[PowerSourceTrait.PowerSourceStatus]
    POWER_SOURCE_STATUS_UNSPECIFIED: PowerSourceTrait.PowerSourceStatus
    POWER_SOURCE_STATUS_ACTIVE: PowerSourceTrait.PowerSourceStatus
    POWER_SOURCE_STATUS_STANDBY: PowerSourceTrait.PowerSourceStatus
    POWER_SOURCE_STATUS_INACTIVE: PowerSourceTrait.PowerSourceStatus
    class PowerSourceChangedEvent(_message.Message):
        __slots__ = ("condition", "status")
        CONDITION_FIELD_NUMBER: _ClassVar[int]
        STATUS_FIELD_NUMBER: _ClassVar[int]
        condition: PowerSourceTrait.PowerSourceCondition
        status: PowerSourceTrait.PowerSourceStatus
        def __init__(self, condition: _Optional[_Union[PowerSourceTrait.PowerSourceCondition, str]] = ..., status: _Optional[_Union[PowerSourceTrait.PowerSourceStatus, str]] = ...) -> None: ...
    TYPE_FIELD_NUMBER: _ClassVar[int]
    ASSESSEDVOLTAGE_FIELD_NUMBER: _ClassVar[int]
    ASSESSEDCURRENT_FIELD_NUMBER: _ClassVar[int]
    ASSESSEDFREQUENCY_FIELD_NUMBER: _ClassVar[int]
    CONDITION_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    PRESENT_FIELD_NUMBER: _ClassVar[int]
    type: PowerSourceCapabilitiesTrait.PowerSourceType
    assessedVoltage: _wrappers_pb2.FloatValue
    assessedCurrent: _wrappers_pb2.FloatValue
    assessedFrequency: _wrappers_pb2.FloatValue
    condition: PowerSourceTrait.PowerSourceCondition
    status: PowerSourceTrait.PowerSourceStatus
    present: bool
    def __init__(self, type: _Optional[_Union[PowerSourceCapabilitiesTrait.PowerSourceType, str]] = ..., assessedVoltage: _Optional[_Union[_wrappers_pb2.FloatValue, _Mapping]] = ..., assessedCurrent: _Optional[_Union[_wrappers_pb2.FloatValue, _Mapping]] = ..., assessedFrequency: _Optional[_Union[_wrappers_pb2.FloatValue, _Mapping]] = ..., condition: _Optional[_Union[PowerSourceTrait.PowerSourceCondition, str]] = ..., status: _Optional[_Union[PowerSourceTrait.PowerSourceStatus, str]] = ..., present: bool = ...) -> None: ...

class PowerSourceCapabilitiesTrait(_message.Message):
    __slots__ = ("type", "description", "nominalVoltage", "maximumCurrent", "currentType", "order", "removable")
    class PowerSourceType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        POWER_SOURCE_TYPE_UNSPECIFIED: _ClassVar[PowerSourceCapabilitiesTrait.PowerSourceType]
        POWER_SOURCE_TYPE_BATTERY: _ClassVar[PowerSourceCapabilitiesTrait.PowerSourceType]
        POWER_SOURCE_TYPE_RECHARGEABLE_BATTERY: _ClassVar[PowerSourceCapabilitiesTrait.PowerSourceType]
    POWER_SOURCE_TYPE_UNSPECIFIED: PowerSourceCapabilitiesTrait.PowerSourceType
    POWER_SOURCE_TYPE_BATTERY: PowerSourceCapabilitiesTrait.PowerSourceType
    POWER_SOURCE_TYPE_RECHARGEABLE_BATTERY: PowerSourceCapabilitiesTrait.PowerSourceType
    class PowerSourceCurrentType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        POWER_SOURCE_CURRENT_TYPE_UNSPECIFIED: _ClassVar[PowerSourceCapabilitiesTrait.PowerSourceCurrentType]
        POWER_SOURCE_CURRENT_TYPE_DC: _ClassVar[PowerSourceCapabilitiesTrait.PowerSourceCurrentType]
        POWER_SOURCE_CURRENT_TYPE_AC: _ClassVar[PowerSourceCapabilitiesTrait.PowerSourceCurrentType]
    POWER_SOURCE_CURRENT_TYPE_UNSPECIFIED: PowerSourceCapabilitiesTrait.PowerSourceCurrentType
    POWER_SOURCE_CURRENT_TYPE_DC: PowerSourceCapabilitiesTrait.PowerSourceCurrentType
    POWER_SOURCE_CURRENT_TYPE_AC: PowerSourceCapabilitiesTrait.PowerSourceCurrentType
    TYPE_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    NOMINALVOLTAGE_FIELD_NUMBER: _ClassVar[int]
    MAXIMUMCURRENT_FIELD_NUMBER: _ClassVar[int]
    CURRENTTYPE_FIELD_NUMBER: _ClassVar[int]
    ORDER_FIELD_NUMBER: _ClassVar[int]
    REMOVABLE_FIELD_NUMBER: _ClassVar[int]
    type: PowerSourceCapabilitiesTrait.PowerSourceType
    description: _common_pb2.StringRef
    nominalVoltage: float
    maximumCurrent: _wrappers_pb2.FloatValue
    currentType: PowerSourceCapabilitiesTrait.PowerSourceCurrentType
    order: int
    removable: bool
    def __init__(self, type: _Optional[_Union[PowerSourceCapabilitiesTrait.PowerSourceType, str]] = ..., description: _Optional[_Union[_common_pb2.StringRef, _Mapping]] = ..., nominalVoltage: _Optional[float] = ..., maximumCurrent: _Optional[_Union[_wrappers_pb2.FloatValue, _Mapping]] = ..., currentType: _Optional[_Union[PowerSourceCapabilitiesTrait.PowerSourceCurrentType, str]] = ..., order: _Optional[int] = ..., removable: bool = ...) -> None: ...

class BatteryPowerSourceTrait(_message.Message):
    __slots__ = ("type", "assessedVoltage", "assessedCurrent", "assessedFrequency", "condition", "status", "present", "replacementIndicator", "remaining")
    class BatteryReplacementIndicator(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        BATTERY_REPLACEMENT_INDICATOR_UNSPECIFIED: _ClassVar[BatteryPowerSourceTrait.BatteryReplacementIndicator]
        BATTERY_REPLACEMENT_INDICATOR_NOT_AT_ALL: _ClassVar[BatteryPowerSourceTrait.BatteryReplacementIndicator]
        BATTERY_REPLACEMENT_INDICATOR_SOON: _ClassVar[BatteryPowerSourceTrait.BatteryReplacementIndicator]
        BATTERY_REPLACEMENT_INDICATOR_IMMEDIATELY: _ClassVar[BatteryPowerSourceTrait.BatteryReplacementIndicator]
    BATTERY_REPLACEMENT_INDICATOR_UNSPECIFIED: BatteryPowerSourceTrait.BatteryReplacementIndicator
    BATTERY_REPLACEMENT_INDICATOR_NOT_AT_ALL: BatteryPowerSourceTrait.BatteryReplacementIndicator
    BATTERY_REPLACEMENT_INDICATOR_SOON: BatteryPowerSourceTrait.BatteryReplacementIndicator
    BATTERY_REPLACEMENT_INDICATOR_IMMEDIATELY: BatteryPowerSourceTrait.BatteryReplacementIndicator
    class BatteryRemaining(_message.Message):
        __slots__ = ("remainingPercent", "remainingTime")
        REMAININGPERCENT_FIELD_NUMBER: _ClassVar[int]
        REMAININGTIME_FIELD_NUMBER: _ClassVar[int]
        remainingPercent: _wrappers_pb2.FloatValue
        remainingTime: _common_pb2.Timer
        def __init__(self, remainingPercent: _Optional[_Union[_wrappers_pb2.FloatValue, _Mapping]] = ..., remainingTime: _Optional[_Union[_common_pb2.Timer, _Mapping]] = ...) -> None: ...
    class BatteryChangedEvent(_message.Message):
        __slots__ = ("condition", "status", "replacementIndicator", "remaining")
        CONDITION_FIELD_NUMBER: _ClassVar[int]
        STATUS_FIELD_NUMBER: _ClassVar[int]
        REPLACEMENTINDICATOR_FIELD_NUMBER: _ClassVar[int]
        REMAINING_FIELD_NUMBER: _ClassVar[int]
        condition: PowerSourceTrait.PowerSourceCondition
        status: PowerSourceTrait.PowerSourceStatus
        replacementIndicator: BatteryPowerSourceTrait.BatteryReplacementIndicator
        remaining: BatteryPowerSourceTrait.BatteryRemaining
        def __init__(self, condition: _Optional[_Union[PowerSourceTrait.PowerSourceCondition, str]] = ..., status: _Optional[_Union[PowerSourceTrait.PowerSourceStatus, str]] = ..., replacementIndicator: _Optional[_Union[BatteryPowerSourceTrait.BatteryReplacementIndicator, str]] = ..., remaining: _Optional[_Union[BatteryPowerSourceTrait.BatteryRemaining, _Mapping]] = ...) -> None: ...
    TYPE_FIELD_NUMBER: _ClassVar[int]
    ASSESSEDVOLTAGE_FIELD_NUMBER: _ClassVar[int]
    ASSESSEDCURRENT_FIELD_NUMBER: _ClassVar[int]
    ASSESSEDFREQUENCY_FIELD_NUMBER: _ClassVar[int]
    CONDITION_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    PRESENT_FIELD_NUMBER: _ClassVar[int]
    REPLACEMENTINDICATOR_FIELD_NUMBER: _ClassVar[int]
    REMAINING_FIELD_NUMBER: _ClassVar[int]
    type: PowerSourceCapabilitiesTrait.PowerSourceType
    assessedVoltage: _wrappers_pb2.FloatValue
    assessedCurrent: _wrappers_pb2.FloatValue
    assessedFrequency: _wrappers_pb2.FloatValue
    condition: PowerSourceTrait.PowerSourceCondition
    status: PowerSourceTrait.PowerSourceStatus
    present: bool
    replacementIndicator: BatteryPowerSourceTrait.BatteryReplacementIndicator
    remaining: BatteryPowerSourceTrait.BatteryRemaining
    def __init__(self, type: _Optional[_Union[PowerSourceCapabilitiesTrait.PowerSourceType, str]] = ..., assessedVoltage: _Optional[_Union[_wrappers_pb2.FloatValue, _Mapping]] = ..., assessedCurrent: _Optional[_Union[_wrappers_pb2.FloatValue, _Mapping]] = ..., assessedFrequency: _Optional[_Union[_wrappers_pb2.FloatValue, _Mapping]] = ..., condition: _Optional[_Union[PowerSourceTrait.PowerSourceCondition, str]] = ..., status: _Optional[_Union[PowerSourceTrait.PowerSourceStatus, str]] = ..., present: bool = ..., replacementIndicator: _Optional[_Union[BatteryPowerSourceTrait.BatteryReplacementIndicator, str]] = ..., remaining: _Optional[_Union[BatteryPowerSourceTrait.BatteryRemaining, _Mapping]] = ...) -> None: ...
