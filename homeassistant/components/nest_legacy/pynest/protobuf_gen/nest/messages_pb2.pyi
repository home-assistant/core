from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Optional as _Optional

DESCRIPTOR: _descriptor.FileDescriptor

class SchemaVersion(_message.Message):
    __slots__ = ("currentVersion", "minCompatVersion")
    CURRENTVERSION_FIELD_NUMBER: _ClassVar[int]
    MINCOMPATVERSION_FIELD_NUMBER: _ClassVar[int]
    currentVersion: int
    minCompatVersion: int
    def __init__(self, currentVersion: _Optional[int] = ..., minCompatVersion: _Optional[int] = ...) -> None: ...
