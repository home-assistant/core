import datetime

from google.protobuf import any_pb2 as _any_pb2
from google.protobuf import field_mask_pb2 as _field_mask_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.rpc import status_pb2 as _status_pb2
from ...nest import messages_pb2 as _messages_pb2
import wdl_event_importance_pb2 as _wdl_event_importance_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class TraitStateNotification(_message.Message):
    __slots__ = ("state", "stateMask", "monotonicVersion", "notificationContext", "publisherVersion")
    class NotificationContext(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        NOTIFICATION_CONTEXT_UNSPECIFIED: _ClassVar[TraitStateNotification.NotificationContext]
        INITIAL_OBSERVE_RESPONSE: _ClassVar[TraitStateNotification.NotificationContext]
    NOTIFICATION_CONTEXT_UNSPECIFIED: TraitStateNotification.NotificationContext
    INITIAL_OBSERVE_RESPONSE: TraitStateNotification.NotificationContext
    STATE_FIELD_NUMBER: _ClassVar[int]
    STATEMASK_FIELD_NUMBER: _ClassVar[int]
    MONOTONICVERSION_FIELD_NUMBER: _ClassVar[int]
    NOTIFICATIONCONTEXT_FIELD_NUMBER: _ClassVar[int]
    PUBLISHERVERSION_FIELD_NUMBER: _ClassVar[int]
    state: _any_pb2.Any
    stateMask: _field_mask_pb2.FieldMask
    monotonicVersion: int
    notificationContext: TraitStateNotification.NotificationContext
    publisherVersion: int
    def __init__(self, state: _Optional[_Union[_any_pb2.Any, _Mapping]] = ..., stateMask: _Optional[_Union[_field_mask_pb2.FieldMask, _Mapping]] = ..., monotonicVersion: _Optional[int] = ..., notificationContext: _Optional[_Union[TraitStateNotification.NotificationContext, str]] = ..., publisherVersion: _Optional[int] = ...) -> None: ...

class TraitEventsNotification(_message.Message):
    __slots__ = ("events", "requestUtcTimestamp", "requestSystemTimeOffsetMillis", "serviceReceivedTimestamp")
    EVENTS_FIELD_NUMBER: _ClassVar[int]
    REQUESTUTCTIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    REQUESTSYSTEMTIMEOFFSETMILLIS_FIELD_NUMBER: _ClassVar[int]
    SERVICERECEIVEDTIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    events: _containers.RepeatedCompositeFieldContainer[Event]
    requestUtcTimestamp: _timestamp_pb2.Timestamp
    requestSystemTimeOffsetMillis: int
    serviceReceivedTimestamp: _timestamp_pb2.Timestamp
    def __init__(self, events: _Optional[_Iterable[_Union[Event, _Mapping]]] = ..., requestUtcTimestamp: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., requestSystemTimeOffsetMillis: _Optional[int] = ..., serviceReceivedTimestamp: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class Event(_message.Message):
    __slots__ = ("data", "importance", "eventId", "relatedEventImportance", "relatedEventId", "utcTimestamp", "systemTimeOffsetMillis", "relaybyResourceId", "subjectResourceId", "subjectPairerId", "subjectTypeName", "subjectInstanceId", "schemaVersion")
    DATA_FIELD_NUMBER: _ClassVar[int]
    IMPORTANCE_FIELD_NUMBER: _ClassVar[int]
    EVENTID_FIELD_NUMBER: _ClassVar[int]
    RELATEDEVENTIMPORTANCE_FIELD_NUMBER: _ClassVar[int]
    RELATEDEVENTID_FIELD_NUMBER: _ClassVar[int]
    UTCTIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    SYSTEMTIMEOFFSETMILLIS_FIELD_NUMBER: _ClassVar[int]
    RELAYBYRESOURCEID_FIELD_NUMBER: _ClassVar[int]
    SUBJECTRESOURCEID_FIELD_NUMBER: _ClassVar[int]
    SUBJECTPAIRERID_FIELD_NUMBER: _ClassVar[int]
    SUBJECTTYPENAME_FIELD_NUMBER: _ClassVar[int]
    SUBJECTINSTANCEID_FIELD_NUMBER: _ClassVar[int]
    SCHEMAVERSION_FIELD_NUMBER: _ClassVar[int]
    data: _any_pb2.Any
    importance: _wdl_event_importance_pb2.EventImportance
    eventId: int
    relatedEventImportance: _wdl_event_importance_pb2.EventImportance
    relatedEventId: int
    utcTimestamp: _timestamp_pb2.Timestamp
    systemTimeOffsetMillis: int
    relaybyResourceId: str
    subjectResourceId: str
    subjectPairerId: str
    subjectTypeName: str
    subjectInstanceId: str
    schemaVersion: _messages_pb2.SchemaVersion
    def __init__(self, data: _Optional[_Union[_any_pb2.Any, _Mapping]] = ..., importance: _Optional[_Union[_wdl_event_importance_pb2.EventImportance, str]] = ..., eventId: _Optional[int] = ..., relatedEventImportance: _Optional[_Union[_wdl_event_importance_pb2.EventImportance, str]] = ..., relatedEventId: _Optional[int] = ..., utcTimestamp: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., systemTimeOffsetMillis: _Optional[int] = ..., relaybyResourceId: _Optional[str] = ..., subjectResourceId: _Optional[str] = ..., subjectPairerId: _Optional[str] = ..., subjectTypeName: _Optional[str] = ..., subjectInstanceId: _Optional[str] = ..., schemaVersion: _Optional[_Union[_messages_pb2.SchemaVersion, _Mapping]] = ...) -> None: ...

class TraitRequest(_message.Message):
    __slots__ = ("resourceId", "traitLabel", "requestId")
    RESOURCEID_FIELD_NUMBER: _ClassVar[int]
    TRAITLABEL_FIELD_NUMBER: _ClassVar[int]
    REQUESTID_FIELD_NUMBER: _ClassVar[int]
    resourceId: str
    traitLabel: str
    requestId: str
    def __init__(self, resourceId: _Optional[str] = ..., traitLabel: _Optional[str] = ..., requestId: _Optional[str] = ...) -> None: ...

class TraitOperation(_message.Message):
    __slots__ = ("traitRequest", "progress", "status", "event", "publisherAcceptedStateVersion", "command", "update")
    class RequestCase(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        REQUEST_NOT_SET: _ClassVar[TraitOperation.RequestCase]
        COMMAND: _ClassVar[TraitOperation.RequestCase]
        UPDATE: _ClassVar[TraitOperation.RequestCase]
    REQUEST_NOT_SET: TraitOperation.RequestCase
    COMMAND: TraitOperation.RequestCase
    UPDATE: TraitOperation.RequestCase
    class State(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        STATE_UNSPECIFIED: _ClassVar[TraitOperation.State]
        QUEUED: _ClassVar[TraitOperation.State]
        PENDING: _ClassVar[TraitOperation.State]
        STARTED: _ClassVar[TraitOperation.State]
        COMPLETE: _ClassVar[TraitOperation.State]
    STATE_UNSPECIFIED: TraitOperation.State
    QUEUED: TraitOperation.State
    PENDING: TraitOperation.State
    STARTED: TraitOperation.State
    COMPLETE: TraitOperation.State
    TRAITREQUEST_FIELD_NUMBER: _ClassVar[int]
    PROGRESS_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    EVENT_FIELD_NUMBER: _ClassVar[int]
    PUBLISHERACCEPTEDSTATEVERSION_FIELD_NUMBER: _ClassVar[int]
    COMMAND_FIELD_NUMBER: _ClassVar[int]
    UPDATE_FIELD_NUMBER: _ClassVar[int]
    traitRequest: TraitRequest
    progress: TraitOperation.State
    status: _status_pb2.Status
    event: TraitEvent
    publisherAcceptedStateVersion: int
    command: TraitCommand
    update: TraitUpdateStateRequest
    def __init__(self, traitRequest: _Optional[_Union[TraitRequest, _Mapping]] = ..., progress: _Optional[_Union[TraitOperation.State, str]] = ..., status: _Optional[_Union[_status_pb2.Status, _Mapping]] = ..., event: _Optional[_Union[TraitEvent, _Mapping]] = ..., publisherAcceptedStateVersion: _Optional[int] = ..., command: _Optional[_Union[TraitCommand, _Mapping]] = ..., update: _Optional[_Union[TraitUpdateStateRequest, _Mapping]] = ...) -> None: ...

class TraitObserveRequest(_message.Message):
    __slots__ = ("traitRequest", "fieldMask", "monotonicVersionFilter", "includeConfirmedState", "includePendingOperations")
    TRAITREQUEST_FIELD_NUMBER: _ClassVar[int]
    FIELDMASK_FIELD_NUMBER: _ClassVar[int]
    MONOTONICVERSIONFILTER_FIELD_NUMBER: _ClassVar[int]
    INCLUDECONFIRMEDSTATE_FIELD_NUMBER: _ClassVar[int]
    INCLUDEPENDINGOPERATIONS_FIELD_NUMBER: _ClassVar[int]
    traitRequest: TraitRequest
    fieldMask: _field_mask_pb2.FieldMask
    monotonicVersionFilter: int
    includeConfirmedState: bool
    includePendingOperations: bool
    def __init__(self, traitRequest: _Optional[_Union[TraitRequest, _Mapping]] = ..., fieldMask: _Optional[_Union[_field_mask_pb2.FieldMask, _Mapping]] = ..., monotonicVersionFilter: _Optional[int] = ..., includeConfirmedState: bool = ..., includePendingOperations: bool = ...) -> None: ...

class TraitObserveResponse(_message.Message):
    __slots__ = ("traitRequest", "acceptedState", "traitInfo", "confirmedState", "pendingOperations")
    TRAITREQUEST_FIELD_NUMBER: _ClassVar[int]
    ACCEPTEDSTATE_FIELD_NUMBER: _ClassVar[int]
    TRAITINFO_FIELD_NUMBER: _ClassVar[int]
    CONFIRMEDSTATE_FIELD_NUMBER: _ClassVar[int]
    PENDINGOPERATIONS_FIELD_NUMBER: _ClassVar[int]
    traitRequest: TraitRequest
    acceptedState: TraitStateNotification
    traitInfo: TraitInfo
    confirmedState: TraitStateNotification
    pendingOperations: _containers.RepeatedCompositeFieldContainer[TraitOperation]
    def __init__(self, traitRequest: _Optional[_Union[TraitRequest, _Mapping]] = ..., acceptedState: _Optional[_Union[TraitStateNotification, _Mapping]] = ..., traitInfo: _Optional[_Union[TraitInfo, _Mapping]] = ..., confirmedState: _Optional[_Union[TraitStateNotification, _Mapping]] = ..., pendingOperations: _Optional[_Iterable[_Union[TraitOperation, _Mapping]]] = ...) -> None: ...

class TraitGetStateRequest(_message.Message):
    __slots__ = ("traitRequest", "fieldMask", "monotonicVersionFilter", "includeConfirmedState", "includePendingOperations")
    TRAITREQUEST_FIELD_NUMBER: _ClassVar[int]
    FIELDMASK_FIELD_NUMBER: _ClassVar[int]
    MONOTONICVERSIONFILTER_FIELD_NUMBER: _ClassVar[int]
    INCLUDECONFIRMEDSTATE_FIELD_NUMBER: _ClassVar[int]
    INCLUDEPENDINGOPERATIONS_FIELD_NUMBER: _ClassVar[int]
    traitRequest: TraitRequest
    fieldMask: _field_mask_pb2.FieldMask
    monotonicVersionFilter: int
    includeConfirmedState: bool
    includePendingOperations: bool
    def __init__(self, traitRequest: _Optional[_Union[TraitRequest, _Mapping]] = ..., fieldMask: _Optional[_Union[_field_mask_pb2.FieldMask, _Mapping]] = ..., monotonicVersionFilter: _Optional[int] = ..., includeConfirmedState: bool = ..., includePendingOperations: bool = ...) -> None: ...

class TraitGetStateResponse(_message.Message):
    __slots__ = ("traitRequest", "acceptedState", "traitInfo", "confirmedState")
    TRAITREQUEST_FIELD_NUMBER: _ClassVar[int]
    ACCEPTEDSTATE_FIELD_NUMBER: _ClassVar[int]
    TRAITINFO_FIELD_NUMBER: _ClassVar[int]
    CONFIRMEDSTATE_FIELD_NUMBER: _ClassVar[int]
    traitRequest: TraitRequest
    acceptedState: TraitStateNotification
    traitInfo: TraitInfo
    confirmedState: TraitStateNotification
    def __init__(self, traitRequest: _Optional[_Union[TraitRequest, _Mapping]] = ..., acceptedState: _Optional[_Union[TraitStateNotification, _Mapping]] = ..., traitInfo: _Optional[_Union[TraitInfo, _Mapping]] = ..., confirmedState: _Optional[_Union[TraitStateNotification, _Mapping]] = ...) -> None: ...

class TraitInfo(_message.Message):
    __slots__ = ("traitType", "schemaVersion")
    TRAITTYPE_FIELD_NUMBER: _ClassVar[int]
    SCHEMAVERSION_FIELD_NUMBER: _ClassVar[int]
    traitType: str
    schemaVersion: _messages_pb2.SchemaVersion
    def __init__(self, traitType: _Optional[str] = ..., schemaVersion: _Optional[_Union[_messages_pb2.SchemaVersion, _Mapping]] = ...) -> None: ...

class TraitUpdateStateRequest(_message.Message):
    __slots__ = ("traitRequest", "state", "stateMask", "matchPublisherVersion", "schemaVersion")
    TRAITREQUEST_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    STATEMASK_FIELD_NUMBER: _ClassVar[int]
    MATCHPUBLISHERVERSION_FIELD_NUMBER: _ClassVar[int]
    SCHEMAVERSION_FIELD_NUMBER: _ClassVar[int]
    traitRequest: TraitRequest
    state: _any_pb2.Any
    stateMask: _field_mask_pb2.FieldMask
    matchPublisherVersion: int
    schemaVersion: _messages_pb2.SchemaVersion
    def __init__(self, traitRequest: _Optional[_Union[TraitRequest, _Mapping]] = ..., state: _Optional[_Union[_any_pb2.Any, _Mapping]] = ..., stateMask: _Optional[_Union[_field_mask_pb2.FieldMask, _Mapping]] = ..., matchPublisherVersion: _Optional[int] = ..., schemaVersion: _Optional[_Union[_messages_pb2.SchemaVersion, _Mapping]] = ...) -> None: ...

class TraitNotifyRequest(_message.Message):
    __slots__ = ("traitRequest", "confirmedState", "events")
    TRAITREQUEST_FIELD_NUMBER: _ClassVar[int]
    CONFIRMEDSTATE_FIELD_NUMBER: _ClassVar[int]
    EVENTS_FIELD_NUMBER: _ClassVar[int]
    traitRequest: TraitRequest
    confirmedState: TraitStateNotification
    events: TraitEventsNotification
    def __init__(self, traitRequest: _Optional[_Union[TraitRequest, _Mapping]] = ..., confirmedState: _Optional[_Union[TraitStateNotification, _Mapping]] = ..., events: _Optional[_Union[TraitEventsNotification, _Mapping]] = ...) -> None: ...

class TraitNotifyResponse(_message.Message):
    __slots__ = ("traitRequest",)
    TRAITREQUEST_FIELD_NUMBER: _ClassVar[int]
    traitRequest: TraitRequest
    def __init__(self, traitRequest: _Optional[_Union[TraitRequest, _Mapping]] = ...) -> None: ...

class TraitEvent(_message.Message):
    __slots__ = ("event",)
    EVENT_FIELD_NUMBER: _ClassVar[int]
    event: _any_pb2.Any
    def __init__(self, event: _Optional[_Union[_any_pb2.Any, _Mapping]] = ...) -> None: ...

class TraitCommand(_message.Message):
    __slots__ = ("traitRequest", "command", "expiryTime", "authenticator", "matchPublisherVersion", "schemaVersion", "namespaceId")
    TRAITREQUEST_FIELD_NUMBER: _ClassVar[int]
    COMMAND_FIELD_NUMBER: _ClassVar[int]
    EXPIRYTIME_FIELD_NUMBER: _ClassVar[int]
    AUTHENTICATOR_FIELD_NUMBER: _ClassVar[int]
    MATCHPUBLISHERVERSION_FIELD_NUMBER: _ClassVar[int]
    SCHEMAVERSION_FIELD_NUMBER: _ClassVar[int]
    NAMESPACEID_FIELD_NUMBER: _ClassVar[int]
    traitRequest: TraitRequest
    command: _any_pb2.Any
    expiryTime: _timestamp_pb2.Timestamp
    authenticator: bytes
    matchPublisherVersion: int
    schemaVersion: _messages_pb2.SchemaVersion
    namespaceId: str
    def __init__(self, traitRequest: _Optional[_Union[TraitRequest, _Mapping]] = ..., command: _Optional[_Union[_any_pb2.Any, _Mapping]] = ..., expiryTime: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., authenticator: _Optional[bytes] = ..., matchPublisherVersion: _Optional[int] = ..., schemaVersion: _Optional[_Union[_messages_pb2.SchemaVersion, _Mapping]] = ..., namespaceId: _Optional[str] = ...) -> None: ...

class WeaveStatusReport(_message.Message):
    __slots__ = ("profileId", "statusCode")
    PROFILEID_FIELD_NUMBER: _ClassVar[int]
    STATUSCODE_FIELD_NUMBER: _ClassVar[int]
    profileId: int
    statusCode: int
    def __init__(self, profileId: _Optional[int] = ..., statusCode: _Optional[int] = ...) -> None: ...

class ResourceRequest(_message.Message):
    __slots__ = ("resourceId", "requestId", "namespaceId")
    RESOURCEID_FIELD_NUMBER: _ClassVar[int]
    REQUESTID_FIELD_NUMBER: _ClassVar[int]
    NAMESPACEID_FIELD_NUMBER: _ClassVar[int]
    resourceId: str
    requestId: str
    namespaceId: str
    def __init__(self, resourceId: _Optional[str] = ..., requestId: _Optional[str] = ..., namespaceId: _Optional[str] = ...) -> None: ...

class ResourceObserveRequest(_message.Message):
    __slots__ = ("resourceRequest", "traitStateObserves", "includeConfirmedState", "includePendingOperations")
    RESOURCEREQUEST_FIELD_NUMBER: _ClassVar[int]
    TRAITSTATEOBSERVES_FIELD_NUMBER: _ClassVar[int]
    INCLUDECONFIRMEDSTATE_FIELD_NUMBER: _ClassVar[int]
    INCLUDEPENDINGOPERATIONS_FIELD_NUMBER: _ClassVar[int]
    resourceRequest: ResourceRequest
    traitStateObserves: _containers.RepeatedCompositeFieldContainer[TraitStateObserve]
    includeConfirmedState: bool
    includePendingOperations: bool
    def __init__(self, resourceRequest: _Optional[_Union[ResourceRequest, _Mapping]] = ..., traitStateObserves: _Optional[_Iterable[_Union[TraitStateObserve, _Mapping]]] = ..., includeConfirmedState: bool = ..., includePendingOperations: bool = ...) -> None: ...

class TraitStateObserve(_message.Message):
    __slots__ = ("traitLabel", "fieldMask", "monotonicVersionFilter")
    TRAITLABEL_FIELD_NUMBER: _ClassVar[int]
    FIELDMASK_FIELD_NUMBER: _ClassVar[int]
    MONOTONICVERSIONFILTER_FIELD_NUMBER: _ClassVar[int]
    traitLabel: str
    fieldMask: _field_mask_pb2.FieldMask
    monotonicVersionFilter: int
    def __init__(self, traitLabel: _Optional[str] = ..., fieldMask: _Optional[_Union[_field_mask_pb2.FieldMask, _Mapping]] = ..., monotonicVersionFilter: _Optional[int] = ...) -> None: ...

class ResourceObserveResponse(_message.Message):
    __slots__ = ("resourceRequest", "resourceInfo", "traitResponses")
    RESOURCEREQUEST_FIELD_NUMBER: _ClassVar[int]
    RESOURCEINFO_FIELD_NUMBER: _ClassVar[int]
    TRAITRESPONSES_FIELD_NUMBER: _ClassVar[int]
    resourceRequest: ResourceRequest
    resourceInfo: ResourceInfo
    traitResponses: _containers.RepeatedCompositeFieldContainer[TraitObserveResponse]
    def __init__(self, resourceRequest: _Optional[_Union[ResourceRequest, _Mapping]] = ..., resourceInfo: _Optional[_Union[ResourceInfo, _Mapping]] = ..., traitResponses: _Optional[_Iterable[_Union[TraitObserveResponse, _Mapping]]] = ...) -> None: ...

class ResourceInfo(_message.Message):
    __slots__ = ("resourceType", "traitInfos", "ifaceInfos", "currentSchemaVersion")
    class TraitInfosEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: TraitInfo
        def __init__(self, key: _Optional[str] = ..., value: _Optional[_Union[TraitInfo, _Mapping]] = ...) -> None: ...
    RESOURCETYPE_FIELD_NUMBER: _ClassVar[int]
    TRAITINFOS_FIELD_NUMBER: _ClassVar[int]
    IFACEINFOS_FIELD_NUMBER: _ClassVar[int]
    CURRENTSCHEMAVERSION_FIELD_NUMBER: _ClassVar[int]
    resourceType: str
    traitInfos: _containers.MessageMap[str, TraitInfo]
    ifaceInfos: _containers.RepeatedCompositeFieldContainer[IfaceInfo]
    currentSchemaVersion: int
    def __init__(self, resourceType: _Optional[str] = ..., traitInfos: _Optional[_Mapping[str, TraitInfo]] = ..., ifaceInfos: _Optional[_Iterable[_Union[IfaceInfo, _Mapping]]] = ..., currentSchemaVersion: _Optional[int] = ...) -> None: ...

class IfaceInfo(_message.Message):
    __slots__ = ("ifaceType", "ifaceTraitInfos", "schemaVersion")
    IFACETYPE_FIELD_NUMBER: _ClassVar[int]
    IFACETRAITINFOS_FIELD_NUMBER: _ClassVar[int]
    SCHEMAVERSION_FIELD_NUMBER: _ClassVar[int]
    ifaceType: str
    ifaceTraitInfos: _containers.RepeatedCompositeFieldContainer[IfaceTraitInfo]
    schemaVersion: _messages_pb2.SchemaVersion
    def __init__(self, ifaceType: _Optional[str] = ..., ifaceTraitInfos: _Optional[_Iterable[_Union[IfaceTraitInfo, _Mapping]]] = ..., schemaVersion: _Optional[_Union[_messages_pb2.SchemaVersion, _Mapping]] = ...) -> None: ...

class IfaceTraitInfo(_message.Message):
    __slots__ = ("ifaceTraitLabel", "resourceTraitLabel")
    IFACETRAITLABEL_FIELD_NUMBER: _ClassVar[int]
    RESOURCETRAITLABEL_FIELD_NUMBER: _ClassVar[int]
    ifaceTraitLabel: str
    resourceTraitLabel: str
    def __init__(self, ifaceTraitLabel: _Optional[str] = ..., resourceTraitLabel: _Optional[str] = ...) -> None: ...

class ResourceGetStateRequest(_message.Message):
    __slots__ = ("resourceRequest", "resourceGetStates", "includeConfirmedState", "includePendingOperations")
    RESOURCEREQUEST_FIELD_NUMBER: _ClassVar[int]
    RESOURCEGETSTATES_FIELD_NUMBER: _ClassVar[int]
    INCLUDECONFIRMEDSTATE_FIELD_NUMBER: _ClassVar[int]
    INCLUDEPENDINGOPERATIONS_FIELD_NUMBER: _ClassVar[int]
    resourceRequest: ResourceRequest
    resourceGetStates: _containers.RepeatedCompositeFieldContainer[ResourceGetState]
    includeConfirmedState: bool
    includePendingOperations: bool
    def __init__(self, resourceRequest: _Optional[_Union[ResourceRequest, _Mapping]] = ..., resourceGetStates: _Optional[_Iterable[_Union[ResourceGetState, _Mapping]]] = ..., includeConfirmedState: bool = ..., includePendingOperations: bool = ...) -> None: ...

class ResourceGetState(_message.Message):
    __slots__ = ("traitLabel", "fieldMask", "monotonicVersionFilter")
    TRAITLABEL_FIELD_NUMBER: _ClassVar[int]
    FIELDMASK_FIELD_NUMBER: _ClassVar[int]
    MONOTONICVERSIONFILTER_FIELD_NUMBER: _ClassVar[int]
    traitLabel: str
    fieldMask: _field_mask_pb2.FieldMask
    monotonicVersionFilter: int
    def __init__(self, traitLabel: _Optional[str] = ..., fieldMask: _Optional[_Union[_field_mask_pb2.FieldMask, _Mapping]] = ..., monotonicVersionFilter: _Optional[int] = ...) -> None: ...

class ResourceGetStateResponse(_message.Message):
    __slots__ = ("resourceRequest", "resourceInfo", "traitResponses")
    RESOURCEREQUEST_FIELD_NUMBER: _ClassVar[int]
    RESOURCEINFO_FIELD_NUMBER: _ClassVar[int]
    TRAITRESPONSES_FIELD_NUMBER: _ClassVar[int]
    resourceRequest: ResourceRequest
    resourceInfo: ResourceInfo
    traitResponses: _containers.RepeatedCompositeFieldContainer[TraitGetStateResponse]
    def __init__(self, resourceRequest: _Optional[_Union[ResourceRequest, _Mapping]] = ..., resourceInfo: _Optional[_Union[ResourceInfo, _Mapping]] = ..., traitResponses: _Optional[_Iterable[_Union[TraitGetStateResponse, _Mapping]]] = ...) -> None: ...

class ResourceNotifyRequest(_message.Message):
    __slots__ = ("resourceRequest", "resourceStateNotifies", "resourceEventsNotifies")
    RESOURCEREQUEST_FIELD_NUMBER: _ClassVar[int]
    RESOURCESTATENOTIFIES_FIELD_NUMBER: _ClassVar[int]
    RESOURCEEVENTSNOTIFIES_FIELD_NUMBER: _ClassVar[int]
    resourceRequest: ResourceRequest
    resourceStateNotifies: _containers.RepeatedCompositeFieldContainer[ResourceStateNotify]
    resourceEventsNotifies: _containers.RepeatedCompositeFieldContainer[ResourceEventsNotify]
    def __init__(self, resourceRequest: _Optional[_Union[ResourceRequest, _Mapping]] = ..., resourceStateNotifies: _Optional[_Iterable[_Union[ResourceStateNotify, _Mapping]]] = ..., resourceEventsNotifies: _Optional[_Iterable[_Union[ResourceEventsNotify, _Mapping]]] = ...) -> None: ...

class ResourceStateNotify(_message.Message):
    __slots__ = ("traitLabel", "confirmedState")
    TRAITLABEL_FIELD_NUMBER: _ClassVar[int]
    CONFIRMEDSTATE_FIELD_NUMBER: _ClassVar[int]
    traitLabel: str
    confirmedState: TraitStateNotification
    def __init__(self, traitLabel: _Optional[str] = ..., confirmedState: _Optional[_Union[TraitStateNotification, _Mapping]] = ...) -> None: ...

class ResourceEventsNotify(_message.Message):
    __slots__ = ("traitLabel", "events")
    TRAITLABEL_FIELD_NUMBER: _ClassVar[int]
    EVENTS_FIELD_NUMBER: _ClassVar[int]
    traitLabel: str
    events: TraitEventsNotification
    def __init__(self, traitLabel: _Optional[str] = ..., events: _Optional[_Union[TraitEventsNotification, _Mapping]] = ...) -> None: ...

class ResourceNotifyResponse(_message.Message):
    __slots__ = ("resourceRequest", "traitResponses")
    RESOURCEREQUEST_FIELD_NUMBER: _ClassVar[int]
    TRAITRESPONSES_FIELD_NUMBER: _ClassVar[int]
    resourceRequest: ResourceRequest
    traitResponses: _containers.RepeatedCompositeFieldContainer[TraitNotifyResponse]
    def __init__(self, resourceRequest: _Optional[_Union[ResourceRequest, _Mapping]] = ..., traitResponses: _Optional[_Iterable[_Union[TraitNotifyResponse, _Mapping]]] = ...) -> None: ...

class ResourceCommand(_message.Message):
    __slots__ = ("traitLabel", "command", "expiryTime", "authenticator", "matchPublisherVersion", "schemaVersion", "resourceType")
    TRAITLABEL_FIELD_NUMBER: _ClassVar[int]
    COMMAND_FIELD_NUMBER: _ClassVar[int]
    EXPIRYTIME_FIELD_NUMBER: _ClassVar[int]
    AUTHENTICATOR_FIELD_NUMBER: _ClassVar[int]
    MATCHPUBLISHERVERSION_FIELD_NUMBER: _ClassVar[int]
    SCHEMAVERSION_FIELD_NUMBER: _ClassVar[int]
    RESOURCETYPE_FIELD_NUMBER: _ClassVar[int]
    traitLabel: str
    command: _any_pb2.Any
    expiryTime: _timestamp_pb2.Timestamp
    authenticator: bytes
    matchPublisherVersion: int
    schemaVersion: _messages_pb2.SchemaVersion
    resourceType: str
    def __init__(self, traitLabel: _Optional[str] = ..., command: _Optional[_Union[_any_pb2.Any, _Mapping]] = ..., expiryTime: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., authenticator: _Optional[bytes] = ..., matchPublisherVersion: _Optional[int] = ..., schemaVersion: _Optional[_Union[_messages_pb2.SchemaVersion, _Mapping]] = ..., resourceType: _Optional[str] = ...) -> None: ...

class SendCommandRequest(_message.Message):
    __slots__ = ("resourceRequest", "resourceCommands")
    RESOURCEREQUEST_FIELD_NUMBER: _ClassVar[int]
    RESOURCECOMMANDS_FIELD_NUMBER: _ClassVar[int]
    resourceRequest: ResourceRequest
    resourceCommands: _containers.RepeatedCompositeFieldContainer[ResourceCommand]
    def __init__(self, resourceRequest: _Optional[_Union[ResourceRequest, _Mapping]] = ..., resourceCommands: _Optional[_Iterable[_Union[ResourceCommand, _Mapping]]] = ...) -> None: ...

class SendCommandResponse(_message.Message):
    __slots__ = ("sendCommandResponse", "status")
    class ResourceCommandResponse(_message.Message):
        __slots__ = ("resourceRequest", "traitOperations")
        RESOURCEREQUEST_FIELD_NUMBER: _ClassVar[int]
        TRAITOPERATIONS_FIELD_NUMBER: _ClassVar[int]
        resourceRequest: ResourceRequest
        traitOperations: _containers.RepeatedCompositeFieldContainer[TraitOperation]
        def __init__(self, resourceRequest: _Optional[_Union[ResourceRequest, _Mapping]] = ..., traitOperations: _Optional[_Iterable[_Union[TraitOperation, _Mapping]]] = ...) -> None: ...
    SENDCOMMANDRESPONSE_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    sendCommandResponse: _containers.RepeatedCompositeFieldContainer[SendCommandResponse.ResourceCommandResponse]
    status: _status_pb2.Status
    def __init__(self, sendCommandResponse: _Optional[_Iterable[_Union[SendCommandResponse.ResourceCommandResponse, _Mapping]]] = ..., status: _Optional[_Union[_status_pb2.Status, _Mapping]] = ...) -> None: ...

class BatchUpdateStateRequest(_message.Message):
    __slots__ = ("batchUpdateStateRequest",)
    BATCHUPDATESTATEREQUEST_FIELD_NUMBER: _ClassVar[int]
    batchUpdateStateRequest: _containers.RepeatedCompositeFieldContainer[TraitUpdateStateRequest]
    def __init__(self, batchUpdateStateRequest: _Optional[_Iterable[_Union[TraitUpdateStateRequest, _Mapping]]] = ...) -> None: ...

class BatchUpdateStateResponse(_message.Message):
    __slots__ = ("batchUpdateStateResponse", "status")
    class TraitOperationStateResponse(_message.Message):
        __slots__ = ("traitOperations",)
        TRAITOPERATIONS_FIELD_NUMBER: _ClassVar[int]
        traitOperations: _containers.RepeatedCompositeFieldContainer[TraitOperation]
        def __init__(self, traitOperations: _Optional[_Iterable[_Union[TraitOperation, _Mapping]]] = ...) -> None: ...
    BATCHUPDATESTATERESPONSE_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    batchUpdateStateResponse: _containers.RepeatedCompositeFieldContainer[BatchUpdateStateResponse.TraitOperationStateResponse]
    status: _status_pb2.Status
    def __init__(self, batchUpdateStateResponse: _Optional[_Iterable[_Union[BatchUpdateStateResponse.TraitOperationStateResponse, _Mapping]]] = ..., status: _Optional[_Union[_status_pb2.Status, _Mapping]] = ...) -> None: ...
