import datetime

from google.protobuf import any_pb2 as _any_pb2
from google.protobuf import field_mask_pb2 as _field_mask_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from ...nest import messages_pb2 as _messages_pb2
from ...nestlabs.gateway import v1_pb2 as _v1_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class ResourceStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    NORMAL: _ClassVar[ResourceStatus]
    ADDED: _ClassVar[ResourceStatus]
    REMOVED: _ClassVar[ResourceStatus]

class StateType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    STATE_TYPE_UNSPECIFIED: _ClassVar[StateType]
    CONFIRMED: _ClassVar[StateType]
    ACCEPTED: _ClassVar[StateType]
NORMAL: ResourceStatus
ADDED: ResourceStatus
REMOVED: ResourceStatus
STATE_TYPE_UNSPECIFIED: StateType
CONFIRMED: StateType
ACCEPTED: StateType

class TraitMeta(_message.Message):
    __slots__ = ("traitLabel", "type", "schemaVersion")
    TRAITLABEL_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    SCHEMAVERSION_FIELD_NUMBER: _ClassVar[int]
    traitLabel: str
    type: str
    schemaVersion: _messages_pb2.SchemaVersion
    def __init__(self, traitLabel: _Optional[str] = ..., type: _Optional[str] = ..., schemaVersion: _Optional[_Union[_messages_pb2.SchemaVersion, _Mapping]] = ...) -> None: ...

class IfaceMeta(_message.Message):
    __slots__ = ("ifaceLabel", "type", "traitLabelMapping", "schemaVersion")
    class TraitLabelMappingEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: str
        def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...
    IFACELABEL_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    TRAITLABELMAPPING_FIELD_NUMBER: _ClassVar[int]
    SCHEMAVERSION_FIELD_NUMBER: _ClassVar[int]
    ifaceLabel: str
    type: str
    traitLabelMapping: _containers.ScalarMap[str, str]
    schemaVersion: _messages_pb2.SchemaVersion
    def __init__(self, ifaceLabel: _Optional[str] = ..., type: _Optional[str] = ..., traitLabelMapping: _Optional[_Mapping[str, str]] = ..., schemaVersion: _Optional[_Union[_messages_pb2.SchemaVersion, _Mapping]] = ...) -> None: ...

class ResourceMeta(_message.Message):
    __slots__ = ("resourceId", "type", "status", "traitMetas", "currentSchemaVersion", "ifaceMetas")
    RESOURCEID_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    TRAITMETAS_FIELD_NUMBER: _ClassVar[int]
    CURRENTSCHEMAVERSION_FIELD_NUMBER: _ClassVar[int]
    IFACEMETAS_FIELD_NUMBER: _ClassVar[int]
    resourceId: str
    type: str
    status: ResourceStatus
    traitMetas: _containers.RepeatedCompositeFieldContainer[TraitMeta]
    currentSchemaVersion: int
    ifaceMetas: _containers.RepeatedCompositeFieldContainer[IfaceMeta]
    def __init__(self, resourceId: _Optional[str] = ..., type: _Optional[str] = ..., status: _Optional[_Union[ResourceStatus, str]] = ..., traitMetas: _Optional[_Iterable[_Union[TraitMeta, _Mapping]]] = ..., currentSchemaVersion: _Optional[int] = ..., ifaceMetas: _Optional[_Iterable[_Union[IfaceMeta, _Mapping]]] = ...) -> None: ...

class TraitId(_message.Message):
    __slots__ = ("resourceId", "traitLabel")
    RESOURCEID_FIELD_NUMBER: _ClassVar[int]
    TRAITLABEL_FIELD_NUMBER: _ClassVar[int]
    resourceId: str
    traitLabel: str
    def __init__(self, resourceId: _Optional[str] = ..., traitLabel: _Optional[str] = ...) -> None: ...

class Patch(_message.Message):
    __slots__ = ("values",)
    VALUES_FIELD_NUMBER: _ClassVar[int]
    values: _any_pb2.Any
    def __init__(self, values: _Optional[_Union[_any_pb2.Any, _Mapping]] = ...) -> None: ...

class TraitState(_message.Message):
    __slots__ = ("traitId", "stateTypes", "patch", "monotonicVersion", "publisherVersion")
    TRAITID_FIELD_NUMBER: _ClassVar[int]
    STATETYPES_FIELD_NUMBER: _ClassVar[int]
    PATCH_FIELD_NUMBER: _ClassVar[int]
    MONOTONICVERSION_FIELD_NUMBER: _ClassVar[int]
    PUBLISHERVERSION_FIELD_NUMBER: _ClassVar[int]
    traitId: TraitId
    stateTypes: _containers.RepeatedScalarFieldContainer[StateType]
    patch: Patch
    monotonicVersion: int
    publisherVersion: int
    def __init__(self, traitId: _Optional[_Union[TraitId, _Mapping]] = ..., stateTypes: _Optional[_Iterable[_Union[StateType, str]]] = ..., patch: _Optional[_Union[Patch, _Mapping]] = ..., monotonicVersion: _Optional[int] = ..., publisherVersion: _Optional[int] = ...) -> None: ...

class TraitTypeObserveParams(_message.Message):
    __slots__ = ("traitType", "stateFieldMask", "observerSchemaVersion")
    TRAITTYPE_FIELD_NUMBER: _ClassVar[int]
    STATEFIELDMASK_FIELD_NUMBER: _ClassVar[int]
    OBSERVERSCHEMAVERSION_FIELD_NUMBER: _ClassVar[int]
    traitType: str
    stateFieldMask: _field_mask_pb2.FieldMask
    observerSchemaVersion: int
    def __init__(self, traitType: _Optional[str] = ..., stateFieldMask: _Optional[_Union[_field_mask_pb2.FieldMask, _Mapping]] = ..., observerSchemaVersion: _Optional[int] = ...) -> None: ...

class TraitInstanceObserveParams(_message.Message):
    __slots__ = ("traitId", "monotonicVersionFilters")
    TRAITID_FIELD_NUMBER: _ClassVar[int]
    MONOTONICVERSIONFILTERS_FIELD_NUMBER: _ClassVar[int]
    traitId: TraitId
    monotonicVersionFilters: _containers.RepeatedScalarFieldContainer[int]
    def __init__(self, traitId: _Optional[_Union[TraitId, _Mapping]] = ..., monotonicVersionFilters: _Optional[_Iterable[int]] = ...) -> None: ...

class ObserveRequest(_message.Message):
    __slots__ = ("stateTypes", "resourceIds", "traitTypeParams", "traitInstanceParams", "userId")
    STATETYPES_FIELD_NUMBER: _ClassVar[int]
    RESOURCEIDS_FIELD_NUMBER: _ClassVar[int]
    TRAITTYPEPARAMS_FIELD_NUMBER: _ClassVar[int]
    TRAITINSTANCEPARAMS_FIELD_NUMBER: _ClassVar[int]
    USERID_FIELD_NUMBER: _ClassVar[int]
    stateTypes: _containers.RepeatedScalarFieldContainer[StateType]
    resourceIds: _containers.RepeatedScalarFieldContainer[str]
    traitTypeParams: _containers.RepeatedCompositeFieldContainer[TraitTypeObserveParams]
    traitInstanceParams: _containers.RepeatedCompositeFieldContainer[TraitInstanceObserveParams]
    userId: str
    def __init__(self, stateTypes: _Optional[_Iterable[_Union[StateType, str]]] = ..., resourceIds: _Optional[_Iterable[str]] = ..., traitTypeParams: _Optional[_Iterable[_Union[TraitTypeObserveParams, _Mapping]]] = ..., traitInstanceParams: _Optional[_Iterable[_Union[TraitInstanceObserveParams, _Mapping]]] = ..., userId: _Optional[str] = ...) -> None: ...

class TraitOperationList(_message.Message):
    __slots__ = ("traitId", "traitOperations")
    TRAITID_FIELD_NUMBER: _ClassVar[int]
    TRAITOPERATIONS_FIELD_NUMBER: _ClassVar[int]
    traitId: TraitId
    traitOperations: _containers.RepeatedCompositeFieldContainer[_v1_pb2.TraitOperation]
    def __init__(self, traitId: _Optional[_Union[TraitId, _Mapping]] = ..., traitOperations: _Optional[_Iterable[_Union[_v1_pb2.TraitOperation, _Mapping]]] = ...) -> None: ...

class ObserveResponse(_message.Message):
    __slots__ = ("observeResponse",)
    class ObserveResponse(_message.Message):
        __slots__ = ("resourceMetas", "initialResourceMetasContinue", "traitStates", "traitOperationLists", "currentTime")
        RESOURCEMETAS_FIELD_NUMBER: _ClassVar[int]
        INITIALRESOURCEMETASCONTINUE_FIELD_NUMBER: _ClassVar[int]
        TRAITSTATES_FIELD_NUMBER: _ClassVar[int]
        TRAITOPERATIONLISTS_FIELD_NUMBER: _ClassVar[int]
        CURRENTTIME_FIELD_NUMBER: _ClassVar[int]
        resourceMetas: _containers.RepeatedCompositeFieldContainer[ResourceMeta]
        initialResourceMetasContinue: bool
        traitStates: _containers.RepeatedCompositeFieldContainer[TraitState]
        traitOperationLists: _containers.RepeatedCompositeFieldContainer[TraitOperationList]
        currentTime: _timestamp_pb2.Timestamp
        def __init__(self, resourceMetas: _Optional[_Iterable[_Union[ResourceMeta, _Mapping]]] = ..., initialResourceMetasContinue: bool = ..., traitStates: _Optional[_Iterable[_Union[TraitState, _Mapping]]] = ..., traitOperationLists: _Optional[_Iterable[_Union[TraitOperationList, _Mapping]]] = ..., currentTime: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...
    OBSERVERESPONSE_FIELD_NUMBER: _ClassVar[int]
    observeResponse: _containers.RepeatedCompositeFieldContainer[ObserveResponse.ObserveResponse]
    def __init__(self, observeResponse: _Optional[_Iterable[_Union[ObserveResponse.ObserveResponse, _Mapping]]] = ...) -> None: ...
