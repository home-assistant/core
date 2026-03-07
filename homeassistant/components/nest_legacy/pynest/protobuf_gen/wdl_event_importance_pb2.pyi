from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from typing import ClassVar as _ClassVar

DESCRIPTOR: _descriptor.FileDescriptor

class EventImportance(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    EVENT_IMPORTANCE_UNSPECIFIED: _ClassVar[EventImportance]
    EVENT_IMPORTANCE_PRODUCTION_CRITICAL: _ClassVar[EventImportance]
    EVENT_IMPORTANCE_PRODUCTION_STANDARD: _ClassVar[EventImportance]
    EVENT_IMPORTANCE_INFO: _ClassVar[EventImportance]
    EVENT_IMPORTANCE_DEBUG: _ClassVar[EventImportance]
EVENT_IMPORTANCE_UNSPECIFIED: EventImportance
EVENT_IMPORTANCE_PRODUCTION_CRITICAL: EventImportance
EVENT_IMPORTANCE_PRODUCTION_STANDARD: EventImportance
EVENT_IMPORTANCE_INFO: EventImportance
EVENT_IMPORTANCE_DEBUG: EventImportance
