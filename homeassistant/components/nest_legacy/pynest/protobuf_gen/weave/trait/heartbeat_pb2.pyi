import datetime

from google.protobuf import duration_pb2 as _duration_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf import wrappers_pb2 as _wrappers_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class LivenessTrait(_message.Message):
    __slots__ = ("status", "timeStatusChanged", "maxInactivityDuration", "heartbeatStatus", "timeHeartbeatStatusChanged", "notifyRequestUnresponsiveness", "notifyRequestUnresponsivenessTimeStatusChanged", "commandRequestUnresponsiveness", "commandRequestUnresponsivenessTimeStatusChanged", "publisherName", "tunnelDisconnected", "tunnelDisconnectedTimeStatusChanged", "lastContactedTime", "lastWdmHeartbeatTime", "tunnelClosedTime", "frontend", "disconnected", "disconnectedTimeStatusChanged", "connectionClosedTime")
    class LivenessDeviceStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        LIVENESS_DEVICE_STATUS_UNSPECIFIED: _ClassVar[LivenessTrait.LivenessDeviceStatus]
        LIVENESS_DEVICE_STATUS_ONLINE: _ClassVar[LivenessTrait.LivenessDeviceStatus]
        LIVENESS_DEVICE_STATUS_UNREACHABLE: _ClassVar[LivenessTrait.LivenessDeviceStatus]
        LIVENESS_DEVICE_STATUS_UNINITIALIZED: _ClassVar[LivenessTrait.LivenessDeviceStatus]
        LIVENESS_DEVICE_STATUS_REBOOTING: _ClassVar[LivenessTrait.LivenessDeviceStatus]
        LIVENESS_DEVICE_STATUS_UPGRADING: _ClassVar[LivenessTrait.LivenessDeviceStatus]
        LIVENESS_DEVICE_STATUS_SCHEDULED_DOWN: _ClassVar[LivenessTrait.LivenessDeviceStatus]
    LIVENESS_DEVICE_STATUS_UNSPECIFIED: LivenessTrait.LivenessDeviceStatus
    LIVENESS_DEVICE_STATUS_ONLINE: LivenessTrait.LivenessDeviceStatus
    LIVENESS_DEVICE_STATUS_UNREACHABLE: LivenessTrait.LivenessDeviceStatus
    LIVENESS_DEVICE_STATUS_UNINITIALIZED: LivenessTrait.LivenessDeviceStatus
    LIVENESS_DEVICE_STATUS_REBOOTING: LivenessTrait.LivenessDeviceStatus
    LIVENESS_DEVICE_STATUS_UPGRADING: LivenessTrait.LivenessDeviceStatus
    LIVENESS_DEVICE_STATUS_SCHEDULED_DOWN: LivenessTrait.LivenessDeviceStatus
    class DeviceFrontendType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        DEVICE_FRONTEND_TYPE_UNSPECIFIED: _ClassVar[LivenessTrait.DeviceFrontendType]
        DEVICE_FRONTEND_TYPE_LYCRA: _ClassVar[LivenessTrait.DeviceFrontendType]
        DEVICE_FRONTEND_TYPE_WEAVE_FE_1: _ClassVar[LivenessTrait.DeviceFrontendType]
    DEVICE_FRONTEND_TYPE_UNSPECIFIED: LivenessTrait.DeviceFrontendType
    DEVICE_FRONTEND_TYPE_LYCRA: LivenessTrait.DeviceFrontendType
    DEVICE_FRONTEND_TYPE_WEAVE_FE_1: LivenessTrait.DeviceFrontendType
    class LivenessChangeEvent(_message.Message):
        __slots__ = ("status", "heartbeatStatus", "notifyRequestUnresponsiveness", "commandRequestUnresponsiveness", "prevStatus", "tunnelDisconnected", "lastContactedTime", "lastWdmHeartbeatTime", "tunnelClosedTime", "timeStatusChanged", "timePrevStatusChanged", "frontend", "disconnected", "disconnectedTimeStatusChanged", "connectionClosedTime", "traitLabel")
        STATUS_FIELD_NUMBER: _ClassVar[int]
        HEARTBEATSTATUS_FIELD_NUMBER: _ClassVar[int]
        NOTIFYREQUESTUNRESPONSIVENESS_FIELD_NUMBER: _ClassVar[int]
        COMMANDREQUESTUNRESPONSIVENESS_FIELD_NUMBER: _ClassVar[int]
        PREVSTATUS_FIELD_NUMBER: _ClassVar[int]
        TUNNELDISCONNECTED_FIELD_NUMBER: _ClassVar[int]
        LASTCONTACTEDTIME_FIELD_NUMBER: _ClassVar[int]
        LASTWDMHEARTBEATTIME_FIELD_NUMBER: _ClassVar[int]
        TUNNELCLOSEDTIME_FIELD_NUMBER: _ClassVar[int]
        TIMESTATUSCHANGED_FIELD_NUMBER: _ClassVar[int]
        TIMEPREVSTATUSCHANGED_FIELD_NUMBER: _ClassVar[int]
        FRONTEND_FIELD_NUMBER: _ClassVar[int]
        DISCONNECTED_FIELD_NUMBER: _ClassVar[int]
        DISCONNECTEDTIMESTATUSCHANGED_FIELD_NUMBER: _ClassVar[int]
        CONNECTIONCLOSEDTIME_FIELD_NUMBER: _ClassVar[int]
        TRAITLABEL_FIELD_NUMBER: _ClassVar[int]
        status: LivenessTrait.LivenessDeviceStatus
        heartbeatStatus: LivenessTrait.LivenessDeviceStatus
        notifyRequestUnresponsiveness: _wrappers_pb2.BoolValue
        commandRequestUnresponsiveness: _wrappers_pb2.BoolValue
        prevStatus: LivenessTrait.LivenessDeviceStatus
        tunnelDisconnected: _wrappers_pb2.BoolValue
        lastContactedTime: _timestamp_pb2.Timestamp
        lastWdmHeartbeatTime: _timestamp_pb2.Timestamp
        tunnelClosedTime: _timestamp_pb2.Timestamp
        timeStatusChanged: _timestamp_pb2.Timestamp
        timePrevStatusChanged: _timestamp_pb2.Timestamp
        frontend: _containers.RepeatedScalarFieldContainer[LivenessTrait.DeviceFrontendType]
        disconnected: _wrappers_pb2.BoolValue
        disconnectedTimeStatusChanged: _timestamp_pb2.Timestamp
        connectionClosedTime: _timestamp_pb2.Timestamp
        traitLabel: _wrappers_pb2.StringValue
        def __init__(self, status: _Optional[_Union[LivenessTrait.LivenessDeviceStatus, str]] = ..., heartbeatStatus: _Optional[_Union[LivenessTrait.LivenessDeviceStatus, str]] = ..., notifyRequestUnresponsiveness: _Optional[_Union[_wrappers_pb2.BoolValue, _Mapping]] = ..., commandRequestUnresponsiveness: _Optional[_Union[_wrappers_pb2.BoolValue, _Mapping]] = ..., prevStatus: _Optional[_Union[LivenessTrait.LivenessDeviceStatus, str]] = ..., tunnelDisconnected: _Optional[_Union[_wrappers_pb2.BoolValue, _Mapping]] = ..., lastContactedTime: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., lastWdmHeartbeatTime: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., tunnelClosedTime: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., timeStatusChanged: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., timePrevStatusChanged: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., frontend: _Optional[_Iterable[_Union[LivenessTrait.DeviceFrontendType, str]]] = ..., disconnected: _Optional[_Union[_wrappers_pb2.BoolValue, _Mapping]] = ..., disconnectedTimeStatusChanged: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., connectionClosedTime: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., traitLabel: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ...) -> None: ...
    class LivenessConnectedSignalEvent(_message.Message):
        __slots__ = ("connectionId", "frontend", "occurrenceTime", "connectionTag")
        CONNECTIONID_FIELD_NUMBER: _ClassVar[int]
        FRONTEND_FIELD_NUMBER: _ClassVar[int]
        OCCURRENCETIME_FIELD_NUMBER: _ClassVar[int]
        CONNECTIONTAG_FIELD_NUMBER: _ClassVar[int]
        connectionId: str
        frontend: LivenessTrait.DeviceFrontendType
        occurrenceTime: _timestamp_pb2.Timestamp
        connectionTag: _wrappers_pb2.StringValue
        def __init__(self, connectionId: _Optional[str] = ..., frontend: _Optional[_Union[LivenessTrait.DeviceFrontendType, str]] = ..., occurrenceTime: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., connectionTag: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ...) -> None: ...
    class LivenessDisconnectedSignalEvent(_message.Message):
        __slots__ = ("connectionId", "frontend", "occurrenceTime", "connectionTag")
        CONNECTIONID_FIELD_NUMBER: _ClassVar[int]
        FRONTEND_FIELD_NUMBER: _ClassVar[int]
        OCCURRENCETIME_FIELD_NUMBER: _ClassVar[int]
        CONNECTIONTAG_FIELD_NUMBER: _ClassVar[int]
        connectionId: str
        frontend: LivenessTrait.DeviceFrontendType
        occurrenceTime: _timestamp_pb2.Timestamp
        connectionTag: _wrappers_pb2.StringValue
        def __init__(self, connectionId: _Optional[str] = ..., frontend: _Optional[_Union[LivenessTrait.DeviceFrontendType, str]] = ..., occurrenceTime: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., connectionTag: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ...) -> None: ...
    STATUS_FIELD_NUMBER: _ClassVar[int]
    TIMESTATUSCHANGED_FIELD_NUMBER: _ClassVar[int]
    MAXINACTIVITYDURATION_FIELD_NUMBER: _ClassVar[int]
    HEARTBEATSTATUS_FIELD_NUMBER: _ClassVar[int]
    TIMEHEARTBEATSTATUSCHANGED_FIELD_NUMBER: _ClassVar[int]
    NOTIFYREQUESTUNRESPONSIVENESS_FIELD_NUMBER: _ClassVar[int]
    NOTIFYREQUESTUNRESPONSIVENESSTIMESTATUSCHANGED_FIELD_NUMBER: _ClassVar[int]
    COMMANDREQUESTUNRESPONSIVENESS_FIELD_NUMBER: _ClassVar[int]
    COMMANDREQUESTUNRESPONSIVENESSTIMESTATUSCHANGED_FIELD_NUMBER: _ClassVar[int]
    PUBLISHERNAME_FIELD_NUMBER: _ClassVar[int]
    TUNNELDISCONNECTED_FIELD_NUMBER: _ClassVar[int]
    TUNNELDISCONNECTEDTIMESTATUSCHANGED_FIELD_NUMBER: _ClassVar[int]
    LASTCONTACTEDTIME_FIELD_NUMBER: _ClassVar[int]
    LASTWDMHEARTBEATTIME_FIELD_NUMBER: _ClassVar[int]
    TUNNELCLOSEDTIME_FIELD_NUMBER: _ClassVar[int]
    FRONTEND_FIELD_NUMBER: _ClassVar[int]
    DISCONNECTED_FIELD_NUMBER: _ClassVar[int]
    DISCONNECTEDTIMESTATUSCHANGED_FIELD_NUMBER: _ClassVar[int]
    CONNECTIONCLOSEDTIME_FIELD_NUMBER: _ClassVar[int]
    status: LivenessTrait.LivenessDeviceStatus
    timeStatusChanged: _timestamp_pb2.Timestamp
    maxInactivityDuration: _duration_pb2.Duration
    heartbeatStatus: LivenessTrait.LivenessDeviceStatus
    timeHeartbeatStatusChanged: _timestamp_pb2.Timestamp
    notifyRequestUnresponsiveness: _wrappers_pb2.BoolValue
    notifyRequestUnresponsivenessTimeStatusChanged: _timestamp_pb2.Timestamp
    commandRequestUnresponsiveness: _wrappers_pb2.BoolValue
    commandRequestUnresponsivenessTimeStatusChanged: _timestamp_pb2.Timestamp
    publisherName: _wrappers_pb2.StringValue
    tunnelDisconnected: _wrappers_pb2.BoolValue
    tunnelDisconnectedTimeStatusChanged: _timestamp_pb2.Timestamp
    lastContactedTime: _timestamp_pb2.Timestamp
    lastWdmHeartbeatTime: _timestamp_pb2.Timestamp
    tunnelClosedTime: _timestamp_pb2.Timestamp
    frontend: _containers.RepeatedScalarFieldContainer[LivenessTrait.DeviceFrontendType]
    disconnected: _wrappers_pb2.BoolValue
    disconnectedTimeStatusChanged: _timestamp_pb2.Timestamp
    connectionClosedTime: _timestamp_pb2.Timestamp
    def __init__(self, status: _Optional[_Union[LivenessTrait.LivenessDeviceStatus, str]] = ..., timeStatusChanged: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., maxInactivityDuration: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ..., heartbeatStatus: _Optional[_Union[LivenessTrait.LivenessDeviceStatus, str]] = ..., timeHeartbeatStatusChanged: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., notifyRequestUnresponsiveness: _Optional[_Union[_wrappers_pb2.BoolValue, _Mapping]] = ..., notifyRequestUnresponsivenessTimeStatusChanged: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., commandRequestUnresponsiveness: _Optional[_Union[_wrappers_pb2.BoolValue, _Mapping]] = ..., commandRequestUnresponsivenessTimeStatusChanged: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., publisherName: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., tunnelDisconnected: _Optional[_Union[_wrappers_pb2.BoolValue, _Mapping]] = ..., tunnelDisconnectedTimeStatusChanged: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., lastContactedTime: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., lastWdmHeartbeatTime: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., tunnelClosedTime: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., frontend: _Optional[_Iterable[_Union[LivenessTrait.DeviceFrontendType, str]]] = ..., disconnected: _Optional[_Union[_wrappers_pb2.BoolValue, _Mapping]] = ..., disconnectedTimeStatusChanged: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., connectionClosedTime: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...
