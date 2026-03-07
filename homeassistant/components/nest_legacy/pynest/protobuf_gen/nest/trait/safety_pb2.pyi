import datetime

from google.protobuf import duration_pb2 as _duration_pb2
from ...weave import common_pb2 as _common_pb2
from ...nest.trait import sensor_pb2 as _sensor_pb2
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class SafetyAlarmTrait(_message.Message):
    __slots__ = ("sessionId", "alarmState", "silenceState")
    class AlarmLevel(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        ALARM_LEVEL_UNSPECIFIED: _ClassVar[SafetyAlarmTrait.AlarmLevel]
        ALARM_LEVEL_IDLE: _ClassVar[SafetyAlarmTrait.AlarmLevel]
        ALARM_LEVEL_MONITOR: _ClassVar[SafetyAlarmTrait.AlarmLevel]
        ALARM_LEVEL_MODERATE: _ClassVar[SafetyAlarmTrait.AlarmLevel]
        ALARM_LEVEL_SUBSTANTIAL: _ClassVar[SafetyAlarmTrait.AlarmLevel]
        ALARM_LEVEL_SEVERE: _ClassVar[SafetyAlarmTrait.AlarmLevel]
        ALARM_LEVEL_CRITICAL: _ClassVar[SafetyAlarmTrait.AlarmLevel]
    ALARM_LEVEL_UNSPECIFIED: SafetyAlarmTrait.AlarmLevel
    ALARM_LEVEL_IDLE: SafetyAlarmTrait.AlarmLevel
    ALARM_LEVEL_MONITOR: SafetyAlarmTrait.AlarmLevel
    ALARM_LEVEL_MODERATE: SafetyAlarmTrait.AlarmLevel
    ALARM_LEVEL_SUBSTANTIAL: SafetyAlarmTrait.AlarmLevel
    ALARM_LEVEL_SEVERE: SafetyAlarmTrait.AlarmLevel
    ALARM_LEVEL_CRITICAL: SafetyAlarmTrait.AlarmLevel
    class AlarmState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        ALARM_STATE_UNSPECIFIED: _ClassVar[SafetyAlarmTrait.AlarmState]
        ALARM_STATE_IDLE: _ClassVar[SafetyAlarmTrait.AlarmState]
        ALARM_STATE_HEADS_UP1: _ClassVar[SafetyAlarmTrait.AlarmState]
        ALARM_STATE_HEADS_UP2: _ClassVar[SafetyAlarmTrait.AlarmState]
        ALARM_STATE_ALARM: _ClassVar[SafetyAlarmTrait.AlarmState]
    ALARM_STATE_UNSPECIFIED: SafetyAlarmTrait.AlarmState
    ALARM_STATE_IDLE: SafetyAlarmTrait.AlarmState
    ALARM_STATE_HEADS_UP1: SafetyAlarmTrait.AlarmState
    ALARM_STATE_HEADS_UP2: SafetyAlarmTrait.AlarmState
    ALARM_STATE_ALARM: SafetyAlarmTrait.AlarmState
    class SilenceState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        SILENCE_STATE_UNSPECIFIED: _ClassVar[SafetyAlarmTrait.SilenceState]
        SILENCE_STATE_DISALLOWED: _ClassVar[SafetyAlarmTrait.SilenceState]
        SILENCE_STATE_ALLOWED: _ClassVar[SafetyAlarmTrait.SilenceState]
        SILENCE_STATE_SILENCED: _ClassVar[SafetyAlarmTrait.SilenceState]
    SILENCE_STATE_UNSPECIFIED: SafetyAlarmTrait.SilenceState
    SILENCE_STATE_DISALLOWED: SafetyAlarmTrait.SilenceState
    SILENCE_STATE_ALLOWED: SafetyAlarmTrait.SilenceState
    SILENCE_STATE_SILENCED: SafetyAlarmTrait.SilenceState
    class SafetyAlarmChangeEvent(_message.Message):
        __slots__ = ("sessionId", "alarmLevel", "alarmState", "prevAlarmState", "silenceState", "prevSilenceState", "prevStateDuration")
        SESSIONID_FIELD_NUMBER: _ClassVar[int]
        ALARMLEVEL_FIELD_NUMBER: _ClassVar[int]
        ALARMSTATE_FIELD_NUMBER: _ClassVar[int]
        PREVALARMSTATE_FIELD_NUMBER: _ClassVar[int]
        SILENCESTATE_FIELD_NUMBER: _ClassVar[int]
        PREVSILENCESTATE_FIELD_NUMBER: _ClassVar[int]
        PREVSTATEDURATION_FIELD_NUMBER: _ClassVar[int]
        sessionId: int
        alarmLevel: SafetyAlarmTrait.AlarmLevel
        alarmState: SafetyAlarmTrait.AlarmState
        prevAlarmState: SafetyAlarmTrait.AlarmState
        silenceState: SafetyAlarmTrait.SilenceState
        prevSilenceState: SafetyAlarmTrait.SilenceState
        prevStateDuration: _duration_pb2.Duration
        def __init__(self, sessionId: _Optional[int] = ..., alarmLevel: _Optional[_Union[SafetyAlarmTrait.AlarmLevel, str]] = ..., alarmState: _Optional[_Union[SafetyAlarmTrait.AlarmState, str]] = ..., prevAlarmState: _Optional[_Union[SafetyAlarmTrait.AlarmState, str]] = ..., silenceState: _Optional[_Union[SafetyAlarmTrait.SilenceState, str]] = ..., prevSilenceState: _Optional[_Union[SafetyAlarmTrait.SilenceState, str]] = ..., prevStateDuration: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ...) -> None: ...
    SESSIONID_FIELD_NUMBER: _ClassVar[int]
    ALARMSTATE_FIELD_NUMBER: _ClassVar[int]
    SILENCESTATE_FIELD_NUMBER: _ClassVar[int]
    sessionId: int
    alarmState: SafetyAlarmTrait.AlarmState
    silenceState: SafetyAlarmTrait.SilenceState
    def __init__(self, sessionId: _Optional[int] = ..., alarmState: _Optional[_Union[SafetyAlarmTrait.AlarmState, str]] = ..., silenceState: _Optional[_Union[SafetyAlarmTrait.SilenceState, str]] = ...) -> None: ...

class SafetyAlarmRemoteTrait(_message.Message):
    __slots__ = ()
    class SafetyAlarmStatus(_message.Message):
        __slots__ = ("originator", "alarmState", "silenceState")
        ORIGINATOR_FIELD_NUMBER: _ClassVar[int]
        ALARMSTATE_FIELD_NUMBER: _ClassVar[int]
        SILENCESTATE_FIELD_NUMBER: _ClassVar[int]
        originator: _common_pb2.ResourceId
        alarmState: SafetyAlarmTrait.AlarmState
        silenceState: SafetyAlarmTrait.SilenceState
        def __init__(self, originator: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ..., alarmState: _Optional[_Union[SafetyAlarmTrait.AlarmState, str]] = ..., silenceState: _Optional[_Union[SafetyAlarmTrait.SilenceState, str]] = ...) -> None: ...
    class SafetyAlarmRemoteChangeEvent(_message.Message):
        __slots__ = ("remoteStatus", "prevRemoteStatus")
        REMOTESTATUS_FIELD_NUMBER: _ClassVar[int]
        PREVREMOTESTATUS_FIELD_NUMBER: _ClassVar[int]
        remoteStatus: SafetyAlarmRemoteTrait.SafetyAlarmStatus
        prevRemoteStatus: SafetyAlarmRemoteTrait.SafetyAlarmStatus
        def __init__(self, remoteStatus: _Optional[_Union[SafetyAlarmRemoteTrait.SafetyAlarmStatus, _Mapping]] = ..., prevRemoteStatus: _Optional[_Union[SafetyAlarmRemoteTrait.SafetyAlarmStatus, _Mapping]] = ...) -> None: ...
    def __init__(self) -> None: ...

class SafetyAlarmCOTrait(_message.Message):
    __slots__ = ("sessionId", "alarmState", "silenceState", "peakConcentration", "blameThreshold", "blameDuration")
    class SafetyAlarmCOChangeEvent(_message.Message):
        __slots__ = ("sessionId", "alarmLevel", "alarmState", "prevAlarmState", "silenceState", "prevSilenceState", "prevStateDuration", "peakConcentration", "blameThreshold", "blameDuration")
        SESSIONID_FIELD_NUMBER: _ClassVar[int]
        ALARMLEVEL_FIELD_NUMBER: _ClassVar[int]
        ALARMSTATE_FIELD_NUMBER: _ClassVar[int]
        PREVALARMSTATE_FIELD_NUMBER: _ClassVar[int]
        SILENCESTATE_FIELD_NUMBER: _ClassVar[int]
        PREVSILENCESTATE_FIELD_NUMBER: _ClassVar[int]
        PREVSTATEDURATION_FIELD_NUMBER: _ClassVar[int]
        PEAKCONCENTRATION_FIELD_NUMBER: _ClassVar[int]
        BLAMETHRESHOLD_FIELD_NUMBER: _ClassVar[int]
        BLAMEDURATION_FIELD_NUMBER: _ClassVar[int]
        sessionId: int
        alarmLevel: SafetyAlarmTrait.AlarmLevel
        alarmState: SafetyAlarmTrait.AlarmState
        prevAlarmState: SafetyAlarmTrait.AlarmState
        silenceState: SafetyAlarmTrait.SilenceState
        prevSilenceState: SafetyAlarmTrait.SilenceState
        prevStateDuration: _duration_pb2.Duration
        peakConcentration: _sensor_pb2.CarbonMonoxideTrait.CoSample
        blameThreshold: _sensor_pb2.CarbonMonoxideTrait.CoSample
        blameDuration: _duration_pb2.Duration
        def __init__(self, sessionId: _Optional[int] = ..., alarmLevel: _Optional[_Union[SafetyAlarmTrait.AlarmLevel, str]] = ..., alarmState: _Optional[_Union[SafetyAlarmTrait.AlarmState, str]] = ..., prevAlarmState: _Optional[_Union[SafetyAlarmTrait.AlarmState, str]] = ..., silenceState: _Optional[_Union[SafetyAlarmTrait.SilenceState, str]] = ..., prevSilenceState: _Optional[_Union[SafetyAlarmTrait.SilenceState, str]] = ..., prevStateDuration: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ..., peakConcentration: _Optional[_Union[_sensor_pb2.CarbonMonoxideTrait.CoSample, _Mapping]] = ..., blameThreshold: _Optional[_Union[_sensor_pb2.CarbonMonoxideTrait.CoSample, _Mapping]] = ..., blameDuration: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ...) -> None: ...
    SESSIONID_FIELD_NUMBER: _ClassVar[int]
    ALARMSTATE_FIELD_NUMBER: _ClassVar[int]
    SILENCESTATE_FIELD_NUMBER: _ClassVar[int]
    PEAKCONCENTRATION_FIELD_NUMBER: _ClassVar[int]
    BLAMETHRESHOLD_FIELD_NUMBER: _ClassVar[int]
    BLAMEDURATION_FIELD_NUMBER: _ClassVar[int]
    sessionId: int
    alarmState: SafetyAlarmTrait.AlarmState
    silenceState: SafetyAlarmTrait.SilenceState
    peakConcentration: _sensor_pb2.CarbonMonoxideTrait.CoSample
    blameThreshold: _sensor_pb2.CarbonMonoxideTrait.CoSample
    blameDuration: _duration_pb2.Duration
    def __init__(self, sessionId: _Optional[int] = ..., alarmState: _Optional[_Union[SafetyAlarmTrait.AlarmState, str]] = ..., silenceState: _Optional[_Union[SafetyAlarmTrait.SilenceState, str]] = ..., peakConcentration: _Optional[_Union[_sensor_pb2.CarbonMonoxideTrait.CoSample, _Mapping]] = ..., blameThreshold: _Optional[_Union[_sensor_pb2.CarbonMonoxideTrait.CoSample, _Mapping]] = ..., blameDuration: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ...) -> None: ...

class SafetyAlarmRemoteCOTrait(_message.Message):
    __slots__ = ()
    class SafetyAlarmRemoteCOChangeEvent(_message.Message):
        __slots__ = ("remoteStatus", "prevRemoteStatus")
        REMOTESTATUS_FIELD_NUMBER: _ClassVar[int]
        PREVREMOTESTATUS_FIELD_NUMBER: _ClassVar[int]
        remoteStatus: SafetyAlarmRemoteTrait.SafetyAlarmStatus
        prevRemoteStatus: SafetyAlarmRemoteTrait.SafetyAlarmStatus
        def __init__(self, remoteStatus: _Optional[_Union[SafetyAlarmRemoteTrait.SafetyAlarmStatus, _Mapping]] = ..., prevRemoteStatus: _Optional[_Union[SafetyAlarmRemoteTrait.SafetyAlarmStatus, _Mapping]] = ...) -> None: ...
    def __init__(self) -> None: ...

class SafetyAlarmRemoteSmokeTrait(_message.Message):
    __slots__ = ()
    class SafetyAlarmRemoteSmokeChangeEvent(_message.Message):
        __slots__ = ("remoteStatus", "prevRemoteStatus")
        REMOTESTATUS_FIELD_NUMBER: _ClassVar[int]
        PREVREMOTESTATUS_FIELD_NUMBER: _ClassVar[int]
        remoteStatus: SafetyAlarmRemoteTrait.SafetyAlarmStatus
        prevRemoteStatus: SafetyAlarmRemoteTrait.SafetyAlarmStatus
        def __init__(self, remoteStatus: _Optional[_Union[SafetyAlarmRemoteTrait.SafetyAlarmStatus, _Mapping]] = ..., prevRemoteStatus: _Optional[_Union[SafetyAlarmRemoteTrait.SafetyAlarmStatus, _Mapping]] = ...) -> None: ...
    def __init__(self) -> None: ...

class SafetyAlarmSmokeTrait(_message.Message):
    __slots__ = ("sessionId", "alarmState", "silenceState")
    class SafetyAlarmSmokeChangeEvent(_message.Message):
        __slots__ = ("sessionId", "alarmLevel", "alarmState", "prevAlarmState", "silenceState", "prevSilenceState", "prevStateDuration", "steamDetected")
        SESSIONID_FIELD_NUMBER: _ClassVar[int]
        ALARMLEVEL_FIELD_NUMBER: _ClassVar[int]
        ALARMSTATE_FIELD_NUMBER: _ClassVar[int]
        PREVALARMSTATE_FIELD_NUMBER: _ClassVar[int]
        SILENCESTATE_FIELD_NUMBER: _ClassVar[int]
        PREVSILENCESTATE_FIELD_NUMBER: _ClassVar[int]
        PREVSTATEDURATION_FIELD_NUMBER: _ClassVar[int]
        STEAMDETECTED_FIELD_NUMBER: _ClassVar[int]
        sessionId: int
        alarmLevel: SafetyAlarmTrait.AlarmLevel
        alarmState: SafetyAlarmTrait.AlarmState
        prevAlarmState: SafetyAlarmTrait.AlarmState
        silenceState: SafetyAlarmTrait.SilenceState
        prevSilenceState: SafetyAlarmTrait.SilenceState
        prevStateDuration: _duration_pb2.Duration
        steamDetected: bool
        def __init__(self, sessionId: _Optional[int] = ..., alarmLevel: _Optional[_Union[SafetyAlarmTrait.AlarmLevel, str]] = ..., alarmState: _Optional[_Union[SafetyAlarmTrait.AlarmState, str]] = ..., prevAlarmState: _Optional[_Union[SafetyAlarmTrait.AlarmState, str]] = ..., silenceState: _Optional[_Union[SafetyAlarmTrait.SilenceState, str]] = ..., prevSilenceState: _Optional[_Union[SafetyAlarmTrait.SilenceState, str]] = ..., prevStateDuration: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ..., steamDetected: bool = ...) -> None: ...
    SESSIONID_FIELD_NUMBER: _ClassVar[int]
    ALARMSTATE_FIELD_NUMBER: _ClassVar[int]
    SILENCESTATE_FIELD_NUMBER: _ClassVar[int]
    sessionId: int
    alarmState: SafetyAlarmTrait.AlarmState
    silenceState: SafetyAlarmTrait.SilenceState
    def __init__(self, sessionId: _Optional[int] = ..., alarmState: _Optional[_Union[SafetyAlarmTrait.AlarmState, str]] = ..., silenceState: _Optional[_Union[SafetyAlarmTrait.SilenceState, str]] = ...) -> None: ...

class SafetyAlarmSettingsTrait(_message.Message):
    __slots__ = ("headsUpEnabled", "steamDetectionEnabled")
    HEADSUPENABLED_FIELD_NUMBER: _ClassVar[int]
    STEAMDETECTIONENABLED_FIELD_NUMBER: _ClassVar[int]
    headsUpEnabled: bool
    steamDetectionEnabled: bool
    def __init__(self, headsUpEnabled: bool = ..., steamDetectionEnabled: bool = ...) -> None: ...
