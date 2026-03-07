import datetime

from google.protobuf import duration_pb2 as _duration_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
import wdl_event_importance_pb2 as _wdl_event_importance_pb2
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class DayOfWeek(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    DAY_OF_WEEK_UNSPECIFIED: _ClassVar[DayOfWeek]
    DAY_OF_WEEK_SUNDAY: _ClassVar[DayOfWeek]
    DAY_OF_WEEK_MONDAY: _ClassVar[DayOfWeek]
    DAY_OF_WEEK_TUESDAY: _ClassVar[DayOfWeek]
    DAY_OF_WEEK_WEDNESDAY: _ClassVar[DayOfWeek]
    DAY_OF_WEEK_THURSDAY: _ClassVar[DayOfWeek]
    DAY_OF_WEEK_FRIDAY: _ClassVar[DayOfWeek]
    DAY_OF_WEEK_SATURDAY: _ClassVar[DayOfWeek]

class MonthOfYear(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    MONTH_OF_YEAR_UNSPECIFIED: _ClassVar[MonthOfYear]
    MONTH_OF_YEAR_JANUARY: _ClassVar[MonthOfYear]
    MONTH_OF_YEAR_FEBRUARY: _ClassVar[MonthOfYear]
    MONTH_OF_YEAR_MARCH: _ClassVar[MonthOfYear]
    MONTH_OF_YEAR_APRIL: _ClassVar[MonthOfYear]
    MONTH_OF_YEAR_MAY: _ClassVar[MonthOfYear]
    MONTH_OF_YEAR_JUNE: _ClassVar[MonthOfYear]
    MONTH_OF_YEAR_JULY: _ClassVar[MonthOfYear]
    MONTH_OF_YEAR_AUGUST: _ClassVar[MonthOfYear]
    MONTH_OF_YEAR_SEPTEMBER: _ClassVar[MonthOfYear]
    MONTH_OF_YEAR_OCTOBER: _ClassVar[MonthOfYear]
    MONTH_OF_YEAR_NOVEMBER: _ClassVar[MonthOfYear]
    MONTH_OF_YEAR_DECEMBER: _ClassVar[MonthOfYear]

class ResourceType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    RESOURCE_TYPE_UNSPECIFIED: _ClassVar[ResourceType]
    RESOURCE_TYPE_DEVICE: _ClassVar[ResourceType]
    RESOURCE_TYPE_USER: _ClassVar[ResourceType]
    RESOURCE_TYPE_ACCOUNT: _ClassVar[ResourceType]
    RESOURCE_TYPE_AREA: _ClassVar[ResourceType]
    RESOURCE_TYPE_FIXTURE: _ClassVar[ResourceType]
    RESOURCE_TYPE_GROUP: _ClassVar[ResourceType]
    RESOURCE_TYPE_ANNOTATION: _ClassVar[ResourceType]
    RESOURCE_TYPE_STRUCTURE: _ClassVar[ResourceType]
    RESOURCE_TYPE_GUEST: _ClassVar[ResourceType]
    RESOURCE_TYPE_SERVICE: _ClassVar[ResourceType]

class QuantityType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    QUANTITY_TYPE_UNSPECIFIED: _ClassVar[QuantityType]
    LENGTH: _ClassVar[QuantityType]
    MASS: _ClassVar[QuantityType]
    DURATION: _ClassVar[QuantityType]
    CURRENT: _ClassVar[QuantityType]
    TEMPERATURE: _ClassVar[QuantityType]
    LUMINOUS_INTENSITY: _ClassVar[QuantityType]
    AREA: _ClassVar[QuantityType]
    VOLUME: _ClassVar[QuantityType]
    VELOCITY: _ClassVar[QuantityType]
    ACCELERATION: _ClassVar[QuantityType]
    FREQUENCY: _ClassVar[QuantityType]
    ENERGY: _ClassVar[QuantityType]
    ELECTRIC_CHARGE: _ClassVar[QuantityType]
    VOLTAGE: _ClassVar[QuantityType]
    RESISTANCE: _ClassVar[QuantityType]
    MAGNETIC_FLUX_DENSITY: _ClassVar[QuantityType]
    ILLUMINANCE: _ClassVar[QuantityType]
    HUMIDITY: _ClassVar[QuantityType]
    DBM: _ClassVar[QuantityType]
    PPM: _ClassVar[QuantityType]
    PIRMEASUREMENT: _ClassVar[QuantityType]
    NORMALIZED: _ClassVar[QuantityType]
    ANGLE: _ClassVar[QuantityType]
DAY_OF_WEEK_UNSPECIFIED: DayOfWeek
DAY_OF_WEEK_SUNDAY: DayOfWeek
DAY_OF_WEEK_MONDAY: DayOfWeek
DAY_OF_WEEK_TUESDAY: DayOfWeek
DAY_OF_WEEK_WEDNESDAY: DayOfWeek
DAY_OF_WEEK_THURSDAY: DayOfWeek
DAY_OF_WEEK_FRIDAY: DayOfWeek
DAY_OF_WEEK_SATURDAY: DayOfWeek
MONTH_OF_YEAR_UNSPECIFIED: MonthOfYear
MONTH_OF_YEAR_JANUARY: MonthOfYear
MONTH_OF_YEAR_FEBRUARY: MonthOfYear
MONTH_OF_YEAR_MARCH: MonthOfYear
MONTH_OF_YEAR_APRIL: MonthOfYear
MONTH_OF_YEAR_MAY: MonthOfYear
MONTH_OF_YEAR_JUNE: MonthOfYear
MONTH_OF_YEAR_JULY: MonthOfYear
MONTH_OF_YEAR_AUGUST: MonthOfYear
MONTH_OF_YEAR_SEPTEMBER: MonthOfYear
MONTH_OF_YEAR_OCTOBER: MonthOfYear
MONTH_OF_YEAR_NOVEMBER: MonthOfYear
MONTH_OF_YEAR_DECEMBER: MonthOfYear
RESOURCE_TYPE_UNSPECIFIED: ResourceType
RESOURCE_TYPE_DEVICE: ResourceType
RESOURCE_TYPE_USER: ResourceType
RESOURCE_TYPE_ACCOUNT: ResourceType
RESOURCE_TYPE_AREA: ResourceType
RESOURCE_TYPE_FIXTURE: ResourceType
RESOURCE_TYPE_GROUP: ResourceType
RESOURCE_TYPE_ANNOTATION: ResourceType
RESOURCE_TYPE_STRUCTURE: ResourceType
RESOURCE_TYPE_GUEST: ResourceType
RESOURCE_TYPE_SERVICE: ResourceType
QUANTITY_TYPE_UNSPECIFIED: QuantityType
LENGTH: QuantityType
MASS: QuantityType
DURATION: QuantityType
CURRENT: QuantityType
TEMPERATURE: QuantityType
LUMINOUS_INTENSITY: QuantityType
AREA: QuantityType
VOLUME: QuantityType
VELOCITY: QuantityType
ACCELERATION: QuantityType
FREQUENCY: QuantityType
ENERGY: QuantityType
ELECTRIC_CHARGE: QuantityType
VOLTAGE: QuantityType
RESISTANCE: QuantityType
MAGNETIC_FLUX_DENSITY: QuantityType
ILLUMINANCE: QuantityType
HUMIDITY: QuantityType
DBM: QuantityType
PPM: QuantityType
PIRMEASUREMENT: QuantityType
NORMALIZED: QuantityType
ANGLE: QuantityType

class ResourceId(_message.Message):
    __slots__ = ("resourceId",)
    RESOURCEID_FIELD_NUMBER: _ClassVar[int]
    resourceId: str
    def __init__(self, resourceId: _Optional[str] = ...) -> None: ...

class ResourceName(_message.Message):
    __slots__ = ("resourceName",)
    RESOURCENAME_FIELD_NUMBER: _ClassVar[int]
    resourceName: str
    def __init__(self, resourceName: _Optional[str] = ...) -> None: ...

class TraitTypeId(_message.Message):
    __slots__ = ("traitTypeId",)
    TRAITTYPEID_FIELD_NUMBER: _ClassVar[int]
    traitTypeId: int
    def __init__(self, traitTypeId: _Optional[int] = ...) -> None: ...

class TraitTypeInstance(_message.Message):
    __slots__ = ("traitTypeId", "instanceId")
    TRAITTYPEID_FIELD_NUMBER: _ClassVar[int]
    INSTANCEID_FIELD_NUMBER: _ClassVar[int]
    traitTypeId: TraitTypeId
    instanceId: int
    def __init__(self, traitTypeId: _Optional[_Union[TraitTypeId, _Mapping]] = ..., instanceId: _Optional[int] = ...) -> None: ...

class TraitInstanceId(_message.Message):
    __slots__ = ("traitInstanceLabel", "traitInstanceId")
    class TraitInstanceCase(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        TRAIT_INSTANCE_NOT_SET: _ClassVar[TraitInstanceId.TraitInstanceCase]
        TRAIT_INSTANCE_LABEL: _ClassVar[TraitInstanceId.TraitInstanceCase]
        TRAIT_INSTANCE_ID: _ClassVar[TraitInstanceId.TraitInstanceCase]
    TRAIT_INSTANCE_NOT_SET: TraitInstanceId.TraitInstanceCase
    TRAIT_INSTANCE_LABEL: TraitInstanceId.TraitInstanceCase
    TRAIT_INSTANCE_ID: TraitInstanceId.TraitInstanceCase
    TRAITINSTANCELABEL_FIELD_NUMBER: _ClassVar[int]
    TRAITINSTANCEID_FIELD_NUMBER: _ClassVar[int]
    traitInstanceLabel: str
    traitInstanceId: TraitTypeInstance
    def __init__(self, traitInstanceLabel: _Optional[str] = ..., traitInstanceId: _Optional[_Union[TraitTypeInstance, _Mapping]] = ...) -> None: ...

class FullTraitInstanceId(_message.Message):
    __slots__ = ("resourceId", "traitInstanceId")
    RESOURCEID_FIELD_NUMBER: _ClassVar[int]
    TRAITINSTANCEID_FIELD_NUMBER: _ClassVar[int]
    resourceId: ResourceId
    traitInstanceId: TraitInstanceId
    def __init__(self, resourceId: _Optional[_Union[ResourceId, _Mapping]] = ..., traitInstanceId: _Optional[_Union[TraitInstanceId, _Mapping]] = ...) -> None: ...

class InterfaceName(_message.Message):
    __slots__ = ("interfaceName",)
    INTERFACENAME_FIELD_NUMBER: _ClassVar[int]
    interfaceName: str
    def __init__(self, interfaceName: _Optional[str] = ...) -> None: ...

class EventId(_message.Message):
    __slots__ = ("resourceId", "importance", "id")
    RESOURCEID_FIELD_NUMBER: _ClassVar[int]
    IMPORTANCE_FIELD_NUMBER: _ClassVar[int]
    ID_FIELD_NUMBER: _ClassVar[int]
    resourceId: ResourceId
    importance: _wdl_event_importance_pb2.EventImportance
    id: int
    def __init__(self, resourceId: _Optional[_Union[ResourceId, _Mapping]] = ..., importance: _Optional[_Union[_wdl_event_importance_pb2.EventImportance, str]] = ..., id: _Optional[int] = ...) -> None: ...

class ProfileSpecificStatusCode(_message.Message):
    __slots__ = ("profileId", "statusCode")
    PROFILEID_FIELD_NUMBER: _ClassVar[int]
    STATUSCODE_FIELD_NUMBER: _ClassVar[int]
    profileId: int
    statusCode: int
    def __init__(self, profileId: _Optional[int] = ..., statusCode: _Optional[int] = ...) -> None: ...

class StringRef(_message.Message):
    __slots__ = ("literal", "reference")
    class StringRefCase(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        STRING_REF_NOT_SET: _ClassVar[StringRef.StringRefCase]
        LITERAL: _ClassVar[StringRef.StringRefCase]
        REFERENCE: _ClassVar[StringRef.StringRefCase]
    STRING_REF_NOT_SET: StringRef.StringRefCase
    LITERAL: StringRef.StringRefCase
    REFERENCE: StringRef.StringRefCase
    LITERAL_FIELD_NUMBER: _ClassVar[int]
    REFERENCE_FIELD_NUMBER: _ClassVar[int]
    literal: str
    reference: int
    def __init__(self, literal: _Optional[str] = ..., reference: _Optional[int] = ...) -> None: ...

class Timer(_message.Message):
    __slots__ = ("time", "timeBasis")
    TIME_FIELD_NUMBER: _ClassVar[int]
    TIMEBASIS_FIELD_NUMBER: _ClassVar[int]
    time: _duration_pb2.Duration
    timeBasis: _timestamp_pb2.Timestamp
    def __init__(self, time: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ..., timeBasis: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class TimeOfDay(_message.Message):
    __slots__ = ("hour", "minute", "second")
    HOUR_FIELD_NUMBER: _ClassVar[int]
    MINUTE_FIELD_NUMBER: _ClassVar[int]
    SECOND_FIELD_NUMBER: _ClassVar[int]
    hour: int
    minute: int
    second: int
    def __init__(self, hour: _Optional[int] = ..., minute: _Optional[int] = ..., second: _Optional[int] = ...) -> None: ...
