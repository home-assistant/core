from google.protobuf import wrappers_pb2 as _wrappers_pb2
from ...weave import common_pb2 as _common_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class SoftwareComponentTrait(_message.Message):
    __slots__ = ("softwareComponents",)
    class SoftwareComponentTypeStruct(_message.Message):
        __slots__ = ("componentName", "componentVersion")
        COMPONENTNAME_FIELD_NUMBER: _ClassVar[int]
        COMPONENTVERSION_FIELD_NUMBER: _ClassVar[int]
        componentName: str
        componentVersion: str
        def __init__(self, componentName: _Optional[str] = ..., componentVersion: _Optional[str] = ...) -> None: ...
    SOFTWARECOMPONENTS_FIELD_NUMBER: _ClassVar[int]
    softwareComponents: _containers.RepeatedCompositeFieldContainer[SoftwareComponentTrait.SoftwareComponentTypeStruct]
    def __init__(self, softwareComponents: _Optional[_Iterable[_Union[SoftwareComponentTrait.SoftwareComponentTypeStruct, _Mapping]]] = ...) -> None: ...

class DeviceIdentityTrait(_message.Message):
    __slots__ = ("vendorId", "vendorIdDescription", "vendorProductId", "productIdDescription", "productRevision", "serialNumber", "softwareVersion", "manufacturingDate", "deviceId", "fabricId")
    VENDORID_FIELD_NUMBER: _ClassVar[int]
    VENDORIDDESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    VENDORPRODUCTID_FIELD_NUMBER: _ClassVar[int]
    PRODUCTIDDESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    PRODUCTREVISION_FIELD_NUMBER: _ClassVar[int]
    SERIALNUMBER_FIELD_NUMBER: _ClassVar[int]
    SOFTWAREVERSION_FIELD_NUMBER: _ClassVar[int]
    MANUFACTURINGDATE_FIELD_NUMBER: _ClassVar[int]
    DEVICEID_FIELD_NUMBER: _ClassVar[int]
    FABRICID_FIELD_NUMBER: _ClassVar[int]
    vendorId: int
    vendorIdDescription: _common_pb2.StringRef
    vendorProductId: int
    productIdDescription: _common_pb2.StringRef
    productRevision: int
    serialNumber: str
    softwareVersion: str
    manufacturingDate: _wrappers_pb2.StringValue
    deviceId: _common_pb2.ResourceId
    fabricId: int
    def __init__(self, vendorId: _Optional[int] = ..., vendorIdDescription: _Optional[_Union[_common_pb2.StringRef, _Mapping]] = ..., vendorProductId: _Optional[int] = ..., productIdDescription: _Optional[_Union[_common_pb2.StringRef, _Mapping]] = ..., productRevision: _Optional[int] = ..., serialNumber: _Optional[str] = ..., softwareVersion: _Optional[str] = ..., manufacturingDate: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., deviceId: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ..., fabricId: _Optional[int] = ...) -> None: ...

class LabelSettingsTrait(_message.Message):
    __slots__ = ("label",)
    LABEL_FIELD_NUMBER: _ClassVar[int]
    label: str
    def __init__(self, label: _Optional[str] = ...) -> None: ...
