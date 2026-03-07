import datetime

from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf import wrappers_pb2 as _wrappers_pb2
from ...weave import common_pb2 as _common_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class CustomLocatedAnnotationsTrait(_message.Message):
    __slots__ = ("wheresList", "fixturesList")
    class CustomLocatedStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        CUSTOM_LOCATED_STATUS_UNSPECIFIED: _ClassVar[CustomLocatedAnnotationsTrait.CustomLocatedStatus]
        CUSTOM_LOCATED_STATUS_ANNOTATION_EXISTS: _ClassVar[CustomLocatedAnnotationsTrait.CustomLocatedStatus]
        CUSTOM_LOCATED_STATUS_ANNOTATION_DOESNT_EXIST: _ClassVar[CustomLocatedAnnotationsTrait.CustomLocatedStatus]
        CUSTOM_LOCATED_STATUS_MISSING_PARAMS: _ClassVar[CustomLocatedAnnotationsTrait.CustomLocatedStatus]
        CUSTOM_LOCATED_STATUS_SUCCESS: _ClassVar[CustomLocatedAnnotationsTrait.CustomLocatedStatus]
        CUSTOM_LOCATED_STATUS_FAILURE: _ClassVar[CustomLocatedAnnotationsTrait.CustomLocatedStatus]
    CUSTOM_LOCATED_STATUS_UNSPECIFIED: CustomLocatedAnnotationsTrait.CustomLocatedStatus
    CUSTOM_LOCATED_STATUS_ANNOTATION_EXISTS: CustomLocatedAnnotationsTrait.CustomLocatedStatus
    CUSTOM_LOCATED_STATUS_ANNOTATION_DOESNT_EXIST: CustomLocatedAnnotationsTrait.CustomLocatedStatus
    CUSTOM_LOCATED_STATUS_MISSING_PARAMS: CustomLocatedAnnotationsTrait.CustomLocatedStatus
    CUSTOM_LOCATED_STATUS_SUCCESS: CustomLocatedAnnotationsTrait.CustomLocatedStatus
    CUSTOM_LOCATED_STATUS_FAILURE: CustomLocatedAnnotationsTrait.CustomLocatedStatus
    class WheresListEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: int
        value: CustomLocatedAnnotationsTrait.WhereItem
        def __init__(self, key: _Optional[int] = ..., value: _Optional[_Union[CustomLocatedAnnotationsTrait.WhereItem, _Mapping]] = ...) -> None: ...
    class FixturesListEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: int
        value: CustomLocatedAnnotationsTrait.FixtureItem
        def __init__(self, key: _Optional[int] = ..., value: _Optional[_Union[CustomLocatedAnnotationsTrait.FixtureItem, _Mapping]] = ...) -> None: ...
    class WhereItem(_message.Message):
        __slots__ = ("label", "legacyUuid", "whereId")
        LABEL_FIELD_NUMBER: _ClassVar[int]
        LEGACYUUID_FIELD_NUMBER: _ClassVar[int]
        WHEREID_FIELD_NUMBER: _ClassVar[int]
        label: _common_pb2.StringRef
        legacyUuid: _common_pb2.StringRef
        whereId: _common_pb2.ResourceId
        def __init__(self, label: _Optional[_Union[_common_pb2.StringRef, _Mapping]] = ..., legacyUuid: _Optional[_Union[_common_pb2.StringRef, _Mapping]] = ..., whereId: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ...) -> None: ...
    class FixtureItem(_message.Message):
        __slots__ = ("label", "fixtureId")
        LABEL_FIELD_NUMBER: _ClassVar[int]
        FIXTUREID_FIELD_NUMBER: _ClassVar[int]
        label: _common_pb2.StringRef
        fixtureId: _common_pb2.ResourceId
        def __init__(self, label: _Optional[_Union[_common_pb2.StringRef, _Mapping]] = ..., fixtureId: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ...) -> None: ...
    class CustomWhereCreationRequest(_message.Message):
        __slots__ = ("label",)
        LABEL_FIELD_NUMBER: _ClassVar[int]
        label: _common_pb2.StringRef
        def __init__(self, label: _Optional[_Union[_common_pb2.StringRef, _Mapping]] = ...) -> None: ...
    class CustomWhereCreationResponse(_message.Message):
        __slots__ = ("whereItem", "status")
        WHEREITEM_FIELD_NUMBER: _ClassVar[int]
        STATUS_FIELD_NUMBER: _ClassVar[int]
        whereItem: CustomLocatedAnnotationsTrait.WhereItem
        status: CustomLocatedAnnotationsTrait.CustomLocatedStatus
        def __init__(self, whereItem: _Optional[_Union[CustomLocatedAnnotationsTrait.WhereItem, _Mapping]] = ..., status: _Optional[_Union[CustomLocatedAnnotationsTrait.CustomLocatedStatus, str]] = ...) -> None: ...
    class CustomWhereDeletionRequest(_message.Message):
        __slots__ = ("whereId",)
        WHEREID_FIELD_NUMBER: _ClassVar[int]
        whereId: _common_pb2.ResourceId
        def __init__(self, whereId: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ...) -> None: ...
    class CustomWhereDeletionResponse(_message.Message):
        __slots__ = ("status",)
        STATUS_FIELD_NUMBER: _ClassVar[int]
        status: CustomLocatedAnnotationsTrait.CustomLocatedStatus
        def __init__(self, status: _Optional[_Union[CustomLocatedAnnotationsTrait.CustomLocatedStatus, str]] = ...) -> None: ...
    class CustomFixtureCreationRequest(_message.Message):
        __slots__ = ("label",)
        LABEL_FIELD_NUMBER: _ClassVar[int]
        label: _common_pb2.StringRef
        def __init__(self, label: _Optional[_Union[_common_pb2.StringRef, _Mapping]] = ...) -> None: ...
    class CustomFixtureCreationResponse(_message.Message):
        __slots__ = ("fixtureItem", "status")
        FIXTUREITEM_FIELD_NUMBER: _ClassVar[int]
        STATUS_FIELD_NUMBER: _ClassVar[int]
        fixtureItem: CustomLocatedAnnotationsTrait.FixtureItem
        status: CustomLocatedAnnotationsTrait.CustomLocatedStatus
        def __init__(self, fixtureItem: _Optional[_Union[CustomLocatedAnnotationsTrait.FixtureItem, _Mapping]] = ..., status: _Optional[_Union[CustomLocatedAnnotationsTrait.CustomLocatedStatus, str]] = ...) -> None: ...
    class CustomFixtureDeletionRequest(_message.Message):
        __slots__ = ("fixtureId",)
        FIXTUREID_FIELD_NUMBER: _ClassVar[int]
        fixtureId: _common_pb2.ResourceId
        def __init__(self, fixtureId: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ...) -> None: ...
    class CustomFixtureDeletionResponse(_message.Message):
        __slots__ = ("status",)
        STATUS_FIELD_NUMBER: _ClassVar[int]
        status: CustomLocatedAnnotationsTrait.CustomLocatedStatus
        def __init__(self, status: _Optional[_Union[CustomLocatedAnnotationsTrait.CustomLocatedStatus, str]] = ...) -> None: ...
    class CustomFixtureCreationEvent(_message.Message):
        __slots__ = ("fixture",)
        FIXTURE_FIELD_NUMBER: _ClassVar[int]
        fixture: CustomLocatedAnnotationsTrait.FixtureItem
        def __init__(self, fixture: _Optional[_Union[CustomLocatedAnnotationsTrait.FixtureItem, _Mapping]] = ...) -> None: ...
    class CustomWhereCreationEvent(_message.Message):
        __slots__ = ("where",)
        WHERE_FIELD_NUMBER: _ClassVar[int]
        where: CustomLocatedAnnotationsTrait.WhereItem
        def __init__(self, where: _Optional[_Union[CustomLocatedAnnotationsTrait.WhereItem, _Mapping]] = ...) -> None: ...
    WHERESLIST_FIELD_NUMBER: _ClassVar[int]
    FIXTURESLIST_FIELD_NUMBER: _ClassVar[int]
    wheresList: _containers.MessageMap[int, CustomLocatedAnnotationsTrait.WhereItem]
    fixturesList: _containers.MessageMap[int, CustomLocatedAnnotationsTrait.FixtureItem]
    def __init__(self, wheresList: _Optional[_Mapping[int, CustomLocatedAnnotationsTrait.WhereItem]] = ..., fixturesList: _Optional[_Mapping[int, CustomLocatedAnnotationsTrait.FixtureItem]] = ...) -> None: ...

class LocatedTrait(_message.Message):
    __slots__ = ()
    class LocatedMajorFixtureType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        LOCATED_MAJOR_FIXTURE_TYPE_UNSPECIFIED: _ClassVar[LocatedTrait.LocatedMajorFixtureType]
        LOCATED_MAJOR_FIXTURE_TYPE_DOOR: _ClassVar[LocatedTrait.LocatedMajorFixtureType]
        LOCATED_MAJOR_FIXTURE_TYPE_WINDOW: _ClassVar[LocatedTrait.LocatedMajorFixtureType]
        LOCATED_MAJOR_FIXTURE_TYPE_WALL: _ClassVar[LocatedTrait.LocatedMajorFixtureType]
        LOCATED_MAJOR_FIXTURE_TYPE_OBJECT: _ClassVar[LocatedTrait.LocatedMajorFixtureType]
    LOCATED_MAJOR_FIXTURE_TYPE_UNSPECIFIED: LocatedTrait.LocatedMajorFixtureType
    LOCATED_MAJOR_FIXTURE_TYPE_DOOR: LocatedTrait.LocatedMajorFixtureType
    LOCATED_MAJOR_FIXTURE_TYPE_WINDOW: LocatedTrait.LocatedMajorFixtureType
    LOCATED_MAJOR_FIXTURE_TYPE_WALL: LocatedTrait.LocatedMajorFixtureType
    LOCATED_MAJOR_FIXTURE_TYPE_OBJECT: LocatedTrait.LocatedMajorFixtureType
    class LocatedMinorFixtureTypeDoor(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        LOCATED_MINOR_FIXTURE_TYPE_DOOR_UNSPECIFIED: _ClassVar[LocatedTrait.LocatedMinorFixtureTypeDoor]
        LOCATED_MINOR_FIXTURE_TYPE_DOOR_GENERIC: _ClassVar[LocatedTrait.LocatedMinorFixtureTypeDoor]
        LOCATED_MINOR_FIXTURE_TYPE_DOOR_HINGED: _ClassVar[LocatedTrait.LocatedMinorFixtureTypeDoor]
        LOCATED_MINOR_FIXTURE_TYPE_DOOR_FRENCH: _ClassVar[LocatedTrait.LocatedMinorFixtureTypeDoor]
        LOCATED_MINOR_FIXTURE_TYPE_DOOR_SLIDING: _ClassVar[LocatedTrait.LocatedMinorFixtureTypeDoor]
        LOCATED_MINOR_FIXTURE_TYPE_DOOR_GARAGE_SEGMENTED: _ClassVar[LocatedTrait.LocatedMinorFixtureTypeDoor]
        LOCATED_MINOR_FIXTURE_TYPE_DOOR_GARAGE_SINGLE_PANEL: _ClassVar[LocatedTrait.LocatedMinorFixtureTypeDoor]
    LOCATED_MINOR_FIXTURE_TYPE_DOOR_UNSPECIFIED: LocatedTrait.LocatedMinorFixtureTypeDoor
    LOCATED_MINOR_FIXTURE_TYPE_DOOR_GENERIC: LocatedTrait.LocatedMinorFixtureTypeDoor
    LOCATED_MINOR_FIXTURE_TYPE_DOOR_HINGED: LocatedTrait.LocatedMinorFixtureTypeDoor
    LOCATED_MINOR_FIXTURE_TYPE_DOOR_FRENCH: LocatedTrait.LocatedMinorFixtureTypeDoor
    LOCATED_MINOR_FIXTURE_TYPE_DOOR_SLIDING: LocatedTrait.LocatedMinorFixtureTypeDoor
    LOCATED_MINOR_FIXTURE_TYPE_DOOR_GARAGE_SEGMENTED: LocatedTrait.LocatedMinorFixtureTypeDoor
    LOCATED_MINOR_FIXTURE_TYPE_DOOR_GARAGE_SINGLE_PANEL: LocatedTrait.LocatedMinorFixtureTypeDoor
    class LocatedMinorFixtureTypeWindow(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        LOCATED_MINOR_FIXTURE_TYPE_WINDOW_UNSPECIFIED: _ClassVar[LocatedTrait.LocatedMinorFixtureTypeWindow]
        LOCATED_MINOR_FIXTURE_TYPE_WINDOW_GENERIC: _ClassVar[LocatedTrait.LocatedMinorFixtureTypeWindow]
        LOCATED_MINOR_FIXTURE_TYPE_WINDOW_VERTICAL_SINGLE_HUNG: _ClassVar[LocatedTrait.LocatedMinorFixtureTypeWindow]
        LOCATED_MINOR_FIXTURE_TYPE_WINDOW_HORIZONTAL_SINGLE_HUNG: _ClassVar[LocatedTrait.LocatedMinorFixtureTypeWindow]
        LOCATED_MINOR_FIXTURE_TYPE_WINDOW_VERTICAL_DOUBLE_HUNG: _ClassVar[LocatedTrait.LocatedMinorFixtureTypeWindow]
        LOCATED_MINOR_FIXTURE_TYPE_WINDOW_HORIZONTAL_DOUBLE_HUNG: _ClassVar[LocatedTrait.LocatedMinorFixtureTypeWindow]
        LOCATED_MINOR_FIXTURE_TYPE_WINDOW_VERTICAL_CASEMENT: _ClassVar[LocatedTrait.LocatedMinorFixtureTypeWindow]
        LOCATED_MINOR_FIXTURE_TYPE_WINDOW_HORIZONTAL_CASEMENT: _ClassVar[LocatedTrait.LocatedMinorFixtureTypeWindow]
        LOCATED_MINOR_FIXTURE_TYPE_WINDOW_TILTTURN: _ClassVar[LocatedTrait.LocatedMinorFixtureTypeWindow]
        LOCATED_MINOR_FIXTURE_TYPE_WINDOW_ROOF: _ClassVar[LocatedTrait.LocatedMinorFixtureTypeWindow]
    LOCATED_MINOR_FIXTURE_TYPE_WINDOW_UNSPECIFIED: LocatedTrait.LocatedMinorFixtureTypeWindow
    LOCATED_MINOR_FIXTURE_TYPE_WINDOW_GENERIC: LocatedTrait.LocatedMinorFixtureTypeWindow
    LOCATED_MINOR_FIXTURE_TYPE_WINDOW_VERTICAL_SINGLE_HUNG: LocatedTrait.LocatedMinorFixtureTypeWindow
    LOCATED_MINOR_FIXTURE_TYPE_WINDOW_HORIZONTAL_SINGLE_HUNG: LocatedTrait.LocatedMinorFixtureTypeWindow
    LOCATED_MINOR_FIXTURE_TYPE_WINDOW_VERTICAL_DOUBLE_HUNG: LocatedTrait.LocatedMinorFixtureTypeWindow
    LOCATED_MINOR_FIXTURE_TYPE_WINDOW_HORIZONTAL_DOUBLE_HUNG: LocatedTrait.LocatedMinorFixtureTypeWindow
    LOCATED_MINOR_FIXTURE_TYPE_WINDOW_VERTICAL_CASEMENT: LocatedTrait.LocatedMinorFixtureTypeWindow
    LOCATED_MINOR_FIXTURE_TYPE_WINDOW_HORIZONTAL_CASEMENT: LocatedTrait.LocatedMinorFixtureTypeWindow
    LOCATED_MINOR_FIXTURE_TYPE_WINDOW_TILTTURN: LocatedTrait.LocatedMinorFixtureTypeWindow
    LOCATED_MINOR_FIXTURE_TYPE_WINDOW_ROOF: LocatedTrait.LocatedMinorFixtureTypeWindow
    class LocatedMinorFixtureTypeWall(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        LOCATED_MINOR_FIXTURE_TYPE_WALL_UNSPECIFIED: _ClassVar[LocatedTrait.LocatedMinorFixtureTypeWall]
        LOCATED_MINOR_FIXTURE_TYPE_WALL_GENERIC: _ClassVar[LocatedTrait.LocatedMinorFixtureTypeWall]
        LOCATED_MINOR_FIXTURE_TYPE_WALL_CORNER: _ClassVar[LocatedTrait.LocatedMinorFixtureTypeWall]
        LOCATED_MINOR_FIXTURE_TYPE_WALL_FLUSH: _ClassVar[LocatedTrait.LocatedMinorFixtureTypeWall]
    LOCATED_MINOR_FIXTURE_TYPE_WALL_UNSPECIFIED: LocatedTrait.LocatedMinorFixtureTypeWall
    LOCATED_MINOR_FIXTURE_TYPE_WALL_GENERIC: LocatedTrait.LocatedMinorFixtureTypeWall
    LOCATED_MINOR_FIXTURE_TYPE_WALL_CORNER: LocatedTrait.LocatedMinorFixtureTypeWall
    LOCATED_MINOR_FIXTURE_TYPE_WALL_FLUSH: LocatedTrait.LocatedMinorFixtureTypeWall
    class LocatedMinorFixtureTypeObject(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        LOCATED_MINOR_FIXTURE_TYPE_OBJECT_UNSPECIFIED: _ClassVar[LocatedTrait.LocatedMinorFixtureTypeObject]
        LOCATED_MINOR_FIXTURE_TYPE_OBJECT_GENERIC: _ClassVar[LocatedTrait.LocatedMinorFixtureTypeObject]
    LOCATED_MINOR_FIXTURE_TYPE_OBJECT_UNSPECIFIED: LocatedTrait.LocatedMinorFixtureTypeObject
    LOCATED_MINOR_FIXTURE_TYPE_OBJECT_GENERIC: LocatedTrait.LocatedMinorFixtureTypeObject
    class LocatedFixtureType(_message.Message):
        __slots__ = ("majorType", "minorTypeDoor", "minorTypeWindow", "minorTypeWall", "minorTypeObject")
        MAJORTYPE_FIELD_NUMBER: _ClassVar[int]
        MINORTYPEDOOR_FIELD_NUMBER: _ClassVar[int]
        MINORTYPEWINDOW_FIELD_NUMBER: _ClassVar[int]
        MINORTYPEWALL_FIELD_NUMBER: _ClassVar[int]
        MINORTYPEOBJECT_FIELD_NUMBER: _ClassVar[int]
        majorType: LocatedTrait.LocatedMajorFixtureType
        minorTypeDoor: LocatedTrait.LocatedMinorFixtureTypeDoor
        minorTypeWindow: LocatedTrait.LocatedMinorFixtureTypeWindow
        minorTypeWall: LocatedTrait.LocatedMinorFixtureTypeWall
        minorTypeObject: LocatedTrait.LocatedMinorFixtureTypeObject
        def __init__(self, majorType: _Optional[_Union[LocatedTrait.LocatedMajorFixtureType, str]] = ..., minorTypeDoor: _Optional[_Union[LocatedTrait.LocatedMinorFixtureTypeDoor, str]] = ..., minorTypeWindow: _Optional[_Union[LocatedTrait.LocatedMinorFixtureTypeWindow, str]] = ..., minorTypeWall: _Optional[_Union[LocatedTrait.LocatedMinorFixtureTypeWall, str]] = ..., minorTypeObject: _Optional[_Union[LocatedTrait.LocatedMinorFixtureTypeObject, str]] = ...) -> None: ...
    def __init__(self) -> None: ...

class LocatedAnnotationsTrait(_message.Message):
    __slots__ = ("predefinedWheres", "customWheres", "deprecatedPredefinedWheresToInclude")
    class StatusCode(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        STATUS_CODE_UNSPECIFIED: _ClassVar[LocatedAnnotationsTrait.StatusCode]
        STATUS_CODE_SUCCESS: _ClassVar[LocatedAnnotationsTrait.StatusCode]
        STATUS_CODE_FAILURE: _ClassVar[LocatedAnnotationsTrait.StatusCode]
        STATUS_CODE_MISSING_LABEL: _ClassVar[LocatedAnnotationsTrait.StatusCode]
        STATUS_CODE_ANNOTATION_EXISTS: _ClassVar[LocatedAnnotationsTrait.StatusCode]
        STATUS_CODE_MISSING_ANNOTATION: _ClassVar[LocatedAnnotationsTrait.StatusCode]
        STATUS_CODE_ANNOTATION_DOESNT_EXIST: _ClassVar[LocatedAnnotationsTrait.StatusCode]
    STATUS_CODE_UNSPECIFIED: LocatedAnnotationsTrait.StatusCode
    STATUS_CODE_SUCCESS: LocatedAnnotationsTrait.StatusCode
    STATUS_CODE_FAILURE: LocatedAnnotationsTrait.StatusCode
    STATUS_CODE_MISSING_LABEL: LocatedAnnotationsTrait.StatusCode
    STATUS_CODE_ANNOTATION_EXISTS: LocatedAnnotationsTrait.StatusCode
    STATUS_CODE_MISSING_ANNOTATION: LocatedAnnotationsTrait.StatusCode
    STATUS_CODE_ANNOTATION_DOESNT_EXIST: LocatedAnnotationsTrait.StatusCode
    class PredefinedWheresEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: int
        value: LocatedAnnotationsTrait.WhereItem
        def __init__(self, key: _Optional[int] = ..., value: _Optional[_Union[LocatedAnnotationsTrait.WhereItem, _Mapping]] = ...) -> None: ...
    class CustomWheresEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: int
        value: LocatedAnnotationsTrait.WhereItem
        def __init__(self, key: _Optional[int] = ..., value: _Optional[_Union[LocatedAnnotationsTrait.WhereItem, _Mapping]] = ...) -> None: ...
    class DeprecatedPredefinedWheresToIncludeEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: int
        value: _common_pb2.ResourceId
        def __init__(self, key: _Optional[int] = ..., value: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ...) -> None: ...
    class WhereItem(_message.Message):
        __slots__ = ("whereId", "label", "legacyUuid")
        WHEREID_FIELD_NUMBER: _ClassVar[int]
        LABEL_FIELD_NUMBER: _ClassVar[int]
        LEGACYUUID_FIELD_NUMBER: _ClassVar[int]
        whereId: _common_pb2.ResourceId
        label: _common_pb2.StringRef
        legacyUuid: str
        def __init__(self, whereId: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ..., label: _Optional[_Union[_common_pb2.StringRef, _Mapping]] = ..., legacyUuid: _Optional[str] = ...) -> None: ...
    class CustomWhereCreationRequest(_message.Message):
        __slots__ = ("label",)
        LABEL_FIELD_NUMBER: _ClassVar[int]
        label: str
        def __init__(self, label: _Optional[str] = ...) -> None: ...
    class CustomWhereCreationResponse(_message.Message):
        __slots__ = ("status", "whereItem")
        STATUS_FIELD_NUMBER: _ClassVar[int]
        WHEREITEM_FIELD_NUMBER: _ClassVar[int]
        status: LocatedAnnotationsTrait.StatusCode
        whereItem: LocatedAnnotationsTrait.WhereItem
        def __init__(self, status: _Optional[_Union[LocatedAnnotationsTrait.StatusCode, str]] = ..., whereItem: _Optional[_Union[LocatedAnnotationsTrait.WhereItem, _Mapping]] = ...) -> None: ...
    class CustomWhereDeletionRequest(_message.Message):
        __slots__ = ("whereId",)
        WHEREID_FIELD_NUMBER: _ClassVar[int]
        whereId: _common_pb2.ResourceId
        def __init__(self, whereId: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ...) -> None: ...
    class CustomWhereDeletionResponse(_message.Message):
        __slots__ = ("status",)
        STATUS_FIELD_NUMBER: _ClassVar[int]
        status: LocatedAnnotationsTrait.StatusCode
        def __init__(self, status: _Optional[_Union[LocatedAnnotationsTrait.StatusCode, str]] = ...) -> None: ...
    class GetWhereItemRequest(_message.Message):
        __slots__ = ("whereId",)
        WHEREID_FIELD_NUMBER: _ClassVar[int]
        whereId: _common_pb2.ResourceId
        def __init__(self, whereId: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ...) -> None: ...
    class GetWhereItemResponse(_message.Message):
        __slots__ = ("whereItem",)
        WHEREITEM_FIELD_NUMBER: _ClassVar[int]
        whereItem: LocatedAnnotationsTrait.WhereItem
        def __init__(self, whereItem: _Optional[_Union[LocatedAnnotationsTrait.WhereItem, _Mapping]] = ...) -> None: ...
    PREDEFINEDWHERES_FIELD_NUMBER: _ClassVar[int]
    CUSTOMWHERES_FIELD_NUMBER: _ClassVar[int]
    DEPRECATEDPREDEFINEDWHERESTOINCLUDE_FIELD_NUMBER: _ClassVar[int]
    predefinedWheres: _containers.MessageMap[int, LocatedAnnotationsTrait.WhereItem]
    customWheres: _containers.MessageMap[int, LocatedAnnotationsTrait.WhereItem]
    deprecatedPredefinedWheresToInclude: _containers.MessageMap[int, _common_pb2.ResourceId]
    def __init__(self, predefinedWheres: _Optional[_Mapping[int, LocatedAnnotationsTrait.WhereItem]] = ..., customWheres: _Optional[_Mapping[int, LocatedAnnotationsTrait.WhereItem]] = ..., deprecatedPredefinedWheresToInclude: _Optional[_Mapping[int, _common_pb2.ResourceId]] = ...) -> None: ...

class DeviceLocatedSettingsTrait(_message.Message):
    __slots__ = ("whereAnnotationRid", "fixtureAnnotationRid", "fixtureType", "whereLabel", "whereSpokenAnnotationRids", "fixtureNameLabel", "fixtureSpokenAnnotationRids", "lastModifiedTimestamp", "lastKnownRelocationTimestamp", "whereLegacyUuid")
    class StatusCode(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        STATUS_CODE_UNSPECIFIED: _ClassVar[DeviceLocatedSettingsTrait.StatusCode]
        STATUS_CODE_SUCCESS: _ClassVar[DeviceLocatedSettingsTrait.StatusCode]
        STATUS_CODE_INTERNAL: _ClassVar[DeviceLocatedSettingsTrait.StatusCode]
        STATUS_CODE_UNAUTHORIZED: _ClassVar[DeviceLocatedSettingsTrait.StatusCode]
        STATUS_CODE_RESOURCE_NOT_FOUND: _ClassVar[DeviceLocatedSettingsTrait.StatusCode]
    STATUS_CODE_UNSPECIFIED: DeviceLocatedSettingsTrait.StatusCode
    STATUS_CODE_SUCCESS: DeviceLocatedSettingsTrait.StatusCode
    STATUS_CODE_INTERNAL: DeviceLocatedSettingsTrait.StatusCode
    STATUS_CODE_UNAUTHORIZED: DeviceLocatedSettingsTrait.StatusCode
    STATUS_CODE_RESOURCE_NOT_FOUND: DeviceLocatedSettingsTrait.StatusCode
    class SetWhereRequest(_message.Message):
        __slots__ = ("whereLabel", "locale")
        WHERELABEL_FIELD_NUMBER: _ClassVar[int]
        LOCALE_FIELD_NUMBER: _ClassVar[int]
        whereLabel: str
        locale: str
        def __init__(self, whereLabel: _Optional[str] = ..., locale: _Optional[str] = ...) -> None: ...
    class SetWhereResponse(_message.Message):
        __slots__ = ("whereAnnotationRid",)
        WHEREANNOTATIONRID_FIELD_NUMBER: _ClassVar[int]
        whereAnnotationRid: _common_pb2.ResourceId
        def __init__(self, whereAnnotationRid: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ...) -> None: ...
    class SyncRoomAssignmentRequest(_message.Message):
        __slots__ = ("resourceId", "roomName")
        RESOURCEID_FIELD_NUMBER: _ClassVar[int]
        ROOMNAME_FIELD_NUMBER: _ClassVar[int]
        resourceId: _common_pb2.ResourceId
        roomName: str
        def __init__(self, resourceId: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ..., roomName: _Optional[str] = ...) -> None: ...
    class SyncRoomAssignmentResponse(_message.Message):
        __slots__ = ("status", "resourceId")
        STATUS_FIELD_NUMBER: _ClassVar[int]
        RESOURCEID_FIELD_NUMBER: _ClassVar[int]
        status: DeviceLocatedSettingsTrait.StatusCode
        resourceId: _common_pb2.ResourceId
        def __init__(self, status: _Optional[_Union[DeviceLocatedSettingsTrait.StatusCode, str]] = ..., resourceId: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ...) -> None: ...
    WHEREANNOTATIONRID_FIELD_NUMBER: _ClassVar[int]
    FIXTUREANNOTATIONRID_FIELD_NUMBER: _ClassVar[int]
    FIXTURETYPE_FIELD_NUMBER: _ClassVar[int]
    WHERELABEL_FIELD_NUMBER: _ClassVar[int]
    WHERESPOKENANNOTATIONRIDS_FIELD_NUMBER: _ClassVar[int]
    FIXTURENAMELABEL_FIELD_NUMBER: _ClassVar[int]
    FIXTURESPOKENANNOTATIONRIDS_FIELD_NUMBER: _ClassVar[int]
    LASTMODIFIEDTIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    LASTKNOWNRELOCATIONTIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    WHERELEGACYUUID_FIELD_NUMBER: _ClassVar[int]
    whereAnnotationRid: _common_pb2.ResourceId
    fixtureAnnotationRid: _common_pb2.ResourceId
    fixtureType: LocatedTrait.LocatedFixtureType
    whereLabel: _common_pb2.StringRef
    whereSpokenAnnotationRids: _containers.RepeatedCompositeFieldContainer[_common_pb2.ResourceId]
    fixtureNameLabel: _common_pb2.StringRef
    fixtureSpokenAnnotationRids: _containers.RepeatedCompositeFieldContainer[_common_pb2.ResourceId]
    lastModifiedTimestamp: _timestamp_pb2.Timestamp
    lastKnownRelocationTimestamp: _timestamp_pb2.Timestamp
    whereLegacyUuid: str
    def __init__(self, whereAnnotationRid: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ..., fixtureAnnotationRid: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ..., fixtureType: _Optional[_Union[LocatedTrait.LocatedFixtureType, _Mapping]] = ..., whereLabel: _Optional[_Union[_common_pb2.StringRef, _Mapping]] = ..., whereSpokenAnnotationRids: _Optional[_Iterable[_Union[_common_pb2.ResourceId, _Mapping]]] = ..., fixtureNameLabel: _Optional[_Union[_common_pb2.StringRef, _Mapping]] = ..., fixtureSpokenAnnotationRids: _Optional[_Iterable[_Union[_common_pb2.ResourceId, _Mapping]]] = ..., lastModifiedTimestamp: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., lastKnownRelocationTimestamp: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., whereLegacyUuid: _Optional[str] = ...) -> None: ...

class GeoCommon(_message.Message):
    __slots__ = ()
    class GeoCoordinateStruct(_message.Message):
        __slots__ = ("latitude", "longitude")
        LATITUDE_FIELD_NUMBER: _ClassVar[int]
        LONGITUDE_FIELD_NUMBER: _ClassVar[int]
        latitude: float
        longitude: float
        def __init__(self, latitude: _Optional[float] = ..., longitude: _Optional[float] = ...) -> None: ...
    class PostalAddress(_message.Message):
        __slots__ = ("postalCode", "regionCode", "addressLines", "locality", "administrativeArea")
        POSTALCODE_FIELD_NUMBER: _ClassVar[int]
        REGIONCODE_FIELD_NUMBER: _ClassVar[int]
        ADDRESSLINES_FIELD_NUMBER: _ClassVar[int]
        LOCALITY_FIELD_NUMBER: _ClassVar[int]
        ADMINISTRATIVEAREA_FIELD_NUMBER: _ClassVar[int]
        postalCode: _wrappers_pb2.StringValue
        regionCode: str
        addressLines: _containers.RepeatedScalarFieldContainer[str]
        locality: _wrappers_pb2.StringValue
        administrativeArea: _wrappers_pb2.StringValue
        def __init__(self, postalCode: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., regionCode: _Optional[str] = ..., addressLines: _Optional[_Iterable[str]] = ..., locality: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., administrativeArea: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ...) -> None: ...
    def __init__(self) -> None: ...

class DeviceLocatedCapabilitiesTrait(_message.Message):
    __slots__ = ("validWhereAnnotationRids", "validWhereSpokenAnnotationRids", "validFixtureAnnotationRids", "validFixtureSpokenAnnotationRids", "validFixtureTypes")
    VALIDWHEREANNOTATIONRIDS_FIELD_NUMBER: _ClassVar[int]
    VALIDWHERESPOKENANNOTATIONRIDS_FIELD_NUMBER: _ClassVar[int]
    VALIDFIXTUREANNOTATIONRIDS_FIELD_NUMBER: _ClassVar[int]
    VALIDFIXTURESPOKENANNOTATIONRIDS_FIELD_NUMBER: _ClassVar[int]
    VALIDFIXTURETYPES_FIELD_NUMBER: _ClassVar[int]
    validWhereAnnotationRids: _containers.RepeatedCompositeFieldContainer[_common_pb2.ResourceId]
    validWhereSpokenAnnotationRids: _containers.RepeatedCompositeFieldContainer[_common_pb2.ResourceId]
    validFixtureAnnotationRids: _containers.RepeatedCompositeFieldContainer[_common_pb2.ResourceId]
    validFixtureSpokenAnnotationRids: _containers.RepeatedCompositeFieldContainer[_common_pb2.ResourceId]
    validFixtureTypes: _containers.RepeatedCompositeFieldContainer[LocatedTrait.LocatedFixtureType]
    def __init__(self, validWhereAnnotationRids: _Optional[_Iterable[_Union[_common_pb2.ResourceId, _Mapping]]] = ..., validWhereSpokenAnnotationRids: _Optional[_Iterable[_Union[_common_pb2.ResourceId, _Mapping]]] = ..., validFixtureAnnotationRids: _Optional[_Iterable[_Union[_common_pb2.ResourceId, _Mapping]]] = ..., validFixtureSpokenAnnotationRids: _Optional[_Iterable[_Union[_common_pb2.ResourceId, _Mapping]]] = ..., validFixtureTypes: _Optional[_Iterable[_Union[LocatedTrait.LocatedFixtureType, _Mapping]]] = ...) -> None: ...
