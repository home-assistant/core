from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Optional as _Optional

DESCRIPTOR: _descriptor.FileDescriptor

class MicrophoneSettingsTrait(_message.Message):
    __slots__ = ("enableMicrophone",)
    ENABLEMICROPHONE_FIELD_NUMBER: _ClassVar[int]
    enableMicrophone: bool
    def __init__(self, enableMicrophone: bool = ...) -> None: ...
