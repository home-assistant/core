import datetime

from google.protobuf import duration_pb2 as _duration_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf import wrappers_pb2 as _wrappers_pb2
from ...nest.trait import hvac_pb2 as _hvac_pb2
from ...nest.trait import occupancy_pb2 as _occupancy_pb2
from ...weave import common_pb2 as _common_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class CameraObservationHistoryTrait(_message.Message):
    __slots__ = ()
    class CameraObservationHistoryRequest(_message.Message):
        __slots__ = ("queryStartTime", "queryEndTime")
        QUERYSTARTTIME_FIELD_NUMBER: _ClassVar[int]
        QUERYENDTIME_FIELD_NUMBER: _ClassVar[int]
        queryStartTime: _timestamp_pb2.Timestamp
        queryEndTime: _timestamp_pb2.Timestamp
        def __init__(self, queryStartTime: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., queryEndTime: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...
    class CameraObservationHistoryResponse(_message.Message):
        __slots__ = ("cameraEventWindow",)
        class CameraEventTimeWindow(_message.Message):
            __slots__ = ("uuid", "startTime", "endTime", "cameraEvent", "activityZone", "familiarFace", "timeWindowUrls", "unknown")
            class EventType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
                __slots__ = ()
                EVENT_UNSPECIFIED: _ClassVar[CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow.EventType]
                EVENT_MOTION: _ClassVar[CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow.EventType]
                EVENT_SOUND: _ClassVar[CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow.EventType]
                EVENT_PERSON: _ClassVar[CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow.EventType]
                EVENT_FACE: _ClassVar[CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow.EventType]
                EVENT_UNFAMILIAR_FACE: _ClassVar[CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow.EventType]
                EVENT_PERSON_TALKING: _ClassVar[CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow.EventType]
                EVENT_DOG_BARKING: _ClassVar[CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow.EventType]
                EVENT_DOORBELL: _ClassVar[CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow.EventType]
                EVENT_PACKAGE_DELIVERED: _ClassVar[CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow.EventType]
                EVENT_PACKAGE_RETRIEVED: _ClassVar[CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow.EventType]
                EVENT_SMOKE_ALARM: _ClassVar[CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow.EventType]
                EVENT_CO_ALARM: _ClassVar[CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow.EventType]
                EVENT_FIRE_ALARM: _ClassVar[CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow.EventType]
                EVENT_GLASS_BREAK: _ClassVar[CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow.EventType]
                EVENT_OFFLINE: _ClassVar[CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow.EventType]
                EVENT_BABY_CRYING: _ClassVar[CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow.EventType]
                EVENT_DOOR_KNOCK: _ClassVar[CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow.EventType]
                EVENT_VEHICLE: _ClassVar[CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow.EventType]
                EVENT_FACE_OTHER: _ClassVar[CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow.EventType]
                EVENT_PACKAGE_IN_TRANSIT: _ClassVar[CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow.EventType]
                EVENT_ANIMAL_DOG: _ClassVar[CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow.EventType]
                EVENT_ANIMAL_CAT: _ClassVar[CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow.EventType]
                EVENT_ANIMAL: _ClassVar[CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow.EventType]
                EVENT_MAGIC_MOMENT: _ClassVar[CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow.EventType]
                EVENT_CTD: _ClassVar[CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow.EventType]
                EVENT_CMDT: _ClassVar[CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow.EventType]
                EVENT_TALKBACK: _ClassVar[CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow.EventType]
                EVENT_SECURITY_ALARM: _ClassVar[CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow.EventType]
                EVENT_NOT_A_FACE: _ClassVar[CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow.EventType]
                EVENT_DOOR_OPEN: _ClassVar[CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow.EventType]
                EVENT_DOOR_CLOSE: _ClassVar[CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow.EventType]
                EVENT_DOOR_AJAR: _ClassVar[CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow.EventType]
                EVENT_UNRECOGNIZED: _ClassVar[CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow.EventType]
            EVENT_UNSPECIFIED: CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow.EventType
            EVENT_MOTION: CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow.EventType
            EVENT_SOUND: CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow.EventType
            EVENT_PERSON: CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow.EventType
            EVENT_FACE: CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow.EventType
            EVENT_UNFAMILIAR_FACE: CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow.EventType
            EVENT_PERSON_TALKING: CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow.EventType
            EVENT_DOG_BARKING: CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow.EventType
            EVENT_DOORBELL: CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow.EventType
            EVENT_PACKAGE_DELIVERED: CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow.EventType
            EVENT_PACKAGE_RETRIEVED: CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow.EventType
            EVENT_SMOKE_ALARM: CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow.EventType
            EVENT_CO_ALARM: CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow.EventType
            EVENT_FIRE_ALARM: CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow.EventType
            EVENT_GLASS_BREAK: CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow.EventType
            EVENT_OFFLINE: CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow.EventType
            EVENT_BABY_CRYING: CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow.EventType
            EVENT_DOOR_KNOCK: CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow.EventType
            EVENT_VEHICLE: CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow.EventType
            EVENT_FACE_OTHER: CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow.EventType
            EVENT_PACKAGE_IN_TRANSIT: CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow.EventType
            EVENT_ANIMAL_DOG: CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow.EventType
            EVENT_ANIMAL_CAT: CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow.EventType
            EVENT_ANIMAL: CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow.EventType
            EVENT_MAGIC_MOMENT: CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow.EventType
            EVENT_CTD: CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow.EventType
            EVENT_CMDT: CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow.EventType
            EVENT_TALKBACK: CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow.EventType
            EVENT_SECURITY_ALARM: CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow.EventType
            EVENT_NOT_A_FACE: CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow.EventType
            EVENT_DOOR_OPEN: CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow.EventType
            EVENT_DOOR_CLOSE: CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow.EventType
            EVENT_DOOR_AJAR: CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow.EventType
            EVENT_UNRECOGNIZED: CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow.EventType
            class CameraEvent(_message.Message):
                __slots__ = ("eventId", "startTime", "endTime", "eventType", "familiarFace", "activityZone", "eventUrls")
                EVENTID_FIELD_NUMBER: _ClassVar[int]
                STARTTIME_FIELD_NUMBER: _ClassVar[int]
                ENDTIME_FIELD_NUMBER: _ClassVar[int]
                EVENTTYPE_FIELD_NUMBER: _ClassVar[int]
                FAMILIARFACE_FIELD_NUMBER: _ClassVar[int]
                ACTIVITYZONE_FIELD_NUMBER: _ClassVar[int]
                EVENTURLS_FIELD_NUMBER: _ClassVar[int]
                eventId: str
                startTime: _timestamp_pb2.Timestamp
                endTime: _timestamp_pb2.Timestamp
                eventType: _containers.RepeatedScalarFieldContainer[CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow.EventType]
                familiarFace: CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow.FamiliarFace
                activityZone: _containers.RepeatedCompositeFieldContainer[CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow.ActivityZone]
                eventUrls: CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow.EventUrls
                def __init__(self, eventId: _Optional[str] = ..., startTime: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., endTime: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., eventType: _Optional[_Iterable[_Union[CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow.EventType, str]]] = ..., familiarFace: _Optional[_Union[CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow.FamiliarFace, _Mapping]] = ..., activityZone: _Optional[_Iterable[_Union[CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow.ActivityZone, _Mapping]]] = ..., eventUrls: _Optional[_Union[CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow.EventUrls, _Mapping]] = ...) -> None: ...
            class EventUrls(_message.Message):
                __slots__ = ("snapshotUrl", "clipUrl")
                SNAPSHOTURL_FIELD_NUMBER: _ClassVar[int]
                CLIPURL_FIELD_NUMBER: _ClassVar[int]
                snapshotUrl: str
                clipUrl: _wrappers_pb2.StringValue
                def __init__(self, snapshotUrl: _Optional[str] = ..., clipUrl: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ...) -> None: ...
            class FamiliarFace(_message.Message):
                __slots__ = ("faceId", "faceName", "facePictureUrl")
                FACEID_FIELD_NUMBER: _ClassVar[int]
                FACENAME_FIELD_NUMBER: _ClassVar[int]
                FACEPICTUREURL_FIELD_NUMBER: _ClassVar[int]
                faceId: str
                faceName: str
                facePictureUrl: str
                def __init__(self, faceId: _Optional[str] = ..., faceName: _Optional[str] = ..., facePictureUrl: _Optional[str] = ...) -> None: ...
            class ActivityZone(_message.Message):
                __slots__ = ("zoneIndex", "name", "internalIndex")
                ZONEINDEX_FIELD_NUMBER: _ClassVar[int]
                NAME_FIELD_NUMBER: _ClassVar[int]
                INTERNALINDEX_FIELD_NUMBER: _ClassVar[int]
                zoneIndex: int
                name: str
                internalIndex: int
                def __init__(self, zoneIndex: _Optional[int] = ..., name: _Optional[str] = ..., internalIndex: _Optional[int] = ...) -> None: ...
            UUID_FIELD_NUMBER: _ClassVar[int]
            STARTTIME_FIELD_NUMBER: _ClassVar[int]
            ENDTIME_FIELD_NUMBER: _ClassVar[int]
            CAMERAEVENT_FIELD_NUMBER: _ClassVar[int]
            ACTIVITYZONE_FIELD_NUMBER: _ClassVar[int]
            FAMILIARFACE_FIELD_NUMBER: _ClassVar[int]
            TIMEWINDOWURLS_FIELD_NUMBER: _ClassVar[int]
            UNKNOWN_FIELD_NUMBER: _ClassVar[int]
            uuid: str
            startTime: _timestamp_pb2.Timestamp
            endTime: _timestamp_pb2.Timestamp
            cameraEvent: _containers.RepeatedCompositeFieldContainer[CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow.CameraEvent]
            activityZone: _containers.RepeatedCompositeFieldContainer[CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow.ActivityZone]
            familiarFace: CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow.FamiliarFace
            timeWindowUrls: CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow.EventUrls
            unknown: int
            def __init__(self, uuid: _Optional[str] = ..., startTime: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., endTime: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., cameraEvent: _Optional[_Iterable[_Union[CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow.CameraEvent, _Mapping]]] = ..., activityZone: _Optional[_Iterable[_Union[CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow.ActivityZone, _Mapping]]] = ..., familiarFace: _Optional[_Union[CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow.FamiliarFace, _Mapping]] = ..., timeWindowUrls: _Optional[_Union[CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow.EventUrls, _Mapping]] = ..., unknown: _Optional[int] = ...) -> None: ...
        CAMERAEVENTWINDOW_FIELD_NUMBER: _ClassVar[int]
        cameraEventWindow: CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow
        def __init__(self, cameraEventWindow: _Optional[_Union[CameraObservationHistoryTrait.CameraObservationHistoryResponse.CameraEventTimeWindow, _Mapping]] = ...) -> None: ...
    def __init__(self) -> None: ...

class EnergyHistoryTrait(_message.Message):
    __slots__ = ()
    class LegacyEnergyWinner(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        LEGACY_ENERGY_WINNER_UNSPECIFIED: _ClassVar[EnergyHistoryTrait.LegacyEnergyWinner]
        LEGACY_ENERGY_WINNER_USER: _ClassVar[EnergyHistoryTrait.LegacyEnergyWinner]
        LEGACY_ENERGY_WINNER_WEATHER: _ClassVar[EnergyHistoryTrait.LegacyEnergyWinner]
        LEGACY_ENERGY_WINNER_AWAY: _ClassVar[EnergyHistoryTrait.LegacyEnergyWinner]
        LEGACY_ENERGY_WINNER_AUTO_AWAY: _ClassVar[EnergyHistoryTrait.LegacyEnergyWinner]
        LEGACY_ENERGY_WINNER_TUNE_UP: _ClassVar[EnergyHistoryTrait.LegacyEnergyWinner]
        LEGACY_ENERGY_WINNER_AUTO_DEHUM: _ClassVar[EnergyHistoryTrait.LegacyEnergyWinner]
        LEGACY_ENERGY_WINNER_DEMAND_RESPONSE: _ClassVar[EnergyHistoryTrait.LegacyEnergyWinner]
        LEGACY_ENERGY_WINNER_TIME_OF_USE: _ClassVar[EnergyHistoryTrait.LegacyEnergyWinner]
    LEGACY_ENERGY_WINNER_UNSPECIFIED: EnergyHistoryTrait.LegacyEnergyWinner
    LEGACY_ENERGY_WINNER_USER: EnergyHistoryTrait.LegacyEnergyWinner
    LEGACY_ENERGY_WINNER_WEATHER: EnergyHistoryTrait.LegacyEnergyWinner
    LEGACY_ENERGY_WINNER_AWAY: EnergyHistoryTrait.LegacyEnergyWinner
    LEGACY_ENERGY_WINNER_AUTO_AWAY: EnergyHistoryTrait.LegacyEnergyWinner
    LEGACY_ENERGY_WINNER_TUNE_UP: EnergyHistoryTrait.LegacyEnergyWinner
    LEGACY_ENERGY_WINNER_AUTO_DEHUM: EnergyHistoryTrait.LegacyEnergyWinner
    LEGACY_ENERGY_WINNER_DEMAND_RESPONSE: EnergyHistoryTrait.LegacyEnergyWinner
    LEGACY_ENERGY_WINNER_TIME_OF_USE: EnergyHistoryTrait.LegacyEnergyWinner
    class LegacySetPointType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        LEGACY_SET_POINT_TYPE_UNSPECIFIED: _ClassVar[EnergyHistoryTrait.LegacySetPointType]
        LEGACY_SET_POINT_TYPE_HEAT: _ClassVar[EnergyHistoryTrait.LegacySetPointType]
        LEGACY_SET_POINT_TYPE_COOL: _ClassVar[EnergyHistoryTrait.LegacySetPointType]
        LEGACY_SET_POINT_TYPE_RANGE: _ClassVar[EnergyHistoryTrait.LegacySetPointType]
        LEGACY_SET_POINT_TYPE_EMERGENCY_HEAT: _ClassVar[EnergyHistoryTrait.LegacySetPointType]
    LEGACY_SET_POINT_TYPE_UNSPECIFIED: EnergyHistoryTrait.LegacySetPointType
    LEGACY_SET_POINT_TYPE_HEAT: EnergyHistoryTrait.LegacySetPointType
    LEGACY_SET_POINT_TYPE_COOL: EnergyHistoryTrait.LegacySetPointType
    LEGACY_SET_POINT_TYPE_RANGE: EnergyHistoryTrait.LegacySetPointType
    LEGACY_SET_POINT_TYPE_EMERGENCY_HEAT: EnergyHistoryTrait.LegacySetPointType
    class LegacyEventType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        LEGACY_EVENT_TYPE_UNSPECIFIED: _ClassVar[EnergyHistoryTrait.LegacyEventType]
        LEGACY_EVENT_TYPE_HEAT: _ClassVar[EnergyHistoryTrait.LegacyEventType]
        LEGACY_EVENT_TYPE_COOL: _ClassVar[EnergyHistoryTrait.LegacyEventType]
        LEGACY_EVENT_TYPE_RANGE: _ClassVar[EnergyHistoryTrait.LegacyEventType]
        LEGACY_EVENT_TYPE_AWAY: _ClassVar[EnergyHistoryTrait.LegacyEventType]
        LEGACY_EVENT_TYPE_AUTOAWAY: _ClassVar[EnergyHistoryTrait.LegacyEventType]
        LEGACY_EVENT_TYPE_OFF: _ClassVar[EnergyHistoryTrait.LegacyEventType]
        LEGACY_EVENT_TYPE_ON: _ClassVar[EnergyHistoryTrait.LegacyEventType]
        LEGACY_EVENT_TYPE_EMERGENCY_HEAT: _ClassVar[EnergyHistoryTrait.LegacyEventType]
        LEGACY_EVENT_TYPE_SUNLIGHT_CORRECTION: _ClassVar[EnergyHistoryTrait.LegacyEventType]
    LEGACY_EVENT_TYPE_UNSPECIFIED: EnergyHistoryTrait.LegacyEventType
    LEGACY_EVENT_TYPE_HEAT: EnergyHistoryTrait.LegacyEventType
    LEGACY_EVENT_TYPE_COOL: EnergyHistoryTrait.LegacyEventType
    LEGACY_EVENT_TYPE_RANGE: EnergyHistoryTrait.LegacyEventType
    LEGACY_EVENT_TYPE_AWAY: EnergyHistoryTrait.LegacyEventType
    LEGACY_EVENT_TYPE_AUTOAWAY: EnergyHistoryTrait.LegacyEventType
    LEGACY_EVENT_TYPE_OFF: EnergyHistoryTrait.LegacyEventType
    LEGACY_EVENT_TYPE_ON: EnergyHistoryTrait.LegacyEventType
    LEGACY_EVENT_TYPE_EMERGENCY_HEAT: EnergyHistoryTrait.LegacyEventType
    LEGACY_EVENT_TYPE_SUNLIGHT_CORRECTION: EnergyHistoryTrait.LegacyEventType
    class LegacyTouchedWhere(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        LEGACY_TOUCHED_WHERE_UNSPECIFIED: _ClassVar[EnergyHistoryTrait.LegacyTouchedWhere]
        LEGACY_TOUCHED_WHERE_SCHEDULE: _ClassVar[EnergyHistoryTrait.LegacyTouchedWhere]
        LEGACY_TOUCHED_WHERE_ADHOC: _ClassVar[EnergyHistoryTrait.LegacyTouchedWhere]
    LEGACY_TOUCHED_WHERE_UNSPECIFIED: EnergyHistoryTrait.LegacyTouchedWhere
    LEGACY_TOUCHED_WHERE_SCHEDULE: EnergyHistoryTrait.LegacyTouchedWhere
    LEGACY_TOUCHED_WHERE_ADHOC: EnergyHistoryTrait.LegacyTouchedWhere
    class LegacyEnergyHistoryRequest(_message.Message):
        __slots__ = ("queryStartTime", "queryEndTime")
        QUERYSTARTTIME_FIELD_NUMBER: _ClassVar[int]
        QUERYENDTIME_FIELD_NUMBER: _ClassVar[int]
        queryStartTime: _timestamp_pb2.Timestamp
        queryEndTime: _timestamp_pb2.Timestamp
        def __init__(self, queryStartTime: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., queryEndTime: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...
    class LegacyEnergyHistoryResponse(_message.Message):
        __slots__ = ("days", "recentMaxUsedSeconds")
        DAYS_FIELD_NUMBER: _ClassVar[int]
        RECENTMAXUSEDSECONDS_FIELD_NUMBER: _ClassVar[int]
        days: _containers.RepeatedCompositeFieldContainer[EnergyHistoryTrait.LegacyDayUsage]
        recentMaxUsedSeconds: _duration_pb2.Duration
        def __init__(self, days: _Optional[_Iterable[_Union[EnergyHistoryTrait.LegacyDayUsage, _Mapping]]] = ..., recentMaxUsedSeconds: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ...) -> None: ...
    class LegacyDayUsage(_message.Message):
        __slots__ = ("dayStart", "dayEnd", "totalHeatingSeconds", "totalCoolingSeconds", "totalFanCoolingSeconds", "totalHumidifierSeconds", "totalDehumidifierSeconds", "energyWinner", "energyLeaf", "recentAverageUsedSeconds", "secondsUsageOverAverage", "systemCapabilities", "cyclesIncomplete", "cycles", "eventsIncomplete", "usageEvents", "rates")
        DAYSTART_FIELD_NUMBER: _ClassVar[int]
        DAYEND_FIELD_NUMBER: _ClassVar[int]
        TOTALHEATINGSECONDS_FIELD_NUMBER: _ClassVar[int]
        TOTALCOOLINGSECONDS_FIELD_NUMBER: _ClassVar[int]
        TOTALFANCOOLINGSECONDS_FIELD_NUMBER: _ClassVar[int]
        TOTALHUMIDIFIERSECONDS_FIELD_NUMBER: _ClassVar[int]
        TOTALDEHUMIDIFIERSECONDS_FIELD_NUMBER: _ClassVar[int]
        ENERGYWINNER_FIELD_NUMBER: _ClassVar[int]
        ENERGYLEAF_FIELD_NUMBER: _ClassVar[int]
        RECENTAVERAGEUSEDSECONDS_FIELD_NUMBER: _ClassVar[int]
        SECONDSUSAGEOVERAVERAGE_FIELD_NUMBER: _ClassVar[int]
        SYSTEMCAPABILITIES_FIELD_NUMBER: _ClassVar[int]
        CYCLESINCOMPLETE_FIELD_NUMBER: _ClassVar[int]
        CYCLES_FIELD_NUMBER: _ClassVar[int]
        EVENTSINCOMPLETE_FIELD_NUMBER: _ClassVar[int]
        USAGEEVENTS_FIELD_NUMBER: _ClassVar[int]
        RATES_FIELD_NUMBER: _ClassVar[int]
        dayStart: _timestamp_pb2.Timestamp
        dayEnd: _timestamp_pb2.Timestamp
        totalHeatingSeconds: _duration_pb2.Duration
        totalCoolingSeconds: _duration_pb2.Duration
        totalFanCoolingSeconds: _duration_pb2.Duration
        totalHumidifierSeconds: _duration_pb2.Duration
        totalDehumidifierSeconds: _duration_pb2.Duration
        energyWinner: EnergyHistoryTrait.LegacyEnergyWinner
        energyLeaf: _wrappers_pb2.BoolValue
        recentAverageUsedSeconds: _wrappers_pb2.Int32Value
        secondsUsageOverAverage: _wrappers_pb2.Int32Value
        systemCapabilities: EnergyHistoryTrait.LegacySystemCapabilities
        cyclesIncomplete: bool
        cycles: _containers.RepeatedCompositeFieldContainer[EnergyHistoryTrait.LegacyHVACCycle]
        eventsIncomplete: bool
        usageEvents: _containers.RepeatedCompositeFieldContainer[EnergyHistoryTrait.LegacyHVACUsage]
        rates: _containers.RepeatedCompositeFieldContainer[EnergyHistoryTrait.LegacyRatePlanChange]
        def __init__(self, dayStart: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., dayEnd: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., totalHeatingSeconds: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ..., totalCoolingSeconds: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ..., totalFanCoolingSeconds: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ..., totalHumidifierSeconds: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ..., totalDehumidifierSeconds: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ..., energyWinner: _Optional[_Union[EnergyHistoryTrait.LegacyEnergyWinner, str]] = ..., energyLeaf: _Optional[_Union[_wrappers_pb2.BoolValue, _Mapping]] = ..., recentAverageUsedSeconds: _Optional[_Union[_wrappers_pb2.Int32Value, _Mapping]] = ..., secondsUsageOverAverage: _Optional[_Union[_wrappers_pb2.Int32Value, _Mapping]] = ..., systemCapabilities: _Optional[_Union[EnergyHistoryTrait.LegacySystemCapabilities, _Mapping]] = ..., cyclesIncomplete: bool = ..., cycles: _Optional[_Iterable[_Union[EnergyHistoryTrait.LegacyHVACCycle, _Mapping]]] = ..., eventsIncomplete: bool = ..., usageEvents: _Optional[_Iterable[_Union[EnergyHistoryTrait.LegacyHVACUsage, _Mapping]]] = ..., rates: _Optional[_Iterable[_Union[EnergyHistoryTrait.LegacyRatePlanChange, _Mapping]]] = ...) -> None: ...
    class LegacyHVACCycle(_message.Message):
        __slots__ = ("cycleStart", "duration", "isComplete", "heat1", "heat2", "heat3", "heatAux", "altHeat", "altHeat2", "emergencyHeat", "cool1", "cool2", "cool3", "fan", "fanCooling", "humidifier", "dehumidifier", "autoDehumdifier", "waterHeater")
        CYCLESTART_FIELD_NUMBER: _ClassVar[int]
        DURATION_FIELD_NUMBER: _ClassVar[int]
        ISCOMPLETE_FIELD_NUMBER: _ClassVar[int]
        HEAT1_FIELD_NUMBER: _ClassVar[int]
        HEAT2_FIELD_NUMBER: _ClassVar[int]
        HEAT3_FIELD_NUMBER: _ClassVar[int]
        HEATAUX_FIELD_NUMBER: _ClassVar[int]
        ALTHEAT_FIELD_NUMBER: _ClassVar[int]
        ALTHEAT2_FIELD_NUMBER: _ClassVar[int]
        EMERGENCYHEAT_FIELD_NUMBER: _ClassVar[int]
        COOL1_FIELD_NUMBER: _ClassVar[int]
        COOL2_FIELD_NUMBER: _ClassVar[int]
        COOL3_FIELD_NUMBER: _ClassVar[int]
        FAN_FIELD_NUMBER: _ClassVar[int]
        FANCOOLING_FIELD_NUMBER: _ClassVar[int]
        HUMIDIFIER_FIELD_NUMBER: _ClassVar[int]
        DEHUMIDIFIER_FIELD_NUMBER: _ClassVar[int]
        AUTODEHUMDIFIER_FIELD_NUMBER: _ClassVar[int]
        WATERHEATER_FIELD_NUMBER: _ClassVar[int]
        cycleStart: _timestamp_pb2.Timestamp
        duration: _duration_pb2.Duration
        isComplete: bool
        heat1: bool
        heat2: bool
        heat3: bool
        heatAux: bool
        altHeat: bool
        altHeat2: bool
        emergencyHeat: bool
        cool1: bool
        cool2: bool
        cool3: bool
        fan: bool
        fanCooling: bool
        humidifier: bool
        dehumidifier: bool
        autoDehumdifier: bool
        waterHeater: bool
        def __init__(self, cycleStart: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., duration: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ..., isComplete: bool = ..., heat1: bool = ..., heat2: bool = ..., heat3: bool = ..., heatAux: bool = ..., altHeat: bool = ..., altHeat2: bool = ..., emergencyHeat: bool = ..., cool1: bool = ..., cool2: bool = ..., cool3: bool = ..., fan: bool = ..., fanCooling: bool = ..., humidifier: bool = ..., dehumidifier: bool = ..., autoDehumdifier: bool = ..., waterHeater: bool = ...) -> None: ...
    class LegacySystemCapabilities(_message.Message):
        __slots__ = ("hasStage1Cool", "hasStage2Cool", "hasStage3Cool", "hasStage1Heat", "hasStage2Heat", "hasStage3Heat", "hasStage1AlternateHeat", "hasStage2AlternateHeat", "hasHumidifier", "hasDehumidifier", "hasDualFuel", "hasAuxHeat", "hasEmergencyHeat", "hasAirFilter", "hasFossilFuel", "hasHotWaterControl", "hasHeatPump", "hasHotWaterTemperature", "hasFan")
        HASSTAGE1COOL_FIELD_NUMBER: _ClassVar[int]
        HASSTAGE2COOL_FIELD_NUMBER: _ClassVar[int]
        HASSTAGE3COOL_FIELD_NUMBER: _ClassVar[int]
        HASSTAGE1HEAT_FIELD_NUMBER: _ClassVar[int]
        HASSTAGE2HEAT_FIELD_NUMBER: _ClassVar[int]
        HASSTAGE3HEAT_FIELD_NUMBER: _ClassVar[int]
        HASSTAGE1ALTERNATEHEAT_FIELD_NUMBER: _ClassVar[int]
        HASSTAGE2ALTERNATEHEAT_FIELD_NUMBER: _ClassVar[int]
        HASHUMIDIFIER_FIELD_NUMBER: _ClassVar[int]
        HASDEHUMIDIFIER_FIELD_NUMBER: _ClassVar[int]
        HASDUALFUEL_FIELD_NUMBER: _ClassVar[int]
        HASAUXHEAT_FIELD_NUMBER: _ClassVar[int]
        HASEMERGENCYHEAT_FIELD_NUMBER: _ClassVar[int]
        HASAIRFILTER_FIELD_NUMBER: _ClassVar[int]
        HASFOSSILFUEL_FIELD_NUMBER: _ClassVar[int]
        HASHOTWATERCONTROL_FIELD_NUMBER: _ClassVar[int]
        HASHEATPUMP_FIELD_NUMBER: _ClassVar[int]
        HASHOTWATERTEMPERATURE_FIELD_NUMBER: _ClassVar[int]
        HASFAN_FIELD_NUMBER: _ClassVar[int]
        hasStage1Cool: bool
        hasStage2Cool: bool
        hasStage3Cool: bool
        hasStage1Heat: bool
        hasStage2Heat: bool
        hasStage3Heat: bool
        hasStage1AlternateHeat: bool
        hasStage2AlternateHeat: bool
        hasHumidifier: bool
        hasDehumidifier: bool
        hasDualFuel: bool
        hasAuxHeat: bool
        hasEmergencyHeat: bool
        hasAirFilter: bool
        hasFossilFuel: bool
        hasHotWaterControl: bool
        hasHeatPump: bool
        hasHotWaterTemperature: bool
        hasFan: bool
        def __init__(self, hasStage1Cool: bool = ..., hasStage2Cool: bool = ..., hasStage3Cool: bool = ..., hasStage1Heat: bool = ..., hasStage2Heat: bool = ..., hasStage3Heat: bool = ..., hasStage1AlternateHeat: bool = ..., hasStage2AlternateHeat: bool = ..., hasHumidifier: bool = ..., hasDehumidifier: bool = ..., hasDualFuel: bool = ..., hasAuxHeat: bool = ..., hasEmergencyHeat: bool = ..., hasAirFilter: bool = ..., hasFossilFuel: bool = ..., hasHotWaterControl: bool = ..., hasHeatPump: bool = ..., hasHotWaterTemperature: bool = ..., hasFan: bool = ...) -> None: ...
    class LegacyRatePlanChange(_message.Message):
        __slots__ = ("timestamp", "ratePlanStart", "ratePlanEnd", "tierLevel")
        TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
        RATEPLANSTART_FIELD_NUMBER: _ClassVar[int]
        RATEPLANEND_FIELD_NUMBER: _ClassVar[int]
        TIERLEVEL_FIELD_NUMBER: _ClassVar[int]
        timestamp: _timestamp_pb2.Timestamp
        ratePlanStart: _timestamp_pb2.Timestamp
        ratePlanEnd: _timestamp_pb2.Timestamp
        tierLevel: _wrappers_pb2.UInt32Value
        def __init__(self, timestamp: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., ratePlanStart: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., ratePlanEnd: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., tierLevel: _Optional[_Union[_wrappers_pb2.UInt32Value, _Mapping]] = ...) -> None: ...
    class LegacyHVACUsage(_message.Message):
        __slots__ = ("eventStart", "timezoneOffset", "duration", "continuation", "eventType", "on", "off", "ecoAway", "ecoAutoAway", "sunlightCorrection", "setPoint")
        EVENTSTART_FIELD_NUMBER: _ClassVar[int]
        TIMEZONEOFFSET_FIELD_NUMBER: _ClassVar[int]
        DURATION_FIELD_NUMBER: _ClassVar[int]
        CONTINUATION_FIELD_NUMBER: _ClassVar[int]
        EVENTTYPE_FIELD_NUMBER: _ClassVar[int]
        ON_FIELD_NUMBER: _ClassVar[int]
        OFF_FIELD_NUMBER: _ClassVar[int]
        ECOAWAY_FIELD_NUMBER: _ClassVar[int]
        ECOAUTOAWAY_FIELD_NUMBER: _ClassVar[int]
        SUNLIGHTCORRECTION_FIELD_NUMBER: _ClassVar[int]
        SETPOINT_FIELD_NUMBER: _ClassVar[int]
        eventStart: _timestamp_pb2.Timestamp
        timezoneOffset: int
        duration: _duration_pb2.Duration
        continuation: bool
        eventType: EnergyHistoryTrait.LegacyEventType
        on: EnergyHistoryTrait.LegacyEventOnMode
        off: EnergyHistoryTrait.LegacyEventOffMode
        ecoAway: EnergyHistoryTrait.LegacyEventEcoAwayMode
        ecoAutoAway: EnergyHistoryTrait.LegacyEventEcoAutoAwayMode
        sunlightCorrection: EnergyHistoryTrait.LegacyEventSunlightCorrection
        setPoint: EnergyHistoryTrait.LegacyEventSetPoint
        def __init__(self, eventStart: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., timezoneOffset: _Optional[int] = ..., duration: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ..., continuation: bool = ..., eventType: _Optional[_Union[EnergyHistoryTrait.LegacyEventType, str]] = ..., on: _Optional[_Union[EnergyHistoryTrait.LegacyEventOnMode, _Mapping]] = ..., off: _Optional[_Union[EnergyHistoryTrait.LegacyEventOffMode, _Mapping]] = ..., ecoAway: _Optional[_Union[EnergyHistoryTrait.LegacyEventEcoAwayMode, _Mapping]] = ..., ecoAutoAway: _Optional[_Union[EnergyHistoryTrait.LegacyEventEcoAutoAwayMode, _Mapping]] = ..., sunlightCorrection: _Optional[_Union[EnergyHistoryTrait.LegacyEventSunlightCorrection, _Mapping]] = ..., setPoint: _Optional[_Union[EnergyHistoryTrait.LegacyEventSetPoint, _Mapping]] = ...) -> None: ...
    class LegacyEventOnMode(_message.Message):
        __slots__ = ("eventSource",)
        EVENTSOURCE_FIELD_NUMBER: _ClassVar[int]
        eventSource: EnergyHistoryTrait.LegacyEventSource
        def __init__(self, eventSource: _Optional[_Union[EnergyHistoryTrait.LegacyEventSource, _Mapping]] = ...) -> None: ...
    class LegacyEventOffMode(_message.Message):
        __slots__ = ("eventSource",)
        EVENTSOURCE_FIELD_NUMBER: _ClassVar[int]
        eventSource: EnergyHistoryTrait.LegacyEventSource
        def __init__(self, eventSource: _Optional[_Union[EnergyHistoryTrait.LegacyEventSource, _Mapping]] = ...) -> None: ...
    class LegacyEventEcoAwayMode(_message.Message):
        __slots__ = ("heatingTarget", "coolingTarget", "eventSource")
        HEATINGTARGET_FIELD_NUMBER: _ClassVar[int]
        COOLINGTARGET_FIELD_NUMBER: _ClassVar[int]
        EVENTSOURCE_FIELD_NUMBER: _ClassVar[int]
        heatingTarget: _hvac_pb2.HvacControl.TemperatureThreshold
        coolingTarget: _hvac_pb2.HvacControl.TemperatureThreshold
        eventSource: EnergyHistoryTrait.LegacyEventSource
        def __init__(self, heatingTarget: _Optional[_Union[_hvac_pb2.HvacControl.TemperatureThreshold, _Mapping]] = ..., coolingTarget: _Optional[_Union[_hvac_pb2.HvacControl.TemperatureThreshold, _Mapping]] = ..., eventSource: _Optional[_Union[EnergyHistoryTrait.LegacyEventSource, _Mapping]] = ...) -> None: ...
    class LegacyEventEcoAutoAwayMode(_message.Message):
        __slots__ = ("heatingTarget", "coolingTarget", "eventSource")
        HEATINGTARGET_FIELD_NUMBER: _ClassVar[int]
        COOLINGTARGET_FIELD_NUMBER: _ClassVar[int]
        EVENTSOURCE_FIELD_NUMBER: _ClassVar[int]
        heatingTarget: _hvac_pb2.HvacControl.TemperatureThreshold
        coolingTarget: _hvac_pb2.HvacControl.TemperatureThreshold
        eventSource: EnergyHistoryTrait.LegacyEventSource
        def __init__(self, heatingTarget: _Optional[_Union[_hvac_pb2.HvacControl.TemperatureThreshold, _Mapping]] = ..., coolingTarget: _Optional[_Union[_hvac_pb2.HvacControl.TemperatureThreshold, _Mapping]] = ..., eventSource: _Optional[_Union[EnergyHistoryTrait.LegacyEventSource, _Mapping]] = ...) -> None: ...
    class LegacyEventSunlightCorrection(_message.Message):
        __slots__ = ("eventSource",)
        EVENTSOURCE_FIELD_NUMBER: _ClassVar[int]
        eventSource: EnergyHistoryTrait.LegacyEventSource
        def __init__(self, eventSource: _Optional[_Union[EnergyHistoryTrait.LegacyEventSource, _Mapping]] = ...) -> None: ...
    class LegacyEventSetPoint(_message.Message):
        __slots__ = ("setPointType", "scheduleType", "heatingTarget", "coolingTarget", "actor", "touchedWhen", "touchedTimezoneOffset", "touchedWhere", "touchedUserId", "scheduledStart", "scheduledDay", "previousEventType", "source")
        SETPOINTTYPE_FIELD_NUMBER: _ClassVar[int]
        SCHEDULETYPE_FIELD_NUMBER: _ClassVar[int]
        HEATINGTARGET_FIELD_NUMBER: _ClassVar[int]
        COOLINGTARGET_FIELD_NUMBER: _ClassVar[int]
        ACTOR_FIELD_NUMBER: _ClassVar[int]
        TOUCHEDWHEN_FIELD_NUMBER: _ClassVar[int]
        TOUCHEDTIMEZONEOFFSET_FIELD_NUMBER: _ClassVar[int]
        TOUCHEDWHERE_FIELD_NUMBER: _ClassVar[int]
        TOUCHEDUSERID_FIELD_NUMBER: _ClassVar[int]
        SCHEDULEDSTART_FIELD_NUMBER: _ClassVar[int]
        SCHEDULEDDAY_FIELD_NUMBER: _ClassVar[int]
        PREVIOUSEVENTTYPE_FIELD_NUMBER: _ClassVar[int]
        SOURCE_FIELD_NUMBER: _ClassVar[int]
        setPointType: EnergyHistoryTrait.LegacySetPointType
        scheduleType: _hvac_pb2.SetPointScheduleSettingsTrait.SetPointScheduleType
        heatingTarget: _hvac_pb2.HvacControl.TemperatureThreshold
        coolingTarget: _hvac_pb2.HvacControl.TemperatureThreshold
        actor: _hvac_pb2.HvacActor.HvacActorMethod
        touchedWhen: _timestamp_pb2.Timestamp
        touchedTimezoneOffset: _wrappers_pb2.Int32Value
        touchedWhere: EnergyHistoryTrait.LegacyTouchedWhere
        touchedUserId: _wrappers_pb2.StringValue
        scheduledStart: _wrappers_pb2.UInt32Value
        scheduledDay: _wrappers_pb2.UInt32Value
        previousEventType: EnergyHistoryTrait.LegacyEventType
        source: EnergyHistoryTrait.LegacyEventSource
        def __init__(self, setPointType: _Optional[_Union[EnergyHistoryTrait.LegacySetPointType, str]] = ..., scheduleType: _Optional[_Union[_hvac_pb2.SetPointScheduleSettingsTrait.SetPointScheduleType, str]] = ..., heatingTarget: _Optional[_Union[_hvac_pb2.HvacControl.TemperatureThreshold, _Mapping]] = ..., coolingTarget: _Optional[_Union[_hvac_pb2.HvacControl.TemperatureThreshold, _Mapping]] = ..., actor: _Optional[_Union[_hvac_pb2.HvacActor.HvacActorMethod, str]] = ..., touchedWhen: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., touchedTimezoneOffset: _Optional[_Union[_wrappers_pb2.Int32Value, _Mapping]] = ..., touchedWhere: _Optional[_Union[EnergyHistoryTrait.LegacyTouchedWhere, str]] = ..., touchedUserId: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., scheduledStart: _Optional[_Union[_wrappers_pb2.UInt32Value, _Mapping]] = ..., scheduledDay: _Optional[_Union[_wrappers_pb2.UInt32Value, _Mapping]] = ..., previousEventType: _Optional[_Union[EnergyHistoryTrait.LegacyEventType, str]] = ..., source: _Optional[_Union[EnergyHistoryTrait.LegacyEventSource, _Mapping]] = ...) -> None: ...
    class LegacyEventSource(_message.Message):
        __slots__ = ("actor", "touchedWhere", "userName")
        ACTOR_FIELD_NUMBER: _ClassVar[int]
        TOUCHEDWHERE_FIELD_NUMBER: _ClassVar[int]
        USERNAME_FIELD_NUMBER: _ClassVar[int]
        actor: _hvac_pb2.HvacActor.HvacActorMethod
        touchedWhere: EnergyHistoryTrait.LegacyTouchedWhere
        userName: _wrappers_pb2.StringValue
        def __init__(self, actor: _Optional[_Union[_hvac_pb2.HvacActor.HvacActorMethod, str]] = ..., touchedWhere: _Optional[_Union[EnergyHistoryTrait.LegacyTouchedWhere, str]] = ..., userName: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ...) -> None: ...
    def __init__(self) -> None: ...

class OccupancyHistoryTrait(_message.Message):
    __slots__ = ()
    class ImplicitChangeReason(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        IMPLICIT_CHANGE_REASON_UNSPECIFIED: _ClassVar[OccupancyHistoryTrait.ImplicitChangeReason]
        IMPLICIT_CHANGE_REASON_ARM: _ClassVar[OccupancyHistoryTrait.ImplicitChangeReason]
        IMPLICIT_CHANGE_REASON_DISARM: _ClassVar[OccupancyHistoryTrait.ImplicitChangeReason]
        IMPLICIT_CHANGE_REASON_UNLOCK: _ClassVar[OccupancyHistoryTrait.ImplicitChangeReason]
    IMPLICIT_CHANGE_REASON_UNSPECIFIED: OccupancyHistoryTrait.ImplicitChangeReason
    IMPLICIT_CHANGE_REASON_ARM: OccupancyHistoryTrait.ImplicitChangeReason
    IMPLICIT_CHANGE_REASON_DISARM: OccupancyHistoryTrait.ImplicitChangeReason
    IMPLICIT_CHANGE_REASON_UNLOCK: OccupancyHistoryTrait.ImplicitChangeReason
    class FindOccupancyEventListRequest(_message.Message):
        __slots__ = ("queryStartTime", "queryEndTime", "fenceId")
        QUERYSTARTTIME_FIELD_NUMBER: _ClassVar[int]
        QUERYENDTIME_FIELD_NUMBER: _ClassVar[int]
        FENCEID_FIELD_NUMBER: _ClassVar[int]
        queryStartTime: _timestamp_pb2.Timestamp
        queryEndTime: _timestamp_pb2.Timestamp
        fenceId: _wrappers_pb2.StringValue
        def __init__(self, queryStartTime: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., queryEndTime: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., fenceId: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ...) -> None: ...
    class ExplicitStructureModeChange(_message.Message):
        __slots__ = ("mode", "user", "wwnClientId", "priorMode")
        MODE_FIELD_NUMBER: _ClassVar[int]
        USER_FIELD_NUMBER: _ClassVar[int]
        WWNCLIENTID_FIELD_NUMBER: _ClassVar[int]
        PRIORMODE_FIELD_NUMBER: _ClassVar[int]
        mode: _occupancy_pb2.StructureModeTrait.StructureMode
        user: _common_pb2.ResourceId
        wwnClientId: _wrappers_pb2.StringValue
        priorMode: _occupancy_pb2.StructureModeTrait.StructureMode
        def __init__(self, mode: _Optional[_Union[_occupancy_pb2.StructureModeTrait.StructureMode, str]] = ..., user: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ..., wwnClientId: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., priorMode: _Optional[_Union[_occupancy_pb2.StructureModeTrait.StructureMode, str]] = ...) -> None: ...
    class ImplicitStructureModeChange(_message.Message):
        __slots__ = ("mode", "actor", "reason", "priorMode")
        MODE_FIELD_NUMBER: _ClassVar[int]
        ACTOR_FIELD_NUMBER: _ClassVar[int]
        REASON_FIELD_NUMBER: _ClassVar[int]
        PRIORMODE_FIELD_NUMBER: _ClassVar[int]
        mode: _occupancy_pb2.StructureModeTrait.StructureMode
        actor: _common_pb2.ResourceId
        reason: OccupancyHistoryTrait.ImplicitChangeReason
        priorMode: _occupancy_pb2.StructureModeTrait.StructureMode
        def __init__(self, mode: _Optional[_Union[_occupancy_pb2.StructureModeTrait.StructureMode, str]] = ..., actor: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ..., reason: _Optional[_Union[OccupancyHistoryTrait.ImplicitChangeReason, str]] = ..., priorMode: _Optional[_Union[_occupancy_pb2.StructureModeTrait.StructureMode, str]] = ...) -> None: ...
    class EstimatedOccupancyStructureModeChange(_message.Message):
        __slots__ = ("mode", "reason", "weaveDeviceId", "rtsSerialNumber", "priorMode")
        MODE_FIELD_NUMBER: _ClassVar[int]
        REASON_FIELD_NUMBER: _ClassVar[int]
        WEAVEDEVICEID_FIELD_NUMBER: _ClassVar[int]
        RTSSERIALNUMBER_FIELD_NUMBER: _ClassVar[int]
        PRIORMODE_FIELD_NUMBER: _ClassVar[int]
        mode: _occupancy_pb2.StructureModeTrait.StructureMode
        reason: _occupancy_pb2.StructureModeTrait.StructureModeReason
        weaveDeviceId: _common_pb2.ResourceId
        rtsSerialNumber: _wrappers_pb2.StringValue
        priorMode: _occupancy_pb2.StructureModeTrait.StructureMode
        def __init__(self, mode: _Optional[_Union[_occupancy_pb2.StructureModeTrait.StructureMode, str]] = ..., reason: _Optional[_Union[_occupancy_pb2.StructureModeTrait.StructureModeReason, str]] = ..., weaveDeviceId: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ..., rtsSerialNumber: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., priorMode: _Optional[_Union[_occupancy_pb2.StructureModeTrait.StructureMode, str]] = ...) -> None: ...
    class CombinedPresenceChange(_message.Message):
        __slots__ = ("presence", "priorPresence")
        PRESENCE_FIELD_NUMBER: _ClassVar[int]
        PRIORPRESENCE_FIELD_NUMBER: _ClassVar[int]
        presence: _occupancy_pb2.StructureModeTrait.Presence
        priorPresence: _occupancy_pb2.StructureModeTrait.Presence
        def __init__(self, presence: _Optional[_Union[_occupancy_pb2.StructureModeTrait.Presence, str]] = ..., priorPresence: _Optional[_Union[_occupancy_pb2.StructureModeTrait.Presence, str]] = ...) -> None: ...
    class GeofenceStateChange(_message.Message):
        __slots__ = ("geofenceState", "userId", "rtsDeviceId", "weaveMobileDeviceId", "assertionTimestamp")
        GEOFENCESTATE_FIELD_NUMBER: _ClassVar[int]
        USERID_FIELD_NUMBER: _ClassVar[int]
        RTSDEVICEID_FIELD_NUMBER: _ClassVar[int]
        WEAVEMOBILEDEVICEID_FIELD_NUMBER: _ClassVar[int]
        ASSERTIONTIMESTAMP_FIELD_NUMBER: _ClassVar[int]
        geofenceState: _occupancy_pb2.Geofencing.GeofenceState
        userId: _common_pb2.ResourceId
        rtsDeviceId: _wrappers_pb2.StringValue
        weaveMobileDeviceId: _common_pb2.ResourceId
        assertionTimestamp: _timestamp_pb2.Timestamp
        def __init__(self, geofenceState: _Optional[_Union[_occupancy_pb2.Geofencing.GeofenceState, str]] = ..., userId: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ..., rtsDeviceId: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., weaveMobileDeviceId: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ..., assertionTimestamp: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...
    class OccupancyHistoryRecord(_message.Message):
        __slots__ = ("eventTimestamp", "explicitChangeEvent", "implicitChangeEvent", "estimatedOccupancyChangeEvent", "presenceEvent", "geofenceEvent")
        EVENTTIMESTAMP_FIELD_NUMBER: _ClassVar[int]
        EXPLICITCHANGEEVENT_FIELD_NUMBER: _ClassVar[int]
        IMPLICITCHANGEEVENT_FIELD_NUMBER: _ClassVar[int]
        ESTIMATEDOCCUPANCYCHANGEEVENT_FIELD_NUMBER: _ClassVar[int]
        PRESENCEEVENT_FIELD_NUMBER: _ClassVar[int]
        GEOFENCEEVENT_FIELD_NUMBER: _ClassVar[int]
        eventTimestamp: _timestamp_pb2.Timestamp
        explicitChangeEvent: OccupancyHistoryTrait.ExplicitStructureModeChange
        implicitChangeEvent: OccupancyHistoryTrait.ImplicitStructureModeChange
        estimatedOccupancyChangeEvent: OccupancyHistoryTrait.EstimatedOccupancyStructureModeChange
        presenceEvent: OccupancyHistoryTrait.CombinedPresenceChange
        geofenceEvent: OccupancyHistoryTrait.GeofenceStateChange
        def __init__(self, eventTimestamp: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., explicitChangeEvent: _Optional[_Union[OccupancyHistoryTrait.ExplicitStructureModeChange, _Mapping]] = ..., implicitChangeEvent: _Optional[_Union[OccupancyHistoryTrait.ImplicitStructureModeChange, _Mapping]] = ..., estimatedOccupancyChangeEvent: _Optional[_Union[OccupancyHistoryTrait.EstimatedOccupancyStructureModeChange, _Mapping]] = ..., presenceEvent: _Optional[_Union[OccupancyHistoryTrait.CombinedPresenceChange, _Mapping]] = ..., geofenceEvent: _Optional[_Union[OccupancyHistoryTrait.GeofenceStateChange, _Mapping]] = ...) -> None: ...
    class FindOccupancyEventsResponse(_message.Message):
        __slots__ = ("record",)
        RECORD_FIELD_NUMBER: _ClassVar[int]
        record: OccupancyHistoryTrait.OccupancyHistoryRecord
        def __init__(self, record: _Optional[_Union[OccupancyHistoryTrait.OccupancyHistoryRecord, _Mapping]] = ...) -> None: ...
    class FindOccupancyEventListResponse(_message.Message):
        __slots__ = ("responses",)
        RESPONSES_FIELD_NUMBER: _ClassVar[int]
        responses: _containers.RepeatedCompositeFieldContainer[OccupancyHistoryTrait.FindOccupancyEventsResponse]
        def __init__(self, responses: _Optional[_Iterable[_Union[OccupancyHistoryTrait.FindOccupancyEventsResponse, _Mapping]]] = ...) -> None: ...
    def __init__(self) -> None: ...
