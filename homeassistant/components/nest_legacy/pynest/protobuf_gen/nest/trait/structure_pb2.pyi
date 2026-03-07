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

class HomeInfoSettingsTrait(_message.Message):
    __slots__ = ("houseType", "userSpecifiedNumThermostats", "renovationDate", "structureArea", "measurementScale")
    class HouseType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        HOUSE_TYPE_UNSPECIFIED: _ClassVar[HomeInfoSettingsTrait.HouseType]
        HOUSE_TYPE_SINGLE_FAMILY: _ClassVar[HomeInfoSettingsTrait.HouseType]
        HOUSE_TYPE_MULTI_FAMILY: _ClassVar[HomeInfoSettingsTrait.HouseType]
        HOUSE_TYPE_CONDO: _ClassVar[HomeInfoSettingsTrait.HouseType]
        HOUSE_TYPE_BUSINESS: _ClassVar[HomeInfoSettingsTrait.HouseType]
        HOUSE_TYPE_UNKNOWN: _ClassVar[HomeInfoSettingsTrait.HouseType]
    HOUSE_TYPE_UNSPECIFIED: HomeInfoSettingsTrait.HouseType
    HOUSE_TYPE_SINGLE_FAMILY: HomeInfoSettingsTrait.HouseType
    HOUSE_TYPE_MULTI_FAMILY: HomeInfoSettingsTrait.HouseType
    HOUSE_TYPE_CONDO: HomeInfoSettingsTrait.HouseType
    HOUSE_TYPE_BUSINESS: HomeInfoSettingsTrait.HouseType
    HOUSE_TYPE_UNKNOWN: HomeInfoSettingsTrait.HouseType
    class NumThermostats(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        NUM_THERMOSTATS_UNSPECIFIED: _ClassVar[HomeInfoSettingsTrait.NumThermostats]
        NUM_THERMOSTATS_ONE: _ClassVar[HomeInfoSettingsTrait.NumThermostats]
        NUM_THERMOSTATS_TWO: _ClassVar[HomeInfoSettingsTrait.NumThermostats]
        NUM_THERMOSTATS_THREE: _ClassVar[HomeInfoSettingsTrait.NumThermostats]
        NUM_THERMOSTATS_FOUR: _ClassVar[HomeInfoSettingsTrait.NumThermostats]
        NUM_THERMOSTATS_FIVE_PLUS: _ClassVar[HomeInfoSettingsTrait.NumThermostats]
        NUM_THERMOSTATS_UNKNOWN: _ClassVar[HomeInfoSettingsTrait.NumThermostats]
    NUM_THERMOSTATS_UNSPECIFIED: HomeInfoSettingsTrait.NumThermostats
    NUM_THERMOSTATS_ONE: HomeInfoSettingsTrait.NumThermostats
    NUM_THERMOSTATS_TWO: HomeInfoSettingsTrait.NumThermostats
    NUM_THERMOSTATS_THREE: HomeInfoSettingsTrait.NumThermostats
    NUM_THERMOSTATS_FOUR: HomeInfoSettingsTrait.NumThermostats
    NUM_THERMOSTATS_FIVE_PLUS: HomeInfoSettingsTrait.NumThermostats
    NUM_THERMOSTATS_UNKNOWN: HomeInfoSettingsTrait.NumThermostats
    class RenovationDate(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        RENOVATION_DATE_UNSPECIFIED: _ClassVar[HomeInfoSettingsTrait.RenovationDate]
        RENOVATION_DATE_DONT_KNOW: _ClassVar[HomeInfoSettingsTrait.RenovationDate]
        RENOVATION_DATE_PRE_1940: _ClassVar[HomeInfoSettingsTrait.RenovationDate]
        RENOVATION_DATE_1940: _ClassVar[HomeInfoSettingsTrait.RenovationDate]
        RENOVATION_DATE_1950: _ClassVar[HomeInfoSettingsTrait.RenovationDate]
        RENOVATION_DATE_1960: _ClassVar[HomeInfoSettingsTrait.RenovationDate]
        RENOVATION_DATE_1970: _ClassVar[HomeInfoSettingsTrait.RenovationDate]
        RENOVATION_DATE_1980: _ClassVar[HomeInfoSettingsTrait.RenovationDate]
        RENOVATION_DATE_1990: _ClassVar[HomeInfoSettingsTrait.RenovationDate]
        RENOVATION_DATE_2000: _ClassVar[HomeInfoSettingsTrait.RenovationDate]
        RENOVATION_DATE_2010: _ClassVar[HomeInfoSettingsTrait.RenovationDate]
        RENOVATION_DATE_UNKNOWN: _ClassVar[HomeInfoSettingsTrait.RenovationDate]
    RENOVATION_DATE_UNSPECIFIED: HomeInfoSettingsTrait.RenovationDate
    RENOVATION_DATE_DONT_KNOW: HomeInfoSettingsTrait.RenovationDate
    RENOVATION_DATE_PRE_1940: HomeInfoSettingsTrait.RenovationDate
    RENOVATION_DATE_1940: HomeInfoSettingsTrait.RenovationDate
    RENOVATION_DATE_1950: HomeInfoSettingsTrait.RenovationDate
    RENOVATION_DATE_1960: HomeInfoSettingsTrait.RenovationDate
    RENOVATION_DATE_1970: HomeInfoSettingsTrait.RenovationDate
    RENOVATION_DATE_1980: HomeInfoSettingsTrait.RenovationDate
    RENOVATION_DATE_1990: HomeInfoSettingsTrait.RenovationDate
    RENOVATION_DATE_2000: HomeInfoSettingsTrait.RenovationDate
    RENOVATION_DATE_2010: HomeInfoSettingsTrait.RenovationDate
    RENOVATION_DATE_UNKNOWN: HomeInfoSettingsTrait.RenovationDate
    class MeasurementScale(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        MEASUREMENT_SCALE_UNSPECIFIED: _ClassVar[HomeInfoSettingsTrait.MeasurementScale]
        MEASUREMENT_SCALE_METRIC: _ClassVar[HomeInfoSettingsTrait.MeasurementScale]
        MEASUREMENT_SCALE_IMPERIAL: _ClassVar[HomeInfoSettingsTrait.MeasurementScale]
    MEASUREMENT_SCALE_UNSPECIFIED: HomeInfoSettingsTrait.MeasurementScale
    MEASUREMENT_SCALE_METRIC: HomeInfoSettingsTrait.MeasurementScale
    MEASUREMENT_SCALE_IMPERIAL: HomeInfoSettingsTrait.MeasurementScale
    HOUSETYPE_FIELD_NUMBER: _ClassVar[int]
    USERSPECIFIEDNUMTHERMOSTATS_FIELD_NUMBER: _ClassVar[int]
    RENOVATIONDATE_FIELD_NUMBER: _ClassVar[int]
    STRUCTUREAREA_FIELD_NUMBER: _ClassVar[int]
    MEASUREMENTSCALE_FIELD_NUMBER: _ClassVar[int]
    houseType: HomeInfoSettingsTrait.HouseType
    userSpecifiedNumThermostats: HomeInfoSettingsTrait.NumThermostats
    renovationDate: HomeInfoSettingsTrait.RenovationDate
    structureArea: float
    measurementScale: HomeInfoSettingsTrait.MeasurementScale
    def __init__(self, houseType: _Optional[_Union[HomeInfoSettingsTrait.HouseType, str]] = ..., userSpecifiedNumThermostats: _Optional[_Union[HomeInfoSettingsTrait.NumThermostats, str]] = ..., renovationDate: _Optional[_Union[HomeInfoSettingsTrait.RenovationDate, str]] = ..., structureArea: _Optional[float] = ..., measurementScale: _Optional[_Union[HomeInfoSettingsTrait.MeasurementScale, str]] = ...) -> None: ...

class StructureInfoTrait(_message.Message):
    __slots__ = ("rtsStructureId", "maxNestGuardCount", "maxNestSensorCount", "maxNestConnectCount", "primaryFabricId", "pairerId", "maxNestLockCount", "maxNestMoonstoneCount", "maxNestProtectCount", "name", "createdAt", "hgId", "maxResourceCounts")
    class StatusCode(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        STATUS_CODE_UNSPECIFIED: _ClassVar[StructureInfoTrait.StatusCode]
        STATUS_CODE_SUCCESS: _ClassVar[StructureInfoTrait.StatusCode]
        STATUS_CODE_FAILURE: _ClassVar[StructureInfoTrait.StatusCode]
        STATUS_CODE_UNAUTHORIZED: _ClassVar[StructureInfoTrait.StatusCode]
        STATUS_CODE_RESOURCE_NOT_FOUND: _ClassVar[StructureInfoTrait.StatusCode]
    STATUS_CODE_UNSPECIFIED: StructureInfoTrait.StatusCode
    STATUS_CODE_SUCCESS: StructureInfoTrait.StatusCode
    STATUS_CODE_FAILURE: StructureInfoTrait.StatusCode
    STATUS_CODE_UNAUTHORIZED: StructureInfoTrait.StatusCode
    STATUS_CODE_RESOURCE_NOT_FOUND: StructureInfoTrait.StatusCode
    class MaxResourceCountsEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: int
        def __init__(self, key: _Optional[str] = ..., value: _Optional[int] = ...) -> None: ...
    class StructureDeletionEvent(_message.Message):
        __slots__ = ("structureId",)
        STRUCTUREID_FIELD_NUMBER: _ClassVar[int]
        structureId: _common_pb2.ResourceId
        def __init__(self, structureId: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ...) -> None: ...
    class SyncStructureMetadataRequest(_message.Message):
        __slots__ = ("resourceId", "name")
        RESOURCEID_FIELD_NUMBER: _ClassVar[int]
        NAME_FIELD_NUMBER: _ClassVar[int]
        resourceId: _common_pb2.ResourceId
        name: str
        def __init__(self, resourceId: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ..., name: _Optional[str] = ...) -> None: ...
    class SyncStructureMetadataResponse(_message.Message):
        __slots__ = ("status", "resourceId")
        STATUS_FIELD_NUMBER: _ClassVar[int]
        RESOURCEID_FIELD_NUMBER: _ClassVar[int]
        status: StructureInfoTrait.StatusCode
        resourceId: _common_pb2.ResourceId
        def __init__(self, status: _Optional[_Union[StructureInfoTrait.StatusCode, str]] = ..., resourceId: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ...) -> None: ...
    RTSSTRUCTUREID_FIELD_NUMBER: _ClassVar[int]
    MAXNESTGUARDCOUNT_FIELD_NUMBER: _ClassVar[int]
    MAXNESTSENSORCOUNT_FIELD_NUMBER: _ClassVar[int]
    MAXNESTCONNECTCOUNT_FIELD_NUMBER: _ClassVar[int]
    PRIMARYFABRICID_FIELD_NUMBER: _ClassVar[int]
    PAIRERID_FIELD_NUMBER: _ClassVar[int]
    MAXNESTLOCKCOUNT_FIELD_NUMBER: _ClassVar[int]
    MAXNESTMOONSTONECOUNT_FIELD_NUMBER: _ClassVar[int]
    MAXNESTPROTECTCOUNT_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    CREATEDAT_FIELD_NUMBER: _ClassVar[int]
    HGID_FIELD_NUMBER: _ClassVar[int]
    MAXRESOURCECOUNTS_FIELD_NUMBER: _ClassVar[int]
    rtsStructureId: str
    maxNestGuardCount: int
    maxNestSensorCount: int
    maxNestConnectCount: int
    primaryFabricId: int
    pairerId: _common_pb2.ResourceId
    maxNestLockCount: int
    maxNestMoonstoneCount: int
    maxNestProtectCount: int
    name: str
    createdAt: _timestamp_pb2.Timestamp
    hgId: _wrappers_pb2.StringValue
    maxResourceCounts: _containers.ScalarMap[str, int]
    def __init__(self, rtsStructureId: _Optional[str] = ..., maxNestGuardCount: _Optional[int] = ..., maxNestSensorCount: _Optional[int] = ..., maxNestConnectCount: _Optional[int] = ..., primaryFabricId: _Optional[int] = ..., pairerId: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ..., maxNestLockCount: _Optional[int] = ..., maxNestMoonstoneCount: _Optional[int] = ..., maxNestProtectCount: _Optional[int] = ..., name: _Optional[str] = ..., createdAt: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., hgId: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., maxResourceCounts: _Optional[_Mapping[str, int]] = ...) -> None: ...

class StructureLocationTrait(_message.Message):
    __slots__ = ("postalCode", "countryCode", "addressLines", "city", "state", "geoCoordinate")
    class StatusCode(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        STATUS_CODE_UNSPECIFIED: _ClassVar[StructureLocationTrait.StatusCode]
        STATUS_CODE_SUCCESS: _ClassVar[StructureLocationTrait.StatusCode]
        STATUS_CODE_FAILURE: _ClassVar[StructureLocationTrait.StatusCode]
        STATUS_CODE_UNAUTHORIZED: _ClassVar[StructureLocationTrait.StatusCode]
        STATUS_CODE_RESOURCE_NOT_FOUND: _ClassVar[StructureLocationTrait.StatusCode]
    STATUS_CODE_UNSPECIFIED: StructureLocationTrait.StatusCode
    STATUS_CODE_SUCCESS: StructureLocationTrait.StatusCode
    STATUS_CODE_FAILURE: StructureLocationTrait.StatusCode
    STATUS_CODE_UNAUTHORIZED: StructureLocationTrait.StatusCode
    STATUS_CODE_RESOURCE_NOT_FOUND: StructureLocationTrait.StatusCode
    class GeoCoordinate(_message.Message):
        __slots__ = ("latitude", "longitude")
        LATITUDE_FIELD_NUMBER: _ClassVar[int]
        LONGITUDE_FIELD_NUMBER: _ClassVar[int]
        latitude: float
        longitude: float
        def __init__(self, latitude: _Optional[float] = ..., longitude: _Optional[float] = ...) -> None: ...
    class UpdateAddressRequest(_message.Message):
        __slots__ = ("resourceId", "postalCode", "countryCode", "addressLines", "city", "state", "geoCoordinate", "timezoneName")
        RESOURCEID_FIELD_NUMBER: _ClassVar[int]
        POSTALCODE_FIELD_NUMBER: _ClassVar[int]
        COUNTRYCODE_FIELD_NUMBER: _ClassVar[int]
        ADDRESSLINES_FIELD_NUMBER: _ClassVar[int]
        CITY_FIELD_NUMBER: _ClassVar[int]
        STATE_FIELD_NUMBER: _ClassVar[int]
        GEOCOORDINATE_FIELD_NUMBER: _ClassVar[int]
        TIMEZONENAME_FIELD_NUMBER: _ClassVar[int]
        resourceId: _common_pb2.ResourceId
        postalCode: _wrappers_pb2.StringValue
        countryCode: _wrappers_pb2.StringValue
        addressLines: _containers.RepeatedScalarFieldContainer[str]
        city: _wrappers_pb2.StringValue
        state: _wrappers_pb2.StringValue
        geoCoordinate: StructureLocationTrait.GeoCoordinate
        timezoneName: _wrappers_pb2.StringValue
        def __init__(self, resourceId: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ..., postalCode: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., countryCode: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., addressLines: _Optional[_Iterable[str]] = ..., city: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., state: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., geoCoordinate: _Optional[_Union[StructureLocationTrait.GeoCoordinate, _Mapping]] = ..., timezoneName: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ...) -> None: ...
    class UpdateAddressResponse(_message.Message):
        __slots__ = ("status", "resourceId")
        STATUS_FIELD_NUMBER: _ClassVar[int]
        RESOURCEID_FIELD_NUMBER: _ClassVar[int]
        status: StructureLocationTrait.StatusCode
        resourceId: _common_pb2.ResourceId
        def __init__(self, status: _Optional[_Union[StructureLocationTrait.StatusCode, str]] = ..., resourceId: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ...) -> None: ...
    POSTALCODE_FIELD_NUMBER: _ClassVar[int]
    COUNTRYCODE_FIELD_NUMBER: _ClassVar[int]
    ADDRESSLINES_FIELD_NUMBER: _ClassVar[int]
    CITY_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    GEOCOORDINATE_FIELD_NUMBER: _ClassVar[int]
    postalCode: _wrappers_pb2.StringValue
    countryCode: _wrappers_pb2.StringValue
    addressLines: _containers.RepeatedScalarFieldContainer[str]
    city: _wrappers_pb2.StringValue
    state: _wrappers_pb2.StringValue
    geoCoordinate: StructureLocationTrait.GeoCoordinate
    def __init__(self, postalCode: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., countryCode: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., addressLines: _Optional[_Iterable[str]] = ..., city: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., state: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., geoCoordinate: _Optional[_Union[StructureLocationTrait.GeoCoordinate, _Mapping]] = ...) -> None: ...
