import datetime

from google.protobuf import duration_pb2 as _duration_pb2
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class DoorbellIndoorChimeSettingsTrait(_message.Message):
    __slots__ = ("chimeType", "chimeDuration", "chimeEnabled")
    class ChimeType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        CHIME_TYPE_UNSPECIFIED: _ClassVar[DoorbellIndoorChimeSettingsTrait.ChimeType]
        CHIME_TYPE_MECHANICAL: _ClassVar[DoorbellIndoorChimeSettingsTrait.ChimeType]
        CHIME_TYPE_ELECTRONIC: _ClassVar[DoorbellIndoorChimeSettingsTrait.ChimeType]
    CHIME_TYPE_UNSPECIFIED: DoorbellIndoorChimeSettingsTrait.ChimeType
    CHIME_TYPE_MECHANICAL: DoorbellIndoorChimeSettingsTrait.ChimeType
    CHIME_TYPE_ELECTRONIC: DoorbellIndoorChimeSettingsTrait.ChimeType
    CHIMETYPE_FIELD_NUMBER: _ClassVar[int]
    CHIMEDURATION_FIELD_NUMBER: _ClassVar[int]
    CHIMEENABLED_FIELD_NUMBER: _ClassVar[int]
    chimeType: DoorbellIndoorChimeSettingsTrait.ChimeType
    chimeDuration: _duration_pb2.Duration
    chimeEnabled: bool
    def __init__(self, chimeType: _Optional[_Union[DoorbellIndoorChimeSettingsTrait.ChimeType, str]] = ..., chimeDuration: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ..., chimeEnabled: bool = ...) -> None: ...
