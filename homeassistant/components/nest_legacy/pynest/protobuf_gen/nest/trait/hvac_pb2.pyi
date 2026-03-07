import datetime

from google.protobuf import duration_pb2 as _duration_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf import wrappers_pb2 as _wrappers_pb2
from ...nest.trait import located_pb2 as _located_pb2
from ...nest.trait import ui_pb2 as _ui_pb2
from ...nest.trait import sensor_pb2 as _sensor_pb2
from ...weave import common_pb2 as _common_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class RemoteComfortSensingSettingsTrait(_message.Message):
    __slots__ = ("rcsControlMode", "activeRcsSelection", "rcsControlSchedule", "associatedRcsSensors", "multiSensorSettings", "sensorSelection")
    class RcsControlMode(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        RCS_CONTROL_MODE_UNSPECIFIED: _ClassVar[RemoteComfortSensingSettingsTrait.RcsControlMode]
        RCS_CONTROL_MODE_HOLD: _ClassVar[RemoteComfortSensingSettingsTrait.RcsControlMode]
        RCS_CONTROL_MODE_SCHEDULE: _ClassVar[RemoteComfortSensingSettingsTrait.RcsControlMode]
        RCS_CONTROL_MODE_SCHEDULE_OVERRIDE: _ClassVar[RemoteComfortSensingSettingsTrait.RcsControlMode]
    RCS_CONTROL_MODE_UNSPECIFIED: RemoteComfortSensingSettingsTrait.RcsControlMode
    RCS_CONTROL_MODE_HOLD: RemoteComfortSensingSettingsTrait.RcsControlMode
    RCS_CONTROL_MODE_SCHEDULE: RemoteComfortSensingSettingsTrait.RcsControlMode
    RCS_CONTROL_MODE_SCHEDULE_OVERRIDE: RemoteComfortSensingSettingsTrait.RcsControlMode
    class RcsSourceType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        RCS_SOURCE_TYPE_UNSPECIFIED: _ClassVar[RemoteComfortSensingSettingsTrait.RcsSourceType]
        RCS_SOURCE_TYPE_BACKPLATE: _ClassVar[RemoteComfortSensingSettingsTrait.RcsSourceType]
        RCS_SOURCE_TYPE_SINGLE_SENSOR: _ClassVar[RemoteComfortSensingSettingsTrait.RcsSourceType]
        RCS_SOURCE_TYPE_MULTI_SENSOR: _ClassVar[RemoteComfortSensingSettingsTrait.RcsSourceType]
    RCS_SOURCE_TYPE_UNSPECIFIED: RemoteComfortSensingSettingsTrait.RcsSourceType
    RCS_SOURCE_TYPE_BACKPLATE: RemoteComfortSensingSettingsTrait.RcsSourceType
    RCS_SOURCE_TYPE_SINGLE_SENSOR: RemoteComfortSensingSettingsTrait.RcsSourceType
    RCS_SOURCE_TYPE_MULTI_SENSOR: RemoteComfortSensingSettingsTrait.RcsSourceType
    class StatusCode(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        STATUS_CODE_UNSPECIFIED: _ClassVar[RemoteComfortSensingSettingsTrait.StatusCode]
        STATUS_CODE_SUCCESS: _ClassVar[RemoteComfortSensingSettingsTrait.StatusCode]
        STATUS_CODE_FAILURE: _ClassVar[RemoteComfortSensingSettingsTrait.StatusCode]
        STATUS_CODE_SENSOR_ALREADY_ASSOCIATED: _ClassVar[RemoteComfortSensingSettingsTrait.StatusCode]
        STATUS_CODE_SENSOR_LIMIT_REACHED: _ClassVar[RemoteComfortSensingSettingsTrait.StatusCode]
        STATUS_CODE_SENSOR_NOT_ASSOCIATED: _ClassVar[RemoteComfortSensingSettingsTrait.StatusCode]
    STATUS_CODE_UNSPECIFIED: RemoteComfortSensingSettingsTrait.StatusCode
    STATUS_CODE_SUCCESS: RemoteComfortSensingSettingsTrait.StatusCode
    STATUS_CODE_FAILURE: RemoteComfortSensingSettingsTrait.StatusCode
    STATUS_CODE_SENSOR_ALREADY_ASSOCIATED: RemoteComfortSensingSettingsTrait.StatusCode
    STATUS_CODE_SENSOR_LIMIT_REACHED: RemoteComfortSensingSettingsTrait.StatusCode
    STATUS_CODE_SENSOR_NOT_ASSOCIATED: RemoteComfortSensingSettingsTrait.StatusCode
    class CompatibleSensorStatusCode(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        COMPATIBLE_SENSOR_STATUS_CODE_UNSPECIFIED: _ClassVar[RemoteComfortSensingSettingsTrait.CompatibleSensorStatusCode]
        COMPATIBLE_SENSOR_STATUS_CODE_ASSOCIATED: _ClassVar[RemoteComfortSensingSettingsTrait.CompatibleSensorStatusCode]
        COMPATIBLE_SENSOR_STATUS_CODE_NOT_ASSOCIATED: _ClassVar[RemoteComfortSensingSettingsTrait.CompatibleSensorStatusCode]
    COMPATIBLE_SENSOR_STATUS_CODE_UNSPECIFIED: RemoteComfortSensingSettingsTrait.CompatibleSensorStatusCode
    COMPATIBLE_SENSOR_STATUS_CODE_ASSOCIATED: RemoteComfortSensingSettingsTrait.CompatibleSensorStatusCode
    COMPATIBLE_SENSOR_STATUS_CODE_NOT_ASSOCIATED: RemoteComfortSensingSettingsTrait.CompatibleSensorStatusCode
    class SensorSelectionChangeReason(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        SENSOR_SELECTION_CHANGE_REASON_UNSPECIFIED: _ClassVar[RemoteComfortSensingSettingsTrait.SensorSelectionChangeReason]
        SENSOR_SELECTION_CHANGE_REASON_NONE: _ClassVar[RemoteComfortSensingSettingsTrait.SensorSelectionChangeReason]
        SENSOR_SELECTION_CHANGE_REASON_ADHOC: _ClassVar[RemoteComfortSensingSettingsTrait.SensorSelectionChangeReason]
        SENSOR_SELECTION_CHANGE_REASON_SCHEDULE: _ClassVar[RemoteComfortSensingSettingsTrait.SensorSelectionChangeReason]
        SENSOR_SELECTION_CHANGE_REASON_EARLY_ON: _ClassVar[RemoteComfortSensingSettingsTrait.SensorSelectionChangeReason]
        SENSOR_SELECTION_CHANGE_REASON_FAILSAFE: _ClassVar[RemoteComfortSensingSettingsTrait.SensorSelectionChangeReason]
        SENSOR_SELECTION_CHANGE_REASON_PERIODICAL: _ClassVar[RemoteComfortSensingSettingsTrait.SensorSelectionChangeReason]
    SENSOR_SELECTION_CHANGE_REASON_UNSPECIFIED: RemoteComfortSensingSettingsTrait.SensorSelectionChangeReason
    SENSOR_SELECTION_CHANGE_REASON_NONE: RemoteComfortSensingSettingsTrait.SensorSelectionChangeReason
    SENSOR_SELECTION_CHANGE_REASON_ADHOC: RemoteComfortSensingSettingsTrait.SensorSelectionChangeReason
    SENSOR_SELECTION_CHANGE_REASON_SCHEDULE: RemoteComfortSensingSettingsTrait.SensorSelectionChangeReason
    SENSOR_SELECTION_CHANGE_REASON_EARLY_ON: RemoteComfortSensingSettingsTrait.SensorSelectionChangeReason
    SENSOR_SELECTION_CHANGE_REASON_FAILSAFE: RemoteComfortSensingSettingsTrait.SensorSelectionChangeReason
    SENSOR_SELECTION_CHANGE_REASON_PERIODICAL: RemoteComfortSensingSettingsTrait.SensorSelectionChangeReason
    class RcsSensorId(_message.Message):
        __slots__ = ("deviceId", "vendorId", "productId")
        DEVICEID_FIELD_NUMBER: _ClassVar[int]
        VENDORID_FIELD_NUMBER: _ClassVar[int]
        PRODUCTID_FIELD_NUMBER: _ClassVar[int]
        deviceId: _common_pb2.ResourceId
        vendorId: int
        productId: int
        def __init__(self, deviceId: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ..., vendorId: _Optional[int] = ..., productId: _Optional[int] = ...) -> None: ...
    class MultiSensorSettings(_message.Message):
        __slots__ = ("multiSensorEnabled", "multiSensorGroup")
        MULTISENSORENABLED_FIELD_NUMBER: _ClassVar[int]
        MULTISENSORGROUP_FIELD_NUMBER: _ClassVar[int]
        multiSensorEnabled: bool
        multiSensorGroup: _containers.RepeatedCompositeFieldContainer[_common_pb2.ResourceId]
        def __init__(self, multiSensorEnabled: bool = ..., multiSensorGroup: _Optional[_Iterable[_Union[_common_pb2.ResourceId, _Mapping]]] = ...) -> None: ...
    class RcsSourceSelection(_message.Message):
        __slots__ = ("rcsSourceType", "activeRcsSensor")
        RCSSOURCETYPE_FIELD_NUMBER: _ClassVar[int]
        ACTIVERCSSENSOR_FIELD_NUMBER: _ClassVar[int]
        rcsSourceType: RemoteComfortSensingSettingsTrait.RcsSourceType
        activeRcsSensor: _common_pb2.ResourceId
        def __init__(self, rcsSourceType: _Optional[_Union[RemoteComfortSensingSettingsTrait.RcsSourceType, str]] = ..., activeRcsSensor: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ...) -> None: ...
    class RcsInterval(_message.Message):
        __slots__ = ("rcsSelection", "startSecondsInDay", "endSecondsInDay")
        RCSSELECTION_FIELD_NUMBER: _ClassVar[int]
        STARTSECONDSINDAY_FIELD_NUMBER: _ClassVar[int]
        ENDSECONDSINDAY_FIELD_NUMBER: _ClassVar[int]
        rcsSelection: RemoteComfortSensingSettingsTrait.RcsSourceSelection
        startSecondsInDay: int
        endSecondsInDay: int
        def __init__(self, rcsSelection: _Optional[_Union[RemoteComfortSensingSettingsTrait.RcsSourceSelection, _Mapping]] = ..., startSecondsInDay: _Optional[int] = ..., endSecondsInDay: _Optional[int] = ...) -> None: ...
    class RcsSchedule(_message.Message):
        __slots__ = ("intervals",)
        class IntervalsEntry(_message.Message):
            __slots__ = ("key", "value")
            KEY_FIELD_NUMBER: _ClassVar[int]
            VALUE_FIELD_NUMBER: _ClassVar[int]
            key: int
            value: RemoteComfortSensingSettingsTrait.RcsInterval
            def __init__(self, key: _Optional[int] = ..., value: _Optional[_Union[RemoteComfortSensingSettingsTrait.RcsInterval, _Mapping]] = ...) -> None: ...
        INTERVALS_FIELD_NUMBER: _ClassVar[int]
        intervals: _containers.MessageMap[int, RemoteComfortSensingSettingsTrait.RcsInterval]
        def __init__(self, intervals: _Optional[_Mapping[int, RemoteComfortSensingSettingsTrait.RcsInterval]] = ...) -> None: ...
    class AssociateRcsSensorRequest(_message.Message):
        __slots__ = ("resourceId",)
        RESOURCEID_FIELD_NUMBER: _ClassVar[int]
        resourceId: _common_pb2.ResourceId
        def __init__(self, resourceId: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ...) -> None: ...
    class AssociateRcsSensorResponse(_message.Message):
        __slots__ = ("status",)
        STATUS_FIELD_NUMBER: _ClassVar[int]
        status: RemoteComfortSensingSettingsTrait.StatusCode
        def __init__(self, status: _Optional[_Union[RemoteComfortSensingSettingsTrait.StatusCode, str]] = ...) -> None: ...
    class DissociateRcsSensorRequest(_message.Message):
        __slots__ = ("resourceId",)
        RESOURCEID_FIELD_NUMBER: _ClassVar[int]
        resourceId: _common_pb2.ResourceId
        def __init__(self, resourceId: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ...) -> None: ...
    class DissociateRcsSensorResponse(_message.Message):
        __slots__ = ("status",)
        STATUS_FIELD_NUMBER: _ClassVar[int]
        status: RemoteComfortSensingSettingsTrait.StatusCode
        def __init__(self, status: _Optional[_Union[RemoteComfortSensingSettingsTrait.StatusCode, str]] = ...) -> None: ...
    class TemperatureSensorChangeEvent(_message.Message):
        __slots__ = ("previousSensorIds", "currentSensorIds")
        PREVIOUSSENSORIDS_FIELD_NUMBER: _ClassVar[int]
        CURRENTSENSORIDS_FIELD_NUMBER: _ClassVar[int]
        previousSensorIds: _containers.RepeatedCompositeFieldContainer[_common_pb2.ResourceId]
        currentSensorIds: _containers.RepeatedCompositeFieldContainer[_common_pb2.ResourceId]
        def __init__(self, previousSensorIds: _Optional[_Iterable[_Union[_common_pb2.ResourceId, _Mapping]]] = ..., currentSensorIds: _Optional[_Iterable[_Union[_common_pb2.ResourceId, _Mapping]]] = ...) -> None: ...
    class AssociationEvent(_message.Message):
        __slots__ = ("sensorId",)
        SENSORID_FIELD_NUMBER: _ClassVar[int]
        sensorId: _common_pb2.ResourceId
        def __init__(self, sensorId: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ...) -> None: ...
    class DissociationEvent(_message.Message):
        __slots__ = ("sensorId",)
        SENSORID_FIELD_NUMBER: _ClassVar[int]
        sensorId: _common_pb2.ResourceId
        def __init__(self, sensorId: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ...) -> None: ...
    class CompatibleSensorsRequest(_message.Message):
        __slots__ = ()
        def __init__(self) -> None: ...
    class CompatibleSensorsResponse(_message.Message):
        __slots__ = ("compatibleSensors",)
        COMPATIBLESENSORS_FIELD_NUMBER: _ClassVar[int]
        compatibleSensors: _containers.RepeatedCompositeFieldContainer[RemoteComfortSensingSettingsTrait.SensorCompatibility]
        def __init__(self, compatibleSensors: _Optional[_Iterable[_Union[RemoteComfortSensingSettingsTrait.SensorCompatibility, _Mapping]]] = ...) -> None: ...
    class SensorCompatibility(_message.Message):
        __slots__ = ("resourceId", "status")
        RESOURCEID_FIELD_NUMBER: _ClassVar[int]
        STATUS_FIELD_NUMBER: _ClassVar[int]
        resourceId: _common_pb2.ResourceId
        status: RemoteComfortSensingSettingsTrait.StatusCode
        def __init__(self, resourceId: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ..., status: _Optional[_Union[RemoteComfortSensingSettingsTrait.StatusCode, str]] = ...) -> None: ...
    class SensorSelectionChangeEvent(_message.Message):
        __slots__ = ("sensorSelection", "prevSensorSelection", "changeReason")
        SENSORSELECTION_FIELD_NUMBER: _ClassVar[int]
        PREVSENSORSELECTION_FIELD_NUMBER: _ClassVar[int]
        CHANGEREASON_FIELD_NUMBER: _ClassVar[int]
        sensorSelection: HvacSensor.SensorSelection
        prevSensorSelection: HvacSensor.SensorSelection
        changeReason: RemoteComfortSensingSettingsTrait.SensorSelectionChangeReason
        def __init__(self, sensorSelection: _Optional[_Union[HvacSensor.SensorSelection, _Mapping]] = ..., prevSensorSelection: _Optional[_Union[HvacSensor.SensorSelection, _Mapping]] = ..., changeReason: _Optional[_Union[RemoteComfortSensingSettingsTrait.SensorSelectionChangeReason, str]] = ...) -> None: ...
    RCSCONTROLMODE_FIELD_NUMBER: _ClassVar[int]
    ACTIVERCSSELECTION_FIELD_NUMBER: _ClassVar[int]
    RCSCONTROLSCHEDULE_FIELD_NUMBER: _ClassVar[int]
    ASSOCIATEDRCSSENSORS_FIELD_NUMBER: _ClassVar[int]
    MULTISENSORSETTINGS_FIELD_NUMBER: _ClassVar[int]
    SENSORSELECTION_FIELD_NUMBER: _ClassVar[int]
    rcsControlMode: RemoteComfortSensingSettingsTrait.RcsControlMode
    activeRcsSelection: RemoteComfortSensingSettingsTrait.RcsSourceSelection
    rcsControlSchedule: RemoteComfortSensingSettingsTrait.RcsSchedule
    associatedRcsSensors: _containers.RepeatedCompositeFieldContainer[RemoteComfortSensingSettingsTrait.RcsSensorId]
    multiSensorSettings: RemoteComfortSensingSettingsTrait.MultiSensorSettings
    sensorSelection: HvacSensor.SensorSelection
    def __init__(self, rcsControlMode: _Optional[_Union[RemoteComfortSensingSettingsTrait.RcsControlMode, str]] = ..., activeRcsSelection: _Optional[_Union[RemoteComfortSensingSettingsTrait.RcsSourceSelection, _Mapping]] = ..., rcsControlSchedule: _Optional[_Union[RemoteComfortSensingSettingsTrait.RcsSchedule, _Mapping]] = ..., associatedRcsSensors: _Optional[_Iterable[_Union[RemoteComfortSensingSettingsTrait.RcsSensorId, _Mapping]]] = ..., multiSensorSettings: _Optional[_Union[RemoteComfortSensingSettingsTrait.MultiSensorSettings, _Mapping]] = ..., sensorSelection: _Optional[_Union[HvacSensor.SensorSelection, _Mapping]] = ...) -> None: ...

class HvacControl(_message.Message):
    __slots__ = ()
    class TargetChangeReason(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        TARGET_CHANGE_REASON_UNSPECIFIED: _ClassVar[HvacControl.TargetChangeReason]
        TARGET_CHANGE_REASON_NONE: _ClassVar[HvacControl.TargetChangeReason]
        TARGET_CHANGE_REASON_ADHOC: _ClassVar[HvacControl.TargetChangeReason]
        TARGET_CHANGE_REASON_SCHEDULE: _ClassVar[HvacControl.TargetChangeReason]
        TARGET_CHANGE_REASON_EARLY_ON: _ClassVar[HvacControl.TargetChangeReason]
        TARGET_CHANGE_REASON_EMERGENCY_HEAT: _ClassVar[HvacControl.TargetChangeReason]
        TARGET_CHANGE_REASON_HOLD: _ClassVar[HvacControl.TargetChangeReason]
        TARGET_CHANGE_REASON_ECO_MODE: _ClassVar[HvacControl.TargetChangeReason]
        TARGET_CHANGE_REASON_PERIODICAL: _ClassVar[HvacControl.TargetChangeReason]
    TARGET_CHANGE_REASON_UNSPECIFIED: HvacControl.TargetChangeReason
    TARGET_CHANGE_REASON_NONE: HvacControl.TargetChangeReason
    TARGET_CHANGE_REASON_ADHOC: HvacControl.TargetChangeReason
    TARGET_CHANGE_REASON_SCHEDULE: HvacControl.TargetChangeReason
    TARGET_CHANGE_REASON_EARLY_ON: HvacControl.TargetChangeReason
    TARGET_CHANGE_REASON_EMERGENCY_HEAT: HvacControl.TargetChangeReason
    TARGET_CHANGE_REASON_HOLD: HvacControl.TargetChangeReason
    TARGET_CHANGE_REASON_ECO_MODE: HvacControl.TargetChangeReason
    TARGET_CHANGE_REASON_PERIODICAL: HvacControl.TargetChangeReason
    class Temperature(_message.Message):
        __slots__ = ("value",)
        VALUE_FIELD_NUMBER: _ClassVar[int]
        value: float
        def __init__(self, value: _Optional[float] = ...) -> None: ...
    class TemperatureThreshold(_message.Message):
        __slots__ = ("value", "enabled")
        VALUE_FIELD_NUMBER: _ClassVar[int]
        ENABLED_FIELD_NUMBER: _ClassVar[int]
        value: HvacControl.Temperature
        enabled: bool
        def __init__(self, value: _Optional[_Union[HvacControl.Temperature, _Mapping]] = ..., enabled: bool = ...) -> None: ...
    class HumidityThreshold(_message.Message):
        __slots__ = ("value", "enabled")
        VALUE_FIELD_NUMBER: _ClassVar[int]
        ENABLED_FIELD_NUMBER: _ClassVar[int]
        value: float
        enabled: bool
        def __init__(self, value: _Optional[float] = ..., enabled: bool = ...) -> None: ...
    class RangeTarget(_message.Message):
        __slots__ = ("heatingTarget", "coolingTarget")
        HEATINGTARGET_FIELD_NUMBER: _ClassVar[int]
        COOLINGTARGET_FIELD_NUMBER: _ClassVar[int]
        heatingTarget: HvacControl.TemperatureThreshold
        coolingTarget: HvacControl.TemperatureThreshold
        def __init__(self, heatingTarget: _Optional[_Union[HvacControl.TemperatureThreshold, _Mapping]] = ..., coolingTarget: _Optional[_Union[HvacControl.TemperatureThreshold, _Mapping]] = ...) -> None: ...
    def __init__(self) -> None: ...

class HvacDiagnosticsAlertsSettingsTrait(_message.Message):
    __slots__ = ("enableAlerts", "lastAlertTime", "lastConsentTime")
    class HvacSystem(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        HVAC_SYSTEM_UNSPECIFIED: _ClassVar[HvacDiagnosticsAlertsSettingsTrait.HvacSystem]
        HVAC_SYSTEM_COOL: _ClassVar[HvacDiagnosticsAlertsSettingsTrait.HvacSystem]
        HVAC_SYSTEM_HEAT: _ClassVar[HvacDiagnosticsAlertsSettingsTrait.HvacSystem]
    HVAC_SYSTEM_UNSPECIFIED: HvacDiagnosticsAlertsSettingsTrait.HvacSystem
    HVAC_SYSTEM_COOL: HvacDiagnosticsAlertsSettingsTrait.HvacSystem
    HVAC_SYSTEM_HEAT: HvacDiagnosticsAlertsSettingsTrait.HvacSystem
    class RangeInclusion(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        RANGE_INCLUSION_UNSPECIFIED: _ClassVar[HvacDiagnosticsAlertsSettingsTrait.RangeInclusion]
        RANGE_INCLUSION_ABOVE_BOUNDS: _ClassVar[HvacDiagnosticsAlertsSettingsTrait.RangeInclusion]
        RANGE_INCLUSION_BELOW_BOUNDS: _ClassVar[HvacDiagnosticsAlertsSettingsTrait.RangeInclusion]
    RANGE_INCLUSION_UNSPECIFIED: HvacDiagnosticsAlertsSettingsTrait.RangeInclusion
    RANGE_INCLUSION_ABOVE_BOUNDS: HvacDiagnosticsAlertsSettingsTrait.RangeInclusion
    RANGE_INCLUSION_BELOW_BOUNDS: HvacDiagnosticsAlertsSettingsTrait.RangeInclusion
    class FailureCause(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        FAILURE_CAUSE_UNSPECIFIED: _ClassVar[HvacDiagnosticsAlertsSettingsTrait.FailureCause]
        FAILURE_CAUSE_BY_ASSEMBLY_LINE: _ClassVar[HvacDiagnosticsAlertsSettingsTrait.FailureCause]
        FAILURE_CAUSE_BY_IMPROPER_USAGE: _ClassVar[HvacDiagnosticsAlertsSettingsTrait.FailureCause]
    FAILURE_CAUSE_UNSPECIFIED: HvacDiagnosticsAlertsSettingsTrait.FailureCause
    FAILURE_CAUSE_BY_ASSEMBLY_LINE: HvacDiagnosticsAlertsSettingsTrait.FailureCause
    FAILURE_CAUSE_BY_IMPROPER_USAGE: HvacDiagnosticsAlertsSettingsTrait.FailureCause
    class WiringError(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        WIRING_ERROR_UNSPECIFIED: _ClassVar[HvacDiagnosticsAlertsSettingsTrait.WiringError]
        WIRING_ERROR_NO_POWER_TO_C: _ClassVar[HvacDiagnosticsAlertsSettingsTrait.WiringError]
        WIRING_ERROR_LOW_POWER_TO_C: _ClassVar[HvacDiagnosticsAlertsSettingsTrait.WiringError]
    WIRING_ERROR_UNSPECIFIED: HvacDiagnosticsAlertsSettingsTrait.WiringError
    WIRING_ERROR_NO_POWER_TO_C: HvacDiagnosticsAlertsSettingsTrait.WiringError
    WIRING_ERROR_LOW_POWER_TO_C: HvacDiagnosticsAlertsSettingsTrait.WiringError
    class HvacSystemAlertEvent(_message.Message):
        __slots__ = ("structurePostalCode", "structureCountryCode", "optOutUrl", "proLeadEnabled", "nestReportedIssue", "isWithinServiceArea", "proInfo", "hvacVendorPartner")
        STRUCTUREPOSTALCODE_FIELD_NUMBER: _ClassVar[int]
        STRUCTURECOUNTRYCODE_FIELD_NUMBER: _ClassVar[int]
        OPTOUTURL_FIELD_NUMBER: _ClassVar[int]
        PROLEADENABLED_FIELD_NUMBER: _ClassVar[int]
        NESTREPORTEDISSUE_FIELD_NUMBER: _ClassVar[int]
        ISWITHINSERVICEAREA_FIELD_NUMBER: _ClassVar[int]
        PROINFO_FIELD_NUMBER: _ClassVar[int]
        HVACVENDORPARTNER_FIELD_NUMBER: _ClassVar[int]
        structurePostalCode: str
        structureCountryCode: str
        optOutUrl: str
        proLeadEnabled: bool
        nestReportedIssue: HvacDiagnosticsAlertsSettingsTrait.NestReportedIssue
        isWithinServiceArea: bool
        proInfo: HvacDiagnosticsAlertsSettingsTrait.ProInformation
        hvacVendorPartner: HvacVendorPartnerInfoTrait.HvacVendorPartner
        def __init__(self, structurePostalCode: _Optional[str] = ..., structureCountryCode: _Optional[str] = ..., optOutUrl: _Optional[str] = ..., proLeadEnabled: bool = ..., nestReportedIssue: _Optional[_Union[HvacDiagnosticsAlertsSettingsTrait.NestReportedIssue, _Mapping]] = ..., isWithinServiceArea: bool = ..., proInfo: _Optional[_Union[HvacDiagnosticsAlertsSettingsTrait.ProInformation, _Mapping]] = ..., hvacVendorPartner: _Optional[_Union[HvacVendorPartnerInfoTrait.HvacVendorPartner, str]] = ...) -> None: ...
    class ProInformation(_message.Message):
        __slots__ = ("proId", "businessName", "address", "phoneNumber", "email")
        PROID_FIELD_NUMBER: _ClassVar[int]
        BUSINESSNAME_FIELD_NUMBER: _ClassVar[int]
        ADDRESS_FIELD_NUMBER: _ClassVar[int]
        PHONENUMBER_FIELD_NUMBER: _ClassVar[int]
        EMAIL_FIELD_NUMBER: _ClassVar[int]
        proId: str
        businessName: str
        address: _located_pb2.GeoCommon.PostalAddress
        phoneNumber: str
        email: str
        def __init__(self, proId: _Optional[str] = ..., businessName: _Optional[str] = ..., address: _Optional[_Union[_located_pb2.GeoCommon.PostalAddress, _Mapping]] = ..., phoneNumber: _Optional[str] = ..., email: _Optional[str] = ...) -> None: ...
    class NestReportedIssue(_message.Message):
        __slots__ = ("issueId", "surveyUrlGaia", "surveyUrlNongaia", "visualAssetUrl", "hvacSystem", "degradation", "intermittent", "severe", "temperatureAlert", "humidityAlert", "furnaceHeadsUp", "bookAProUrl", "hardwareResistorFailure", "deviceSerialNumber", "hardwareWiringError", "phoenixDeviceId", "hvacDeliveryType", "heatLinkPowerSupplyFailure", "heatLinkPowerSupplyReplacement")
        ISSUEID_FIELD_NUMBER: _ClassVar[int]
        SURVEYURLGAIA_FIELD_NUMBER: _ClassVar[int]
        SURVEYURLNONGAIA_FIELD_NUMBER: _ClassVar[int]
        VISUALASSETURL_FIELD_NUMBER: _ClassVar[int]
        HVACSYSTEM_FIELD_NUMBER: _ClassVar[int]
        DEGRADATION_FIELD_NUMBER: _ClassVar[int]
        INTERMITTENT_FIELD_NUMBER: _ClassVar[int]
        SEVERE_FIELD_NUMBER: _ClassVar[int]
        TEMPERATUREALERT_FIELD_NUMBER: _ClassVar[int]
        HUMIDITYALERT_FIELD_NUMBER: _ClassVar[int]
        FURNACEHEADSUP_FIELD_NUMBER: _ClassVar[int]
        BOOKAPROURL_FIELD_NUMBER: _ClassVar[int]
        HARDWARERESISTORFAILURE_FIELD_NUMBER: _ClassVar[int]
        DEVICESERIALNUMBER_FIELD_NUMBER: _ClassVar[int]
        HARDWAREWIRINGERROR_FIELD_NUMBER: _ClassVar[int]
        PHOENIXDEVICEID_FIELD_NUMBER: _ClassVar[int]
        HVACDELIVERYTYPE_FIELD_NUMBER: _ClassVar[int]
        HEATLINKPOWERSUPPLYFAILURE_FIELD_NUMBER: _ClassVar[int]
        HEATLINKPOWERSUPPLYREPLACEMENT_FIELD_NUMBER: _ClassVar[int]
        issueId: str
        surveyUrlGaia: str
        surveyUrlNongaia: str
        visualAssetUrl: str
        hvacSystem: HvacDiagnosticsAlertsSettingsTrait.HvacSystem
        degradation: HvacDiagnosticsAlertsSettingsTrait.Degradation
        intermittent: HvacDiagnosticsAlertsSettingsTrait.Intermittent
        severe: HvacDiagnosticsAlertsSettingsTrait.Severe
        temperatureAlert: HvacDiagnosticsAlertsSettingsTrait.TemperatureAlert
        humidityAlert: HvacDiagnosticsAlertsSettingsTrait.HumidityAlert
        furnaceHeadsUp: HvacDiagnosticsAlertsSettingsTrait.FurnaceHeadsUp
        bookAProUrl: _wrappers_pb2.StringValue
        hardwareResistorFailure: HvacDiagnosticsAlertsSettingsTrait.HardwareResistorFailure
        deviceSerialNumber: str
        hardwareWiringError: HvacDiagnosticsAlertsSettingsTrait.HardwareWiringError
        phoenixDeviceId: _common_pb2.ResourceId
        hvacDeliveryType: EquipmentSettingsTrait.DeliveryType
        heatLinkPowerSupplyFailure: HvacDiagnosticsAlertsSettingsTrait.HeatLinkPowerSupplyFailure
        heatLinkPowerSupplyReplacement: HvacDiagnosticsAlertsSettingsTrait.HeatLinkPowerSupplyReplacement
        def __init__(self, issueId: _Optional[str] = ..., surveyUrlGaia: _Optional[str] = ..., surveyUrlNongaia: _Optional[str] = ..., visualAssetUrl: _Optional[str] = ..., hvacSystem: _Optional[_Union[HvacDiagnosticsAlertsSettingsTrait.HvacSystem, str]] = ..., degradation: _Optional[_Union[HvacDiagnosticsAlertsSettingsTrait.Degradation, _Mapping]] = ..., intermittent: _Optional[_Union[HvacDiagnosticsAlertsSettingsTrait.Intermittent, _Mapping]] = ..., severe: _Optional[_Union[HvacDiagnosticsAlertsSettingsTrait.Severe, _Mapping]] = ..., temperatureAlert: _Optional[_Union[HvacDiagnosticsAlertsSettingsTrait.TemperatureAlert, _Mapping]] = ..., humidityAlert: _Optional[_Union[HvacDiagnosticsAlertsSettingsTrait.HumidityAlert, _Mapping]] = ..., furnaceHeadsUp: _Optional[_Union[HvacDiagnosticsAlertsSettingsTrait.FurnaceHeadsUp, _Mapping]] = ..., bookAProUrl: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., hardwareResistorFailure: _Optional[_Union[HvacDiagnosticsAlertsSettingsTrait.HardwareResistorFailure, _Mapping]] = ..., deviceSerialNumber: _Optional[str] = ..., hardwareWiringError: _Optional[_Union[HvacDiagnosticsAlertsSettingsTrait.HardwareWiringError, _Mapping]] = ..., phoenixDeviceId: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ..., hvacDeliveryType: _Optional[_Union[EquipmentSettingsTrait.DeliveryType, str]] = ..., heatLinkPowerSupplyFailure: _Optional[_Union[HvacDiagnosticsAlertsSettingsTrait.HeatLinkPowerSupplyFailure, _Mapping]] = ..., heatLinkPowerSupplyReplacement: _Optional[_Union[HvacDiagnosticsAlertsSettingsTrait.HeatLinkPowerSupplyReplacement, _Mapping]] = ...) -> None: ...
    class Intermittent(_message.Message):
        __slots__ = ("duration", "misbehavingCycles", "issueStartTimestamp")
        DURATION_FIELD_NUMBER: _ClassVar[int]
        MISBEHAVINGCYCLES_FIELD_NUMBER: _ClassVar[int]
        ISSUESTARTTIMESTAMP_FIELD_NUMBER: _ClassVar[int]
        duration: _duration_pb2.Duration
        misbehavingCycles: int
        issueStartTimestamp: _timestamp_pb2.Timestamp
        def __init__(self, duration: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ..., misbehavingCycles: _Optional[int] = ..., issueStartTimestamp: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...
    class Severe(_message.Message):
        __slots__ = ("issueStartTimestamp", "issueEndTimestamp", "actualTemperatureChange", "expectedTemperatureChange")
        ISSUESTARTTIMESTAMP_FIELD_NUMBER: _ClassVar[int]
        ISSUEENDTIMESTAMP_FIELD_NUMBER: _ClassVar[int]
        ACTUALTEMPERATURECHANGE_FIELD_NUMBER: _ClassVar[int]
        EXPECTEDTEMPERATURECHANGE_FIELD_NUMBER: _ClassVar[int]
        issueStartTimestamp: _timestamp_pb2.Timestamp
        issueEndTimestamp: _timestamp_pb2.Timestamp
        actualTemperatureChange: float
        expectedTemperatureChange: float
        def __init__(self, issueStartTimestamp: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., issueEndTimestamp: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., actualTemperatureChange: _Optional[float] = ..., expectedTemperatureChange: _Optional[float] = ...) -> None: ...
    class Degradation(_message.Message):
        __slots__ = ("issueStartTimestamp", "duration", "historical", "cohort", "auxHeat")
        ISSUESTARTTIMESTAMP_FIELD_NUMBER: _ClassVar[int]
        DURATION_FIELD_NUMBER: _ClassVar[int]
        HISTORICAL_FIELD_NUMBER: _ClassVar[int]
        COHORT_FIELD_NUMBER: _ClassVar[int]
        AUXHEAT_FIELD_NUMBER: _ClassVar[int]
        issueStartTimestamp: _timestamp_pb2.Timestamp
        duration: _duration_pb2.Duration
        historical: HvacDiagnosticsAlertsSettingsTrait.HistoricalDegradationDetails
        cohort: HvacDiagnosticsAlertsSettingsTrait.CohortAnalysisDetails
        auxHeat: HvacDiagnosticsAlertsSettingsTrait.ExcessiveAuxHeatDetails
        def __init__(self, issueStartTimestamp: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., duration: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ..., historical: _Optional[_Union[HvacDiagnosticsAlertsSettingsTrait.HistoricalDegradationDetails, _Mapping]] = ..., cohort: _Optional[_Union[HvacDiagnosticsAlertsSettingsTrait.CohortAnalysisDetails, _Mapping]] = ..., auxHeat: _Optional[_Union[HvacDiagnosticsAlertsSettingsTrait.ExcessiveAuxHeatDetails, _Mapping]] = ...) -> None: ...
    class HistoricalDegradationDetails(_message.Message):
        __slots__ = ("expectedRuntime", "observedRuntime", "extraRuntimePercentage")
        EXPECTEDRUNTIME_FIELD_NUMBER: _ClassVar[int]
        OBSERVEDRUNTIME_FIELD_NUMBER: _ClassVar[int]
        EXTRARUNTIMEPERCENTAGE_FIELD_NUMBER: _ClassVar[int]
        expectedRuntime: _duration_pb2.Duration
        observedRuntime: _duration_pb2.Duration
        extraRuntimePercentage: float
        def __init__(self, expectedRuntime: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ..., observedRuntime: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ..., extraRuntimePercentage: _Optional[float] = ...) -> None: ...
    class CohortAnalysisDetails(_message.Message):
        __slots__ = ("observedRuntime",)
        OBSERVEDRUNTIME_FIELD_NUMBER: _ClassVar[int]
        observedRuntime: _duration_pb2.Duration
        def __init__(self, observedRuntime: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ...) -> None: ...
    class ExcessiveAuxHeatDetails(_message.Message):
        __slots__ = ("overallHeatRuntime", "compressorHeatRuntime", "auxHeatRuntime", "heatPumpSettings", "expectedAuxHeatRuntime", "potentialEnergySavingsPercentage")
        OVERALLHEATRUNTIME_FIELD_NUMBER: _ClassVar[int]
        COMPRESSORHEATRUNTIME_FIELD_NUMBER: _ClassVar[int]
        AUXHEATRUNTIME_FIELD_NUMBER: _ClassVar[int]
        HEATPUMPSETTINGS_FIELD_NUMBER: _ClassVar[int]
        EXPECTEDAUXHEATRUNTIME_FIELD_NUMBER: _ClassVar[int]
        POTENTIALENERGYSAVINGSPERCENTAGE_FIELD_NUMBER: _ClassVar[int]
        overallHeatRuntime: _duration_pb2.Duration
        compressorHeatRuntime: _duration_pb2.Duration
        auxHeatRuntime: _duration_pb2.Duration
        heatPumpSettings: HeatPumpControlSettingsTrait.HeatPumpSavingsMode
        expectedAuxHeatRuntime: _duration_pb2.Duration
        potentialEnergySavingsPercentage: float
        def __init__(self, overallHeatRuntime: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ..., compressorHeatRuntime: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ..., auxHeatRuntime: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ..., heatPumpSettings: _Optional[_Union[HeatPumpControlSettingsTrait.HeatPumpSavingsMode, str]] = ..., expectedAuxHeatRuntime: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ..., potentialEnergySavingsPercentage: _Optional[float] = ...) -> None: ...
    class TemperatureAlert(_message.Message):
        __slots__ = ("issueStartTimestamp", "duration", "inclusion", "minObservedTemperature", "maxObservedTemperature", "avgObservedTemperature", "upperTemperatureBound", "lowerTemperatureBound")
        ISSUESTARTTIMESTAMP_FIELD_NUMBER: _ClassVar[int]
        DURATION_FIELD_NUMBER: _ClassVar[int]
        INCLUSION_FIELD_NUMBER: _ClassVar[int]
        MINOBSERVEDTEMPERATURE_FIELD_NUMBER: _ClassVar[int]
        MAXOBSERVEDTEMPERATURE_FIELD_NUMBER: _ClassVar[int]
        AVGOBSERVEDTEMPERATURE_FIELD_NUMBER: _ClassVar[int]
        UPPERTEMPERATUREBOUND_FIELD_NUMBER: _ClassVar[int]
        LOWERTEMPERATUREBOUND_FIELD_NUMBER: _ClassVar[int]
        issueStartTimestamp: _timestamp_pb2.Timestamp
        duration: _duration_pb2.Duration
        inclusion: HvacDiagnosticsAlertsSettingsTrait.RangeInclusion
        minObservedTemperature: float
        maxObservedTemperature: float
        avgObservedTemperature: float
        upperTemperatureBound: float
        lowerTemperatureBound: float
        def __init__(self, issueStartTimestamp: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., duration: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ..., inclusion: _Optional[_Union[HvacDiagnosticsAlertsSettingsTrait.RangeInclusion, str]] = ..., minObservedTemperature: _Optional[float] = ..., maxObservedTemperature: _Optional[float] = ..., avgObservedTemperature: _Optional[float] = ..., upperTemperatureBound: _Optional[float] = ..., lowerTemperatureBound: _Optional[float] = ...) -> None: ...
    class HumidityAlert(_message.Message):
        __slots__ = ("issueStartTimestamp", "duration", "inclusion", "minObservedHumidity", "maxObservedHumidity", "avgObservedHumidity", "upperHumidityBound", "lowerHumidityBound")
        ISSUESTARTTIMESTAMP_FIELD_NUMBER: _ClassVar[int]
        DURATION_FIELD_NUMBER: _ClassVar[int]
        INCLUSION_FIELD_NUMBER: _ClassVar[int]
        MINOBSERVEDHUMIDITY_FIELD_NUMBER: _ClassVar[int]
        MAXOBSERVEDHUMIDITY_FIELD_NUMBER: _ClassVar[int]
        AVGOBSERVEDHUMIDITY_FIELD_NUMBER: _ClassVar[int]
        UPPERHUMIDITYBOUND_FIELD_NUMBER: _ClassVar[int]
        LOWERHUMIDITYBOUND_FIELD_NUMBER: _ClassVar[int]
        issueStartTimestamp: _timestamp_pb2.Timestamp
        duration: _duration_pb2.Duration
        inclusion: HvacDiagnosticsAlertsSettingsTrait.RangeInclusion
        minObservedHumidity: float
        maxObservedHumidity: float
        avgObservedHumidity: float
        upperHumidityBound: float
        lowerHumidityBound: float
        def __init__(self, issueStartTimestamp: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., duration: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ..., inclusion: _Optional[_Union[HvacDiagnosticsAlertsSettingsTrait.RangeInclusion, str]] = ..., minObservedHumidity: _Optional[float] = ..., maxObservedHumidity: _Optional[float] = ..., avgObservedHumidity: _Optional[float] = ..., upperHumidityBound: _Optional[float] = ..., lowerHumidityBound: _Optional[float] = ...) -> None: ...
    class FurnaceHeadsUp(_message.Message):
        __slots__ = ("detectedTimestamp",)
        DETECTEDTIMESTAMP_FIELD_NUMBER: _ClassVar[int]
        detectedTimestamp: _timestamp_pb2.Timestamp
        def __init__(self, detectedTimestamp: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...
    class HardwareResistorFailure(_message.Message):
        __slots__ = ("detectedTimestamp", "failureCause")
        DETECTEDTIMESTAMP_FIELD_NUMBER: _ClassVar[int]
        FAILURECAUSE_FIELD_NUMBER: _ClassVar[int]
        detectedTimestamp: _timestamp_pb2.Timestamp
        failureCause: HvacDiagnosticsAlertsSettingsTrait.FailureCause
        def __init__(self, detectedTimestamp: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., failureCause: _Optional[_Union[HvacDiagnosticsAlertsSettingsTrait.FailureCause, str]] = ...) -> None: ...
    class HardwareWiringError(_message.Message):
        __slots__ = ("detectedTimestamp", "wiringError")
        DETECTEDTIMESTAMP_FIELD_NUMBER: _ClassVar[int]
        WIRINGERROR_FIELD_NUMBER: _ClassVar[int]
        detectedTimestamp: _timestamp_pb2.Timestamp
        wiringError: HvacDiagnosticsAlertsSettingsTrait.WiringError
        def __init__(self, detectedTimestamp: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., wiringError: _Optional[_Union[HvacDiagnosticsAlertsSettingsTrait.WiringError, str]] = ...) -> None: ...
    class HeatLinkPowerSupplyFailure(_message.Message):
        __slots__ = ("heatLinkLastSeenConnected", "headUnitLastSeenConnected")
        HEATLINKLASTSEENCONNECTED_FIELD_NUMBER: _ClassVar[int]
        HEADUNITLASTSEENCONNECTED_FIELD_NUMBER: _ClassVar[int]
        heatLinkLastSeenConnected: _timestamp_pb2.Timestamp
        headUnitLastSeenConnected: _timestamp_pb2.Timestamp
        def __init__(self, heatLinkLastSeenConnected: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., headUnitLastSeenConnected: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...
    class HeatLinkPowerSupplyReplacement(_message.Message):
        __slots__ = ("caseNumber",)
        CASENUMBER_FIELD_NUMBER: _ClassVar[int]
        caseNumber: str
        def __init__(self, caseNumber: _Optional[str] = ...) -> None: ...
    ENABLEALERTS_FIELD_NUMBER: _ClassVar[int]
    LASTALERTTIME_FIELD_NUMBER: _ClassVar[int]
    LASTCONSENTTIME_FIELD_NUMBER: _ClassVar[int]
    enableAlerts: _wrappers_pb2.BoolValue
    lastAlertTime: _timestamp_pb2.Timestamp
    lastConsentTime: _timestamp_pb2.Timestamp
    def __init__(self, enableAlerts: _Optional[_Union[_wrappers_pb2.BoolValue, _Mapping]] = ..., lastAlertTime: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., lastConsentTime: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class EquipmentSettingsTrait(_message.Message):
    __slots__ = ("heatStage1Delivery", "heatStage2Delivery", "heatStage3Delivery", "heatStage1Source", "heatStage2Source", "heatStage3Source", "coolingStage1Delivery", "coolingStage2Delivery", "coolingStage3Delivery", "coolingStage1Source", "coolingStage2Source", "coolingStage3Source", "altHeatStage1Delivery", "altHeatStage2Delivery", "altHeatStage1Source", "altHeatStage2Source", "auxHeatStage1Delivery", "auxHeatStage1Source", "emergencyHeatDelivery", "emergencyHeatSource", "starType", "y2Type", "dehumidifierFanActivation", "dehumidifierOrientationSelected", "dehumidifierType", "humidifierFanActivation", "humidifierType", "dualFuelSelected", "dualFuelBreakpoint", "dualFuelBreakpointOverride", "obOrientation", "obPersistence", "boilerType", "boilerSupplyTemperature", "activateFanIfHeatSourceIsGas", "ventilatorType", "ventilatorRequiresFanActivation", "aqWireType", "compressorMinCycleTime", "compressorLockout", "heatMinCycleTime")
    class DeliveryType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        DELIVERY_TYPE_UNSPECIFIED: _ClassVar[EquipmentSettingsTrait.DeliveryType]
        DELIVERY_TYPE_FORCED_AIR: _ClassVar[EquipmentSettingsTrait.DeliveryType]
        DELIVERY_TYPE_IN_FLOOR_RADIANT: _ClassVar[EquipmentSettingsTrait.DeliveryType]
        DELIVERY_TYPE_RADIATORS: _ClassVar[EquipmentSettingsTrait.DeliveryType]
        DELIVERY_TYPE_ELECTRIC_STRIP: _ClassVar[EquipmentSettingsTrait.DeliveryType]
    DELIVERY_TYPE_UNSPECIFIED: EquipmentSettingsTrait.DeliveryType
    DELIVERY_TYPE_FORCED_AIR: EquipmentSettingsTrait.DeliveryType
    DELIVERY_TYPE_IN_FLOOR_RADIANT: EquipmentSettingsTrait.DeliveryType
    DELIVERY_TYPE_RADIATORS: EquipmentSettingsTrait.DeliveryType
    DELIVERY_TYPE_ELECTRIC_STRIP: EquipmentSettingsTrait.DeliveryType
    class FuelSourceType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        FUEL_SOURCE_TYPE_UNSPECIFIED: _ClassVar[EquipmentSettingsTrait.FuelSourceType]
        FUEL_SOURCE_TYPE_GAS: _ClassVar[EquipmentSettingsTrait.FuelSourceType]
        FUEL_SOURCE_TYPE_ELECTRIC: _ClassVar[EquipmentSettingsTrait.FuelSourceType]
        FUEL_SOURCE_TYPE_OIL: _ClassVar[EquipmentSettingsTrait.FuelSourceType]
        FUEL_SOURCE_TYPE_LP: _ClassVar[EquipmentSettingsTrait.FuelSourceType]
        FUEL_SOURCE_TYPE_GEOTHERMAL: _ClassVar[EquipmentSettingsTrait.FuelSourceType]
        FUEL_SOURCE_TYPE_DISTRICT_HEATING: _ClassVar[EquipmentSettingsTrait.FuelSourceType]
        FUEL_SOURCE_TYPE_PELLETS: _ClassVar[EquipmentSettingsTrait.FuelSourceType]
    FUEL_SOURCE_TYPE_UNSPECIFIED: EquipmentSettingsTrait.FuelSourceType
    FUEL_SOURCE_TYPE_GAS: EquipmentSettingsTrait.FuelSourceType
    FUEL_SOURCE_TYPE_ELECTRIC: EquipmentSettingsTrait.FuelSourceType
    FUEL_SOURCE_TYPE_OIL: EquipmentSettingsTrait.FuelSourceType
    FUEL_SOURCE_TYPE_LP: EquipmentSettingsTrait.FuelSourceType
    FUEL_SOURCE_TYPE_GEOTHERMAL: EquipmentSettingsTrait.FuelSourceType
    FUEL_SOURCE_TYPE_DISTRICT_HEATING: EquipmentSettingsTrait.FuelSourceType
    FUEL_SOURCE_TYPE_PELLETS: EquipmentSettingsTrait.FuelSourceType
    class StarType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        STAR_TYPE_UNSPECIFIED: _ClassVar[EquipmentSettingsTrait.StarType]
        STAR_TYPE_EMERGENCY_HEAT: _ClassVar[EquipmentSettingsTrait.StarType]
        STAR_TYPE_HUMIDIFIER: _ClassVar[EquipmentSettingsTrait.StarType]
        STAR_TYPE_DEHUMIDIFIER: _ClassVar[EquipmentSettingsTrait.StarType]
        STAR_TYPE_W3: _ClassVar[EquipmentSettingsTrait.StarType]
        STAR_TYPE_WATER_HEATER: _ClassVar[EquipmentSettingsTrait.StarType]
        STAR_TYPE_G3: _ClassVar[EquipmentSettingsTrait.StarType]
        STAR_TYPE_OB: _ClassVar[EquipmentSettingsTrait.StarType]
        STAR_TYPE_Y2: _ClassVar[EquipmentSettingsTrait.StarType]
        STAR_TYPE_W2: _ClassVar[EquipmentSettingsTrait.StarType]
    STAR_TYPE_UNSPECIFIED: EquipmentSettingsTrait.StarType
    STAR_TYPE_EMERGENCY_HEAT: EquipmentSettingsTrait.StarType
    STAR_TYPE_HUMIDIFIER: EquipmentSettingsTrait.StarType
    STAR_TYPE_DEHUMIDIFIER: EquipmentSettingsTrait.StarType
    STAR_TYPE_W3: EquipmentSettingsTrait.StarType
    STAR_TYPE_WATER_HEATER: EquipmentSettingsTrait.StarType
    STAR_TYPE_G3: EquipmentSettingsTrait.StarType
    STAR_TYPE_OB: EquipmentSettingsTrait.StarType
    STAR_TYPE_Y2: EquipmentSettingsTrait.StarType
    STAR_TYPE_W2: EquipmentSettingsTrait.StarType
    class Y2Type(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        Y2_TYPE_UNSPECIFIED: _ClassVar[EquipmentSettingsTrait.Y2Type]
        Y2_TYPE_HEATING_AND_COOLING: _ClassVar[EquipmentSettingsTrait.Y2Type]
        Y2_TYPE_HEATING: _ClassVar[EquipmentSettingsTrait.Y2Type]
        Y2_TYPE_COOLING: _ClassVar[EquipmentSettingsTrait.Y2Type]
        Y2_TYPE_G2: _ClassVar[EquipmentSettingsTrait.Y2Type]
    Y2_TYPE_UNSPECIFIED: EquipmentSettingsTrait.Y2Type
    Y2_TYPE_HEATING_AND_COOLING: EquipmentSettingsTrait.Y2Type
    Y2_TYPE_HEATING: EquipmentSettingsTrait.Y2Type
    Y2_TYPE_COOLING: EquipmentSettingsTrait.Y2Type
    Y2_TYPE_G2: EquipmentSettingsTrait.Y2Type
    class AqWireType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        AQ_WIRE_TYPE_UNSPECIFIED: _ClassVar[EquipmentSettingsTrait.AqWireType]
        AQ_WIRE_TYPE_VENTILATOR: _ClassVar[EquipmentSettingsTrait.AqWireType]
        AQ_WIRE_TYPE_HUMIDIFIER: _ClassVar[EquipmentSettingsTrait.AqWireType]
        AQ_WIRE_TYPE_DEHUMIDIFIER: _ClassVar[EquipmentSettingsTrait.AqWireType]
    AQ_WIRE_TYPE_UNSPECIFIED: EquipmentSettingsTrait.AqWireType
    AQ_WIRE_TYPE_VENTILATOR: EquipmentSettingsTrait.AqWireType
    AQ_WIRE_TYPE_HUMIDIFIER: EquipmentSettingsTrait.AqWireType
    AQ_WIRE_TYPE_DEHUMIDIFIER: EquipmentSettingsTrait.AqWireType
    class DehumidifierOrientation(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        DEHUMIDIFIER_ORIENTATION_UNSPECIFIED: _ClassVar[EquipmentSettingsTrait.DehumidifierOrientation]
        DEHUMIDIFIER_ORIENTATION_NORMAL: _ClassVar[EquipmentSettingsTrait.DehumidifierOrientation]
        DEHUMIDIFIER_ORIENTATION_REVERSED: _ClassVar[EquipmentSettingsTrait.DehumidifierOrientation]
    DEHUMIDIFIER_ORIENTATION_UNSPECIFIED: EquipmentSettingsTrait.DehumidifierOrientation
    DEHUMIDIFIER_ORIENTATION_NORMAL: EquipmentSettingsTrait.DehumidifierOrientation
    DEHUMIDIFIER_ORIENTATION_REVERSED: EquipmentSettingsTrait.DehumidifierOrientation
    class DehumidifierType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        DEHUMIDIFIER_TYPE_UNSPECIFIED: _ClassVar[EquipmentSettingsTrait.DehumidifierType]
        DEHUMIDIFIER_TYPE_AC_INTEGRATED: _ClassVar[EquipmentSettingsTrait.DehumidifierType]
        DEHUMIDIFIER_TYPE_STAND_ALONE: _ClassVar[EquipmentSettingsTrait.DehumidifierType]
    DEHUMIDIFIER_TYPE_UNSPECIFIED: EquipmentSettingsTrait.DehumidifierType
    DEHUMIDIFIER_TYPE_AC_INTEGRATED: EquipmentSettingsTrait.DehumidifierType
    DEHUMIDIFIER_TYPE_STAND_ALONE: EquipmentSettingsTrait.DehumidifierType
    class DehumidifierFanType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        DEHUMIDIFIER_FAN_TYPE_UNSPECIFIED: _ClassVar[EquipmentSettingsTrait.DehumidifierFanType]
        DEHUMIDIFIER_FAN_TYPE_ACTIVATE: _ClassVar[EquipmentSettingsTrait.DehumidifierFanType]
        DEHUMIDIFIER_FAN_TYPE_DONT_ACTIVATE: _ClassVar[EquipmentSettingsTrait.DehumidifierFanType]
    DEHUMIDIFIER_FAN_TYPE_UNSPECIFIED: EquipmentSettingsTrait.DehumidifierFanType
    DEHUMIDIFIER_FAN_TYPE_ACTIVATE: EquipmentSettingsTrait.DehumidifierFanType
    DEHUMIDIFIER_FAN_TYPE_DONT_ACTIVATE: EquipmentSettingsTrait.DehumidifierFanType
    class HumidifierType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        HUMIDIFIER_TYPE_UNSPECIFIED: _ClassVar[EquipmentSettingsTrait.HumidifierType]
        HUMIDIFIER_TYPE_STEAM_GENERATING: _ClassVar[EquipmentSettingsTrait.HumidifierType]
        HUMIDIFIER_TYPE_BYPASS: _ClassVar[EquipmentSettingsTrait.HumidifierType]
    HUMIDIFIER_TYPE_UNSPECIFIED: EquipmentSettingsTrait.HumidifierType
    HUMIDIFIER_TYPE_STEAM_GENERATING: EquipmentSettingsTrait.HumidifierType
    HUMIDIFIER_TYPE_BYPASS: EquipmentSettingsTrait.HumidifierType
    class HumidifierFanType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        HUMIDIFIER_FAN_TYPE_UNSPECIFIED: _ClassVar[EquipmentSettingsTrait.HumidifierFanType]
        HUMIDIFIER_FAN_TYPE_ACTIVATE: _ClassVar[EquipmentSettingsTrait.HumidifierFanType]
        HUMIDIFIER_FAN_TYPE_DONT_ACTIVATE: _ClassVar[EquipmentSettingsTrait.HumidifierFanType]
    HUMIDIFIER_FAN_TYPE_UNSPECIFIED: EquipmentSettingsTrait.HumidifierFanType
    HUMIDIFIER_FAN_TYPE_ACTIVATE: EquipmentSettingsTrait.HumidifierFanType
    HUMIDIFIER_FAN_TYPE_DONT_ACTIVATE: EquipmentSettingsTrait.HumidifierFanType
    class DualFuelSelection(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        DUAL_FUEL_SELECTION_UNSPECIFIED: _ClassVar[EquipmentSettingsTrait.DualFuelSelection]
        DUAL_FUEL_SELECTION_DUAL_FUEL: _ClassVar[EquipmentSettingsTrait.DualFuelSelection]
        DUAL_FUEL_SELECTION_SINGLE_FUEL: _ClassVar[EquipmentSettingsTrait.DualFuelSelection]
    DUAL_FUEL_SELECTION_UNSPECIFIED: EquipmentSettingsTrait.DualFuelSelection
    DUAL_FUEL_SELECTION_DUAL_FUEL: EquipmentSettingsTrait.DualFuelSelection
    DUAL_FUEL_SELECTION_SINGLE_FUEL: EquipmentSettingsTrait.DualFuelSelection
    class DualFuelOverride(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        DUAL_FUEL_OVERRIDE_UNSPECIFIED: _ClassVar[EquipmentSettingsTrait.DualFuelOverride]
        DUAL_FUEL_OVERRIDE_NONE: _ClassVar[EquipmentSettingsTrait.DualFuelOverride]
        DUAL_FUEL_OVERRIDE_ALWAYS_ALT: _ClassVar[EquipmentSettingsTrait.DualFuelOverride]
        DUAL_FUEL_OVERRIDE_ALWAYS_PRIMARY: _ClassVar[EquipmentSettingsTrait.DualFuelOverride]
    DUAL_FUEL_OVERRIDE_UNSPECIFIED: EquipmentSettingsTrait.DualFuelOverride
    DUAL_FUEL_OVERRIDE_NONE: EquipmentSettingsTrait.DualFuelOverride
    DUAL_FUEL_OVERRIDE_ALWAYS_ALT: EquipmentSettingsTrait.DualFuelOverride
    DUAL_FUEL_OVERRIDE_ALWAYS_PRIMARY: EquipmentSettingsTrait.DualFuelOverride
    class ObOrientation(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        OB_ORIENTATION_UNSPECIFIED: _ClassVar[EquipmentSettingsTrait.ObOrientation]
        OB_ORIENTATION_O: _ClassVar[EquipmentSettingsTrait.ObOrientation]
        OB_ORIENTATION_B: _ClassVar[EquipmentSettingsTrait.ObOrientation]
    OB_ORIENTATION_UNSPECIFIED: EquipmentSettingsTrait.ObOrientation
    OB_ORIENTATION_O: EquipmentSettingsTrait.ObOrientation
    OB_ORIENTATION_B: EquipmentSettingsTrait.ObOrientation
    class ObPersistence(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        OB_PERSISTENCE_UNSPECIFIED: _ClassVar[EquipmentSettingsTrait.ObPersistence]
        OB_PERSISTENCE_SEASONAL: _ClassVar[EquipmentSettingsTrait.ObPersistence]
        OB_PERSISTENCE_CYCLICAL: _ClassVar[EquipmentSettingsTrait.ObPersistence]
    OB_PERSISTENCE_UNSPECIFIED: EquipmentSettingsTrait.ObPersistence
    OB_PERSISTENCE_SEASONAL: EquipmentSettingsTrait.ObPersistence
    OB_PERSISTENCE_CYCLICAL: EquipmentSettingsTrait.ObPersistence
    class BoilerType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        BOILER_TYPE_UNSPECIFIED: _ClassVar[EquipmentSettingsTrait.BoilerType]
        BOILER_TYPE_COMBI: _ClassVar[EquipmentSettingsTrait.BoilerType]
        BOILER_TYPE_SYSTEM: _ClassVar[EquipmentSettingsTrait.BoilerType]
        BOILER_TYPE_OTHER: _ClassVar[EquipmentSettingsTrait.BoilerType]
        BOILER_TYPE_HEAT_PUMP: _ClassVar[EquipmentSettingsTrait.BoilerType]
        BOILER_TYPE_DISTRICT: _ClassVar[EquipmentSettingsTrait.BoilerType]
        BOILER_TYPE_ELECTRIC: _ClassVar[EquipmentSettingsTrait.BoilerType]
    BOILER_TYPE_UNSPECIFIED: EquipmentSettingsTrait.BoilerType
    BOILER_TYPE_COMBI: EquipmentSettingsTrait.BoilerType
    BOILER_TYPE_SYSTEM: EquipmentSettingsTrait.BoilerType
    BOILER_TYPE_OTHER: EquipmentSettingsTrait.BoilerType
    BOILER_TYPE_HEAT_PUMP: EquipmentSettingsTrait.BoilerType
    BOILER_TYPE_DISTRICT: EquipmentSettingsTrait.BoilerType
    BOILER_TYPE_ELECTRIC: EquipmentSettingsTrait.BoilerType
    class VentilatorType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        VENTILATOR_TYPE_UNSPECIFIED: _ClassVar[EquipmentSettingsTrait.VentilatorType]
        VENTILATOR_TYPE_HRV: _ClassVar[EquipmentSettingsTrait.VentilatorType]
        VENTILATOR_TYPE_ERV: _ClassVar[EquipmentSettingsTrait.VentilatorType]
        VENTILATOR_TYPE_SUPPLY_ONLY: _ClassVar[EquipmentSettingsTrait.VentilatorType]
        VENTILATOR_TYPE_EXHAUST_ONLY: _ClassVar[EquipmentSettingsTrait.VentilatorType]
    VENTILATOR_TYPE_UNSPECIFIED: EquipmentSettingsTrait.VentilatorType
    VENTILATOR_TYPE_HRV: EquipmentSettingsTrait.VentilatorType
    VENTILATOR_TYPE_ERV: EquipmentSettingsTrait.VentilatorType
    VENTILATOR_TYPE_SUPPLY_ONLY: EquipmentSettingsTrait.VentilatorType
    VENTILATOR_TYPE_EXHAUST_ONLY: EquipmentSettingsTrait.VentilatorType
    HEATSTAGE1DELIVERY_FIELD_NUMBER: _ClassVar[int]
    HEATSTAGE2DELIVERY_FIELD_NUMBER: _ClassVar[int]
    HEATSTAGE3DELIVERY_FIELD_NUMBER: _ClassVar[int]
    HEATSTAGE1SOURCE_FIELD_NUMBER: _ClassVar[int]
    HEATSTAGE2SOURCE_FIELD_NUMBER: _ClassVar[int]
    HEATSTAGE3SOURCE_FIELD_NUMBER: _ClassVar[int]
    COOLINGSTAGE1DELIVERY_FIELD_NUMBER: _ClassVar[int]
    COOLINGSTAGE2DELIVERY_FIELD_NUMBER: _ClassVar[int]
    COOLINGSTAGE3DELIVERY_FIELD_NUMBER: _ClassVar[int]
    COOLINGSTAGE1SOURCE_FIELD_NUMBER: _ClassVar[int]
    COOLINGSTAGE2SOURCE_FIELD_NUMBER: _ClassVar[int]
    COOLINGSTAGE3SOURCE_FIELD_NUMBER: _ClassVar[int]
    ALTHEATSTAGE1DELIVERY_FIELD_NUMBER: _ClassVar[int]
    ALTHEATSTAGE2DELIVERY_FIELD_NUMBER: _ClassVar[int]
    ALTHEATSTAGE1SOURCE_FIELD_NUMBER: _ClassVar[int]
    ALTHEATSTAGE2SOURCE_FIELD_NUMBER: _ClassVar[int]
    AUXHEATSTAGE1DELIVERY_FIELD_NUMBER: _ClassVar[int]
    AUXHEATSTAGE1SOURCE_FIELD_NUMBER: _ClassVar[int]
    EMERGENCYHEATDELIVERY_FIELD_NUMBER: _ClassVar[int]
    EMERGENCYHEATSOURCE_FIELD_NUMBER: _ClassVar[int]
    STARTYPE_FIELD_NUMBER: _ClassVar[int]
    Y2TYPE_FIELD_NUMBER: _ClassVar[int]
    DEHUMIDIFIERFANACTIVATION_FIELD_NUMBER: _ClassVar[int]
    DEHUMIDIFIERORIENTATIONSELECTED_FIELD_NUMBER: _ClassVar[int]
    DEHUMIDIFIERTYPE_FIELD_NUMBER: _ClassVar[int]
    HUMIDIFIERFANACTIVATION_FIELD_NUMBER: _ClassVar[int]
    HUMIDIFIERTYPE_FIELD_NUMBER: _ClassVar[int]
    DUALFUELSELECTED_FIELD_NUMBER: _ClassVar[int]
    DUALFUELBREAKPOINT_FIELD_NUMBER: _ClassVar[int]
    DUALFUELBREAKPOINTOVERRIDE_FIELD_NUMBER: _ClassVar[int]
    OBORIENTATION_FIELD_NUMBER: _ClassVar[int]
    OBPERSISTENCE_FIELD_NUMBER: _ClassVar[int]
    BOILERTYPE_FIELD_NUMBER: _ClassVar[int]
    BOILERSUPPLYTEMPERATURE_FIELD_NUMBER: _ClassVar[int]
    ACTIVATEFANIFHEATSOURCEISGAS_FIELD_NUMBER: _ClassVar[int]
    VENTILATORTYPE_FIELD_NUMBER: _ClassVar[int]
    VENTILATORREQUIRESFANACTIVATION_FIELD_NUMBER: _ClassVar[int]
    AQWIRETYPE_FIELD_NUMBER: _ClassVar[int]
    COMPRESSORMINCYCLETIME_FIELD_NUMBER: _ClassVar[int]
    COMPRESSORLOCKOUT_FIELD_NUMBER: _ClassVar[int]
    HEATMINCYCLETIME_FIELD_NUMBER: _ClassVar[int]
    heatStage1Delivery: EquipmentSettingsTrait.DeliveryType
    heatStage2Delivery: EquipmentSettingsTrait.DeliveryType
    heatStage3Delivery: EquipmentSettingsTrait.DeliveryType
    heatStage1Source: EquipmentSettingsTrait.FuelSourceType
    heatStage2Source: EquipmentSettingsTrait.FuelSourceType
    heatStage3Source: EquipmentSettingsTrait.FuelSourceType
    coolingStage1Delivery: EquipmentSettingsTrait.DeliveryType
    coolingStage2Delivery: EquipmentSettingsTrait.DeliveryType
    coolingStage3Delivery: EquipmentSettingsTrait.DeliveryType
    coolingStage1Source: EquipmentSettingsTrait.FuelSourceType
    coolingStage2Source: EquipmentSettingsTrait.FuelSourceType
    coolingStage3Source: EquipmentSettingsTrait.FuelSourceType
    altHeatStage1Delivery: EquipmentSettingsTrait.DeliveryType
    altHeatStage2Delivery: EquipmentSettingsTrait.DeliveryType
    altHeatStage1Source: EquipmentSettingsTrait.FuelSourceType
    altHeatStage2Source: EquipmentSettingsTrait.FuelSourceType
    auxHeatStage1Delivery: EquipmentSettingsTrait.DeliveryType
    auxHeatStage1Source: EquipmentSettingsTrait.FuelSourceType
    emergencyHeatDelivery: EquipmentSettingsTrait.DeliveryType
    emergencyHeatSource: EquipmentSettingsTrait.FuelSourceType
    starType: EquipmentSettingsTrait.StarType
    y2Type: EquipmentSettingsTrait.Y2Type
    dehumidifierFanActivation: EquipmentSettingsTrait.DehumidifierFanType
    dehumidifierOrientationSelected: EquipmentSettingsTrait.DehumidifierOrientation
    dehumidifierType: EquipmentSettingsTrait.DehumidifierType
    humidifierFanActivation: EquipmentSettingsTrait.HumidifierFanType
    humidifierType: EquipmentSettingsTrait.HumidifierType
    dualFuelSelected: EquipmentSettingsTrait.DualFuelSelection
    dualFuelBreakpoint: HvacControl.Temperature
    dualFuelBreakpointOverride: EquipmentSettingsTrait.DualFuelOverride
    obOrientation: EquipmentSettingsTrait.ObOrientation
    obPersistence: EquipmentSettingsTrait.ObPersistence
    boilerType: EquipmentSettingsTrait.BoilerType
    boilerSupplyTemperature: HvacControl.Temperature
    activateFanIfHeatSourceIsGas: bool
    ventilatorType: EquipmentSettingsTrait.VentilatorType
    ventilatorRequiresFanActivation: bool
    aqWireType: EquipmentSettingsTrait.AqWireType
    compressorMinCycleTime: _duration_pb2.Duration
    compressorLockout: _duration_pb2.Duration
    heatMinCycleTime: _duration_pb2.Duration
    def __init__(self, heatStage1Delivery: _Optional[_Union[EquipmentSettingsTrait.DeliveryType, str]] = ..., heatStage2Delivery: _Optional[_Union[EquipmentSettingsTrait.DeliveryType, str]] = ..., heatStage3Delivery: _Optional[_Union[EquipmentSettingsTrait.DeliveryType, str]] = ..., heatStage1Source: _Optional[_Union[EquipmentSettingsTrait.FuelSourceType, str]] = ..., heatStage2Source: _Optional[_Union[EquipmentSettingsTrait.FuelSourceType, str]] = ..., heatStage3Source: _Optional[_Union[EquipmentSettingsTrait.FuelSourceType, str]] = ..., coolingStage1Delivery: _Optional[_Union[EquipmentSettingsTrait.DeliveryType, str]] = ..., coolingStage2Delivery: _Optional[_Union[EquipmentSettingsTrait.DeliveryType, str]] = ..., coolingStage3Delivery: _Optional[_Union[EquipmentSettingsTrait.DeliveryType, str]] = ..., coolingStage1Source: _Optional[_Union[EquipmentSettingsTrait.FuelSourceType, str]] = ..., coolingStage2Source: _Optional[_Union[EquipmentSettingsTrait.FuelSourceType, str]] = ..., coolingStage3Source: _Optional[_Union[EquipmentSettingsTrait.FuelSourceType, str]] = ..., altHeatStage1Delivery: _Optional[_Union[EquipmentSettingsTrait.DeliveryType, str]] = ..., altHeatStage2Delivery: _Optional[_Union[EquipmentSettingsTrait.DeliveryType, str]] = ..., altHeatStage1Source: _Optional[_Union[EquipmentSettingsTrait.FuelSourceType, str]] = ..., altHeatStage2Source: _Optional[_Union[EquipmentSettingsTrait.FuelSourceType, str]] = ..., auxHeatStage1Delivery: _Optional[_Union[EquipmentSettingsTrait.DeliveryType, str]] = ..., auxHeatStage1Source: _Optional[_Union[EquipmentSettingsTrait.FuelSourceType, str]] = ..., emergencyHeatDelivery: _Optional[_Union[EquipmentSettingsTrait.DeliveryType, str]] = ..., emergencyHeatSource: _Optional[_Union[EquipmentSettingsTrait.FuelSourceType, str]] = ..., starType: _Optional[_Union[EquipmentSettingsTrait.StarType, str]] = ..., y2Type: _Optional[_Union[EquipmentSettingsTrait.Y2Type, str]] = ..., dehumidifierFanActivation: _Optional[_Union[EquipmentSettingsTrait.DehumidifierFanType, str]] = ..., dehumidifierOrientationSelected: _Optional[_Union[EquipmentSettingsTrait.DehumidifierOrientation, str]] = ..., dehumidifierType: _Optional[_Union[EquipmentSettingsTrait.DehumidifierType, str]] = ..., humidifierFanActivation: _Optional[_Union[EquipmentSettingsTrait.HumidifierFanType, str]] = ..., humidifierType: _Optional[_Union[EquipmentSettingsTrait.HumidifierType, str]] = ..., dualFuelSelected: _Optional[_Union[EquipmentSettingsTrait.DualFuelSelection, str]] = ..., dualFuelBreakpoint: _Optional[_Union[HvacControl.Temperature, _Mapping]] = ..., dualFuelBreakpointOverride: _Optional[_Union[EquipmentSettingsTrait.DualFuelOverride, str]] = ..., obOrientation: _Optional[_Union[EquipmentSettingsTrait.ObOrientation, str]] = ..., obPersistence: _Optional[_Union[EquipmentSettingsTrait.ObPersistence, str]] = ..., boilerType: _Optional[_Union[EquipmentSettingsTrait.BoilerType, str]] = ..., boilerSupplyTemperature: _Optional[_Union[HvacControl.Temperature, _Mapping]] = ..., activateFanIfHeatSourceIsGas: bool = ..., ventilatorType: _Optional[_Union[EquipmentSettingsTrait.VentilatorType, str]] = ..., ventilatorRequiresFanActivation: bool = ..., aqWireType: _Optional[_Union[EquipmentSettingsTrait.AqWireType, str]] = ..., compressorMinCycleTime: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ..., compressorLockout: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ..., heatMinCycleTime: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ...) -> None: ...

class EnergyCaption(_message.Message):
    __slots__ = ()
    class InteractionBehavior(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        INTERACTION_BEHAVIOR_UNSPECIFIED: _ClassVar[EnergyCaption.InteractionBehavior]
        INTERACTION_BEHAVIOR_CONTINUE: _ClassVar[EnergyCaption.InteractionBehavior]
        INTERACTION_BEHAVIOR_SILENTLY_EXIT: _ClassVar[EnergyCaption.InteractionBehavior]
        INTERACTION_BEHAVIOR_CONFIRM_EXIT: _ClassVar[EnergyCaption.InteractionBehavior]
    INTERACTION_BEHAVIOR_UNSPECIFIED: EnergyCaption.InteractionBehavior
    INTERACTION_BEHAVIOR_CONTINUE: EnergyCaption.InteractionBehavior
    INTERACTION_BEHAVIOR_SILENTLY_EXIT: EnergyCaption.InteractionBehavior
    INTERACTION_BEHAVIOR_CONFIRM_EXIT: EnergyCaption.InteractionBehavior
    class AppUserIntent(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        APP_USER_INTENT_UNSPECIFIED: _ClassVar[EnergyCaption.AppUserIntent]
        APP_USER_INTENT_INEFFICIENT_TEMPERATURE_CHANGE: _ClassVar[EnergyCaption.AppUserIntent]
        APP_USER_INTENT_MODE_CHANGE: _ClassVar[EnergyCaption.AppUserIntent]
        APP_USER_INTENT_USER_HOLD: _ClassVar[EnergyCaption.AppUserIntent]
    APP_USER_INTENT_UNSPECIFIED: EnergyCaption.AppUserIntent
    APP_USER_INTENT_INEFFICIENT_TEMPERATURE_CHANGE: EnergyCaption.AppUserIntent
    APP_USER_INTENT_MODE_CHANGE: EnergyCaption.AppUserIntent
    APP_USER_INTENT_USER_HOLD: EnergyCaption.AppUserIntent
    class AppSpeedBumpButtonAction(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        APP_SPEED_BUMP_BUTTON_ACTION_UNSPECIFIED: _ClassVar[EnergyCaption.AppSpeedBumpButtonAction]
        APP_SPEED_BUMP_BUTTON_ACTION_DISMISS: _ClassVar[EnergyCaption.AppSpeedBumpButtonAction]
        APP_SPEED_BUMP_BUTTON_ACTION_OPT_OUT_ENERGY_PROGRAM: _ClassVar[EnergyCaption.AppSpeedBumpButtonAction]
    APP_SPEED_BUMP_BUTTON_ACTION_UNSPECIFIED: EnergyCaption.AppSpeedBumpButtonAction
    APP_SPEED_BUMP_BUTTON_ACTION_DISMISS: EnergyCaption.AppSpeedBumpButtonAction
    APP_SPEED_BUMP_BUTTON_ACTION_OPT_OUT_ENERGY_PROGRAM: EnergyCaption.AppSpeedBumpButtonAction
    class ScheduleMessageType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        SCHEDULE_MESSAGE_TYPE_UNSPECIFIED: _ClassVar[EnergyCaption.ScheduleMessageType]
        SCHEDULE_MESSAGE_TYPE_ATOM_UPDATE: _ClassVar[EnergyCaption.ScheduleMessageType]
        SCHEDULE_MESSAGE_TYPE_SCHEDULE_ADD: _ClassVar[EnergyCaption.ScheduleMessageType]
        SCHEDULE_MESSAGE_TYPE_SCHEDULE_SHIFT: _ClassVar[EnergyCaption.ScheduleMessageType]
    SCHEDULE_MESSAGE_TYPE_UNSPECIFIED: EnergyCaption.ScheduleMessageType
    SCHEDULE_MESSAGE_TYPE_ATOM_UPDATE: EnergyCaption.ScheduleMessageType
    SCHEDULE_MESSAGE_TYPE_SCHEDULE_ADD: EnergyCaption.ScheduleMessageType
    SCHEDULE_MESSAGE_TYPE_SCHEDULE_SHIFT: EnergyCaption.ScheduleMessageType
    class EnergyProgramId(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        ENERGY_PROGRAM_ID_UNSPECIFIED: _ClassVar[EnergyCaption.EnergyProgramId]
        ENERGY_PROGRAM_ID_RUSH_HOUR_REWARDS: _ClassVar[EnergyCaption.EnergyProgramId]
        ENERGY_PROGRAM_ID_TIME_OF_USE: _ClassVar[EnergyCaption.EnergyProgramId]
        ENERGY_PROGRAM_ID_ENERGY_MANAGEMENT_FOR_EMISSIONS: _ClassVar[EnergyCaption.EnergyProgramId]
    ENERGY_PROGRAM_ID_UNSPECIFIED: EnergyCaption.EnergyProgramId
    ENERGY_PROGRAM_ID_RUSH_HOUR_REWARDS: EnergyCaption.EnergyProgramId
    ENERGY_PROGRAM_ID_TIME_OF_USE: EnergyCaption.EnergyProgramId
    ENERGY_PROGRAM_ID_ENERGY_MANAGEMENT_FOR_EMISSIONS: EnergyCaption.EnergyProgramId
    class EventPhase(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        EVENT_PHASE_UNSPECIFIED: _ClassVar[EnergyCaption.EventPhase]
        EVENT_PHASE_DEFAULT: _ClassVar[EnergyCaption.EventPhase]
        EVENT_PHASE_PRECONDITION: _ClassVar[EnergyCaption.EventPhase]
    EVENT_PHASE_UNSPECIFIED: EnergyCaption.EventPhase
    EVENT_PHASE_DEFAULT: EnergyCaption.EventPhase
    EVENT_PHASE_PRECONDITION: EnergyCaption.EventPhase
    class UxBehaviorConfiguration(_message.Message):
        __slots__ = ("speedbumpText", "speedbumpShortlinkCode", "onEfficientTemperatureChange", "onInefficientTemperatureChange", "onModeChange", "onAtomSelection", "onUserHold", "onEmergencyHeat")
        SPEEDBUMPTEXT_FIELD_NUMBER: _ClassVar[int]
        SPEEDBUMPSHORTLINKCODE_FIELD_NUMBER: _ClassVar[int]
        ONEFFICIENTTEMPERATURECHANGE_FIELD_NUMBER: _ClassVar[int]
        ONINEFFICIENTTEMPERATURECHANGE_FIELD_NUMBER: _ClassVar[int]
        ONMODECHANGE_FIELD_NUMBER: _ClassVar[int]
        ONATOMSELECTION_FIELD_NUMBER: _ClassVar[int]
        ONUSERHOLD_FIELD_NUMBER: _ClassVar[int]
        ONEMERGENCYHEAT_FIELD_NUMBER: _ClassVar[int]
        speedbumpText: str
        speedbumpShortlinkCode: str
        onEfficientTemperatureChange: EnergyCaption.InteractionBehavior
        onInefficientTemperatureChange: EnergyCaption.InteractionBehavior
        onModeChange: EnergyCaption.InteractionBehavior
        onAtomSelection: EnergyCaption.InteractionBehavior
        onUserHold: EnergyCaption.InteractionBehavior
        onEmergencyHeat: EnergyCaption.InteractionBehavior
        def __init__(self, speedbumpText: _Optional[str] = ..., speedbumpShortlinkCode: _Optional[str] = ..., onEfficientTemperatureChange: _Optional[_Union[EnergyCaption.InteractionBehavior, str]] = ..., onInefficientTemperatureChange: _Optional[_Union[EnergyCaption.InteractionBehavior, str]] = ..., onModeChange: _Optional[_Union[EnergyCaption.InteractionBehavior, str]] = ..., onAtomSelection: _Optional[_Union[EnergyCaption.InteractionBehavior, str]] = ..., onUserHold: _Optional[_Union[EnergyCaption.InteractionBehavior, str]] = ..., onEmergencyHeat: _Optional[_Union[EnergyCaption.InteractionBehavior, str]] = ...) -> None: ...
    class DeviceCaption(_message.Message):
        __slots__ = ("firstCaption", "secondCaption", "menuExplanation")
        FIRSTCAPTION_FIELD_NUMBER: _ClassVar[int]
        SECONDCAPTION_FIELD_NUMBER: _ClassVar[int]
        MENUEXPLANATION_FIELD_NUMBER: _ClassVar[int]
        firstCaption: str
        secondCaption: str
        menuExplanation: str
        def __init__(self, firstCaption: _Optional[str] = ..., secondCaption: _Optional[str] = ..., menuExplanation: _Optional[str] = ...) -> None: ...
    class AppCaption(_message.Message):
        __slots__ = ("caption", "bannerText", "speedBumps")
        CAPTION_FIELD_NUMBER: _ClassVar[int]
        BANNERTEXT_FIELD_NUMBER: _ClassVar[int]
        SPEEDBUMPS_FIELD_NUMBER: _ClassVar[int]
        caption: _ui_pb2.SoyMessage.SoyTemplateMessage
        bannerText: _ui_pb2.SoyMessage.SoyTemplateMessage
        speedBumps: _containers.RepeatedCompositeFieldContainer[EnergyCaption.AppSpeedBump]
        def __init__(self, caption: _Optional[_Union[_ui_pb2.SoyMessage.SoyTemplateMessage, _Mapping]] = ..., bannerText: _Optional[_Union[_ui_pb2.SoyMessage.SoyTemplateMessage, _Mapping]] = ..., speedBumps: _Optional[_Iterable[_Union[EnergyCaption.AppSpeedBump, _Mapping]]] = ...) -> None: ...
    class AppSpeedBump(_message.Message):
        __slots__ = ("userIntents", "iconUrl", "title", "description", "learnMoreUrl", "helpCenterContext", "primaryButton", "secondaryButton")
        USERINTENTS_FIELD_NUMBER: _ClassVar[int]
        ICONURL_FIELD_NUMBER: _ClassVar[int]
        TITLE_FIELD_NUMBER: _ClassVar[int]
        DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
        LEARNMOREURL_FIELD_NUMBER: _ClassVar[int]
        HELPCENTERCONTEXT_FIELD_NUMBER: _ClassVar[int]
        PRIMARYBUTTON_FIELD_NUMBER: _ClassVar[int]
        SECONDARYBUTTON_FIELD_NUMBER: _ClassVar[int]
        userIntents: _containers.RepeatedScalarFieldContainer[EnergyCaption.AppUserIntent]
        iconUrl: str
        title: _ui_pb2.SoyMessage.SoyTemplateMessage
        description: _ui_pb2.SoyMessage.SoyTemplateMessage
        learnMoreUrl: str
        helpCenterContext: str
        primaryButton: EnergyCaption.AppSpeedBumpButton
        secondaryButton: EnergyCaption.AppSpeedBumpButton
        def __init__(self, userIntents: _Optional[_Iterable[_Union[EnergyCaption.AppUserIntent, str]]] = ..., iconUrl: _Optional[str] = ..., title: _Optional[_Union[_ui_pb2.SoyMessage.SoyTemplateMessage, _Mapping]] = ..., description: _Optional[_Union[_ui_pb2.SoyMessage.SoyTemplateMessage, _Mapping]] = ..., learnMoreUrl: _Optional[str] = ..., helpCenterContext: _Optional[str] = ..., primaryButton: _Optional[_Union[EnergyCaption.AppSpeedBumpButton, _Mapping]] = ..., secondaryButton: _Optional[_Union[EnergyCaption.AppSpeedBumpButton, _Mapping]] = ...) -> None: ...
    class AppSpeedBumpButton(_message.Message):
        __slots__ = ("text", "action")
        TEXT_FIELD_NUMBER: _ClassVar[int]
        ACTION_FIELD_NUMBER: _ClassVar[int]
        text: _ui_pb2.SoyMessage.SoyTemplateMessage
        action: EnergyCaption.AppSpeedBumpButtonAction
        def __init__(self, text: _Optional[_Union[_ui_pb2.SoyMessage.SoyTemplateMessage, _Mapping]] = ..., action: _Optional[_Union[EnergyCaption.AppSpeedBumpButtonAction, str]] = ...) -> None: ...
    class UxConfiguration(_message.Message):
        __slots__ = ("icon", "deviceCaption", "appCaption", "behavior")
        ICON_FIELD_NUMBER: _ClassVar[int]
        DEVICECAPTION_FIELD_NUMBER: _ClassVar[int]
        APPCAPTION_FIELD_NUMBER: _ClassVar[int]
        BEHAVIOR_FIELD_NUMBER: _ClassVar[int]
        icon: HvacMessageCenterConfig.Icon
        deviceCaption: EnergyCaption.DeviceCaption
        appCaption: EnergyCaption.AppCaption
        behavior: EnergyCaption.UxBehaviorConfiguration
        def __init__(self, icon: _Optional[_Union[HvacMessageCenterConfig.Icon, str]] = ..., deviceCaption: _Optional[_Union[EnergyCaption.DeviceCaption, _Mapping]] = ..., appCaption: _Optional[_Union[EnergyCaption.AppCaption, _Mapping]] = ..., behavior: _Optional[_Union[EnergyCaption.UxBehaviorConfiguration, _Mapping]] = ...) -> None: ...
    class ScheduleMessage(_message.Message):
        __slots__ = ("id", "daysOfWeek", "startTimeOfDay", "duration", "atomId", "uxConfig", "endOfLife", "type")
        ID_FIELD_NUMBER: _ClassVar[int]
        DAYSOFWEEK_FIELD_NUMBER: _ClassVar[int]
        STARTTIMEOFDAY_FIELD_NUMBER: _ClassVar[int]
        DURATION_FIELD_NUMBER: _ClassVar[int]
        ATOMID_FIELD_NUMBER: _ClassVar[int]
        UXCONFIG_FIELD_NUMBER: _ClassVar[int]
        ENDOFLIFE_FIELD_NUMBER: _ClassVar[int]
        TYPE_FIELD_NUMBER: _ClassVar[int]
        id: int
        daysOfWeek: _containers.RepeatedScalarFieldContainer[_common_pb2.DayOfWeek]
        startTimeOfDay: _common_pb2.TimeOfDay
        duration: _duration_pb2.Duration
        atomId: int
        uxConfig: EnergyCaption.UxConfiguration
        endOfLife: _timestamp_pb2.Timestamp
        type: EnergyCaption.ScheduleMessageType
        def __init__(self, id: _Optional[int] = ..., daysOfWeek: _Optional[_Iterable[_Union[_common_pb2.DayOfWeek, str]]] = ..., startTimeOfDay: _Optional[_Union[_common_pb2.TimeOfDay, _Mapping]] = ..., duration: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ..., atomId: _Optional[int] = ..., uxConfig: _Optional[_Union[EnergyCaption.UxConfiguration, _Mapping]] = ..., endOfLife: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., type: _Optional[_Union[EnergyCaption.ScheduleMessageType, str]] = ...) -> None: ...
    class PhaseConfiguration(_message.Message):
        __slots__ = ("id", "designation", "uxConfig")
        ID_FIELD_NUMBER: _ClassVar[int]
        DESIGNATION_FIELD_NUMBER: _ClassVar[int]
        UXCONFIG_FIELD_NUMBER: _ClassVar[int]
        id: int
        designation: EnergyCaption.EventPhase
        uxConfig: EnergyCaption.UxConfiguration
        def __init__(self, id: _Optional[int] = ..., designation: _Optional[_Union[EnergyCaption.EventPhase, str]] = ..., uxConfig: _Optional[_Union[EnergyCaption.UxConfiguration, _Mapping]] = ...) -> None: ...
    class EnergyProgram(_message.Message):
        __slots__ = ("id", "canonicalProgram", "phases")
        class PhasesEntry(_message.Message):
            __slots__ = ("key", "value")
            KEY_FIELD_NUMBER: _ClassVar[int]
            VALUE_FIELD_NUMBER: _ClassVar[int]
            key: int
            value: EnergyCaption.PhaseConfiguration
            def __init__(self, key: _Optional[int] = ..., value: _Optional[_Union[EnergyCaption.PhaseConfiguration, _Mapping]] = ...) -> None: ...
        ID_FIELD_NUMBER: _ClassVar[int]
        CANONICALPROGRAM_FIELD_NUMBER: _ClassVar[int]
        PHASES_FIELD_NUMBER: _ClassVar[int]
        id: int
        canonicalProgram: EnergyCaption.EnergyProgramId
        phases: _containers.MessageMap[int, EnergyCaption.PhaseConfiguration]
        def __init__(self, id: _Optional[int] = ..., canonicalProgram: _Optional[_Union[EnergyCaption.EnergyProgramId, str]] = ..., phases: _Optional[_Mapping[int, EnergyCaption.PhaseConfiguration]] = ...) -> None: ...
    class EventMetadata(_message.Message):
        __slots__ = ("programId", "phaseId", "eventId", "isCritical", "optOutTimeout", "deviceCaptionOverride")
        PROGRAMID_FIELD_NUMBER: _ClassVar[int]
        PHASEID_FIELD_NUMBER: _ClassVar[int]
        EVENTID_FIELD_NUMBER: _ClassVar[int]
        ISCRITICAL_FIELD_NUMBER: _ClassVar[int]
        OPTOUTTIMEOUT_FIELD_NUMBER: _ClassVar[int]
        DEVICECAPTIONOVERRIDE_FIELD_NUMBER: _ClassVar[int]
        programId: int
        phaseId: int
        eventId: str
        isCritical: bool
        optOutTimeout: _timestamp_pb2.Timestamp
        deviceCaptionOverride: EnergyCaption.DeviceCaption
        def __init__(self, programId: _Optional[int] = ..., phaseId: _Optional[int] = ..., eventId: _Optional[str] = ..., isCritical: bool = ..., optOutTimeout: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., deviceCaptionOverride: _Optional[_Union[EnergyCaption.DeviceCaption, _Mapping]] = ...) -> None: ...
    def __init__(self) -> None: ...

class RemoteComfortSensingStateTrait(_message.Message):
    __slots__ = ("rcsCapable", "multiSensorTemperature", "rcsSensorInsights", "rcsThermostatAlerts", "rcsSensorStatuses", "rcsFailsafeState")
    class RcsSensorInsightTemperature(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        RCS_SENSOR_INSIGHT_TEMPERATURE_UNSPECIFIED: _ClassVar[RemoteComfortSensingStateTrait.RcsSensorInsightTemperature]
        RCS_SENSOR_INSIGHT_TEMPERATURE_WARMEST_AND_SWINGS: _ClassVar[RemoteComfortSensingStateTrait.RcsSensorInsightTemperature]
        RCS_SENSOR_INSIGHT_TEMPERATURE_WARMEST: _ClassVar[RemoteComfortSensingStateTrait.RcsSensorInsightTemperature]
        RCS_SENSOR_INSIGHT_TEMPERATURE_WARMER_AND_SWINGS: _ClassVar[RemoteComfortSensingStateTrait.RcsSensorInsightTemperature]
        RCS_SENSOR_INSIGHT_TEMPERATURE_WARMER: _ClassVar[RemoteComfortSensingStateTrait.RcsSensorInsightTemperature]
        RCS_SENSOR_INSIGHT_TEMPERATURE_COOLEST_AND_SWINGS: _ClassVar[RemoteComfortSensingStateTrait.RcsSensorInsightTemperature]
        RCS_SENSOR_INSIGHT_TEMPERATURE_COOLEST: _ClassVar[RemoteComfortSensingStateTrait.RcsSensorInsightTemperature]
        RCS_SENSOR_INSIGHT_TEMPERATURE_COOLER_AND_SWINGS: _ClassVar[RemoteComfortSensingStateTrait.RcsSensorInsightTemperature]
        RCS_SENSOR_INSIGHT_TEMPERATURE_COOLER: _ClassVar[RemoteComfortSensingStateTrait.RcsSensorInsightTemperature]
        RCS_SENSOR_INSIGHT_TEMPERATURE_SWINGS: _ClassVar[RemoteComfortSensingStateTrait.RcsSensorInsightTemperature]
        RCS_SENSOR_INSIGHT_TEMPERATURE_SIMILAR: _ClassVar[RemoteComfortSensingStateTrait.RcsSensorInsightTemperature]
    RCS_SENSOR_INSIGHT_TEMPERATURE_UNSPECIFIED: RemoteComfortSensingStateTrait.RcsSensorInsightTemperature
    RCS_SENSOR_INSIGHT_TEMPERATURE_WARMEST_AND_SWINGS: RemoteComfortSensingStateTrait.RcsSensorInsightTemperature
    RCS_SENSOR_INSIGHT_TEMPERATURE_WARMEST: RemoteComfortSensingStateTrait.RcsSensorInsightTemperature
    RCS_SENSOR_INSIGHT_TEMPERATURE_WARMER_AND_SWINGS: RemoteComfortSensingStateTrait.RcsSensorInsightTemperature
    RCS_SENSOR_INSIGHT_TEMPERATURE_WARMER: RemoteComfortSensingStateTrait.RcsSensorInsightTemperature
    RCS_SENSOR_INSIGHT_TEMPERATURE_COOLEST_AND_SWINGS: RemoteComfortSensingStateTrait.RcsSensorInsightTemperature
    RCS_SENSOR_INSIGHT_TEMPERATURE_COOLEST: RemoteComfortSensingStateTrait.RcsSensorInsightTemperature
    RCS_SENSOR_INSIGHT_TEMPERATURE_COOLER_AND_SWINGS: RemoteComfortSensingStateTrait.RcsSensorInsightTemperature
    RCS_SENSOR_INSIGHT_TEMPERATURE_COOLER: RemoteComfortSensingStateTrait.RcsSensorInsightTemperature
    RCS_SENSOR_INSIGHT_TEMPERATURE_SWINGS: RemoteComfortSensingStateTrait.RcsSensorInsightTemperature
    RCS_SENSOR_INSIGHT_TEMPERATURE_SIMILAR: RemoteComfortSensingStateTrait.RcsSensorInsightTemperature
    class RcsSensorInsightControllability(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        RCS_SENSOR_INSIGHT_CONTROLLABILITY_UNSPECIFIED: _ClassVar[RemoteComfortSensingStateTrait.RcsSensorInsightControllability]
        RCS_SENSOR_INSIGHT_CONTROLLABILITY_TYPICAL: _ClassVar[RemoteComfortSensingStateTrait.RcsSensorInsightControllability]
        RCS_SENSOR_INSIGHT_CONTROLLABILITY_UNRESPONSIVE_TO_HVAC: _ClassVar[RemoteComfortSensingStateTrait.RcsSensorInsightControllability]
        RCS_SENSOR_INSIGHT_CONTROLLABILITY_INTERMITTENTLY_STALE: _ClassVar[RemoteComfortSensingStateTrait.RcsSensorInsightControllability]
    RCS_SENSOR_INSIGHT_CONTROLLABILITY_UNSPECIFIED: RemoteComfortSensingStateTrait.RcsSensorInsightControllability
    RCS_SENSOR_INSIGHT_CONTROLLABILITY_TYPICAL: RemoteComfortSensingStateTrait.RcsSensorInsightControllability
    RCS_SENSOR_INSIGHT_CONTROLLABILITY_UNRESPONSIVE_TO_HVAC: RemoteComfortSensingStateTrait.RcsSensorInsightControllability
    RCS_SENSOR_INSIGHT_CONTROLLABILITY_INTERMITTENTLY_STALE: RemoteComfortSensingStateTrait.RcsSensorInsightControllability
    class SensorDataRecency(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        SENSOR_DATA_RECENCY_UNSPECIFIED: _ClassVar[RemoteComfortSensingStateTrait.SensorDataRecency]
        SENSOR_DATA_RECENCY_OK: _ClassVar[RemoteComfortSensingStateTrait.SensorDataRecency]
        SENSOR_DATA_RECENCY_STALE: _ClassVar[RemoteComfortSensingStateTrait.SensorDataRecency]
        SENSOR_DATA_RECENCY_EXTREMELY_STALE: _ClassVar[RemoteComfortSensingStateTrait.SensorDataRecency]
        SENSOR_DATA_RECENCY_FAIRLY_STALE: _ClassVar[RemoteComfortSensingStateTrait.SensorDataRecency]
        SENSOR_DATA_RECENCY_WAITING_FOR_INITIAL_DATA: _ClassVar[RemoteComfortSensingStateTrait.SensorDataRecency]
    SENSOR_DATA_RECENCY_UNSPECIFIED: RemoteComfortSensingStateTrait.SensorDataRecency
    SENSOR_DATA_RECENCY_OK: RemoteComfortSensingStateTrait.SensorDataRecency
    SENSOR_DATA_RECENCY_STALE: RemoteComfortSensingStateTrait.SensorDataRecency
    SENSOR_DATA_RECENCY_EXTREMELY_STALE: RemoteComfortSensingStateTrait.SensorDataRecency
    SENSOR_DATA_RECENCY_FAIRLY_STALE: RemoteComfortSensingStateTrait.SensorDataRecency
    SENSOR_DATA_RECENCY_WAITING_FOR_INITIAL_DATA: RemoteComfortSensingStateTrait.SensorDataRecency
    class RcsThermostatAlert(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        RCS_THERMOSTAT_ALERT_UNSPECIFIED: _ClassVar[RemoteComfortSensingStateTrait.RcsThermostatAlert]
        RCS_THERMOSTAT_ALERT_TEMPERATURE_OVERSHOOT: _ClassVar[RemoteComfortSensingStateTrait.RcsThermostatAlert]
        RCS_THERMOSTAT_ALERT_EXCESSIVE_RUNTIME_HEAT: _ClassVar[RemoteComfortSensingStateTrait.RcsThermostatAlert]
        RCS_THERMOSTAT_ALERT_EXCESSIVE_RUNTIME_COOL: _ClassVar[RemoteComfortSensingStateTrait.RcsThermostatAlert]
        RCS_THERMOSTAT_ALERT_CONNECTIVITY_FAILSAFE: _ClassVar[RemoteComfortSensingStateTrait.RcsThermostatAlert]
    RCS_THERMOSTAT_ALERT_UNSPECIFIED: RemoteComfortSensingStateTrait.RcsThermostatAlert
    RCS_THERMOSTAT_ALERT_TEMPERATURE_OVERSHOOT: RemoteComfortSensingStateTrait.RcsThermostatAlert
    RCS_THERMOSTAT_ALERT_EXCESSIVE_RUNTIME_HEAT: RemoteComfortSensingStateTrait.RcsThermostatAlert
    RCS_THERMOSTAT_ALERT_EXCESSIVE_RUNTIME_COOL: RemoteComfortSensingStateTrait.RcsThermostatAlert
    RCS_THERMOSTAT_ALERT_CONNECTIVITY_FAILSAFE: RemoteComfortSensingStateTrait.RcsThermostatAlert
    class RcsSingleSensorFailsafeStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        RCS_SINGLE_SENSOR_FAILSAFE_STATUS_UNSPECIFIED: _ClassVar[RemoteComfortSensingStateTrait.RcsSingleSensorFailsafeStatus]
        RCS_SINGLE_SENSOR_FAILSAFE_STATUS_OK: _ClassVar[RemoteComfortSensingStateTrait.RcsSingleSensorFailsafeStatus]
        RCS_SINGLE_SENSOR_FAILSAFE_STATUS_DATA_STALE: _ClassVar[RemoteComfortSensingStateTrait.RcsSingleSensorFailsafeStatus]
        RCS_SINGLE_SENSOR_FAILSAFE_STATUS_WAITING_FOR_INITIAL_DATA: _ClassVar[RemoteComfortSensingStateTrait.RcsSingleSensorFailsafeStatus]
    RCS_SINGLE_SENSOR_FAILSAFE_STATUS_UNSPECIFIED: RemoteComfortSensingStateTrait.RcsSingleSensorFailsafeStatus
    RCS_SINGLE_SENSOR_FAILSAFE_STATUS_OK: RemoteComfortSensingStateTrait.RcsSingleSensorFailsafeStatus
    RCS_SINGLE_SENSOR_FAILSAFE_STATUS_DATA_STALE: RemoteComfortSensingStateTrait.RcsSingleSensorFailsafeStatus
    RCS_SINGLE_SENSOR_FAILSAFE_STATUS_WAITING_FOR_INITIAL_DATA: RemoteComfortSensingStateTrait.RcsSingleSensorFailsafeStatus
    class RcsSensorInsightsEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: int
        value: RemoteComfortSensingStateTrait.RcsSensorInsight
        def __init__(self, key: _Optional[int] = ..., value: _Optional[_Union[RemoteComfortSensingStateTrait.RcsSensorInsight, _Mapping]] = ...) -> None: ...
    class RcsSensorStatusesEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: int
        value: RemoteComfortSensingStateTrait.RcsSensorStatus
        def __init__(self, key: _Optional[int] = ..., value: _Optional[_Union[RemoteComfortSensingStateTrait.RcsSensorStatus, _Mapping]] = ...) -> None: ...
    class RcsSensorInsight(_message.Message):
        __slots__ = ("sensorId", "temperatureInsight", "controllabilityInsight")
        SENSORID_FIELD_NUMBER: _ClassVar[int]
        TEMPERATUREINSIGHT_FIELD_NUMBER: _ClassVar[int]
        CONTROLLABILITYINSIGHT_FIELD_NUMBER: _ClassVar[int]
        sensorId: _common_pb2.ResourceId
        temperatureInsight: RemoteComfortSensingStateTrait.RcsSensorInsightTemperature
        controllabilityInsight: RemoteComfortSensingStateTrait.RcsSensorInsightControllability
        def __init__(self, sensorId: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ..., temperatureInsight: _Optional[_Union[RemoteComfortSensingStateTrait.RcsSensorInsightTemperature, str]] = ..., controllabilityInsight: _Optional[_Union[RemoteComfortSensingStateTrait.RcsSensorInsightControllability, str]] = ...) -> None: ...
    class RcsSensorStatus(_message.Message):
        __slots__ = ("sensorId", "dataRecency")
        SENSORID_FIELD_NUMBER: _ClassVar[int]
        DATARECENCY_FIELD_NUMBER: _ClassVar[int]
        sensorId: _common_pb2.ResourceId
        dataRecency: RemoteComfortSensingStateTrait.SensorDataRecency
        def __init__(self, sensorId: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ..., dataRecency: _Optional[_Union[RemoteComfortSensingStateTrait.SensorDataRecency, str]] = ...) -> None: ...
    class RcsFailsafeState(_message.Message):
        __slots__ = ("singleSensorStatus", "effectiveActiveRcsSelection")
        SINGLESENSORSTATUS_FIELD_NUMBER: _ClassVar[int]
        EFFECTIVEACTIVERCSSELECTION_FIELD_NUMBER: _ClassVar[int]
        singleSensorStatus: RemoteComfortSensingStateTrait.RcsSingleSensorFailsafeStatus
        effectiveActiveRcsSelection: RemoteComfortSensingSettingsTrait.RcsSourceSelection
        def __init__(self, singleSensorStatus: _Optional[_Union[RemoteComfortSensingStateTrait.RcsSingleSensorFailsafeStatus, str]] = ..., effectiveActiveRcsSelection: _Optional[_Union[RemoteComfortSensingSettingsTrait.RcsSourceSelection, _Mapping]] = ...) -> None: ...
    class RcsThermostatAlertEvent(_message.Message):
        __slots__ = ("rcsThermostatAlerts",)
        RCSTHERMOSTATALERTS_FIELD_NUMBER: _ClassVar[int]
        rcsThermostatAlerts: _containers.RepeatedScalarFieldContainer[RemoteComfortSensingStateTrait.RcsThermostatAlert]
        def __init__(self, rcsThermostatAlerts: _Optional[_Iterable[_Union[RemoteComfortSensingStateTrait.RcsThermostatAlert, str]]] = ...) -> None: ...
    class RcsDataRecencyStateChangeEvent(_message.Message):
        __slots__ = ("sensorId", "currentDataRecency", "priorDataRecency")
        SENSORID_FIELD_NUMBER: _ClassVar[int]
        CURRENTDATARECENCY_FIELD_NUMBER: _ClassVar[int]
        PRIORDATARECENCY_FIELD_NUMBER: _ClassVar[int]
        sensorId: _common_pb2.ResourceId
        currentDataRecency: RemoteComfortSensingStateTrait.SensorDataRecency
        priorDataRecency: RemoteComfortSensingStateTrait.SensorDataRecency
        def __init__(self, sensorId: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ..., currentDataRecency: _Optional[_Union[RemoteComfortSensingStateTrait.SensorDataRecency, str]] = ..., priorDataRecency: _Optional[_Union[RemoteComfortSensingStateTrait.SensorDataRecency, str]] = ...) -> None: ...
    class RcsTemperatureOvershootAlertEvent(_message.Message):
        __slots__ = ("sensorId", "priorIsOvershoot", "currentIsOvershoot")
        SENSORID_FIELD_NUMBER: _ClassVar[int]
        PRIORISOVERSHOOT_FIELD_NUMBER: _ClassVar[int]
        CURRENTISOVERSHOOT_FIELD_NUMBER: _ClassVar[int]
        sensorId: _common_pb2.ResourceId
        priorIsOvershoot: bool
        currentIsOvershoot: bool
        def __init__(self, sensorId: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ..., priorIsOvershoot: bool = ..., currentIsOvershoot: bool = ...) -> None: ...
    class ExcessiveRuntimeAlertEvent(_message.Message):
        __slots__ = ("sensorIds", "alert")
        SENSORIDS_FIELD_NUMBER: _ClassVar[int]
        ALERT_FIELD_NUMBER: _ClassVar[int]
        sensorIds: _containers.RepeatedCompositeFieldContainer[_common_pb2.ResourceId]
        alert: RemoteComfortSensingStateTrait.RcsThermostatAlert
        def __init__(self, sensorIds: _Optional[_Iterable[_Union[_common_pb2.ResourceId, _Mapping]]] = ..., alert: _Optional[_Union[RemoteComfortSensingStateTrait.RcsThermostatAlert, str]] = ...) -> None: ...
    class ConnectivityFailsafeAlertEvent(_message.Message):
        __slots__ = ("sensorIds", "alert")
        SENSORIDS_FIELD_NUMBER: _ClassVar[int]
        ALERT_FIELD_NUMBER: _ClassVar[int]
        sensorIds: _containers.RepeatedCompositeFieldContainer[_common_pb2.ResourceId]
        alert: RemoteComfortSensingStateTrait.RcsThermostatAlert
        def __init__(self, sensorIds: _Optional[_Iterable[_Union[_common_pb2.ResourceId, _Mapping]]] = ..., alert: _Optional[_Union[RemoteComfortSensingStateTrait.RcsThermostatAlert, str]] = ...) -> None: ...
    RCSCAPABLE_FIELD_NUMBER: _ClassVar[int]
    MULTISENSORTEMPERATURE_FIELD_NUMBER: _ClassVar[int]
    RCSSENSORINSIGHTS_FIELD_NUMBER: _ClassVar[int]
    RCSTHERMOSTATALERTS_FIELD_NUMBER: _ClassVar[int]
    RCSSENSORSTATUSES_FIELD_NUMBER: _ClassVar[int]
    RCSFAILSAFESTATE_FIELD_NUMBER: _ClassVar[int]
    rcsCapable: bool
    multiSensorTemperature: _sensor_pb2.TemperatureTrait.TemperatureSample
    rcsSensorInsights: _containers.MessageMap[int, RemoteComfortSensingStateTrait.RcsSensorInsight]
    rcsThermostatAlerts: _containers.RepeatedScalarFieldContainer[RemoteComfortSensingStateTrait.RcsThermostatAlert]
    rcsSensorStatuses: _containers.MessageMap[int, RemoteComfortSensingStateTrait.RcsSensorStatus]
    rcsFailsafeState: RemoteComfortSensingStateTrait.RcsFailsafeState
    def __init__(self, rcsCapable: bool = ..., multiSensorTemperature: _Optional[_Union[_sensor_pb2.TemperatureTrait.TemperatureSample, _Mapping]] = ..., rcsSensorInsights: _Optional[_Mapping[int, RemoteComfortSensingStateTrait.RcsSensorInsight]] = ..., rcsThermostatAlerts: _Optional[_Iterable[_Union[RemoteComfortSensingStateTrait.RcsThermostatAlert, str]]] = ..., rcsSensorStatuses: _Optional[_Mapping[int, RemoteComfortSensingStateTrait.RcsSensorStatus]] = ..., rcsFailsafeState: _Optional[_Union[RemoteComfortSensingStateTrait.RcsFailsafeState, _Mapping]] = ...) -> None: ...

class SetPointScheduleSettingsTrait(_message.Message):
    __slots__ = ("name", "type", "setpoints")
    class SetPointScheduleType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        SET_POINT_SCHEDULE_TYPE_UNSPECIFIED: _ClassVar[SetPointScheduleSettingsTrait.SetPointScheduleType]
        SET_POINT_SCHEDULE_TYPE_HEAT: _ClassVar[SetPointScheduleSettingsTrait.SetPointScheduleType]
        SET_POINT_SCHEDULE_TYPE_COOL: _ClassVar[SetPointScheduleSettingsTrait.SetPointScheduleType]
        SET_POINT_SCHEDULE_TYPE_RANGE: _ClassVar[SetPointScheduleSettingsTrait.SetPointScheduleType]
    SET_POINT_SCHEDULE_TYPE_UNSPECIFIED: SetPointScheduleSettingsTrait.SetPointScheduleType
    SET_POINT_SCHEDULE_TYPE_HEAT: SetPointScheduleSettingsTrait.SetPointScheduleType
    SET_POINT_SCHEDULE_TYPE_COOL: SetPointScheduleSettingsTrait.SetPointScheduleType
    SET_POINT_SCHEDULE_TYPE_RANGE: SetPointScheduleSettingsTrait.SetPointScheduleType
    class SetPointType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        SET_POINT_TYPE_UNSPECIFIED: _ClassVar[SetPointScheduleSettingsTrait.SetPointType]
        SET_POINT_TYPE_HEAT: _ClassVar[SetPointScheduleSettingsTrait.SetPointType]
        SET_POINT_TYPE_COOL: _ClassVar[SetPointScheduleSettingsTrait.SetPointType]
        SET_POINT_TYPE_RANGE: _ClassVar[SetPointScheduleSettingsTrait.SetPointType]
    SET_POINT_TYPE_UNSPECIFIED: SetPointScheduleSettingsTrait.SetPointType
    SET_POINT_TYPE_HEAT: SetPointScheduleSettingsTrait.SetPointType
    SET_POINT_TYPE_COOL: SetPointScheduleSettingsTrait.SetPointType
    SET_POINT_TYPE_RANGE: SetPointScheduleSettingsTrait.SetPointType
    class SetpointsEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: int
        value: SetPointScheduleSettingsTrait.TemperatureSetPoint
        def __init__(self, key: _Optional[int] = ..., value: _Optional[_Union[SetPointScheduleSettingsTrait.TemperatureSetPoint, _Mapping]] = ...) -> None: ...
    class TemperatureSetPoint(_message.Message):
        __slots__ = ("setpointType", "dayOfWeek", "secondsInDay", "heatingTarget", "coolingTarget", "currentActorInfo", "originalActorInfo")
        SETPOINTTYPE_FIELD_NUMBER: _ClassVar[int]
        DAYOFWEEK_FIELD_NUMBER: _ClassVar[int]
        SECONDSINDAY_FIELD_NUMBER: _ClassVar[int]
        HEATINGTARGET_FIELD_NUMBER: _ClassVar[int]
        COOLINGTARGET_FIELD_NUMBER: _ClassVar[int]
        CURRENTACTORINFO_FIELD_NUMBER: _ClassVar[int]
        ORIGINALACTORINFO_FIELD_NUMBER: _ClassVar[int]
        setpointType: SetPointScheduleSettingsTrait.SetPointType
        dayOfWeek: _common_pb2.DayOfWeek
        secondsInDay: int
        heatingTarget: HvacControl.Temperature
        coolingTarget: HvacControl.Temperature
        currentActorInfo: HvacActor.HvacActorStruct
        originalActorInfo: HvacActor.HvacActorStruct
        def __init__(self, setpointType: _Optional[_Union[SetPointScheduleSettingsTrait.SetPointType, str]] = ..., dayOfWeek: _Optional[_Union[_common_pb2.DayOfWeek, str]] = ..., secondsInDay: _Optional[int] = ..., heatingTarget: _Optional[_Union[HvacControl.Temperature, _Mapping]] = ..., coolingTarget: _Optional[_Union[HvacControl.Temperature, _Mapping]] = ..., currentActorInfo: _Optional[_Union[HvacActor.HvacActorStruct, _Mapping]] = ..., originalActorInfo: _Optional[_Union[HvacActor.HvacActorStruct, _Mapping]] = ...) -> None: ...
    NAME_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    SETPOINTS_FIELD_NUMBER: _ClassVar[int]
    name: str
    type: SetPointScheduleSettingsTrait.SetPointScheduleType
    setpoints: _containers.MessageMap[int, SetPointScheduleSettingsTrait.TemperatureSetPoint]
    def __init__(self, name: _Optional[str] = ..., type: _Optional[_Union[SetPointScheduleSettingsTrait.SetPointScheduleType, str]] = ..., setpoints: _Optional[_Mapping[int, SetPointScheduleSettingsTrait.TemperatureSetPoint]] = ...) -> None: ...

class SeasonalSavingsSettingsTrait(_message.Message):
    __slots__ = ("eventGuid", "setPointType", "qualStartTimeLocal", "qualStopTimeLocal", "afterglowSeconds", "pausedExpirationSeconds", "forceIgnoreBlackoutTimes", "stages", "partnerName", "season", "campaignId", "debugName", "rtsState", "rtsActualResultsStageIndex", "rtsRequestedAction", "rtsStopReason", "rtsVersion", "rtsType")
    class SeasonalSavingsAnchorType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        SEASONAL_SAVINGS_ANCHOR_TYPE_UNSPECIFIED: _ClassVar[SeasonalSavingsSettingsTrait.SeasonalSavingsAnchorType]
        SEASONAL_SAVINGS_ANCHOR_TYPE_WAKEUP: _ClassVar[SeasonalSavingsSettingsTrait.SeasonalSavingsAnchorType]
        SEASONAL_SAVINGS_ANCHOR_TYPE_EVENING_RETURN: _ClassVar[SeasonalSavingsSettingsTrait.SeasonalSavingsAnchorType]
        SEASONAL_SAVINGS_ANCHOR_TYPE_BED_TIME: _ClassVar[SeasonalSavingsSettingsTrait.SeasonalSavingsAnchorType]
        SEASONAL_SAVINGS_ANCHOR_TYPE_MORNING_LEAVE: _ClassVar[SeasonalSavingsSettingsTrait.SeasonalSavingsAnchorType]
        SEASONAL_SAVINGS_ANCHOR_TYPE_FIXED: _ClassVar[SeasonalSavingsSettingsTrait.SeasonalSavingsAnchorType]
    SEASONAL_SAVINGS_ANCHOR_TYPE_UNSPECIFIED: SeasonalSavingsSettingsTrait.SeasonalSavingsAnchorType
    SEASONAL_SAVINGS_ANCHOR_TYPE_WAKEUP: SeasonalSavingsSettingsTrait.SeasonalSavingsAnchorType
    SEASONAL_SAVINGS_ANCHOR_TYPE_EVENING_RETURN: SeasonalSavingsSettingsTrait.SeasonalSavingsAnchorType
    SEASONAL_SAVINGS_ANCHOR_TYPE_BED_TIME: SeasonalSavingsSettingsTrait.SeasonalSavingsAnchorType
    SEASONAL_SAVINGS_ANCHOR_TYPE_MORNING_LEAVE: SeasonalSavingsSettingsTrait.SeasonalSavingsAnchorType
    SEASONAL_SAVINGS_ANCHOR_TYPE_FIXED: SeasonalSavingsSettingsTrait.SeasonalSavingsAnchorType
    class SeasonalSavingsPunishmentCarry(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        SEASONAL_SAVINGS_PUNISHMENT_CARRY_UNSPECIFIED: _ClassVar[SeasonalSavingsSettingsTrait.SeasonalSavingsPunishmentCarry]
        SEASONAL_SAVINGS_PUNISHMENT_CARRY_DO_NOT_CARRY: _ClassVar[SeasonalSavingsSettingsTrait.SeasonalSavingsPunishmentCarry]
        SEASONAL_SAVINGS_PUNISHMENT_CARRY_SAME_NAME: _ClassVar[SeasonalSavingsSettingsTrait.SeasonalSavingsPunishmentCarry]
        SEASONAL_SAVINGS_PUNISHMENT_CARRY_SUM_ALL: _ClassVar[SeasonalSavingsSettingsTrait.SeasonalSavingsPunishmentCarry]
    SEASONAL_SAVINGS_PUNISHMENT_CARRY_UNSPECIFIED: SeasonalSavingsSettingsTrait.SeasonalSavingsPunishmentCarry
    SEASONAL_SAVINGS_PUNISHMENT_CARRY_DO_NOT_CARRY: SeasonalSavingsSettingsTrait.SeasonalSavingsPunishmentCarry
    SEASONAL_SAVINGS_PUNISHMENT_CARRY_SAME_NAME: SeasonalSavingsSettingsTrait.SeasonalSavingsPunishmentCarry
    SEASONAL_SAVINGS_PUNISHMENT_CARRY_SUM_ALL: SeasonalSavingsSettingsTrait.SeasonalSavingsPunishmentCarry
    class SeasonalSavingsSetpointDirection(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        SEASONAL_SAVINGS_SETPOINT_DIRECTION_UNSPECIFIED: _ClassVar[SeasonalSavingsSettingsTrait.SeasonalSavingsSetpointDirection]
        SEASONAL_SAVINGS_SETPOINT_DIRECTION_VISIBLY_DOWNWARD: _ClassVar[SeasonalSavingsSettingsTrait.SeasonalSavingsSetpointDirection]
        SEASONAL_SAVINGS_SETPOINT_DIRECTION_NONVISIBLY_DOWNWARD: _ClassVar[SeasonalSavingsSettingsTrait.SeasonalSavingsSetpointDirection]
        SEASONAL_SAVINGS_SETPOINT_DIRECTION_EQUAL: _ClassVar[SeasonalSavingsSettingsTrait.SeasonalSavingsSetpointDirection]
        SEASONAL_SAVINGS_SETPOINT_DIRECTION_VISIBLY_UPWARD: _ClassVar[SeasonalSavingsSettingsTrait.SeasonalSavingsSetpointDirection]
        SEASONAL_SAVINGS_SETPOINT_DIRECTION_NONVISIBLY_UPWARD: _ClassVar[SeasonalSavingsSettingsTrait.SeasonalSavingsSetpointDirection]
    SEASONAL_SAVINGS_SETPOINT_DIRECTION_UNSPECIFIED: SeasonalSavingsSettingsTrait.SeasonalSavingsSetpointDirection
    SEASONAL_SAVINGS_SETPOINT_DIRECTION_VISIBLY_DOWNWARD: SeasonalSavingsSettingsTrait.SeasonalSavingsSetpointDirection
    SEASONAL_SAVINGS_SETPOINT_DIRECTION_NONVISIBLY_DOWNWARD: SeasonalSavingsSettingsTrait.SeasonalSavingsSetpointDirection
    SEASONAL_SAVINGS_SETPOINT_DIRECTION_EQUAL: SeasonalSavingsSettingsTrait.SeasonalSavingsSetpointDirection
    SEASONAL_SAVINGS_SETPOINT_DIRECTION_VISIBLY_UPWARD: SeasonalSavingsSettingsTrait.SeasonalSavingsSetpointDirection
    SEASONAL_SAVINGS_SETPOINT_DIRECTION_NONVISIBLY_UPWARD: SeasonalSavingsSettingsTrait.SeasonalSavingsSetpointDirection
    class SeasonalSavingsSeasonType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        SEASONAL_SAVINGS_SEASON_TYPE_UNSPECIFIED: _ClassVar[SeasonalSavingsSettingsTrait.SeasonalSavingsSeasonType]
        SEASONAL_SAVINGS_SEASON_TYPE_SUMMER: _ClassVar[SeasonalSavingsSettingsTrait.SeasonalSavingsSeasonType]
        SEASONAL_SAVINGS_SEASON_TYPE_WINTER: _ClassVar[SeasonalSavingsSettingsTrait.SeasonalSavingsSeasonType]
    SEASONAL_SAVINGS_SEASON_TYPE_UNSPECIFIED: SeasonalSavingsSettingsTrait.SeasonalSavingsSeasonType
    SEASONAL_SAVINGS_SEASON_TYPE_SUMMER: SeasonalSavingsSettingsTrait.SeasonalSavingsSeasonType
    SEASONAL_SAVINGS_SEASON_TYPE_WINTER: SeasonalSavingsSettingsTrait.SeasonalSavingsSeasonType
    class StagesEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: int
        value: SeasonalSavingsSettingsTrait.SeasonalSavingsStage
        def __init__(self, key: _Optional[int] = ..., value: _Optional[_Union[SeasonalSavingsSettingsTrait.SeasonalSavingsStage, _Mapping]] = ...) -> None: ...
    class SeasonalSavingsAnchor(_message.Message):
        __slots__ = ("startAnchor", "endAnchor", "startBeforeSeconds", "startAfterOffsetSeconds", "endBeforeOffsetSeconds", "endAfterOffsetSeconds", "startDelayAfterWrongDirectionSeconds", "startDelayAfterAnchorTimeSeconds", "endDelayBeforeWrongDirectionSeconds", "endDelayBeforeAnchorTimeSeconds")
        STARTANCHOR_FIELD_NUMBER: _ClassVar[int]
        ENDANCHOR_FIELD_NUMBER: _ClassVar[int]
        STARTBEFORESECONDS_FIELD_NUMBER: _ClassVar[int]
        STARTAFTEROFFSETSECONDS_FIELD_NUMBER: _ClassVar[int]
        ENDBEFOREOFFSETSECONDS_FIELD_NUMBER: _ClassVar[int]
        ENDAFTEROFFSETSECONDS_FIELD_NUMBER: _ClassVar[int]
        STARTDELAYAFTERWRONGDIRECTIONSECONDS_FIELD_NUMBER: _ClassVar[int]
        STARTDELAYAFTERANCHORTIMESECONDS_FIELD_NUMBER: _ClassVar[int]
        ENDDELAYBEFOREWRONGDIRECTIONSECONDS_FIELD_NUMBER: _ClassVar[int]
        ENDDELAYBEFOREANCHORTIMESECONDS_FIELD_NUMBER: _ClassVar[int]
        startAnchor: SeasonalSavingsSettingsTrait.SeasonalSavingsAnchorType
        endAnchor: SeasonalSavingsSettingsTrait.SeasonalSavingsAnchorType
        startBeforeSeconds: int
        startAfterOffsetSeconds: int
        endBeforeOffsetSeconds: int
        endAfterOffsetSeconds: int
        startDelayAfterWrongDirectionSeconds: int
        startDelayAfterAnchorTimeSeconds: int
        endDelayBeforeWrongDirectionSeconds: int
        endDelayBeforeAnchorTimeSeconds: int
        def __init__(self, startAnchor: _Optional[_Union[SeasonalSavingsSettingsTrait.SeasonalSavingsAnchorType, str]] = ..., endAnchor: _Optional[_Union[SeasonalSavingsSettingsTrait.SeasonalSavingsAnchorType, str]] = ..., startBeforeSeconds: _Optional[int] = ..., startAfterOffsetSeconds: _Optional[int] = ..., endBeforeOffsetSeconds: _Optional[int] = ..., endAfterOffsetSeconds: _Optional[int] = ..., startDelayAfterWrongDirectionSeconds: _Optional[int] = ..., startDelayAfterAnchorTimeSeconds: _Optional[int] = ..., endDelayBeforeWrongDirectionSeconds: _Optional[int] = ..., endDelayBeforeAnchorTimeSeconds: _Optional[int] = ...) -> None: ...
    class SeasonalSavingsPunishment(_message.Message):
        __slots__ = ("carryMode", "interstageCarryFactor", "intrastageCarryFactor", "strengthScheduleEdit", "strengthDialChange")
        CARRYMODE_FIELD_NUMBER: _ClassVar[int]
        INTERSTAGECARRYFACTOR_FIELD_NUMBER: _ClassVar[int]
        INTRASTAGECARRYFACTOR_FIELD_NUMBER: _ClassVar[int]
        STRENGTHSCHEDULEEDIT_FIELD_NUMBER: _ClassVar[int]
        STRENGTHDIALCHANGE_FIELD_NUMBER: _ClassVar[int]
        carryMode: SeasonalSavingsSettingsTrait.SeasonalSavingsPunishmentCarry
        interstageCarryFactor: float
        intrastageCarryFactor: float
        strengthScheduleEdit: float
        strengthDialChange: float
        def __init__(self, carryMode: _Optional[_Union[SeasonalSavingsSettingsTrait.SeasonalSavingsPunishmentCarry, str]] = ..., interstageCarryFactor: _Optional[float] = ..., intrastageCarryFactor: _Optional[float] = ..., strengthScheduleEdit: _Optional[float] = ..., strengthDialChange: _Optional[float] = ...) -> None: ...
    class SeasonalSavingsAlgoConstants(_message.Message):
        __slots__ = ("dailyTemperatureChange", "anchorDescription", "punishment", "blackoutDays", "forceVisibleChangeOnFirstday", "startSetpointDirectionMask", "endSetpointDirectionMask", "qualParameters")
        DAILYTEMPERATURECHANGE_FIELD_NUMBER: _ClassVar[int]
        ANCHORDESCRIPTION_FIELD_NUMBER: _ClassVar[int]
        PUNISHMENT_FIELD_NUMBER: _ClassVar[int]
        BLACKOUTDAYS_FIELD_NUMBER: _ClassVar[int]
        FORCEVISIBLECHANGEONFIRSTDAY_FIELD_NUMBER: _ClassVar[int]
        STARTSETPOINTDIRECTIONMASK_FIELD_NUMBER: _ClassVar[int]
        ENDSETPOINTDIRECTIONMASK_FIELD_NUMBER: _ClassVar[int]
        QUALPARAMETERS_FIELD_NUMBER: _ClassVar[int]
        dailyTemperatureChange: float
        anchorDescription: SeasonalSavingsSettingsTrait.SeasonalSavingsAnchor
        punishment: SeasonalSavingsSettingsTrait.SeasonalSavingsPunishment
        blackoutDays: _containers.RepeatedScalarFieldContainer[_common_pb2.DayOfWeek]
        forceVisibleChangeOnFirstday: bool
        startSetpointDirectionMask: _containers.RepeatedScalarFieldContainer[SeasonalSavingsSettingsTrait.SeasonalSavingsSetpointDirection]
        endSetpointDirectionMask: _containers.RepeatedScalarFieldContainer[SeasonalSavingsSettingsTrait.SeasonalSavingsSetpointDirection]
        qualParameters: SeasonalSavingsSettingsTrait.SeasonalSavingsQualificationParameters
        def __init__(self, dailyTemperatureChange: _Optional[float] = ..., anchorDescription: _Optional[_Union[SeasonalSavingsSettingsTrait.SeasonalSavingsAnchor, _Mapping]] = ..., punishment: _Optional[_Union[SeasonalSavingsSettingsTrait.SeasonalSavingsPunishment, _Mapping]] = ..., blackoutDays: _Optional[_Iterable[_Union[_common_pb2.DayOfWeek, str]]] = ..., forceVisibleChangeOnFirstday: bool = ..., startSetpointDirectionMask: _Optional[_Iterable[_Union[SeasonalSavingsSettingsTrait.SeasonalSavingsSetpointDirection, str]]] = ..., endSetpointDirectionMask: _Optional[_Iterable[_Union[SeasonalSavingsSettingsTrait.SeasonalSavingsSetpointDirection, str]]] = ..., qualParameters: _Optional[_Union[SeasonalSavingsSettingsTrait.SeasonalSavingsQualificationParameters, _Mapping]] = ...) -> None: ...
    class SeasonalSavingsQualificationParameters(_message.Message):
        __slots__ = ("minimumSavings", "minimumDailySetpoints", "dailyCoolingSecondsMaximum", "requireAutoawayEta", "nextdayForecastTemperatureMaximum", "nextdayForecastTemperatureMinimum", "maximumSavings", "dailyHeatingSecondsMaximum", "dailyHeatingSecondsMinimum", "minimumLearningState", "requireUsageWithinLimits", "minimumWeeklySetpoints", "requireForecast", "dailyCoolingSecondsMinimum")
        MINIMUMSAVINGS_FIELD_NUMBER: _ClassVar[int]
        MINIMUMDAILYSETPOINTS_FIELD_NUMBER: _ClassVar[int]
        DAILYCOOLINGSECONDSMAXIMUM_FIELD_NUMBER: _ClassVar[int]
        REQUIREAUTOAWAYETA_FIELD_NUMBER: _ClassVar[int]
        NEXTDAYFORECASTTEMPERATUREMAXIMUM_FIELD_NUMBER: _ClassVar[int]
        NEXTDAYFORECASTTEMPERATUREMINIMUM_FIELD_NUMBER: _ClassVar[int]
        MAXIMUMSAVINGS_FIELD_NUMBER: _ClassVar[int]
        DAILYHEATINGSECONDSMAXIMUM_FIELD_NUMBER: _ClassVar[int]
        DAILYHEATINGSECONDSMINIMUM_FIELD_NUMBER: _ClassVar[int]
        MINIMUMLEARNINGSTATE_FIELD_NUMBER: _ClassVar[int]
        REQUIREUSAGEWITHINLIMITS_FIELD_NUMBER: _ClassVar[int]
        MINIMUMWEEKLYSETPOINTS_FIELD_NUMBER: _ClassVar[int]
        REQUIREFORECAST_FIELD_NUMBER: _ClassVar[int]
        DAILYCOOLINGSECONDSMINIMUM_FIELD_NUMBER: _ClassVar[int]
        minimumSavings: int
        minimumDailySetpoints: int
        dailyCoolingSecondsMaximum: int
        requireAutoawayEta: bool
        nextdayForecastTemperatureMaximum: int
        nextdayForecastTemperatureMinimum: int
        maximumSavings: int
        dailyHeatingSecondsMaximum: int
        dailyHeatingSecondsMinimum: int
        minimumLearningState: str
        requireUsageWithinLimits: bool
        minimumWeeklySetpoints: int
        requireForecast: bool
        dailyCoolingSecondsMinimum: int
        def __init__(self, minimumSavings: _Optional[int] = ..., minimumDailySetpoints: _Optional[int] = ..., dailyCoolingSecondsMaximum: _Optional[int] = ..., requireAutoawayEta: bool = ..., nextdayForecastTemperatureMaximum: _Optional[int] = ..., nextdayForecastTemperatureMinimum: _Optional[int] = ..., maximumSavings: _Optional[int] = ..., dailyHeatingSecondsMaximum: _Optional[int] = ..., dailyHeatingSecondsMinimum: _Optional[int] = ..., minimumLearningState: _Optional[str] = ..., requireUsageWithinLimits: bool = ..., minimumWeeklySetpoints: _Optional[int] = ..., requireForecast: bool = ..., dailyCoolingSecondsMinimum: _Optional[int] = ...) -> None: ...
    class SeasonalSavingsStage(_message.Message):
        __slots__ = ("stageIndex", "expirationSeconds", "numberUpdates", "forceQualify", "algoConstants")
        STAGEINDEX_FIELD_NUMBER: _ClassVar[int]
        EXPIRATIONSECONDS_FIELD_NUMBER: _ClassVar[int]
        NUMBERUPDATES_FIELD_NUMBER: _ClassVar[int]
        FORCEQUALIFY_FIELD_NUMBER: _ClassVar[int]
        ALGOCONSTANTS_FIELD_NUMBER: _ClassVar[int]
        stageIndex: int
        expirationSeconds: int
        numberUpdates: int
        forceQualify: bool
        algoConstants: SeasonalSavingsSettingsTrait.SeasonalSavingsAlgoConstants
        def __init__(self, stageIndex: _Optional[int] = ..., expirationSeconds: _Optional[int] = ..., numberUpdates: _Optional[int] = ..., forceQualify: bool = ..., algoConstants: _Optional[_Union[SeasonalSavingsSettingsTrait.SeasonalSavingsAlgoConstants, _Mapping]] = ...) -> None: ...
    EVENTGUID_FIELD_NUMBER: _ClassVar[int]
    SETPOINTTYPE_FIELD_NUMBER: _ClassVar[int]
    QUALSTARTTIMELOCAL_FIELD_NUMBER: _ClassVar[int]
    QUALSTOPTIMELOCAL_FIELD_NUMBER: _ClassVar[int]
    AFTERGLOWSECONDS_FIELD_NUMBER: _ClassVar[int]
    PAUSEDEXPIRATIONSECONDS_FIELD_NUMBER: _ClassVar[int]
    FORCEIGNOREBLACKOUTTIMES_FIELD_NUMBER: _ClassVar[int]
    STAGES_FIELD_NUMBER: _ClassVar[int]
    PARTNERNAME_FIELD_NUMBER: _ClassVar[int]
    SEASON_FIELD_NUMBER: _ClassVar[int]
    CAMPAIGNID_FIELD_NUMBER: _ClassVar[int]
    DEBUGNAME_FIELD_NUMBER: _ClassVar[int]
    RTSSTATE_FIELD_NUMBER: _ClassVar[int]
    RTSACTUALRESULTSSTAGEINDEX_FIELD_NUMBER: _ClassVar[int]
    RTSREQUESTEDACTION_FIELD_NUMBER: _ClassVar[int]
    RTSSTOPREASON_FIELD_NUMBER: _ClassVar[int]
    RTSVERSION_FIELD_NUMBER: _ClassVar[int]
    RTSTYPE_FIELD_NUMBER: _ClassVar[int]
    eventGuid: str
    setPointType: SetPointScheduleSettingsTrait.SetPointType
    qualStartTimeLocal: _timestamp_pb2.Timestamp
    qualStopTimeLocal: _timestamp_pb2.Timestamp
    afterglowSeconds: int
    pausedExpirationSeconds: int
    forceIgnoreBlackoutTimes: bool
    stages: _containers.MessageMap[int, SeasonalSavingsSettingsTrait.SeasonalSavingsStage]
    partnerName: PartnerInformation.PartnerName
    season: SeasonalSavingsSettingsTrait.SeasonalSavingsSeasonType
    campaignId: str
    debugName: str
    rtsState: str
    rtsActualResultsStageIndex: int
    rtsRequestedAction: str
    rtsStopReason: str
    rtsVersion: str
    rtsType: str
    def __init__(self, eventGuid: _Optional[str] = ..., setPointType: _Optional[_Union[SetPointScheduleSettingsTrait.SetPointType, str]] = ..., qualStartTimeLocal: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., qualStopTimeLocal: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., afterglowSeconds: _Optional[int] = ..., pausedExpirationSeconds: _Optional[int] = ..., forceIgnoreBlackoutTimes: bool = ..., stages: _Optional[_Mapping[int, SeasonalSavingsSettingsTrait.SeasonalSavingsStage]] = ..., partnerName: _Optional[_Union[PartnerInformation.PartnerName, _Mapping]] = ..., season: _Optional[_Union[SeasonalSavingsSettingsTrait.SeasonalSavingsSeasonType, str]] = ..., campaignId: _Optional[str] = ..., debugName: _Optional[str] = ..., rtsState: _Optional[str] = ..., rtsActualResultsStageIndex: _Optional[int] = ..., rtsRequestedAction: _Optional[str] = ..., rtsStopReason: _Optional[str] = ..., rtsVersion: _Optional[str] = ..., rtsType: _Optional[str] = ...) -> None: ...

class DemandResponseTrait(_message.Message):
    __slots__ = ("stateItems",)
    class DemandResponseEventType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        DEMAND_RESPONSE_EVENT_TYPE_UNSPECIFIED: _ClassVar[DemandResponseTrait.DemandResponseEventType]
        DEMAND_RESPONSE_EVENT_TYPE_STANDARD: _ClassVar[DemandResponseTrait.DemandResponseEventType]
        DEMAND_RESPONSE_EVENT_TYPE_CRITICAL: _ClassVar[DemandResponseTrait.DemandResponseEventType]
    DEMAND_RESPONSE_EVENT_TYPE_UNSPECIFIED: DemandResponseTrait.DemandResponseEventType
    DEMAND_RESPONSE_EVENT_TYPE_STANDARD: DemandResponseTrait.DemandResponseEventType
    DEMAND_RESPONSE_EVENT_TYPE_CRITICAL: DemandResponseTrait.DemandResponseEventType
    class DemandResponseState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        DEMAND_RESPONSE_STATE_UNSPECIFIED: _ClassVar[DemandResponseTrait.DemandResponseState]
        DEMAND_RESPONSE_STATE_INITIAL: _ClassVar[DemandResponseTrait.DemandResponseState]
        DEMAND_RESPONSE_STATE_EVENT_RECEIVED: _ClassVar[DemandResponseTrait.DemandResponseState]
        DEMAND_RESPONSE_STATE_PRESENTING_EVENT: _ClassVar[DemandResponseTrait.DemandResponseState]
        DEMAND_RESPONSE_STATE_PRECONDITIONING: _ClassVar[DemandResponseTrait.DemandResponseState]
        DEMAND_RESPONSE_STATE_CRUISE_CONTROL: _ClassVar[DemandResponseTrait.DemandResponseState]
        DEMAND_RESPONSE_STATE_MANUAL_MODE: _ClassVar[DemandResponseTrait.DemandResponseState]
        DEMAND_RESPONSE_STATE_MANUAL_EFFICIENT: _ClassVar[DemandResponseTrait.DemandResponseState]
        DEMAND_RESPONSE_STATE_FINISHED: _ClassVar[DemandResponseTrait.DemandResponseState]
    DEMAND_RESPONSE_STATE_UNSPECIFIED: DemandResponseTrait.DemandResponseState
    DEMAND_RESPONSE_STATE_INITIAL: DemandResponseTrait.DemandResponseState
    DEMAND_RESPONSE_STATE_EVENT_RECEIVED: DemandResponseTrait.DemandResponseState
    DEMAND_RESPONSE_STATE_PRESENTING_EVENT: DemandResponseTrait.DemandResponseState
    DEMAND_RESPONSE_STATE_PRECONDITIONING: DemandResponseTrait.DemandResponseState
    DEMAND_RESPONSE_STATE_CRUISE_CONTROL: DemandResponseTrait.DemandResponseState
    DEMAND_RESPONSE_STATE_MANUAL_MODE: DemandResponseTrait.DemandResponseState
    DEMAND_RESPONSE_STATE_MANUAL_EFFICIENT: DemandResponseTrait.DemandResponseState
    DEMAND_RESPONSE_STATE_FINISHED: DemandResponseTrait.DemandResponseState
    class DemandResponseStopReason(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        DEMAND_RESPONSE_STOP_REASON_UNSPECIFIED: _ClassVar[DemandResponseTrait.DemandResponseStopReason]
        DEMAND_RESPONSE_STOP_REASON_TEMPERATURE_CHANGE: _ClassVar[DemandResponseTrait.DemandResponseStopReason]
        DEMAND_RESPONSE_STOP_REASON_MODE_CHANGE: _ClassVar[DemandResponseTrait.DemandResponseStopReason]
        DEMAND_RESPONSE_STOP_REASON_RECENT_EVENT: _ClassVar[DemandResponseTrait.DemandResponseStopReason]
        DEMAND_RESPONSE_STOP_REASON_COMPLETED: _ClassVar[DemandResponseTrait.DemandResponseStopReason]
        DEMAND_RESPONSE_STOP_REASON_BAD_PARAMETERS: _ClassVar[DemandResponseTrait.DemandResponseStopReason]
        DEMAND_RESPONSE_STOP_REASON_UNKNOWN: _ClassVar[DemandResponseTrait.DemandResponseStopReason]
        DEMAND_RESPONSE_STOP_REASON_KILLED_BEFORE_EVENT: _ClassVar[DemandResponseTrait.DemandResponseStopReason]
        DEMAND_RESPONSE_STOP_REASON_KILLED_DURING_EVENT: _ClassVar[DemandResponseTrait.DemandResponseStopReason]
        DEMAND_RESPONSE_STOP_REASON_RECEIVED_NEW_DR_BEFORE_EVENT: _ClassVar[DemandResponseTrait.DemandResponseStopReason]
        DEMAND_RESPONSE_STOP_REASON_RECEIVED_NEW_DR_DURING_EVENT: _ClassVar[DemandResponseTrait.DemandResponseStopReason]
        DEMAND_RESPONSE_STOP_REASON_RECEIVED_LATE: _ClassVar[DemandResponseTrait.DemandResponseStopReason]
        DEMAND_RESPONSE_STOP_REASON_WRONG_SCHEDULE_MODE_DURING_QUALIFICATION: _ClassVar[DemandResponseTrait.DemandResponseStopReason]
        DEMAND_RESPONSE_STOP_REASON_SYSTEM_OFF_DURING_QUALIFICATION: _ClassVar[DemandResponseTrait.DemandResponseStopReason]
        DEMAND_RESPONSE_STOP_REASON_WRONG_SCHEDULE_MODE_AT_EVENT_START: _ClassVar[DemandResponseTrait.DemandResponseStopReason]
        DEMAND_RESPONSE_STOP_REASON_SYSTEM_OFF_AT_EVENT_START: _ClassVar[DemandResponseTrait.DemandResponseStopReason]
        DEMAND_RESPONSE_STOP_REASON_SYSTEM_TURNED_OFF_DURING_EVENT: _ClassVar[DemandResponseTrait.DemandResponseStopReason]
        DEMAND_RESPONSE_STOP_REASON_OPT_OUT: _ClassVar[DemandResponseTrait.DemandResponseStopReason]
    DEMAND_RESPONSE_STOP_REASON_UNSPECIFIED: DemandResponseTrait.DemandResponseStopReason
    DEMAND_RESPONSE_STOP_REASON_TEMPERATURE_CHANGE: DemandResponseTrait.DemandResponseStopReason
    DEMAND_RESPONSE_STOP_REASON_MODE_CHANGE: DemandResponseTrait.DemandResponseStopReason
    DEMAND_RESPONSE_STOP_REASON_RECENT_EVENT: DemandResponseTrait.DemandResponseStopReason
    DEMAND_RESPONSE_STOP_REASON_COMPLETED: DemandResponseTrait.DemandResponseStopReason
    DEMAND_RESPONSE_STOP_REASON_BAD_PARAMETERS: DemandResponseTrait.DemandResponseStopReason
    DEMAND_RESPONSE_STOP_REASON_UNKNOWN: DemandResponseTrait.DemandResponseStopReason
    DEMAND_RESPONSE_STOP_REASON_KILLED_BEFORE_EVENT: DemandResponseTrait.DemandResponseStopReason
    DEMAND_RESPONSE_STOP_REASON_KILLED_DURING_EVENT: DemandResponseTrait.DemandResponseStopReason
    DEMAND_RESPONSE_STOP_REASON_RECEIVED_NEW_DR_BEFORE_EVENT: DemandResponseTrait.DemandResponseStopReason
    DEMAND_RESPONSE_STOP_REASON_RECEIVED_NEW_DR_DURING_EVENT: DemandResponseTrait.DemandResponseStopReason
    DEMAND_RESPONSE_STOP_REASON_RECEIVED_LATE: DemandResponseTrait.DemandResponseStopReason
    DEMAND_RESPONSE_STOP_REASON_WRONG_SCHEDULE_MODE_DURING_QUALIFICATION: DemandResponseTrait.DemandResponseStopReason
    DEMAND_RESPONSE_STOP_REASON_SYSTEM_OFF_DURING_QUALIFICATION: DemandResponseTrait.DemandResponseStopReason
    DEMAND_RESPONSE_STOP_REASON_WRONG_SCHEDULE_MODE_AT_EVENT_START: DemandResponseTrait.DemandResponseStopReason
    DEMAND_RESPONSE_STOP_REASON_SYSTEM_OFF_AT_EVENT_START: DemandResponseTrait.DemandResponseStopReason
    DEMAND_RESPONSE_STOP_REASON_SYSTEM_TURNED_OFF_DURING_EVENT: DemandResponseTrait.DemandResponseStopReason
    DEMAND_RESPONSE_STOP_REASON_OPT_OUT: DemandResponseTrait.DemandResponseStopReason
    class DemandResponseProgramType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        DEMAND_RESPONSE_PROGRAM_TYPE_UNSPECIFIED: _ClassVar[DemandResponseTrait.DemandResponseProgramType]
        DEMAND_RESPONSE_PROGRAM_TYPE_SUMMER_RUSH_HOUR_REWARDS: _ClassVar[DemandResponseTrait.DemandResponseProgramType]
        DEMAND_RESPONSE_PROGRAM_TYPE_WINTER_RUSH_HOUR_REWARDS: _ClassVar[DemandResponseTrait.DemandResponseProgramType]
    DEMAND_RESPONSE_PROGRAM_TYPE_UNSPECIFIED: DemandResponseTrait.DemandResponseProgramType
    DEMAND_RESPONSE_PROGRAM_TYPE_SUMMER_RUSH_HOUR_REWARDS: DemandResponseTrait.DemandResponseProgramType
    DEMAND_RESPONSE_PROGRAM_TYPE_WINTER_RUSH_HOUR_REWARDS: DemandResponseTrait.DemandResponseProgramType
    class StateItemsEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: int
        value: DemandResponseTrait.DemandResponseEventStateItem
        def __init__(self, key: _Optional[int] = ..., value: _Optional[_Union[DemandResponseTrait.DemandResponseEventStateItem, _Mapping]] = ...) -> None: ...
    class DemandResponseEventStateItem(_message.Message):
        __slots__ = ("eventGuid", "state", "cruiseControlTemperature", "optedOut", "inPeakPeriod", "stopReason", "requiredScheduleMode", "partnerName")
        EVENTGUID_FIELD_NUMBER: _ClassVar[int]
        STATE_FIELD_NUMBER: _ClassVar[int]
        CRUISECONTROLTEMPERATURE_FIELD_NUMBER: _ClassVar[int]
        OPTEDOUT_FIELD_NUMBER: _ClassVar[int]
        INPEAKPERIOD_FIELD_NUMBER: _ClassVar[int]
        STOPREASON_FIELD_NUMBER: _ClassVar[int]
        REQUIREDSCHEDULEMODE_FIELD_NUMBER: _ClassVar[int]
        PARTNERNAME_FIELD_NUMBER: _ClassVar[int]
        eventGuid: str
        state: DemandResponseTrait.DemandResponseState
        cruiseControlTemperature: HvacControl.Temperature
        optedOut: bool
        inPeakPeriod: bool
        stopReason: DemandResponseTrait.DemandResponseStopReason
        requiredScheduleMode: DemandResponseConfigurationTrait.DemandResponseRequiredScheduleMode
        partnerName: PartnerInformation.PartnerName
        def __init__(self, eventGuid: _Optional[str] = ..., state: _Optional[_Union[DemandResponseTrait.DemandResponseState, str]] = ..., cruiseControlTemperature: _Optional[_Union[HvacControl.Temperature, _Mapping]] = ..., optedOut: bool = ..., inPeakPeriod: bool = ..., stopReason: _Optional[_Union[DemandResponseTrait.DemandResponseStopReason, str]] = ..., requiredScheduleMode: _Optional[_Union[DemandResponseConfigurationTrait.DemandResponseRequiredScheduleMode, str]] = ..., partnerName: _Optional[_Union[PartnerInformation.PartnerName, _Mapping]] = ...) -> None: ...
    class DemandResponseStateChangedEvent(_message.Message):
        __slots__ = ("eventGuid", "eventType", "previousState", "currentState", "qualificationStartTimeUtc", "lengthEventSeconds", "startTimeUtc", "peakPeriodStartTimeUtc", "stopTimeUtc", "partnerName")
        EVENTGUID_FIELD_NUMBER: _ClassVar[int]
        EVENTTYPE_FIELD_NUMBER: _ClassVar[int]
        PREVIOUSSTATE_FIELD_NUMBER: _ClassVar[int]
        CURRENTSTATE_FIELD_NUMBER: _ClassVar[int]
        QUALIFICATIONSTARTTIMEUTC_FIELD_NUMBER: _ClassVar[int]
        LENGTHEVENTSECONDS_FIELD_NUMBER: _ClassVar[int]
        STARTTIMEUTC_FIELD_NUMBER: _ClassVar[int]
        PEAKPERIODSTARTTIMEUTC_FIELD_NUMBER: _ClassVar[int]
        STOPTIMEUTC_FIELD_NUMBER: _ClassVar[int]
        PARTNERNAME_FIELD_NUMBER: _ClassVar[int]
        eventGuid: str
        eventType: DemandResponseTrait.DemandResponseEventType
        previousState: DemandResponseTrait.DemandResponseState
        currentState: DemandResponseTrait.DemandResponseState
        qualificationStartTimeUtc: _timestamp_pb2.Timestamp
        lengthEventSeconds: int
        startTimeUtc: _timestamp_pb2.Timestamp
        peakPeriodStartTimeUtc: _timestamp_pb2.Timestamp
        stopTimeUtc: _timestamp_pb2.Timestamp
        partnerName: PartnerInformation.PartnerName
        def __init__(self, eventGuid: _Optional[str] = ..., eventType: _Optional[_Union[DemandResponseTrait.DemandResponseEventType, str]] = ..., previousState: _Optional[_Union[DemandResponseTrait.DemandResponseState, str]] = ..., currentState: _Optional[_Union[DemandResponseTrait.DemandResponseState, str]] = ..., qualificationStartTimeUtc: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., lengthEventSeconds: _Optional[int] = ..., startTimeUtc: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., peakPeriodStartTimeUtc: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., stopTimeUtc: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., partnerName: _Optional[_Union[PartnerInformation.PartnerName, _Mapping]] = ...) -> None: ...
    class DemandResponsePreStartNotificationEvent(_message.Message):
        __slots__ = ("eventId", "partnerId", "partnerName", "eventType", "programType")
        EVENTID_FIELD_NUMBER: _ClassVar[int]
        PARTNERID_FIELD_NUMBER: _ClassVar[int]
        PARTNERNAME_FIELD_NUMBER: _ClassVar[int]
        EVENTTYPE_FIELD_NUMBER: _ClassVar[int]
        PROGRAMTYPE_FIELD_NUMBER: _ClassVar[int]
        eventId: str
        partnerId: str
        partnerName: PartnerInformation.PartnerName
        eventType: DemandResponseTrait.DemandResponseEventType
        programType: DemandResponseTrait.DemandResponseProgramType
        def __init__(self, eventId: _Optional[str] = ..., partnerId: _Optional[str] = ..., partnerName: _Optional[_Union[PartnerInformation.PartnerName, _Mapping]] = ..., eventType: _Optional[_Union[DemandResponseTrait.DemandResponseEventType, str]] = ..., programType: _Optional[_Union[DemandResponseTrait.DemandResponseProgramType, str]] = ...) -> None: ...
    class DemandResponseFinishedEvent(_message.Message):
        __slots__ = ("eventId", "preconditioningPeriodStartTime", "preconditioningPeriodEndTime", "peakPeriodStartTime", "peakPeriodEndTime", "stopReason")
        EVENTID_FIELD_NUMBER: _ClassVar[int]
        PRECONDITIONINGPERIODSTARTTIME_FIELD_NUMBER: _ClassVar[int]
        PRECONDITIONINGPERIODENDTIME_FIELD_NUMBER: _ClassVar[int]
        PEAKPERIODSTARTTIME_FIELD_NUMBER: _ClassVar[int]
        PEAKPERIODENDTIME_FIELD_NUMBER: _ClassVar[int]
        STOPREASON_FIELD_NUMBER: _ClassVar[int]
        eventId: str
        preconditioningPeriodStartTime: _timestamp_pb2.Timestamp
        preconditioningPeriodEndTime: _timestamp_pb2.Timestamp
        peakPeriodStartTime: _timestamp_pb2.Timestamp
        peakPeriodEndTime: _timestamp_pb2.Timestamp
        stopReason: DemandResponseTrait.DemandResponseStopReason
        def __init__(self, eventId: _Optional[str] = ..., preconditioningPeriodStartTime: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., preconditioningPeriodEndTime: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., peakPeriodStartTime: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., peakPeriodEndTime: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., stopReason: _Optional[_Union[DemandResponseTrait.DemandResponseStopReason, str]] = ...) -> None: ...
    STATEITEMS_FIELD_NUMBER: _ClassVar[int]
    stateItems: _containers.MessageMap[int, DemandResponseTrait.DemandResponseEventStateItem]
    def __init__(self, stateItems: _Optional[_Mapping[int, DemandResponseTrait.DemandResponseEventStateItem]] = ...) -> None: ...

class HvacActor(_message.Message):
    __slots__ = ()
    class HvacActorMethod(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        HVAC_ACTOR_METHOD_UNSPECIFIED: _ClassVar[HvacActor.HvacActorMethod]
        HVAC_ACTOR_METHOD_NOBODY: _ClassVar[HvacActor.HvacActorMethod]
        HVAC_ACTOR_METHOD_SCHEDULE_LEARNING: _ClassVar[HvacActor.HvacActorMethod]
        HVAC_ACTOR_METHOD_LOCAL: _ClassVar[HvacActor.HvacActorMethod]
        HVAC_ACTOR_METHOD_REMOTE: _ClassVar[HvacActor.HvacActorMethod]
        HVAC_ACTOR_METHOD_WEB: _ClassVar[HvacActor.HvacActorMethod]
        HVAC_ACTOR_METHOD_ANDROID: _ClassVar[HvacActor.HvacActorMethod]
        HVAC_ACTOR_METHOD_IOS: _ClassVar[HvacActor.HvacActorMethod]
        HVAC_ACTOR_METHOD_SEASONAL_SAVINGS: _ClassVar[HvacActor.HvacActorMethod]
        HVAC_ACTOR_METHOD_RUSH_HOUR_REWARDS: _ClassVar[HvacActor.HvacActorMethod]
        HVAC_ACTOR_METHOD_TIME_OF_USE: _ClassVar[HvacActor.HvacActorMethod]
        HVAC_ACTOR_METHOD_DEMAND_CHARGE: _ClassVar[HvacActor.HvacActorMethod]
        HVAC_ACTOR_METHOD_TOPAZ_CO: _ClassVar[HvacActor.HvacActorMethod]
        HVAC_ACTOR_METHOD_TOPAZ_SMOKE: _ClassVar[HvacActor.HvacActorMethod]
        HVAC_ACTOR_METHOD_QUICK_SCHEDULE: _ClassVar[HvacActor.HvacActorMethod]
        HVAC_ACTOR_METHOD_WORKS_WITH_NEST: _ClassVar[HvacActor.HvacActorMethod]
        HVAC_ACTOR_METHOD_AMBER_PROGRAMMER: _ClassVar[HvacActor.HvacActorMethod]
        HVAC_ACTOR_METHOD_GOOGLE_ASSISTANT: _ClassVar[HvacActor.HvacActorMethod]
        HVAC_ACTOR_METHOD_SMART_DEVICE_MANAGEMENT: _ClassVar[HvacActor.HvacActorMethod]
        HVAC_ACTOR_METHOD_GOOGLE_ENERGY: _ClassVar[HvacActor.HvacActorMethod]
        HVAC_ACTOR_METHOD_MATTER: _ClassVar[HvacActor.HvacActorMethod]
        HVAC_ACTOR_METHOD_ENERGY_CAPTION: _ClassVar[HvacActor.HvacActorMethod]
        HVAC_ACTOR_METHOD_GOOGLE_ASSISTANT_SCHEDULED_ROUTINE: _ClassVar[HvacActor.HvacActorMethod]
    HVAC_ACTOR_METHOD_UNSPECIFIED: HvacActor.HvacActorMethod
    HVAC_ACTOR_METHOD_NOBODY: HvacActor.HvacActorMethod
    HVAC_ACTOR_METHOD_SCHEDULE_LEARNING: HvacActor.HvacActorMethod
    HVAC_ACTOR_METHOD_LOCAL: HvacActor.HvacActorMethod
    HVAC_ACTOR_METHOD_REMOTE: HvacActor.HvacActorMethod
    HVAC_ACTOR_METHOD_WEB: HvacActor.HvacActorMethod
    HVAC_ACTOR_METHOD_ANDROID: HvacActor.HvacActorMethod
    HVAC_ACTOR_METHOD_IOS: HvacActor.HvacActorMethod
    HVAC_ACTOR_METHOD_SEASONAL_SAVINGS: HvacActor.HvacActorMethod
    HVAC_ACTOR_METHOD_RUSH_HOUR_REWARDS: HvacActor.HvacActorMethod
    HVAC_ACTOR_METHOD_TIME_OF_USE: HvacActor.HvacActorMethod
    HVAC_ACTOR_METHOD_DEMAND_CHARGE: HvacActor.HvacActorMethod
    HVAC_ACTOR_METHOD_TOPAZ_CO: HvacActor.HvacActorMethod
    HVAC_ACTOR_METHOD_TOPAZ_SMOKE: HvacActor.HvacActorMethod
    HVAC_ACTOR_METHOD_QUICK_SCHEDULE: HvacActor.HvacActorMethod
    HVAC_ACTOR_METHOD_WORKS_WITH_NEST: HvacActor.HvacActorMethod
    HVAC_ACTOR_METHOD_AMBER_PROGRAMMER: HvacActor.HvacActorMethod
    HVAC_ACTOR_METHOD_GOOGLE_ASSISTANT: HvacActor.HvacActorMethod
    HVAC_ACTOR_METHOD_SMART_DEVICE_MANAGEMENT: HvacActor.HvacActorMethod
    HVAC_ACTOR_METHOD_GOOGLE_ENERGY: HvacActor.HvacActorMethod
    HVAC_ACTOR_METHOD_MATTER: HvacActor.HvacActorMethod
    HVAC_ACTOR_METHOD_ENERGY_CAPTION: HvacActor.HvacActorMethod
    HVAC_ACTOR_METHOD_GOOGLE_ASSISTANT_SCHEDULED_ROUTINE: HvacActor.HvacActorMethod
    class HvacActorStruct(_message.Message):
        __slots__ = ("method", "originator", "timeOfAction", "originatorRtsId")
        METHOD_FIELD_NUMBER: _ClassVar[int]
        ORIGINATOR_FIELD_NUMBER: _ClassVar[int]
        TIMEOFACTION_FIELD_NUMBER: _ClassVar[int]
        ORIGINATORRTSID_FIELD_NUMBER: _ClassVar[int]
        method: HvacActor.HvacActorMethod
        originator: _common_pb2.ResourceId
        timeOfAction: _timestamp_pb2.Timestamp
        originatorRtsId: str
        def __init__(self, method: _Optional[_Union[HvacActor.HvacActorMethod, str]] = ..., originator: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ..., timeOfAction: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., originatorRtsId: _Optional[str] = ...) -> None: ...
    def __init__(self) -> None: ...

class FanControlTrait(_message.Message):
    __slots__ = ("currentSpeed", "userRequestedFanRunning", "ventilationState", "ventilationAlert", "fanSpeedState")
    class FanSpeedSetting(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        FAN_SPEED_SETTING_UNSPECIFIED: _ClassVar[FanControlTrait.FanSpeedSetting]
        FAN_SPEED_SETTING_STAGE1: _ClassVar[FanControlTrait.FanSpeedSetting]
        FAN_SPEED_SETTING_STAGE2: _ClassVar[FanControlTrait.FanSpeedSetting]
        FAN_SPEED_SETTING_STAGE3: _ClassVar[FanControlTrait.FanSpeedSetting]
        FAN_SPEED_SETTING_OFF: _ClassVar[FanControlTrait.FanSpeedSetting]
        FAN_SPEED_SETTING_AUTO: _ClassVar[FanControlTrait.FanSpeedSetting]
    FAN_SPEED_SETTING_UNSPECIFIED: FanControlTrait.FanSpeedSetting
    FAN_SPEED_SETTING_STAGE1: FanControlTrait.FanSpeedSetting
    FAN_SPEED_SETTING_STAGE2: FanControlTrait.FanSpeedSetting
    FAN_SPEED_SETTING_STAGE3: FanControlTrait.FanSpeedSetting
    FAN_SPEED_SETTING_OFF: FanControlTrait.FanSpeedSetting
    FAN_SPEED_SETTING_AUTO: FanControlTrait.FanSpeedSetting
    class FanSpeedState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        FAN_SPEED_STATE_UNSPECIFIED: _ClassVar[FanControlTrait.FanSpeedState]
        FAN_SPEED_STATE_OFF: _ClassVar[FanControlTrait.FanSpeedState]
        FAN_SPEED_STATE_TIMER: _ClassVar[FanControlTrait.FanSpeedState]
        FAN_SPEED_STATE_SCHEDULE: _ClassVar[FanControlTrait.FanSpeedState]
        FAN_SPEED_STATE_EQUIPMENT_ACTIVATION: _ClassVar[FanControlTrait.FanSpeedState]
        FAN_SPEED_STATE_VENTILATION_ACTIVATION: _ClassVar[FanControlTrait.FanSpeedState]
        FAN_SPEED_STATE_SYSTEM_TEST: _ClassVar[FanControlTrait.FanSpeedState]
    FAN_SPEED_STATE_UNSPECIFIED: FanControlTrait.FanSpeedState
    FAN_SPEED_STATE_OFF: FanControlTrait.FanSpeedState
    FAN_SPEED_STATE_TIMER: FanControlTrait.FanSpeedState
    FAN_SPEED_STATE_SCHEDULE: FanControlTrait.FanSpeedState
    FAN_SPEED_STATE_EQUIPMENT_ACTIVATION: FanControlTrait.FanSpeedState
    FAN_SPEED_STATE_VENTILATION_ACTIVATION: FanControlTrait.FanSpeedState
    FAN_SPEED_STATE_SYSTEM_TEST: FanControlTrait.FanSpeedState
    class VentilationState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        VENTILATION_STATE_UNSPECIFIED: _ClassVar[FanControlTrait.VentilationState]
        VENTILATION_STATE_OFF: _ClassVar[FanControlTrait.VentilationState]
        VENTILATION_STATE_TIMER: _ClassVar[FanControlTrait.VentilationState]
        VENTILATION_STATE_SCHEDULE: _ClassVar[FanControlTrait.VentilationState]
        VENTILATION_STATE_INDOOR_AIR_QUALITY: _ClassVar[FanControlTrait.VentilationState]
        VENTILATION_STATE_HEATING: _ClassVar[FanControlTrait.VentilationState]
        VENTILATION_STATE_COOLING: _ClassVar[FanControlTrait.VentilationState]
        VENTILATION_STATE_SYSTEM_TEST: _ClassVar[FanControlTrait.VentilationState]
    VENTILATION_STATE_UNSPECIFIED: FanControlTrait.VentilationState
    VENTILATION_STATE_OFF: FanControlTrait.VentilationState
    VENTILATION_STATE_TIMER: FanControlTrait.VentilationState
    VENTILATION_STATE_SCHEDULE: FanControlTrait.VentilationState
    VENTILATION_STATE_INDOOR_AIR_QUALITY: FanControlTrait.VentilationState
    VENTILATION_STATE_HEATING: FanControlTrait.VentilationState
    VENTILATION_STATE_COOLING: FanControlTrait.VentilationState
    VENTILATION_STATE_SYSTEM_TEST: FanControlTrait.VentilationState
    class VentilationAlert(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        VENTILATION_ALERT_UNSPECIFIED: _ClassVar[FanControlTrait.VentilationAlert]
        VENTILATION_ALERT_OK: _ClassVar[FanControlTrait.VentilationAlert]
        VENTILATION_ALERT_OUTDOOR_AIR_QUALITY: _ClassVar[FanControlTrait.VentilationAlert]
        VENTILATION_ALERT_INDOOR_AIR_QUALITY: _ClassVar[FanControlTrait.VentilationAlert]
    VENTILATION_ALERT_UNSPECIFIED: FanControlTrait.VentilationAlert
    VENTILATION_ALERT_OK: FanControlTrait.VentilationAlert
    VENTILATION_ALERT_OUTDOOR_AIR_QUALITY: FanControlTrait.VentilationAlert
    VENTILATION_ALERT_INDOOR_AIR_QUALITY: FanControlTrait.VentilationAlert
    class FanState(_message.Message):
        __slots__ = ("speed", "userRequestedFanRunning", "fanSpeedState")
        SPEED_FIELD_NUMBER: _ClassVar[int]
        USERREQUESTEDFANRUNNING_FIELD_NUMBER: _ClassVar[int]
        FANSPEEDSTATE_FIELD_NUMBER: _ClassVar[int]
        speed: FanControlTrait.FanSpeedSetting
        userRequestedFanRunning: bool
        fanSpeedState: FanControlTrait.FanSpeedState
        def __init__(self, speed: _Optional[_Union[FanControlTrait.FanSpeedSetting, str]] = ..., userRequestedFanRunning: bool = ..., fanSpeedState: _Optional[_Union[FanControlTrait.FanSpeedState, str]] = ...) -> None: ...
    class FanStateChangeEvent(_message.Message):
        __slots__ = ("fanState", "priorFanState")
        FANSTATE_FIELD_NUMBER: _ClassVar[int]
        PRIORFANSTATE_FIELD_NUMBER: _ClassVar[int]
        fanState: FanControlTrait.FanState
        priorFanState: FanControlTrait.FanState
        def __init__(self, fanState: _Optional[_Union[FanControlTrait.FanState, _Mapping]] = ..., priorFanState: _Optional[_Union[FanControlTrait.FanState, _Mapping]] = ...) -> None: ...
    class VentilationAlertChangeEvent(_message.Message):
        __slots__ = ("alert", "priorAlert")
        ALERT_FIELD_NUMBER: _ClassVar[int]
        PRIORALERT_FIELD_NUMBER: _ClassVar[int]
        alert: FanControlTrait.VentilationAlert
        priorAlert: FanControlTrait.VentilationAlert
        def __init__(self, alert: _Optional[_Union[FanControlTrait.VentilationAlert, str]] = ..., priorAlert: _Optional[_Union[FanControlTrait.VentilationAlert, str]] = ...) -> None: ...
    CURRENTSPEED_FIELD_NUMBER: _ClassVar[int]
    USERREQUESTEDFANRUNNING_FIELD_NUMBER: _ClassVar[int]
    VENTILATIONSTATE_FIELD_NUMBER: _ClassVar[int]
    VENTILATIONALERT_FIELD_NUMBER: _ClassVar[int]
    FANSPEEDSTATE_FIELD_NUMBER: _ClassVar[int]
    currentSpeed: FanControlTrait.FanSpeedSetting
    userRequestedFanRunning: bool
    ventilationState: FanControlTrait.VentilationState
    ventilationAlert: FanControlTrait.VentilationAlert
    fanSpeedState: FanControlTrait.FanSpeedState
    def __init__(self, currentSpeed: _Optional[_Union[FanControlTrait.FanSpeedSetting, str]] = ..., userRequestedFanRunning: bool = ..., ventilationState: _Optional[_Union[FanControlTrait.VentilationState, str]] = ..., ventilationAlert: _Optional[_Union[FanControlTrait.VentilationAlert, str]] = ..., fanSpeedState: _Optional[_Union[FanControlTrait.FanSpeedState, str]] = ...) -> None: ...

class DisplaySettingsTrait(_message.Message):
    __slots__ = ("farsightDisplay", "temperatureScale", "analogClockSettings", "digitalClockSettings", "customPanelSettings", "wakeOnRemoteTempChange", "farsightNearOnly", "farsightDismissOnVeryNear", "farsightAnalogClockSettings", "farsightDigitalClockSettings", "farsightWeatherSettings", "farsightTemperaturesSettings")
    class FarsightDisplay(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        FARSIGHT_DISPLAY_UNSPECIFIED: _ClassVar[DisplaySettingsTrait.FarsightDisplay]
        FARSIGHT_DISPLAY_TARGET_TEMP: _ClassVar[DisplaySettingsTrait.FarsightDisplay]
        FARSIGHT_DISPLAY_CURRENT_TEMP: _ClassVar[DisplaySettingsTrait.FarsightDisplay]
        FARSIGHT_DISPLAY_ANALOG_CLOCK: _ClassVar[DisplaySettingsTrait.FarsightDisplay]
        FARSIGHT_DISPLAY_DIGITAL_CLOCK: _ClassVar[DisplaySettingsTrait.FarsightDisplay]
        FARSIGHT_DISPLAY_WEATHER: _ClassVar[DisplaySettingsTrait.FarsightDisplay]
        FARSIGHT_DISPLAY_NONE: _ClassVar[DisplaySettingsTrait.FarsightDisplay]
        FARSIGHT_DISPLAY_CUSTOM_PANEL: _ClassVar[DisplaySettingsTrait.FarsightDisplay]
        FARSIGHT_DISPLAY_TEMPERATURES: _ClassVar[DisplaySettingsTrait.FarsightDisplay]
    FARSIGHT_DISPLAY_UNSPECIFIED: DisplaySettingsTrait.FarsightDisplay
    FARSIGHT_DISPLAY_TARGET_TEMP: DisplaySettingsTrait.FarsightDisplay
    FARSIGHT_DISPLAY_CURRENT_TEMP: DisplaySettingsTrait.FarsightDisplay
    FARSIGHT_DISPLAY_ANALOG_CLOCK: DisplaySettingsTrait.FarsightDisplay
    FARSIGHT_DISPLAY_DIGITAL_CLOCK: DisplaySettingsTrait.FarsightDisplay
    FARSIGHT_DISPLAY_WEATHER: DisplaySettingsTrait.FarsightDisplay
    FARSIGHT_DISPLAY_NONE: DisplaySettingsTrait.FarsightDisplay
    FARSIGHT_DISPLAY_CUSTOM_PANEL: DisplaySettingsTrait.FarsightDisplay
    FARSIGHT_DISPLAY_TEMPERATURES: DisplaySettingsTrait.FarsightDisplay
    class TemperatureScale(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        TEMPERATURE_SCALE_UNSPECIFIED: _ClassVar[DisplaySettingsTrait.TemperatureScale]
        TEMPERATURE_SCALE_C: _ClassVar[DisplaySettingsTrait.TemperatureScale]
        TEMPERATURE_SCALE_F: _ClassVar[DisplaySettingsTrait.TemperatureScale]
    TEMPERATURE_SCALE_UNSPECIFIED: DisplaySettingsTrait.TemperatureScale
    TEMPERATURE_SCALE_C: DisplaySettingsTrait.TemperatureScale
    TEMPERATURE_SCALE_F: DisplaySettingsTrait.TemperatureScale
    class CustomDisplayElement(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        CUSTOM_DISPLAY_ELEMENT_UNSPECIFIED: _ClassVar[DisplaySettingsTrait.CustomDisplayElement]
        CUSTOM_DISPLAY_ELEMENT_NONE: _ClassVar[DisplaySettingsTrait.CustomDisplayElement]
        CUSTOM_DISPLAY_ELEMENT_TIME: _ClassVar[DisplaySettingsTrait.CustomDisplayElement]
        CUSTOM_DISPLAY_ELEMENT_DATE: _ClassVar[DisplaySettingsTrait.CustomDisplayElement]
        CUSTOM_DISPLAY_ELEMENT_TARGET_TEMP: _ClassVar[DisplaySettingsTrait.CustomDisplayElement]
        CUSTOM_DISPLAY_ELEMENT_INDOOR_TEMP: _ClassVar[DisplaySettingsTrait.CustomDisplayElement]
        CUSTOM_DISPLAY_ELEMENT_OUTDOOR_TEMP: _ClassVar[DisplaySettingsTrait.CustomDisplayElement]
        CUSTOM_DISPLAY_ELEMENT_OUTDOOR_AQI: _ClassVar[DisplaySettingsTrait.CustomDisplayElement]
        CUSTOM_DISPLAY_ELEMENT_INDOOR_HUMIDITY: _ClassVar[DisplaySettingsTrait.CustomDisplayElement]
        CUSTOM_DISPLAY_ELEMENT_INDOOR_AQ: _ClassVar[DisplaySettingsTrait.CustomDisplayElement]
        CUSTOM_DISPLAY_ELEMENT_LEAF_COUNT: _ClassVar[DisplaySettingsTrait.CustomDisplayElement]
        CUSTOM_DISPLAY_ELEMENT_OUTDOOR_HUMIDITY: _ClassVar[DisplaySettingsTrait.CustomDisplayElement]
        CUSTOM_DISPLAY_ELEMENT_OUTDOOR_FEELS_LIKE_TEMP: _ClassVar[DisplaySettingsTrait.CustomDisplayElement]
    CUSTOM_DISPLAY_ELEMENT_UNSPECIFIED: DisplaySettingsTrait.CustomDisplayElement
    CUSTOM_DISPLAY_ELEMENT_NONE: DisplaySettingsTrait.CustomDisplayElement
    CUSTOM_DISPLAY_ELEMENT_TIME: DisplaySettingsTrait.CustomDisplayElement
    CUSTOM_DISPLAY_ELEMENT_DATE: DisplaySettingsTrait.CustomDisplayElement
    CUSTOM_DISPLAY_ELEMENT_TARGET_TEMP: DisplaySettingsTrait.CustomDisplayElement
    CUSTOM_DISPLAY_ELEMENT_INDOOR_TEMP: DisplaySettingsTrait.CustomDisplayElement
    CUSTOM_DISPLAY_ELEMENT_OUTDOOR_TEMP: DisplaySettingsTrait.CustomDisplayElement
    CUSTOM_DISPLAY_ELEMENT_OUTDOOR_AQI: DisplaySettingsTrait.CustomDisplayElement
    CUSTOM_DISPLAY_ELEMENT_INDOOR_HUMIDITY: DisplaySettingsTrait.CustomDisplayElement
    CUSTOM_DISPLAY_ELEMENT_INDOOR_AQ: DisplaySettingsTrait.CustomDisplayElement
    CUSTOM_DISPLAY_ELEMENT_LEAF_COUNT: DisplaySettingsTrait.CustomDisplayElement
    CUSTOM_DISPLAY_ELEMENT_OUTDOOR_HUMIDITY: DisplaySettingsTrait.CustomDisplayElement
    CUSTOM_DISPLAY_ELEMENT_OUTDOOR_FEELS_LIKE_TEMP: DisplaySettingsTrait.CustomDisplayElement
    class FarsightCustomDisplaySettings(_message.Message):
        __slots__ = ("topElement", "centerElement", "bottomElement")
        TOPELEMENT_FIELD_NUMBER: _ClassVar[int]
        CENTERELEMENT_FIELD_NUMBER: _ClassVar[int]
        BOTTOMELEMENT_FIELD_NUMBER: _ClassVar[int]
        topElement: DisplaySettingsTrait.CustomDisplayElement
        centerElement: DisplaySettingsTrait.CustomDisplayElement
        bottomElement: DisplaySettingsTrait.CustomDisplayElement
        def __init__(self, topElement: _Optional[_Union[DisplaySettingsTrait.CustomDisplayElement, str]] = ..., centerElement: _Optional[_Union[DisplaySettingsTrait.CustomDisplayElement, str]] = ..., bottomElement: _Optional[_Union[DisplaySettingsTrait.CustomDisplayElement, str]] = ...) -> None: ...
    class FarsightDisplayAnalogClockSettings(_message.Message):
        __slots__ = ("bottomElement",)
        BOTTOMELEMENT_FIELD_NUMBER: _ClassVar[int]
        bottomElement: DisplaySettingsTrait.CustomDisplayElement
        def __init__(self, bottomElement: _Optional[_Union[DisplaySettingsTrait.CustomDisplayElement, str]] = ...) -> None: ...
    class FarsightDisplayDigitalClockSettings(_message.Message):
        __slots__ = ("topElement", "bottomElement")
        TOPELEMENT_FIELD_NUMBER: _ClassVar[int]
        BOTTOMELEMENT_FIELD_NUMBER: _ClassVar[int]
        topElement: DisplaySettingsTrait.CustomDisplayElement
        bottomElement: DisplaySettingsTrait.CustomDisplayElement
        def __init__(self, topElement: _Optional[_Union[DisplaySettingsTrait.CustomDisplayElement, str]] = ..., bottomElement: _Optional[_Union[DisplaySettingsTrait.CustomDisplayElement, str]] = ...) -> None: ...
    class FarsightDisplayCustomPanelSettings(_message.Message):
        __slots__ = ("topElement", "primaryElement", "bottomElement")
        TOPELEMENT_FIELD_NUMBER: _ClassVar[int]
        PRIMARYELEMENT_FIELD_NUMBER: _ClassVar[int]
        BOTTOMELEMENT_FIELD_NUMBER: _ClassVar[int]
        topElement: DisplaySettingsTrait.CustomDisplayElement
        primaryElement: DisplaySettingsTrait.CustomDisplayElement
        bottomElement: DisplaySettingsTrait.CustomDisplayElement
        def __init__(self, topElement: _Optional[_Union[DisplaySettingsTrait.CustomDisplayElement, str]] = ..., primaryElement: _Optional[_Union[DisplaySettingsTrait.CustomDisplayElement, str]] = ..., bottomElement: _Optional[_Union[DisplaySettingsTrait.CustomDisplayElement, str]] = ...) -> None: ...
    FARSIGHTDISPLAY_FIELD_NUMBER: _ClassVar[int]
    TEMPERATURESCALE_FIELD_NUMBER: _ClassVar[int]
    ANALOGCLOCKSETTINGS_FIELD_NUMBER: _ClassVar[int]
    DIGITALCLOCKSETTINGS_FIELD_NUMBER: _ClassVar[int]
    CUSTOMPANELSETTINGS_FIELD_NUMBER: _ClassVar[int]
    WAKEONREMOTETEMPCHANGE_FIELD_NUMBER: _ClassVar[int]
    FARSIGHTNEARONLY_FIELD_NUMBER: _ClassVar[int]
    FARSIGHTDISMISSONVERYNEAR_FIELD_NUMBER: _ClassVar[int]
    FARSIGHTANALOGCLOCKSETTINGS_FIELD_NUMBER: _ClassVar[int]
    FARSIGHTDIGITALCLOCKSETTINGS_FIELD_NUMBER: _ClassVar[int]
    FARSIGHTWEATHERSETTINGS_FIELD_NUMBER: _ClassVar[int]
    FARSIGHTTEMPERATURESSETTINGS_FIELD_NUMBER: _ClassVar[int]
    farsightDisplay: DisplaySettingsTrait.FarsightDisplay
    temperatureScale: DisplaySettingsTrait.TemperatureScale
    analogClockSettings: DisplaySettingsTrait.FarsightDisplayAnalogClockSettings
    digitalClockSettings: DisplaySettingsTrait.FarsightDisplayDigitalClockSettings
    customPanelSettings: DisplaySettingsTrait.FarsightDisplayCustomPanelSettings
    wakeOnRemoteTempChange: bool
    farsightNearOnly: bool
    farsightDismissOnVeryNear: bool
    farsightAnalogClockSettings: DisplaySettingsTrait.FarsightCustomDisplaySettings
    farsightDigitalClockSettings: DisplaySettingsTrait.FarsightCustomDisplaySettings
    farsightWeatherSettings: DisplaySettingsTrait.FarsightCustomDisplaySettings
    farsightTemperaturesSettings: DisplaySettingsTrait.FarsightCustomDisplaySettings
    def __init__(self, farsightDisplay: _Optional[_Union[DisplaySettingsTrait.FarsightDisplay, str]] = ..., temperatureScale: _Optional[_Union[DisplaySettingsTrait.TemperatureScale, str]] = ..., analogClockSettings: _Optional[_Union[DisplaySettingsTrait.FarsightDisplayAnalogClockSettings, _Mapping]] = ..., digitalClockSettings: _Optional[_Union[DisplaySettingsTrait.FarsightDisplayDigitalClockSettings, _Mapping]] = ..., customPanelSettings: _Optional[_Union[DisplaySettingsTrait.FarsightDisplayCustomPanelSettings, _Mapping]] = ..., wakeOnRemoteTempChange: bool = ..., farsightNearOnly: bool = ..., farsightDismissOnVeryNear: bool = ..., farsightAnalogClockSettings: _Optional[_Union[DisplaySettingsTrait.FarsightCustomDisplaySettings, _Mapping]] = ..., farsightDigitalClockSettings: _Optional[_Union[DisplaySettingsTrait.FarsightCustomDisplaySettings, _Mapping]] = ..., farsightWeatherSettings: _Optional[_Union[DisplaySettingsTrait.FarsightCustomDisplaySettings, _Mapping]] = ..., farsightTemperaturesSettings: _Optional[_Union[DisplaySettingsTrait.FarsightCustomDisplaySettings, _Mapping]] = ...) -> None: ...

class AssociatedHeatlinksTrait(_message.Message):
    __slots__ = ("heatlinks",)
    class ResponseStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        RESPONSE_STATUS_UNSPECIFIED: _ClassVar[AssociatedHeatlinksTrait.ResponseStatus]
        RESPONSE_STATUS_HEATLINK_EXISTS: _ClassVar[AssociatedHeatlinksTrait.ResponseStatus]
        RESPONSE_STATUS_HEATLINK_DOESNT_EXIST: _ClassVar[AssociatedHeatlinksTrait.ResponseStatus]
        RESPONSE_STATUS_SUCCESS: _ClassVar[AssociatedHeatlinksTrait.ResponseStatus]
        RESPONSE_STATUS_FAILURE: _ClassVar[AssociatedHeatlinksTrait.ResponseStatus]
        RESPONSE_STATUS_MISSING_PARAMS: _ClassVar[AssociatedHeatlinksTrait.ResponseStatus]
        RESPONSE_STATUS_HEATLINK_LIMIT_EXCEEDED: _ClassVar[AssociatedHeatlinksTrait.ResponseStatus]
    RESPONSE_STATUS_UNSPECIFIED: AssociatedHeatlinksTrait.ResponseStatus
    RESPONSE_STATUS_HEATLINK_EXISTS: AssociatedHeatlinksTrait.ResponseStatus
    RESPONSE_STATUS_HEATLINK_DOESNT_EXIST: AssociatedHeatlinksTrait.ResponseStatus
    RESPONSE_STATUS_SUCCESS: AssociatedHeatlinksTrait.ResponseStatus
    RESPONSE_STATUS_FAILURE: AssociatedHeatlinksTrait.ResponseStatus
    RESPONSE_STATUS_MISSING_PARAMS: AssociatedHeatlinksTrait.ResponseStatus
    RESPONSE_STATUS_HEATLINK_LIMIT_EXCEEDED: AssociatedHeatlinksTrait.ResponseStatus
    class AssociatedHeatlink(_message.Message):
        __slots__ = ("deviceId", "vendorId", "productId")
        DEVICEID_FIELD_NUMBER: _ClassVar[int]
        VENDORID_FIELD_NUMBER: _ClassVar[int]
        PRODUCTID_FIELD_NUMBER: _ClassVar[int]
        deviceId: _common_pb2.ResourceId
        vendorId: int
        productId: int
        def __init__(self, deviceId: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ..., vendorId: _Optional[int] = ..., productId: _Optional[int] = ...) -> None: ...
    class AssociateHeatlinkRequest(_message.Message):
        __slots__ = ("deviceId",)
        DEVICEID_FIELD_NUMBER: _ClassVar[int]
        deviceId: _common_pb2.ResourceId
        def __init__(self, deviceId: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ...) -> None: ...
    class AssociateHeatlinkResponse(_message.Message):
        __slots__ = ("status",)
        STATUS_FIELD_NUMBER: _ClassVar[int]
        status: AssociatedHeatlinksTrait.ResponseStatus
        def __init__(self, status: _Optional[_Union[AssociatedHeatlinksTrait.ResponseStatus, str]] = ...) -> None: ...
    class DissociateHeatlinkRequest(_message.Message):
        __slots__ = ("deviceId",)
        DEVICEID_FIELD_NUMBER: _ClassVar[int]
        deviceId: _common_pb2.ResourceId
        def __init__(self, deviceId: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ...) -> None: ...
    class DissociateHeatlinkResponse(_message.Message):
        __slots__ = ("status",)
        STATUS_FIELD_NUMBER: _ClassVar[int]
        status: AssociatedHeatlinksTrait.ResponseStatus
        def __init__(self, status: _Optional[_Union[AssociatedHeatlinksTrait.ResponseStatus, str]] = ...) -> None: ...
    HEATLINKS_FIELD_NUMBER: _ClassVar[int]
    heatlinks: _containers.RepeatedCompositeFieldContainer[AssociatedHeatlinksTrait.AssociatedHeatlink]
    def __init__(self, heatlinks: _Optional[_Iterable[_Union[AssociatedHeatlinksTrait.AssociatedHeatlink, _Mapping]]] = ...) -> None: ...

class DemandResponseConfigurationTrait(_message.Message):
    __slots__ = ("configurationItems",)
    class DemandResponseEventType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        DEMAND_RESPONSE_EVENT_TYPE_UNSPECIFIED: _ClassVar[DemandResponseConfigurationTrait.DemandResponseEventType]
        DEMAND_RESPONSE_EVENT_TYPE_STANDARD: _ClassVar[DemandResponseConfigurationTrait.DemandResponseEventType]
        DEMAND_RESPONSE_EVENT_TYPE_CRITICAL: _ClassVar[DemandResponseConfigurationTrait.DemandResponseEventType]
    DEMAND_RESPONSE_EVENT_TYPE_UNSPECIFIED: DemandResponseConfigurationTrait.DemandResponseEventType
    DEMAND_RESPONSE_EVENT_TYPE_STANDARD: DemandResponseConfigurationTrait.DemandResponseEventType
    DEMAND_RESPONSE_EVENT_TYPE_CRITICAL: DemandResponseConfigurationTrait.DemandResponseEventType
    class DemandResponseRequiredScheduleMode(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        DEMAND_RESPONSE_REQUIRED_SCHEDULE_MODE_UNSPECIFIED: _ClassVar[DemandResponseConfigurationTrait.DemandResponseRequiredScheduleMode]
        DEMAND_RESPONSE_REQUIRED_SCHEDULE_MODE_HEAT: _ClassVar[DemandResponseConfigurationTrait.DemandResponseRequiredScheduleMode]
        DEMAND_RESPONSE_REQUIRED_SCHEDULE_MODE_COOL: _ClassVar[DemandResponseConfigurationTrait.DemandResponseRequiredScheduleMode]
        DEMAND_RESPONSE_REQUIRED_SCHEDULE_MODE_RANGE: _ClassVar[DemandResponseConfigurationTrait.DemandResponseRequiredScheduleMode]
        DEMAND_RESPONSE_REQUIRED_SCHEDULE_MODE_NONE: _ClassVar[DemandResponseConfigurationTrait.DemandResponseRequiredScheduleMode]
    DEMAND_RESPONSE_REQUIRED_SCHEDULE_MODE_UNSPECIFIED: DemandResponseConfigurationTrait.DemandResponseRequiredScheduleMode
    DEMAND_RESPONSE_REQUIRED_SCHEDULE_MODE_HEAT: DemandResponseConfigurationTrait.DemandResponseRequiredScheduleMode
    DEMAND_RESPONSE_REQUIRED_SCHEDULE_MODE_COOL: DemandResponseConfigurationTrait.DemandResponseRequiredScheduleMode
    DEMAND_RESPONSE_REQUIRED_SCHEDULE_MODE_RANGE: DemandResponseConfigurationTrait.DemandResponseRequiredScheduleMode
    DEMAND_RESPONSE_REQUIRED_SCHEDULE_MODE_NONE: DemandResponseConfigurationTrait.DemandResponseRequiredScheduleMode
    class ConfigurationItemsEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: int
        value: DemandResponseConfigurationTrait.DemandResponseEventConfigurationItem
        def __init__(self, key: _Optional[int] = ..., value: _Optional[_Union[DemandResponseConfigurationTrait.DemandResponseEventConfigurationItem, _Mapping]] = ...) -> None: ...
    class DemandResponseOptimizationParameters(_message.Message):
        __slots__ = ("preparationMinimumDisplayedOffset", "preparationMaximumDisplayedOffset", "eventMinimumDisplayedOffset", "eventMaximumDisplayedOffset", "cycleLengthStepsize", "weightTemperatureDeviation", "weightOffpeakUsage", "weightPeakUsage", "defaultPolicyPreparationOffset", "defaultPolicyEventOffset", "defaultEventOffsetStartTimePercent", "minimumTimeFromAdjustmentToEventEnd", "setpointType", "shouldPredictAutoArrival", "baselinePreparationSafetyOffset", "baselineEventSafetyOffset", "baselineSafetyCheckTimeout", "minimumReoptimizationTimeout", "useUct", "obeyPreconditioningSetting", "numUctRollouts", "useOneSidedTempError", "obeyHeatpumpLockouts", "obeyDualfuelBreakpoint", "minimumLengthFactorBetweenEvents", "peakRampInInitialOffset", "peakRampInSeconds", "peakRampOutSeconds", "preparationRampInSeconds")
        PREPARATIONMINIMUMDISPLAYEDOFFSET_FIELD_NUMBER: _ClassVar[int]
        PREPARATIONMAXIMUMDISPLAYEDOFFSET_FIELD_NUMBER: _ClassVar[int]
        EVENTMINIMUMDISPLAYEDOFFSET_FIELD_NUMBER: _ClassVar[int]
        EVENTMAXIMUMDISPLAYEDOFFSET_FIELD_NUMBER: _ClassVar[int]
        CYCLELENGTHSTEPSIZE_FIELD_NUMBER: _ClassVar[int]
        WEIGHTTEMPERATUREDEVIATION_FIELD_NUMBER: _ClassVar[int]
        WEIGHTOFFPEAKUSAGE_FIELD_NUMBER: _ClassVar[int]
        WEIGHTPEAKUSAGE_FIELD_NUMBER: _ClassVar[int]
        DEFAULTPOLICYPREPARATIONOFFSET_FIELD_NUMBER: _ClassVar[int]
        DEFAULTPOLICYEVENTOFFSET_FIELD_NUMBER: _ClassVar[int]
        DEFAULTEVENTOFFSETSTARTTIMEPERCENT_FIELD_NUMBER: _ClassVar[int]
        MINIMUMTIMEFROMADJUSTMENTTOEVENTEND_FIELD_NUMBER: _ClassVar[int]
        SETPOINTTYPE_FIELD_NUMBER: _ClassVar[int]
        SHOULDPREDICTAUTOARRIVAL_FIELD_NUMBER: _ClassVar[int]
        BASELINEPREPARATIONSAFETYOFFSET_FIELD_NUMBER: _ClassVar[int]
        BASELINEEVENTSAFETYOFFSET_FIELD_NUMBER: _ClassVar[int]
        BASELINESAFETYCHECKTIMEOUT_FIELD_NUMBER: _ClassVar[int]
        MINIMUMREOPTIMIZATIONTIMEOUT_FIELD_NUMBER: _ClassVar[int]
        USEUCT_FIELD_NUMBER: _ClassVar[int]
        OBEYPRECONDITIONINGSETTING_FIELD_NUMBER: _ClassVar[int]
        NUMUCTROLLOUTS_FIELD_NUMBER: _ClassVar[int]
        USEONESIDEDTEMPERROR_FIELD_NUMBER: _ClassVar[int]
        OBEYHEATPUMPLOCKOUTS_FIELD_NUMBER: _ClassVar[int]
        OBEYDUALFUELBREAKPOINT_FIELD_NUMBER: _ClassVar[int]
        MINIMUMLENGTHFACTORBETWEENEVENTS_FIELD_NUMBER: _ClassVar[int]
        PEAKRAMPININITIALOFFSET_FIELD_NUMBER: _ClassVar[int]
        PEAKRAMPINSECONDS_FIELD_NUMBER: _ClassVar[int]
        PEAKRAMPOUTSECONDS_FIELD_NUMBER: _ClassVar[int]
        PREPARATIONRAMPINSECONDS_FIELD_NUMBER: _ClassVar[int]
        preparationMinimumDisplayedOffset: HvacControl.Temperature
        preparationMaximumDisplayedOffset: HvacControl.Temperature
        eventMinimumDisplayedOffset: HvacControl.Temperature
        eventMaximumDisplayedOffset: HvacControl.Temperature
        cycleLengthStepsize: int
        weightTemperatureDeviation: HvacControl.Temperature
        weightOffpeakUsage: float
        weightPeakUsage: float
        defaultPolicyPreparationOffset: HvacControl.Temperature
        defaultPolicyEventOffset: HvacControl.Temperature
        defaultEventOffsetStartTimePercent: float
        minimumTimeFromAdjustmentToEventEnd: int
        setpointType: SetPointScheduleSettingsTrait.SetPointType
        shouldPredictAutoArrival: bool
        baselinePreparationSafetyOffset: HvacControl.Temperature
        baselineEventSafetyOffset: HvacControl.Temperature
        baselineSafetyCheckTimeout: int
        minimumReoptimizationTimeout: int
        useUct: bool
        obeyPreconditioningSetting: bool
        numUctRollouts: int
        useOneSidedTempError: bool
        obeyHeatpumpLockouts: bool
        obeyDualfuelBreakpoint: bool
        minimumLengthFactorBetweenEvents: float
        peakRampInInitialOffset: float
        peakRampInSeconds: int
        peakRampOutSeconds: int
        preparationRampInSeconds: int
        def __init__(self, preparationMinimumDisplayedOffset: _Optional[_Union[HvacControl.Temperature, _Mapping]] = ..., preparationMaximumDisplayedOffset: _Optional[_Union[HvacControl.Temperature, _Mapping]] = ..., eventMinimumDisplayedOffset: _Optional[_Union[HvacControl.Temperature, _Mapping]] = ..., eventMaximumDisplayedOffset: _Optional[_Union[HvacControl.Temperature, _Mapping]] = ..., cycleLengthStepsize: _Optional[int] = ..., weightTemperatureDeviation: _Optional[_Union[HvacControl.Temperature, _Mapping]] = ..., weightOffpeakUsage: _Optional[float] = ..., weightPeakUsage: _Optional[float] = ..., defaultPolicyPreparationOffset: _Optional[_Union[HvacControl.Temperature, _Mapping]] = ..., defaultPolicyEventOffset: _Optional[_Union[HvacControl.Temperature, _Mapping]] = ..., defaultEventOffsetStartTimePercent: _Optional[float] = ..., minimumTimeFromAdjustmentToEventEnd: _Optional[int] = ..., setpointType: _Optional[_Union[SetPointScheduleSettingsTrait.SetPointType, str]] = ..., shouldPredictAutoArrival: bool = ..., baselinePreparationSafetyOffset: _Optional[_Union[HvacControl.Temperature, _Mapping]] = ..., baselineEventSafetyOffset: _Optional[_Union[HvacControl.Temperature, _Mapping]] = ..., baselineSafetyCheckTimeout: _Optional[int] = ..., minimumReoptimizationTimeout: _Optional[int] = ..., useUct: bool = ..., obeyPreconditioningSetting: bool = ..., numUctRollouts: _Optional[int] = ..., useOneSidedTempError: bool = ..., obeyHeatpumpLockouts: bool = ..., obeyDualfuelBreakpoint: bool = ..., minimumLengthFactorBetweenEvents: _Optional[float] = ..., peakRampInInitialOffset: _Optional[float] = ..., peakRampInSeconds: _Optional[int] = ..., peakRampOutSeconds: _Optional[int] = ..., preparationRampInSeconds: _Optional[int] = ...) -> None: ...
    class DemandResponseEventConfigurationItem(_message.Message):
        __slots__ = ("eventGuid", "debugName", "eventType", "qualificationStartTimeUtc", "qualificationStopTimeUtc", "peakPeriodStartTimeUtc", "startTimeUtc", "stopTimeUtc", "lengthPreparationSeconds", "lengthEventSeconds", "preparationSpeedbumpDisabled", "optimizationParameters", "partnerName", "requiredScheduleMode")
        EVENTGUID_FIELD_NUMBER: _ClassVar[int]
        DEBUGNAME_FIELD_NUMBER: _ClassVar[int]
        EVENTTYPE_FIELD_NUMBER: _ClassVar[int]
        QUALIFICATIONSTARTTIMEUTC_FIELD_NUMBER: _ClassVar[int]
        QUALIFICATIONSTOPTIMEUTC_FIELD_NUMBER: _ClassVar[int]
        PEAKPERIODSTARTTIMEUTC_FIELD_NUMBER: _ClassVar[int]
        STARTTIMEUTC_FIELD_NUMBER: _ClassVar[int]
        STOPTIMEUTC_FIELD_NUMBER: _ClassVar[int]
        LENGTHPREPARATIONSECONDS_FIELD_NUMBER: _ClassVar[int]
        LENGTHEVENTSECONDS_FIELD_NUMBER: _ClassVar[int]
        PREPARATIONSPEEDBUMPDISABLED_FIELD_NUMBER: _ClassVar[int]
        OPTIMIZATIONPARAMETERS_FIELD_NUMBER: _ClassVar[int]
        PARTNERNAME_FIELD_NUMBER: _ClassVar[int]
        REQUIREDSCHEDULEMODE_FIELD_NUMBER: _ClassVar[int]
        eventGuid: str
        debugName: str
        eventType: DemandResponseConfigurationTrait.DemandResponseEventType
        qualificationStartTimeUtc: _timestamp_pb2.Timestamp
        qualificationStopTimeUtc: _timestamp_pb2.Timestamp
        peakPeriodStartTimeUtc: _timestamp_pb2.Timestamp
        startTimeUtc: _timestamp_pb2.Timestamp
        stopTimeUtc: _timestamp_pb2.Timestamp
        lengthPreparationSeconds: int
        lengthEventSeconds: int
        preparationSpeedbumpDisabled: bool
        optimizationParameters: DemandResponseConfigurationTrait.DemandResponseOptimizationParameters
        partnerName: PartnerInformation.PartnerName
        requiredScheduleMode: DemandResponseConfigurationTrait.DemandResponseRequiredScheduleMode
        def __init__(self, eventGuid: _Optional[str] = ..., debugName: _Optional[str] = ..., eventType: _Optional[_Union[DemandResponseConfigurationTrait.DemandResponseEventType, str]] = ..., qualificationStartTimeUtc: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., qualificationStopTimeUtc: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., peakPeriodStartTimeUtc: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., startTimeUtc: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., stopTimeUtc: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., lengthPreparationSeconds: _Optional[int] = ..., lengthEventSeconds: _Optional[int] = ..., preparationSpeedbumpDisabled: bool = ..., optimizationParameters: _Optional[_Union[DemandResponseConfigurationTrait.DemandResponseOptimizationParameters, _Mapping]] = ..., partnerName: _Optional[_Union[PartnerInformation.PartnerName, _Mapping]] = ..., requiredScheduleMode: _Optional[_Union[DemandResponseConfigurationTrait.DemandResponseRequiredScheduleMode, str]] = ...) -> None: ...
    class DemandResponseScheduledEvent(_message.Message):
        __slots__ = ("eventId", "partnerId", "partnerName", "preconditioningStartTime", "preconditioningTemperatureOffsetCelsius", "peakStartTime", "peakEndTime", "peakTemperatureOffsetCelsius", "eventType", "programType")
        EVENTID_FIELD_NUMBER: _ClassVar[int]
        PARTNERID_FIELD_NUMBER: _ClassVar[int]
        PARTNERNAME_FIELD_NUMBER: _ClassVar[int]
        PRECONDITIONINGSTARTTIME_FIELD_NUMBER: _ClassVar[int]
        PRECONDITIONINGTEMPERATUREOFFSETCELSIUS_FIELD_NUMBER: _ClassVar[int]
        PEAKSTARTTIME_FIELD_NUMBER: _ClassVar[int]
        PEAKENDTIME_FIELD_NUMBER: _ClassVar[int]
        PEAKTEMPERATUREOFFSETCELSIUS_FIELD_NUMBER: _ClassVar[int]
        EVENTTYPE_FIELD_NUMBER: _ClassVar[int]
        PROGRAMTYPE_FIELD_NUMBER: _ClassVar[int]
        eventId: str
        partnerId: str
        partnerName: str
        preconditioningStartTime: _timestamp_pb2.Timestamp
        preconditioningTemperatureOffsetCelsius: _wrappers_pb2.FloatValue
        peakStartTime: _timestamp_pb2.Timestamp
        peakEndTime: _timestamp_pb2.Timestamp
        peakTemperatureOffsetCelsius: float
        eventType: DemandResponseConfigurationTrait.DemandResponseEventType
        programType: DemandResponseTrait.DemandResponseProgramType
        def __init__(self, eventId: _Optional[str] = ..., partnerId: _Optional[str] = ..., partnerName: _Optional[str] = ..., preconditioningStartTime: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., preconditioningTemperatureOffsetCelsius: _Optional[_Union[_wrappers_pb2.FloatValue, _Mapping]] = ..., peakStartTime: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., peakEndTime: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., peakTemperatureOffsetCelsius: _Optional[float] = ..., eventType: _Optional[_Union[DemandResponseConfigurationTrait.DemandResponseEventType, str]] = ..., programType: _Optional[_Union[DemandResponseTrait.DemandResponseProgramType, str]] = ...) -> None: ...
    CONFIGURATIONITEMS_FIELD_NUMBER: _ClassVar[int]
    configurationItems: _containers.MessageMap[int, DemandResponseConfigurationTrait.DemandResponseEventConfigurationItem]
    def __init__(self, configurationItems: _Optional[_Mapping[int, DemandResponseConfigurationTrait.DemandResponseEventConfigurationItem]] = ...) -> None: ...

class EcoModeStateTrait(_message.Message):
    __slots__ = ("ecoMode", "ecoModeChangeReason", "ecoModeActor")
    class EcoMode(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        ECO_MODE_UNSPECIFIED: _ClassVar[EcoModeStateTrait.EcoMode]
        ECO_MODE_INACTIVE: _ClassVar[EcoModeStateTrait.EcoMode]
        ECO_MODE_MANUAL_ECO: _ClassVar[EcoModeStateTrait.EcoMode]
        ECO_MODE_AUTO_ECO: _ClassVar[EcoModeStateTrait.EcoMode]
    ECO_MODE_UNSPECIFIED: EcoModeStateTrait.EcoMode
    ECO_MODE_INACTIVE: EcoModeStateTrait.EcoMode
    ECO_MODE_MANUAL_ECO: EcoModeStateTrait.EcoMode
    ECO_MODE_AUTO_ECO: EcoModeStateTrait.EcoMode
    class EcoModeChangeReason(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        ECO_MODE_CHANGE_REASON_UNSPECIFIED: _ClassVar[EcoModeStateTrait.EcoModeChangeReason]
        ECO_MODE_CHANGE_REASON_MANUAL: _ClassVar[EcoModeStateTrait.EcoModeChangeReason]
        ECO_MODE_CHANGE_REASON_STRUCTURE_MODE: _ClassVar[EcoModeStateTrait.EcoModeChangeReason]
        ECO_MODE_CHANGE_REASON_OCCUPANCY: _ClassVar[EcoModeStateTrait.EcoModeChangeReason]
        ECO_MODE_CHANGE_REASON_TEMPERATURE: _ClassVar[EcoModeStateTrait.EcoModeChangeReason]
        ECO_MODE_CHANGE_REASON_FEATURE_ENABLE: _ClassVar[EcoModeStateTrait.EcoModeChangeReason]
    ECO_MODE_CHANGE_REASON_UNSPECIFIED: EcoModeStateTrait.EcoModeChangeReason
    ECO_MODE_CHANGE_REASON_MANUAL: EcoModeStateTrait.EcoModeChangeReason
    ECO_MODE_CHANGE_REASON_STRUCTURE_MODE: EcoModeStateTrait.EcoModeChangeReason
    ECO_MODE_CHANGE_REASON_OCCUPANCY: EcoModeStateTrait.EcoModeChangeReason
    ECO_MODE_CHANGE_REASON_TEMPERATURE: EcoModeStateTrait.EcoModeChangeReason
    ECO_MODE_CHANGE_REASON_FEATURE_ENABLE: EcoModeStateTrait.EcoModeChangeReason
    class EcoModeChangeRequest(_message.Message):
        __slots__ = ("ecoMode", "ecoModeActor", "setAll")
        ECOMODE_FIELD_NUMBER: _ClassVar[int]
        ECOMODEACTOR_FIELD_NUMBER: _ClassVar[int]
        SETALL_FIELD_NUMBER: _ClassVar[int]
        ecoMode: EcoModeStateTrait.EcoMode
        ecoModeActor: HvacActor.HvacActorStruct
        setAll: bool
        def __init__(self, ecoMode: _Optional[_Union[EcoModeStateTrait.EcoMode, str]] = ..., ecoModeActor: _Optional[_Union[HvacActor.HvacActorStruct, _Mapping]] = ..., setAll: bool = ...) -> None: ...
    class EcoModeChangeEvent(_message.Message):
        __slots__ = ("ecoMode", "priorEcoMode", "ecoModeChangeReason", "ecoModeActor")
        ECOMODE_FIELD_NUMBER: _ClassVar[int]
        PRIORECOMODE_FIELD_NUMBER: _ClassVar[int]
        ECOMODECHANGEREASON_FIELD_NUMBER: _ClassVar[int]
        ECOMODEACTOR_FIELD_NUMBER: _ClassVar[int]
        ecoMode: EcoModeStateTrait.EcoMode
        priorEcoMode: EcoModeStateTrait.EcoMode
        ecoModeChangeReason: EcoModeStateTrait.EcoModeChangeReason
        ecoModeActor: HvacActor.HvacActorStruct
        def __init__(self, ecoMode: _Optional[_Union[EcoModeStateTrait.EcoMode, str]] = ..., priorEcoMode: _Optional[_Union[EcoModeStateTrait.EcoMode, str]] = ..., ecoModeChangeReason: _Optional[_Union[EcoModeStateTrait.EcoModeChangeReason, str]] = ..., ecoModeActor: _Optional[_Union[HvacActor.HvacActorStruct, _Mapping]] = ...) -> None: ...
    class StructureWideEcoModeChangeRequestEvent(_message.Message):
        __slots__ = ("requestedEcoMode", "ecoModeActor")
        REQUESTEDECOMODE_FIELD_NUMBER: _ClassVar[int]
        ECOMODEACTOR_FIELD_NUMBER: _ClassVar[int]
        requestedEcoMode: EcoModeStateTrait.EcoMode
        ecoModeActor: HvacActor.HvacActorStruct
        def __init__(self, requestedEcoMode: _Optional[_Union[EcoModeStateTrait.EcoMode, str]] = ..., ecoModeActor: _Optional[_Union[HvacActor.HvacActorStruct, _Mapping]] = ...) -> None: ...
    ECOMODE_FIELD_NUMBER: _ClassVar[int]
    ECOMODECHANGEREASON_FIELD_NUMBER: _ClassVar[int]
    ECOMODEACTOR_FIELD_NUMBER: _ClassVar[int]
    ecoMode: EcoModeStateTrait.EcoMode
    ecoModeChangeReason: EcoModeStateTrait.EcoModeChangeReason
    ecoModeActor: HvacActor.HvacActorStruct
    def __init__(self, ecoMode: _Optional[_Union[EcoModeStateTrait.EcoMode, str]] = ..., ecoModeChangeReason: _Optional[_Union[EcoModeStateTrait.EcoModeChangeReason, str]] = ..., ecoModeActor: _Optional[_Union[HvacActor.HvacActorStruct, _Mapping]] = ...) -> None: ...

class HvacMessageCenterConfig(_message.Message):
    __slots__ = ()
    class Icon(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        ICON_UNSPECIFIED: _ClassVar[HvacMessageCenterConfig.Icon]
        ICON_INFO: _ClassVar[HvacMessageCenterConfig.Icon]
        ICON_WARNING: _ClassVar[HvacMessageCenterConfig.Icon]
        ICON_EQUIPMENT: _ClassVar[HvacMessageCenterConfig.Icon]
        ICON_ENERGY_PROGRAM: _ClassVar[HvacMessageCenterConfig.Icon]
        ICON_LEAF: _ClassVar[HvacMessageCenterConfig.Icon]
        ICON_ATOM_COMFORT: _ClassVar[HvacMessageCenterConfig.Icon]
        ICON_ATOM_ECO: _ClassVar[HvacMessageCenterConfig.Icon]
        ICON_ATOM_SLEEP: _ClassVar[HvacMessageCenterConfig.Icon]
        ICON_ATOM_CUSTOM: _ClassVar[HvacMessageCenterConfig.Icon]
        ICON_APOLLO_LEAF: _ClassVar[HvacMessageCenterConfig.Icon]
        ICON_SCHEDULE_UPDATED: _ClassVar[HvacMessageCenterConfig.Icon]
    ICON_UNSPECIFIED: HvacMessageCenterConfig.Icon
    ICON_INFO: HvacMessageCenterConfig.Icon
    ICON_WARNING: HvacMessageCenterConfig.Icon
    ICON_EQUIPMENT: HvacMessageCenterConfig.Icon
    ICON_ENERGY_PROGRAM: HvacMessageCenterConfig.Icon
    ICON_LEAF: HvacMessageCenterConfig.Icon
    ICON_ATOM_COMFORT: HvacMessageCenterConfig.Icon
    ICON_ATOM_ECO: HvacMessageCenterConfig.Icon
    ICON_ATOM_SLEEP: HvacMessageCenterConfig.Icon
    ICON_ATOM_CUSTOM: HvacMessageCenterConfig.Icon
    ICON_APOLLO_LEAF: HvacMessageCenterConfig.Icon
    ICON_SCHEDULE_UPDATED: HvacMessageCenterConfig.Icon
    class ElementStyle(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        ELEMENT_STYLE_UNSPECIFIED: _ClassVar[HvacMessageCenterConfig.ElementStyle]
        ELEMENT_STYLE_HEADER: _ClassVar[HvacMessageCenterConfig.ElementStyle]
        ELEMENT_STYLE_BODY: _ClassVar[HvacMessageCenterConfig.ElementStyle]
        ELEMENT_STYLE_BODY_LARGE: _ClassVar[HvacMessageCenterConfig.ElementStyle]
        ELEMENT_STYLE_BUTTON: _ClassVar[HvacMessageCenterConfig.ElementStyle]
        ELEMENT_STYLE_PAGE_BREAK: _ClassVar[HvacMessageCenterConfig.ElementStyle]
        ELEMENT_STYLE_QR_CODE: _ClassVar[HvacMessageCenterConfig.ElementStyle]
    ELEMENT_STYLE_UNSPECIFIED: HvacMessageCenterConfig.ElementStyle
    ELEMENT_STYLE_HEADER: HvacMessageCenterConfig.ElementStyle
    ELEMENT_STYLE_BODY: HvacMessageCenterConfig.ElementStyle
    ELEMENT_STYLE_BODY_LARGE: HvacMessageCenterConfig.ElementStyle
    ELEMENT_STYLE_BUTTON: HvacMessageCenterConfig.ElementStyle
    ELEMENT_STYLE_PAGE_BREAK: HvacMessageCenterConfig.ElementStyle
    ELEMENT_STYLE_QR_CODE: HvacMessageCenterConfig.ElementStyle
    class ElementColor(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        ELEMENT_COLOR_UNSPECIFIED: _ClassVar[HvacMessageCenterConfig.ElementColor]
        ELEMENT_COLOR_WHITE: _ClassVar[HvacMessageCenterConfig.ElementColor]
        ELEMENT_COLOR_RED: _ClassVar[HvacMessageCenterConfig.ElementColor]
        ELEMENT_COLOR_BLUE: _ClassVar[HvacMessageCenterConfig.ElementColor]
        ELEMENT_COLOR_YELLOW: _ClassVar[HvacMessageCenterConfig.ElementColor]
    ELEMENT_COLOR_UNSPECIFIED: HvacMessageCenterConfig.ElementColor
    ELEMENT_COLOR_WHITE: HvacMessageCenterConfig.ElementColor
    ELEMENT_COLOR_RED: HvacMessageCenterConfig.ElementColor
    ELEMENT_COLOR_BLUE: HvacMessageCenterConfig.ElementColor
    ELEMENT_COLOR_YELLOW: HvacMessageCenterConfig.ElementColor
    class MessageType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        MESSAGE_TYPE_UNSPECIFIED: _ClassVar[HvacMessageCenterConfig.MessageType]
        MESSAGE_TYPE_CLOUD_RHR_PRESENTING: _ClassVar[HvacMessageCenterConfig.MessageType]
        MESSAGE_TYPE_FURNACE_HEADSUP: _ClassVar[HvacMessageCenterConfig.MessageType]
        MESSAGE_TYPE_HARDWARE_RESISTOR_FAILURE: _ClassVar[HvacMessageCenterConfig.MessageType]
        MESSAGE_TYPE_HARDWARE_WIRING_ERROR: _ClassVar[HvacMessageCenterConfig.MessageType]
        MESSAGE_TYPE_CLOUD_SEASONAL_SAVINGS_EFFICIENT_COMFORT: _ClassVar[HvacMessageCenterConfig.MessageType]
        MESSAGE_TYPE_USAGE_DRIVEN_SAVINGS_SCHEDULE_IMPROVEMENT: _ClassVar[HvacMessageCenterConfig.MessageType]
        MESSAGE_TYPE_GAMMA_GROWTH_CAMPAIGN: _ClassVar[HvacMessageCenterConfig.MessageType]
        MESSAGE_TYPE_GREEN_ENERGY_WELCOME: _ClassVar[HvacMessageCenterConfig.MessageType]
        MESSAGE_TYPE_GREEN_ENERGY_LEAFS_EARNED_MILESTONE: _ClassVar[HvacMessageCenterConfig.MessageType]
        MESSAGE_TYPE_GREEN_ENERGY_MONTHLY_IMPACT_SUMMARY: _ClassVar[HvacMessageCenterConfig.MessageType]
        MESSAGE_TYPE_SEASONAL_SAVINGS_3: _ClassVar[HvacMessageCenterConfig.MessageType]
        MESSAGE_TYPE_EARLY_LEARNING_SLEEP_SETBACK_REMINDER: _ClassVar[HvacMessageCenterConfig.MessageType]
    MESSAGE_TYPE_UNSPECIFIED: HvacMessageCenterConfig.MessageType
    MESSAGE_TYPE_CLOUD_RHR_PRESENTING: HvacMessageCenterConfig.MessageType
    MESSAGE_TYPE_FURNACE_HEADSUP: HvacMessageCenterConfig.MessageType
    MESSAGE_TYPE_HARDWARE_RESISTOR_FAILURE: HvacMessageCenterConfig.MessageType
    MESSAGE_TYPE_HARDWARE_WIRING_ERROR: HvacMessageCenterConfig.MessageType
    MESSAGE_TYPE_CLOUD_SEASONAL_SAVINGS_EFFICIENT_COMFORT: HvacMessageCenterConfig.MessageType
    MESSAGE_TYPE_USAGE_DRIVEN_SAVINGS_SCHEDULE_IMPROVEMENT: HvacMessageCenterConfig.MessageType
    MESSAGE_TYPE_GAMMA_GROWTH_CAMPAIGN: HvacMessageCenterConfig.MessageType
    MESSAGE_TYPE_GREEN_ENERGY_WELCOME: HvacMessageCenterConfig.MessageType
    MESSAGE_TYPE_GREEN_ENERGY_LEAFS_EARNED_MILESTONE: HvacMessageCenterConfig.MessageType
    MESSAGE_TYPE_GREEN_ENERGY_MONTHLY_IMPACT_SUMMARY: HvacMessageCenterConfig.MessageType
    MESSAGE_TYPE_SEASONAL_SAVINGS_3: HvacMessageCenterConfig.MessageType
    MESSAGE_TYPE_EARLY_LEARNING_SLEEP_SETBACK_REMINDER: HvacMessageCenterConfig.MessageType
    class ValidMode(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        VALID_MODE_UNSPECIFIED: _ClassVar[HvacMessageCenterConfig.ValidMode]
        VALID_MODE_SYSTEM_MODE_HEAT: _ClassVar[HvacMessageCenterConfig.ValidMode]
        VALID_MODE_SYSTEM_MODE_COOL: _ClassVar[HvacMessageCenterConfig.ValidMode]
        VALID_MODE_SYSTEM_MODE_RANGE: _ClassVar[HvacMessageCenterConfig.ValidMode]
        VALID_MODE_SYSTEM_MODE_OFF: _ClassVar[HvacMessageCenterConfig.ValidMode]
    VALID_MODE_UNSPECIFIED: HvacMessageCenterConfig.ValidMode
    VALID_MODE_SYSTEM_MODE_HEAT: HvacMessageCenterConfig.ValidMode
    VALID_MODE_SYSTEM_MODE_COOL: HvacMessageCenterConfig.ValidMode
    VALID_MODE_SYSTEM_MODE_RANGE: HvacMessageCenterConfig.ValidMode
    VALID_MODE_SYSTEM_MODE_OFF: HvacMessageCenterConfig.ValidMode
    def __init__(self) -> None: ...

class SeasonalSavingsTrait(_message.Message):
    __slots__ = ("eventGuid", "state", "stopReason", "scheduleMode", "predictedCompletionTime", "partnerName", "predictedExpirationTimeUtc")
    class SeasonalSavingsState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        SEASONAL_SAVINGS_STATE_UNSPECIFIED: _ClassVar[SeasonalSavingsTrait.SeasonalSavingsState]
        SEASONAL_SAVINGS_STATE_INITIAL: _ClassVar[SeasonalSavingsTrait.SeasonalSavingsState]
        SEASONAL_SAVINGS_STATE_WAITING_TO_QUALIFY: _ClassVar[SeasonalSavingsTrait.SeasonalSavingsState]
        SEASONAL_SAVINGS_STATE_PRESENTING_EVENT: _ClassVar[SeasonalSavingsTrait.SeasonalSavingsState]
        SEASONAL_SAVINGS_STATE_WAITING: _ClassVar[SeasonalSavingsTrait.SeasonalSavingsState]
        SEASONAL_SAVINGS_STATE_RUNNING: _ClassVar[SeasonalSavingsTrait.SeasonalSavingsState]
        SEASONAL_SAVINGS_STATE_PAUSED: _ClassVar[SeasonalSavingsTrait.SeasonalSavingsState]
        SEASONAL_SAVINGS_STATE_PRESENTING_FINAL_STAGE_COMPLETED: _ClassVar[SeasonalSavingsTrait.SeasonalSavingsState]
        SEASONAL_SAVINGS_STATE_AFTERGLOW: _ClassVar[SeasonalSavingsTrait.SeasonalSavingsState]
        SEASONAL_SAVINGS_STATE_FINISHED: _ClassVar[SeasonalSavingsTrait.SeasonalSavingsState]
    SEASONAL_SAVINGS_STATE_UNSPECIFIED: SeasonalSavingsTrait.SeasonalSavingsState
    SEASONAL_SAVINGS_STATE_INITIAL: SeasonalSavingsTrait.SeasonalSavingsState
    SEASONAL_SAVINGS_STATE_WAITING_TO_QUALIFY: SeasonalSavingsTrait.SeasonalSavingsState
    SEASONAL_SAVINGS_STATE_PRESENTING_EVENT: SeasonalSavingsTrait.SeasonalSavingsState
    SEASONAL_SAVINGS_STATE_WAITING: SeasonalSavingsTrait.SeasonalSavingsState
    SEASONAL_SAVINGS_STATE_RUNNING: SeasonalSavingsTrait.SeasonalSavingsState
    SEASONAL_SAVINGS_STATE_PAUSED: SeasonalSavingsTrait.SeasonalSavingsState
    SEASONAL_SAVINGS_STATE_PRESENTING_FINAL_STAGE_COMPLETED: SeasonalSavingsTrait.SeasonalSavingsState
    SEASONAL_SAVINGS_STATE_AFTERGLOW: SeasonalSavingsTrait.SeasonalSavingsState
    SEASONAL_SAVINGS_STATE_FINISHED: SeasonalSavingsTrait.SeasonalSavingsState
    class SeasonalSavingsAction(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        SEASONAL_SAVINGS_ACTION_UNSPECIFIED: _ClassVar[SeasonalSavingsTrait.SeasonalSavingsAction]
        SEASONAL_SAVINGS_ACTION_ACCEPT: _ClassVar[SeasonalSavingsTrait.SeasonalSavingsAction]
        SEASONAL_SAVINGS_ACTION_NOT_NOW: _ClassVar[SeasonalSavingsTrait.SeasonalSavingsAction]
        SEASONAL_SAVINGS_ACTION_STOP: _ClassVar[SeasonalSavingsTrait.SeasonalSavingsAction]
        SEASONAL_SAVINGS_ACTION_DONE: _ClassVar[SeasonalSavingsTrait.SeasonalSavingsAction]
    SEASONAL_SAVINGS_ACTION_UNSPECIFIED: SeasonalSavingsTrait.SeasonalSavingsAction
    SEASONAL_SAVINGS_ACTION_ACCEPT: SeasonalSavingsTrait.SeasonalSavingsAction
    SEASONAL_SAVINGS_ACTION_NOT_NOW: SeasonalSavingsTrait.SeasonalSavingsAction
    SEASONAL_SAVINGS_ACTION_STOP: SeasonalSavingsTrait.SeasonalSavingsAction
    SEASONAL_SAVINGS_ACTION_DONE: SeasonalSavingsTrait.SeasonalSavingsAction
    class SeasonalSavingsStopReason(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        SEASONAL_SAVINGS_STOP_REASON_UNSPECIFIED: _ClassVar[SeasonalSavingsTrait.SeasonalSavingsStopReason]
        SEASONAL_SAVINGS_STOP_REASON_NONE: _ClassVar[SeasonalSavingsTrait.SeasonalSavingsStopReason]
        SEASONAL_SAVINGS_STOP_REASON_INVALID: _ClassVar[SeasonalSavingsTrait.SeasonalSavingsStopReason]
        SEASONAL_SAVINGS_STOP_REASON_KILLED: _ClassVar[SeasonalSavingsTrait.SeasonalSavingsStopReason]
        SEASONAL_SAVINGS_STOP_REASON_KILLED_BY_SERVER: _ClassVar[SeasonalSavingsTrait.SeasonalSavingsStopReason]
        SEASONAL_SAVINGS_STOP_REASON_EVENT_EXPIRED: _ClassVar[SeasonalSavingsTrait.SeasonalSavingsStopReason]
        SEASONAL_SAVINGS_STOP_REASON_PRESENTING_EXPIRED: _ClassVar[SeasonalSavingsTrait.SeasonalSavingsStopReason]
        SEASONAL_SAVINGS_STOP_REASON_WAITING_EXPIRED: _ClassVar[SeasonalSavingsTrait.SeasonalSavingsStopReason]
        SEASONAL_SAVINGS_STOP_REASON_PAUSED_EXPIRED: _ClassVar[SeasonalSavingsTrait.SeasonalSavingsStopReason]
        SEASONAL_SAVINGS_STOP_REASON_DID_NOT_QUALIFY: _ClassVar[SeasonalSavingsTrait.SeasonalSavingsStopReason]
        SEASONAL_SAVINGS_STOP_REASON_USER_REQUESTED: _ClassVar[SeasonalSavingsTrait.SeasonalSavingsStopReason]
    SEASONAL_SAVINGS_STOP_REASON_UNSPECIFIED: SeasonalSavingsTrait.SeasonalSavingsStopReason
    SEASONAL_SAVINGS_STOP_REASON_NONE: SeasonalSavingsTrait.SeasonalSavingsStopReason
    SEASONAL_SAVINGS_STOP_REASON_INVALID: SeasonalSavingsTrait.SeasonalSavingsStopReason
    SEASONAL_SAVINGS_STOP_REASON_KILLED: SeasonalSavingsTrait.SeasonalSavingsStopReason
    SEASONAL_SAVINGS_STOP_REASON_KILLED_BY_SERVER: SeasonalSavingsTrait.SeasonalSavingsStopReason
    SEASONAL_SAVINGS_STOP_REASON_EVENT_EXPIRED: SeasonalSavingsTrait.SeasonalSavingsStopReason
    SEASONAL_SAVINGS_STOP_REASON_PRESENTING_EXPIRED: SeasonalSavingsTrait.SeasonalSavingsStopReason
    SEASONAL_SAVINGS_STOP_REASON_WAITING_EXPIRED: SeasonalSavingsTrait.SeasonalSavingsStopReason
    SEASONAL_SAVINGS_STOP_REASON_PAUSED_EXPIRED: SeasonalSavingsTrait.SeasonalSavingsStopReason
    SEASONAL_SAVINGS_STOP_REASON_DID_NOT_QUALIFY: SeasonalSavingsTrait.SeasonalSavingsStopReason
    SEASONAL_SAVINGS_STOP_REASON_USER_REQUESTED: SeasonalSavingsTrait.SeasonalSavingsStopReason
    class SeasonalSavingsStateChangedEvent(_message.Message):
        __slots__ = ("eventGuid", "state", "previousState", "action", "stopReason", "predictedExpirationTimeUtc", "season")
        EVENTGUID_FIELD_NUMBER: _ClassVar[int]
        STATE_FIELD_NUMBER: _ClassVar[int]
        PREVIOUSSTATE_FIELD_NUMBER: _ClassVar[int]
        ACTION_FIELD_NUMBER: _ClassVar[int]
        STOPREASON_FIELD_NUMBER: _ClassVar[int]
        PREDICTEDEXPIRATIONTIMEUTC_FIELD_NUMBER: _ClassVar[int]
        SEASON_FIELD_NUMBER: _ClassVar[int]
        eventGuid: str
        state: SeasonalSavingsTrait.SeasonalSavingsState
        previousState: SeasonalSavingsTrait.SeasonalSavingsState
        action: SeasonalSavingsTrait.SeasonalSavingsAction
        stopReason: SeasonalSavingsTrait.SeasonalSavingsStopReason
        predictedExpirationTimeUtc: _timestamp_pb2.Timestamp
        season: SeasonalSavingsSettingsTrait.SeasonalSavingsSeasonType
        def __init__(self, eventGuid: _Optional[str] = ..., state: _Optional[_Union[SeasonalSavingsTrait.SeasonalSavingsState, str]] = ..., previousState: _Optional[_Union[SeasonalSavingsTrait.SeasonalSavingsState, str]] = ..., action: _Optional[_Union[SeasonalSavingsTrait.SeasonalSavingsAction, str]] = ..., stopReason: _Optional[_Union[SeasonalSavingsTrait.SeasonalSavingsStopReason, str]] = ..., predictedExpirationTimeUtc: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., season: _Optional[_Union[SeasonalSavingsSettingsTrait.SeasonalSavingsSeasonType, str]] = ...) -> None: ...
    EVENTGUID_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    STOPREASON_FIELD_NUMBER: _ClassVar[int]
    SCHEDULEMODE_FIELD_NUMBER: _ClassVar[int]
    PREDICTEDCOMPLETIONTIME_FIELD_NUMBER: _ClassVar[int]
    PARTNERNAME_FIELD_NUMBER: _ClassVar[int]
    PREDICTEDEXPIRATIONTIMEUTC_FIELD_NUMBER: _ClassVar[int]
    eventGuid: str
    state: SeasonalSavingsTrait.SeasonalSavingsState
    stopReason: SeasonalSavingsTrait.SeasonalSavingsStopReason
    scheduleMode: SetPointScheduleSettingsTrait.SetPointScheduleType
    predictedCompletionTime: _timestamp_pb2.Timestamp
    partnerName: PartnerInformation.PartnerName
    predictedExpirationTimeUtc: _timestamp_pb2.Timestamp
    def __init__(self, eventGuid: _Optional[str] = ..., state: _Optional[_Union[SeasonalSavingsTrait.SeasonalSavingsState, str]] = ..., stopReason: _Optional[_Union[SeasonalSavingsTrait.SeasonalSavingsStopReason, str]] = ..., scheduleMode: _Optional[_Union[SetPointScheduleSettingsTrait.SetPointScheduleType, str]] = ..., predictedCompletionTime: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., partnerName: _Optional[_Union[PartnerInformation.PartnerName, _Mapping]] = ..., predictedExpirationTimeUtc: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class HvacControlTrait(_message.Message):
    __slots__ = ("hvacState", "compressorLockoutEnabled", "compressorLockoutTimeout", "minCycleLockoutEnabled", "minCycleLockoutTimeout")
    class HvacStateChangeReason(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        HVAC_STATE_CHANGE_REASON_UNSPECIFIED: _ClassVar[HvacControlTrait.HvacStateChangeReason]
        HVAC_STATE_CHANGE_REASON_UNKNOWN: _ClassVar[HvacControlTrait.HvacStateChangeReason]
        HVAC_STATE_CHANGE_REASON_HVAC_WIRE_POWER_LOSS: _ClassVar[HvacControlTrait.HvacStateChangeReason]
        HVAC_STATE_CHANGE_REASON_SYSTEM_TEST: _ClassVar[HvacControlTrait.HvacStateChangeReason]
        HVAC_STATE_CHANGE_REASON_SWITCH_SHUT_OFF: _ClassVar[HvacControlTrait.HvacStateChangeReason]
    HVAC_STATE_CHANGE_REASON_UNSPECIFIED: HvacControlTrait.HvacStateChangeReason
    HVAC_STATE_CHANGE_REASON_UNKNOWN: HvacControlTrait.HvacStateChangeReason
    HVAC_STATE_CHANGE_REASON_HVAC_WIRE_POWER_LOSS: HvacControlTrait.HvacStateChangeReason
    HVAC_STATE_CHANGE_REASON_SYSTEM_TEST: HvacControlTrait.HvacStateChangeReason
    HVAC_STATE_CHANGE_REASON_SWITCH_SHUT_OFF: HvacControlTrait.HvacStateChangeReason
    class HvacState(_message.Message):
        __slots__ = ("coolStage1Active", "coolStage2Active", "coolStage3Active", "heatStage1Active", "heatStage2Active", "heatStage3Active", "alternateHeatStage1Active", "alternateHeatStage2Active", "auxiliaryHeatActive", "emergencyHeatActive", "humidifierActive", "dehumidifierActive", "ventilatorActive")
        COOLSTAGE1ACTIVE_FIELD_NUMBER: _ClassVar[int]
        COOLSTAGE2ACTIVE_FIELD_NUMBER: _ClassVar[int]
        COOLSTAGE3ACTIVE_FIELD_NUMBER: _ClassVar[int]
        HEATSTAGE1ACTIVE_FIELD_NUMBER: _ClassVar[int]
        HEATSTAGE2ACTIVE_FIELD_NUMBER: _ClassVar[int]
        HEATSTAGE3ACTIVE_FIELD_NUMBER: _ClassVar[int]
        ALTERNATEHEATSTAGE1ACTIVE_FIELD_NUMBER: _ClassVar[int]
        ALTERNATEHEATSTAGE2ACTIVE_FIELD_NUMBER: _ClassVar[int]
        AUXILIARYHEATACTIVE_FIELD_NUMBER: _ClassVar[int]
        EMERGENCYHEATACTIVE_FIELD_NUMBER: _ClassVar[int]
        HUMIDIFIERACTIVE_FIELD_NUMBER: _ClassVar[int]
        DEHUMIDIFIERACTIVE_FIELD_NUMBER: _ClassVar[int]
        VENTILATORACTIVE_FIELD_NUMBER: _ClassVar[int]
        coolStage1Active: bool
        coolStage2Active: bool
        coolStage3Active: bool
        heatStage1Active: bool
        heatStage2Active: bool
        heatStage3Active: bool
        alternateHeatStage1Active: bool
        alternateHeatStage2Active: bool
        auxiliaryHeatActive: bool
        emergencyHeatActive: bool
        humidifierActive: bool
        dehumidifierActive: bool
        ventilatorActive: bool
        def __init__(self, coolStage1Active: bool = ..., coolStage2Active: bool = ..., coolStage3Active: bool = ..., heatStage1Active: bool = ..., heatStage2Active: bool = ..., heatStage3Active: bool = ..., alternateHeatStage1Active: bool = ..., alternateHeatStage2Active: bool = ..., auxiliaryHeatActive: bool = ..., emergencyHeatActive: bool = ..., humidifierActive: bool = ..., dehumidifierActive: bool = ..., ventilatorActive: bool = ...) -> None: ...
    class HvacStateChangeEvent(_message.Message):
        __slots__ = ("hvacState", "priorHvacState", "priorStateEffectiveTime", "reason")
        HVACSTATE_FIELD_NUMBER: _ClassVar[int]
        PRIORHVACSTATE_FIELD_NUMBER: _ClassVar[int]
        PRIORSTATEEFFECTIVETIME_FIELD_NUMBER: _ClassVar[int]
        REASON_FIELD_NUMBER: _ClassVar[int]
        hvacState: HvacControlTrait.HvacState
        priorHvacState: HvacControlTrait.HvacState
        priorStateEffectiveTime: _timestamp_pb2.Timestamp
        reason: HvacControlTrait.HvacStateChangeReason
        def __init__(self, hvacState: _Optional[_Union[HvacControlTrait.HvacState, _Mapping]] = ..., priorHvacState: _Optional[_Union[HvacControlTrait.HvacState, _Mapping]] = ..., priorStateEffectiveTime: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., reason: _Optional[_Union[HvacControlTrait.HvacStateChangeReason, str]] = ...) -> None: ...
    HVACSTATE_FIELD_NUMBER: _ClassVar[int]
    COMPRESSORLOCKOUTENABLED_FIELD_NUMBER: _ClassVar[int]
    COMPRESSORLOCKOUTTIMEOUT_FIELD_NUMBER: _ClassVar[int]
    MINCYCLELOCKOUTENABLED_FIELD_NUMBER: _ClassVar[int]
    MINCYCLELOCKOUTTIMEOUT_FIELD_NUMBER: _ClassVar[int]
    hvacState: HvacControlTrait.HvacState
    compressorLockoutEnabled: bool
    compressorLockoutTimeout: _timestamp_pb2.Timestamp
    minCycleLockoutEnabled: bool
    minCycleLockoutTimeout: _timestamp_pb2.Timestamp
    def __init__(self, hvacState: _Optional[_Union[HvacControlTrait.HvacState, _Mapping]] = ..., compressorLockoutEnabled: bool = ..., compressorLockoutTimeout: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., minCycleLockoutEnabled: bool = ..., minCycleLockoutTimeout: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class PartnerInformation(_message.Message):
    __slots__ = ()
    class PartnerName(_message.Message):
        __slots__ = ("name", "abbreviation", "suppressNameInMessaging")
        NAME_FIELD_NUMBER: _ClassVar[int]
        ABBREVIATION_FIELD_NUMBER: _ClassVar[int]
        SUPPRESSNAMEINMESSAGING_FIELD_NUMBER: _ClassVar[int]
        name: str
        abbreviation: str
        suppressNameInMessaging: bool
        def __init__(self, name: _Optional[str] = ..., abbreviation: _Optional[str] = ..., suppressNameInMessaging: bool = ...) -> None: ...
    def __init__(self) -> None: ...

class WiringTrait(_message.Message):
    __slots__ = ("connectionsMechanical", "connectionsElectrical", "pinCDescription", "pinGDescription", "pinObDescription", "pinRcDescription", "pinRhDescription", "pinStarDescription", "pinW1Description", "pinW2AuxDescription", "pinY1Description", "pinY2Description", "wiringError", "wiringErrorTimestamp", "pinAqplusDescription", "pinAqminusDescription")
    class WireTerminal(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        WIRE_TERMINAL_UNSPECIFIED: _ClassVar[WiringTrait.WireTerminal]
        WIRE_TERMINAL_W1: _ClassVar[WiringTrait.WireTerminal]
        WIRE_TERMINAL_Y1: _ClassVar[WiringTrait.WireTerminal]
        WIRE_TERMINAL_C: _ClassVar[WiringTrait.WireTerminal]
        WIRE_TERMINAL_RC: _ClassVar[WiringTrait.WireTerminal]
        WIRE_TERMINAL_RH: _ClassVar[WiringTrait.WireTerminal]
        WIRE_TERMINAL_G: _ClassVar[WiringTrait.WireTerminal]
        WIRE_TERMINAL_OB: _ClassVar[WiringTrait.WireTerminal]
        WIRE_TERMINAL_W2: _ClassVar[WiringTrait.WireTerminal]
        WIRE_TERMINAL_Y2: _ClassVar[WiringTrait.WireTerminal]
        WIRE_TERMINAL_STAR: _ClassVar[WiringTrait.WireTerminal]
        WIRE_TERMINAL_AQ_PLUS: _ClassVar[WiringTrait.WireTerminal]
        WIRE_TERMINAL_AQ_MINUS: _ClassVar[WiringTrait.WireTerminal]
    WIRE_TERMINAL_UNSPECIFIED: WiringTrait.WireTerminal
    WIRE_TERMINAL_W1: WiringTrait.WireTerminal
    WIRE_TERMINAL_Y1: WiringTrait.WireTerminal
    WIRE_TERMINAL_C: WiringTrait.WireTerminal
    WIRE_TERMINAL_RC: WiringTrait.WireTerminal
    WIRE_TERMINAL_RH: WiringTrait.WireTerminal
    WIRE_TERMINAL_G: WiringTrait.WireTerminal
    WIRE_TERMINAL_OB: WiringTrait.WireTerminal
    WIRE_TERMINAL_W2: WiringTrait.WireTerminal
    WIRE_TERMINAL_Y2: WiringTrait.WireTerminal
    WIRE_TERMINAL_STAR: WiringTrait.WireTerminal
    WIRE_TERMINAL_AQ_PLUS: WiringTrait.WireTerminal
    WIRE_TERMINAL_AQ_MINUS: WiringTrait.WireTerminal
    class WireLabel(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        WIRE_LABEL_UNSPECIFIED: _ClassVar[WiringTrait.WireLabel]
        WIRE_LABEL_NONE: _ClassVar[WiringTrait.WireLabel]
        WIRE_LABEL_COOL: _ClassVar[WiringTrait.WireLabel]
        WIRE_LABEL_HEAT: _ClassVar[WiringTrait.WireLabel]
        WIRE_LABEL_COOL_HEAT: _ClassVar[WiringTrait.WireLabel]
        WIRE_LABEL_STAGE_2_COOL: _ClassVar[WiringTrait.WireLabel]
        WIRE_LABEL_STAGE_2_HEAT: _ClassVar[WiringTrait.WireLabel]
        WIRE_LABEL_STAGE_2_COOL_HEAT: _ClassVar[WiringTrait.WireLabel]
        WIRE_LABEL_STAGE_3_COOL: _ClassVar[WiringTrait.WireLabel]
        WIRE_LABEL_STAGE_3_HEAT: _ClassVar[WiringTrait.WireLabel]
        WIRE_LABEL_STAGE_3_COOL_HEAT: _ClassVar[WiringTrait.WireLabel]
        WIRE_LABEL_HEAT_PUMP: _ClassVar[WiringTrait.WireLabel]
        WIRE_LABEL_AUX_HEAT: _ClassVar[WiringTrait.WireLabel]
        WIRE_LABEL_ALT_HEAT: _ClassVar[WiringTrait.WireLabel]
        WIRE_LABEL_STAGE_2_ALT_HEAT: _ClassVar[WiringTrait.WireLabel]
        WIRE_LABEL_EMERGENCY_HEAT: _ClassVar[WiringTrait.WireLabel]
        WIRE_LABEL_HUMIDIFIER: _ClassVar[WiringTrait.WireLabel]
        WIRE_LABEL_DEHUMIDIFIER: _ClassVar[WiringTrait.WireLabel]
        WIRE_LABEL_POWER: _ClassVar[WiringTrait.WireLabel]
        WIRE_LABEL_COMMON: _ClassVar[WiringTrait.WireLabel]
        WIRE_LABEL_FAN: _ClassVar[WiringTrait.WireLabel]
        WIRE_LABEL_FAN_2: _ClassVar[WiringTrait.WireLabel]
        WIRE_LABEL_FAN_3: _ClassVar[WiringTrait.WireLabel]
        WIRE_LABEL_THERMAL_SWITCH_INPUT: _ClassVar[WiringTrait.WireLabel]
        WIRE_LABEL_VENTILATOR: _ClassVar[WiringTrait.WireLabel]
    WIRE_LABEL_UNSPECIFIED: WiringTrait.WireLabel
    WIRE_LABEL_NONE: WiringTrait.WireLabel
    WIRE_LABEL_COOL: WiringTrait.WireLabel
    WIRE_LABEL_HEAT: WiringTrait.WireLabel
    WIRE_LABEL_COOL_HEAT: WiringTrait.WireLabel
    WIRE_LABEL_STAGE_2_COOL: WiringTrait.WireLabel
    WIRE_LABEL_STAGE_2_HEAT: WiringTrait.WireLabel
    WIRE_LABEL_STAGE_2_COOL_HEAT: WiringTrait.WireLabel
    WIRE_LABEL_STAGE_3_COOL: WiringTrait.WireLabel
    WIRE_LABEL_STAGE_3_HEAT: WiringTrait.WireLabel
    WIRE_LABEL_STAGE_3_COOL_HEAT: WiringTrait.WireLabel
    WIRE_LABEL_HEAT_PUMP: WiringTrait.WireLabel
    WIRE_LABEL_AUX_HEAT: WiringTrait.WireLabel
    WIRE_LABEL_ALT_HEAT: WiringTrait.WireLabel
    WIRE_LABEL_STAGE_2_ALT_HEAT: WiringTrait.WireLabel
    WIRE_LABEL_EMERGENCY_HEAT: WiringTrait.WireLabel
    WIRE_LABEL_HUMIDIFIER: WiringTrait.WireLabel
    WIRE_LABEL_DEHUMIDIFIER: WiringTrait.WireLabel
    WIRE_LABEL_POWER: WiringTrait.WireLabel
    WIRE_LABEL_COMMON: WiringTrait.WireLabel
    WIRE_LABEL_FAN: WiringTrait.WireLabel
    WIRE_LABEL_FAN_2: WiringTrait.WireLabel
    WIRE_LABEL_FAN_3: WiringTrait.WireLabel
    WIRE_LABEL_THERMAL_SWITCH_INPUT: WiringTrait.WireLabel
    WIRE_LABEL_VENTILATOR: WiringTrait.WireLabel
    class WiringErrorEvent(_message.Message):
        __slots__ = ("wiringError", "priorWiringError")
        WIRINGERROR_FIELD_NUMBER: _ClassVar[int]
        PRIORWIRINGERROR_FIELD_NUMBER: _ClassVar[int]
        wiringError: str
        priorWiringError: str
        def __init__(self, wiringError: _Optional[str] = ..., priorWiringError: _Optional[str] = ...) -> None: ...
    class WiringConnectionsElectricalChangeEvent(_message.Message):
        __slots__ = ("connectionsElectrical", "priorConnectionsElectrical")
        CONNECTIONSELECTRICAL_FIELD_NUMBER: _ClassVar[int]
        PRIORCONNECTIONSELECTRICAL_FIELD_NUMBER: _ClassVar[int]
        connectionsElectrical: _containers.RepeatedScalarFieldContainer[WiringTrait.WireTerminal]
        priorConnectionsElectrical: _containers.RepeatedScalarFieldContainer[WiringTrait.WireTerminal]
        def __init__(self, connectionsElectrical: _Optional[_Iterable[_Union[WiringTrait.WireTerminal, str]]] = ..., priorConnectionsElectrical: _Optional[_Iterable[_Union[WiringTrait.WireTerminal, str]]] = ...) -> None: ...
    CONNECTIONSMECHANICAL_FIELD_NUMBER: _ClassVar[int]
    CONNECTIONSELECTRICAL_FIELD_NUMBER: _ClassVar[int]
    PINCDESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    PINGDESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    PINOBDESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    PINRCDESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    PINRHDESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    PINSTARDESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    PINW1DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    PINW2AUXDESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    PINY1DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    PINY2DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    WIRINGERROR_FIELD_NUMBER: _ClassVar[int]
    WIRINGERRORTIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    PINAQPLUSDESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    PINAQMINUSDESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    connectionsMechanical: _containers.RepeatedScalarFieldContainer[WiringTrait.WireTerminal]
    connectionsElectrical: _containers.RepeatedScalarFieldContainer[WiringTrait.WireTerminal]
    pinCDescription: WiringTrait.WireLabel
    pinGDescription: WiringTrait.WireLabel
    pinObDescription: WiringTrait.WireLabel
    pinRcDescription: WiringTrait.WireLabel
    pinRhDescription: WiringTrait.WireLabel
    pinStarDescription: WiringTrait.WireLabel
    pinW1Description: WiringTrait.WireLabel
    pinW2AuxDescription: WiringTrait.WireLabel
    pinY1Description: WiringTrait.WireLabel
    pinY2Description: WiringTrait.WireLabel
    wiringError: str
    wiringErrorTimestamp: _timestamp_pb2.Timestamp
    pinAqplusDescription: WiringTrait.WireLabel
    pinAqminusDescription: WiringTrait.WireLabel
    def __init__(self, connectionsMechanical: _Optional[_Iterable[_Union[WiringTrait.WireTerminal, str]]] = ..., connectionsElectrical: _Optional[_Iterable[_Union[WiringTrait.WireTerminal, str]]] = ..., pinCDescription: _Optional[_Union[WiringTrait.WireLabel, str]] = ..., pinGDescription: _Optional[_Union[WiringTrait.WireLabel, str]] = ..., pinObDescription: _Optional[_Union[WiringTrait.WireLabel, str]] = ..., pinRcDescription: _Optional[_Union[WiringTrait.WireLabel, str]] = ..., pinRhDescription: _Optional[_Union[WiringTrait.WireLabel, str]] = ..., pinStarDescription: _Optional[_Union[WiringTrait.WireLabel, str]] = ..., pinW1Description: _Optional[_Union[WiringTrait.WireLabel, str]] = ..., pinW2AuxDescription: _Optional[_Union[WiringTrait.WireLabel, str]] = ..., pinY1Description: _Optional[_Union[WiringTrait.WireLabel, str]] = ..., pinY2Description: _Optional[_Union[WiringTrait.WireLabel, str]] = ..., wiringError: _Optional[str] = ..., wiringErrorTimestamp: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., pinAqplusDescription: _Optional[_Union[WiringTrait.WireLabel, str]] = ..., pinAqminusDescription: _Optional[_Union[WiringTrait.WireLabel, str]] = ...) -> None: ...

class FilterReminderTrait(_message.Message):
    __slots__ = ("currentFilterReminderLevel", "filterReplacementNeeded", "filterRuntime")
    class FilterReminderLevel(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        FILTER_REMINDER_LEVEL_UNSPECIFIED: _ClassVar[FilterReminderTrait.FilterReminderLevel]
        FILTER_REMINDER_LEVEL_NONE: _ClassVar[FilterReminderTrait.FilterReminderLevel]
        FILTER_REMINDER_LEVEL_FIRST: _ClassVar[FilterReminderTrait.FilterReminderLevel]
        FILTER_REMINDER_LEVEL_SECOND: _ClassVar[FilterReminderTrait.FilterReminderLevel]
    FILTER_REMINDER_LEVEL_UNSPECIFIED: FilterReminderTrait.FilterReminderLevel
    FILTER_REMINDER_LEVEL_NONE: FilterReminderTrait.FilterReminderLevel
    FILTER_REMINDER_LEVEL_FIRST: FilterReminderTrait.FilterReminderLevel
    FILTER_REMINDER_LEVEL_SECOND: FilterReminderTrait.FilterReminderLevel
    class FilterReminderLevelChangedEvent(_message.Message):
        __slots__ = ("filterReminderLevel", "priorFilterReminderLevel")
        FILTERREMINDERLEVEL_FIELD_NUMBER: _ClassVar[int]
        PRIORFILTERREMINDERLEVEL_FIELD_NUMBER: _ClassVar[int]
        filterReminderLevel: FilterReminderTrait.FilterReminderLevel
        priorFilterReminderLevel: FilterReminderTrait.FilterReminderLevel
        def __init__(self, filterReminderLevel: _Optional[_Union[FilterReminderTrait.FilterReminderLevel, str]] = ..., priorFilterReminderLevel: _Optional[_Union[FilterReminderTrait.FilterReminderLevel, str]] = ...) -> None: ...
    class FilterReplacementNeededEvent(_message.Message):
        __slots__ = ("filterReplacementNeeded",)
        FILTERREPLACEMENTNEEDED_FIELD_NUMBER: _ClassVar[int]
        filterReplacementNeeded: _wrappers_pb2.BoolValue
        def __init__(self, filterReplacementNeeded: _Optional[_Union[_wrappers_pb2.BoolValue, _Mapping]] = ...) -> None: ...
    CURRENTFILTERREMINDERLEVEL_FIELD_NUMBER: _ClassVar[int]
    FILTERREPLACEMENTNEEDED_FIELD_NUMBER: _ClassVar[int]
    FILTERRUNTIME_FIELD_NUMBER: _ClassVar[int]
    currentFilterReminderLevel: FilterReminderTrait.FilterReminderLevel
    filterReplacementNeeded: _wrappers_pb2.BoolValue
    filterRuntime: _duration_pb2.Duration
    def __init__(self, currentFilterReminderLevel: _Optional[_Union[FilterReminderTrait.FilterReminderLevel, str]] = ..., filterReplacementNeeded: _Optional[_Union[_wrappers_pb2.BoolValue, _Mapping]] = ..., filterRuntime: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ...) -> None: ...

class SafetyShutoffTrait(_message.Message):
    __slots__ = ("hvacCoSafetyShutoffActive", "hvacSmokeSafetyShutoffActive", "hvacFurnaceShutdown")
    class COShutoffEvent(_message.Message):
        __slots__ = ("active", "priorActive")
        ACTIVE_FIELD_NUMBER: _ClassVar[int]
        PRIORACTIVE_FIELD_NUMBER: _ClassVar[int]
        active: bool
        priorActive: bool
        def __init__(self, active: bool = ..., priorActive: bool = ...) -> None: ...
    class SmokeShutoffEvent(_message.Message):
        __slots__ = ("active", "priorActive")
        ACTIVE_FIELD_NUMBER: _ClassVar[int]
        PRIORACTIVE_FIELD_NUMBER: _ClassVar[int]
        active: bool
        priorActive: bool
        def __init__(self, active: bool = ..., priorActive: bool = ...) -> None: ...
    class FurnaceShutdownEvent(_message.Message):
        __slots__ = ("active", "priorActive")
        ACTIVE_FIELD_NUMBER: _ClassVar[int]
        PRIORACTIVE_FIELD_NUMBER: _ClassVar[int]
        active: bool
        priorActive: bool
        def __init__(self, active: bool = ..., priorActive: bool = ...) -> None: ...
    HVACCOSAFETYSHUTOFFACTIVE_FIELD_NUMBER: _ClassVar[int]
    HVACSMOKESAFETYSHUTOFFACTIVE_FIELD_NUMBER: _ClassVar[int]
    HVACFURNACESHUTDOWN_FIELD_NUMBER: _ClassVar[int]
    hvacCoSafetyShutoffActive: bool
    hvacSmokeSafetyShutoffActive: bool
    hvacFurnaceShutdown: bool
    def __init__(self, hvacCoSafetyShutoffActive: bool = ..., hvacSmokeSafetyShutoffActive: bool = ..., hvacFurnaceShutdown: bool = ...) -> None: ...

class ScheduleHoldSettingsTrait(_message.Message):
    __slots__ = ("holdSetpoint", "holdMetadata", "eventMetadata")
    class HoldIntent(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        HOLD_INTENT_UNSPECIFIED: _ClassVar[ScheduleHoldSettingsTrait.HoldIntent]
        HOLD_INTENT_DEFAULT: _ClassVar[ScheduleHoldSettingsTrait.HoldIntent]
        HOLD_INTENT_PRECONDITION: _ClassVar[ScheduleHoldSettingsTrait.HoldIntent]
    HOLD_INTENT_UNSPECIFIED: ScheduleHoldSettingsTrait.HoldIntent
    HOLD_INTENT_DEFAULT: ScheduleHoldSettingsTrait.HoldIntent
    HOLD_INTENT_PRECONDITION: ScheduleHoldSettingsTrait.HoldIntent
    class HoldSetpoint(_message.Message):
        __slots__ = ("setpointType", "heatTarget", "coolTarget", "initiatedBy", "lastUpdatedBy", "endTime", "atomId", "isIndefinite")
        SETPOINTTYPE_FIELD_NUMBER: _ClassVar[int]
        HEATTARGET_FIELD_NUMBER: _ClassVar[int]
        COOLTARGET_FIELD_NUMBER: _ClassVar[int]
        INITIATEDBY_FIELD_NUMBER: _ClassVar[int]
        LASTUPDATEDBY_FIELD_NUMBER: _ClassVar[int]
        ENDTIME_FIELD_NUMBER: _ClassVar[int]
        ATOMID_FIELD_NUMBER: _ClassVar[int]
        ISINDEFINITE_FIELD_NUMBER: _ClassVar[int]
        setpointType: SetPointScheduleSettingsTrait.SetPointType
        heatTarget: HvacControl.Temperature
        coolTarget: HvacControl.Temperature
        initiatedBy: HvacActor.HvacActorMethod
        lastUpdatedBy: HvacActor.HvacActorMethod
        endTime: _timestamp_pb2.Timestamp
        atomId: int
        isIndefinite: bool
        def __init__(self, setpointType: _Optional[_Union[SetPointScheduleSettingsTrait.SetPointType, str]] = ..., heatTarget: _Optional[_Union[HvacControl.Temperature, _Mapping]] = ..., coolTarget: _Optional[_Union[HvacControl.Temperature, _Mapping]] = ..., initiatedBy: _Optional[_Union[HvacActor.HvacActorMethod, str]] = ..., lastUpdatedBy: _Optional[_Union[HvacActor.HvacActorMethod, str]] = ..., endTime: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., atomId: _Optional[int] = ..., isIndefinite: bool = ...) -> None: ...
    class HoldMetadata(_message.Message):
        __slots__ = ("isCritical", "intent", "lastUserHoldDuration")
        ISCRITICAL_FIELD_NUMBER: _ClassVar[int]
        INTENT_FIELD_NUMBER: _ClassVar[int]
        LASTUSERHOLDDURATION_FIELD_NUMBER: _ClassVar[int]
        isCritical: bool
        intent: ScheduleHoldSettingsTrait.HoldIntent
        lastUserHoldDuration: _duration_pb2.Duration
        def __init__(self, isCritical: bool = ..., intent: _Optional[_Union[ScheduleHoldSettingsTrait.HoldIntent, str]] = ..., lastUserHoldDuration: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ...) -> None: ...
    HOLDSETPOINT_FIELD_NUMBER: _ClassVar[int]
    HOLDMETADATA_FIELD_NUMBER: _ClassVar[int]
    EVENTMETADATA_FIELD_NUMBER: _ClassVar[int]
    holdSetpoint: ScheduleHoldSettingsTrait.HoldSetpoint
    holdMetadata: ScheduleHoldSettingsTrait.HoldMetadata
    eventMetadata: EnergyCaption.EventMetadata
    def __init__(self, holdSetpoint: _Optional[_Union[ScheduleHoldSettingsTrait.HoldSetpoint, _Mapping]] = ..., holdMetadata: _Optional[_Union[ScheduleHoldSettingsTrait.HoldMetadata, _Mapping]] = ..., eventMetadata: _Optional[_Union[EnergyCaption.EventMetadata, _Mapping]] = ...) -> None: ...

class ScheduleHoldTrait(_message.Message):
    __slots__ = ("state", "reason", "lastUpdateTime")
    class HoldState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        HOLD_STATE_UNSPECIFIED: _ClassVar[ScheduleHoldTrait.HoldState]
        HOLD_STATE_INACTIVE: _ClassVar[ScheduleHoldTrait.HoldState]
        HOLD_STATE_ACTIVE: _ClassVar[ScheduleHoldTrait.HoldState]
    HOLD_STATE_UNSPECIFIED: ScheduleHoldTrait.HoldState
    HOLD_STATE_INACTIVE: ScheduleHoldTrait.HoldState
    HOLD_STATE_ACTIVE: ScheduleHoldTrait.HoldState
    class HoldStateChangeReason(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        HOLD_STATE_CHANGE_REASON_UNSPECIFIED: _ClassVar[ScheduleHoldTrait.HoldStateChangeReason]
        HOLD_STATE_CHANGE_REASON_STARTED: _ClassVar[ScheduleHoldTrait.HoldStateChangeReason]
        HOLD_STATE_CHANGE_REASON_UPDATED: _ClassVar[ScheduleHoldTrait.HoldStateChangeReason]
        HOLD_STATE_CHANGE_REASON_EXPIRED: _ClassVar[ScheduleHoldTrait.HoldStateChangeReason]
        HOLD_STATE_CHANGE_REASON_CANCELLED_BY_INITIATOR: _ClassVar[ScheduleHoldTrait.HoldStateChangeReason]
        HOLD_STATE_CHANGE_REASON_OPTED_OUT: _ClassVar[ScheduleHoldTrait.HoldStateChangeReason]
        HOLD_STATE_CHANGE_REASON_REJECTED: _ClassVar[ScheduleHoldTrait.HoldStateChangeReason]
        HOLD_STATE_CHANGE_REASON_REJECTED_UNAVAILABLE: _ClassVar[ScheduleHoldTrait.HoldStateChangeReason]
        HOLD_STATE_CHANGE_REASON_REJECTED_WRONG_SCHEDULE_MODE: _ClassVar[ScheduleHoldTrait.HoldStateChangeReason]
        HOLD_STATE_CHANGE_REASON_REJECTED_INVALID_SETTINGS: _ClassVar[ScheduleHoldTrait.HoldStateChangeReason]
        HOLD_STATE_CHANGE_REASON_REJECTED_LACK_PERMISSION: _ClassVar[ScheduleHoldTrait.HoldStateChangeReason]
    HOLD_STATE_CHANGE_REASON_UNSPECIFIED: ScheduleHoldTrait.HoldStateChangeReason
    HOLD_STATE_CHANGE_REASON_STARTED: ScheduleHoldTrait.HoldStateChangeReason
    HOLD_STATE_CHANGE_REASON_UPDATED: ScheduleHoldTrait.HoldStateChangeReason
    HOLD_STATE_CHANGE_REASON_EXPIRED: ScheduleHoldTrait.HoldStateChangeReason
    HOLD_STATE_CHANGE_REASON_CANCELLED_BY_INITIATOR: ScheduleHoldTrait.HoldStateChangeReason
    HOLD_STATE_CHANGE_REASON_OPTED_OUT: ScheduleHoldTrait.HoldStateChangeReason
    HOLD_STATE_CHANGE_REASON_REJECTED: ScheduleHoldTrait.HoldStateChangeReason
    HOLD_STATE_CHANGE_REASON_REJECTED_UNAVAILABLE: ScheduleHoldTrait.HoldStateChangeReason
    HOLD_STATE_CHANGE_REASON_REJECTED_WRONG_SCHEDULE_MODE: ScheduleHoldTrait.HoldStateChangeReason
    HOLD_STATE_CHANGE_REASON_REJECTED_INVALID_SETTINGS: ScheduleHoldTrait.HoldStateChangeReason
    HOLD_STATE_CHANGE_REASON_REJECTED_LACK_PERMISSION: ScheduleHoldTrait.HoldStateChangeReason
    class ScheduleHoldEvent(_message.Message):
        __slots__ = ("state", "prevState", "reason", "initiatedBy", "updatedBy")
        STATE_FIELD_NUMBER: _ClassVar[int]
        PREVSTATE_FIELD_NUMBER: _ClassVar[int]
        REASON_FIELD_NUMBER: _ClassVar[int]
        INITIATEDBY_FIELD_NUMBER: _ClassVar[int]
        UPDATEDBY_FIELD_NUMBER: _ClassVar[int]
        state: ScheduleHoldTrait.HoldState
        prevState: ScheduleHoldTrait.HoldState
        reason: ScheduleHoldTrait.HoldStateChangeReason
        initiatedBy: HvacActor.HvacActorMethod
        updatedBy: HvacActor.HvacActorMethod
        def __init__(self, state: _Optional[_Union[ScheduleHoldTrait.HoldState, str]] = ..., prevState: _Optional[_Union[ScheduleHoldTrait.HoldState, str]] = ..., reason: _Optional[_Union[ScheduleHoldTrait.HoldStateChangeReason, str]] = ..., initiatedBy: _Optional[_Union[HvacActor.HvacActorMethod, str]] = ..., updatedBy: _Optional[_Union[HvacActor.HvacActorMethod, str]] = ...) -> None: ...
    STATE_FIELD_NUMBER: _ClassVar[int]
    REASON_FIELD_NUMBER: _ClassVar[int]
    LASTUPDATETIME_FIELD_NUMBER: _ClassVar[int]
    state: ScheduleHoldTrait.HoldState
    reason: ScheduleHoldTrait.HoldStateChangeReason
    lastUpdateTime: _timestamp_pb2.Timestamp
    def __init__(self, state: _Optional[_Union[ScheduleHoldTrait.HoldState, str]] = ..., reason: _Optional[_Union[ScheduleHoldTrait.HoldStateChangeReason, str]] = ..., lastUpdateTime: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class SeasonalSavingsActionTrait(_message.Message):
    __slots__ = ("action",)
    class SeasonalSavingsActionStruct(_message.Message):
        __slots__ = ("eventGuid", "requestedAction", "hvacActor")
        EVENTGUID_FIELD_NUMBER: _ClassVar[int]
        REQUESTEDACTION_FIELD_NUMBER: _ClassVar[int]
        HVACACTOR_FIELD_NUMBER: _ClassVar[int]
        eventGuid: str
        requestedAction: SeasonalSavingsTrait.SeasonalSavingsAction
        hvacActor: HvacActor.HvacActorStruct
        def __init__(self, eventGuid: _Optional[str] = ..., requestedAction: _Optional[_Union[SeasonalSavingsTrait.SeasonalSavingsAction, str]] = ..., hvacActor: _Optional[_Union[HvacActor.HvacActorStruct, _Mapping]] = ...) -> None: ...
    class SeasonalSavingsActionRequest(_message.Message):
        __slots__ = ("action",)
        ACTION_FIELD_NUMBER: _ClassVar[int]
        action: SeasonalSavingsActionTrait.SeasonalSavingsActionStruct
        def __init__(self, action: _Optional[_Union[SeasonalSavingsActionTrait.SeasonalSavingsActionStruct, _Mapping]] = ...) -> None: ...
    class SeasonalSavingsActionRequestEvent(_message.Message):
        __slots__ = ("action",)
        ACTION_FIELD_NUMBER: _ClassVar[int]
        action: SeasonalSavingsActionTrait.SeasonalSavingsActionStruct
        def __init__(self, action: _Optional[_Union[SeasonalSavingsActionTrait.SeasonalSavingsActionStruct, _Mapping]] = ...) -> None: ...
    ACTION_FIELD_NUMBER: _ClassVar[int]
    action: SeasonalSavingsActionTrait.SeasonalSavingsActionStruct
    def __init__(self, action: _Optional[_Union[SeasonalSavingsActionTrait.SeasonalSavingsActionStruct, _Mapping]] = ...) -> None: ...

class BackplateInfoTrait(_message.Message):
    __slots__ = ("serialNumber", "model", "monoVersion", "monoInfo", "bslVersion", "bslInfo")
    class BackplateResetReason(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        BACKPLATE_RESET_REASON_UNSPECIFIED: _ClassVar[BackplateInfoTrait.BackplateResetReason]
        BACKPLATE_RESET_REASON_INVALID: _ClassVar[BackplateInfoTrait.BackplateResetReason]
        BACKPLATE_RESET_REASON_INIT: _ClassVar[BackplateInfoTrait.BackplateResetReason]
        BACKPLATE_RESET_REASON_TIMEOUT_COMMS: _ClassVar[BackplateInfoTrait.BackplateResetReason]
        BACKPLATE_RESET_REASON_EXIT: _ClassVar[BackplateInfoTrait.BackplateResetReason]
        BACKPLATE_RESET_REASON_CORRUPT_TYPE: _ClassVar[BackplateInfoTrait.BackplateResetReason]
        BACKPLATE_RESET_REASON_CORRUPT_MESSAGES: _ClassVar[BackplateInfoTrait.BackplateResetReason]
        BACKPLATE_RESET_REASON_TIMEOUT_MESSAGE: _ClassVar[BackplateInfoTrait.BackplateResetReason]
        BACKPLATE_RESET_REASON_RETRIES: _ClassVar[BackplateInfoTrait.BackplateResetReason]
        BACKPLATE_RESET_REASON_ASYNC: _ClassVar[BackplateInfoTrait.BackplateResetReason]
        BACKPLATE_RESET_REASON_UPDATE_COMPLETE: _ClassVar[BackplateInfoTrait.BackplateResetReason]
        BACKPLATE_RESET_REASON_ATTACH: _ClassVar[BackplateInfoTrait.BackplateResetReason]
        BACKPLATE_RESET_REASON_MISSED_TEMP: _ClassVar[BackplateInfoTrait.BackplateResetReason]
        BACKPLATE_RESET_REASON_I2C_DOWN: _ClassVar[BackplateInfoTrait.BackplateResetReason]
        BACKPLATE_RESET_REASON_TP_ERROR: _ClassVar[BackplateInfoTrait.BackplateResetReason]
        BACKPLATE_RESET_REASON_CORRUPTED_TEMP_MSG: _ClassVar[BackplateInfoTrait.BackplateResetReason]
        BACKPLATE_RESET_REASON_BP_POWER_MISMATCH: _ClassVar[BackplateInfoTrait.BackplateResetReason]
    BACKPLATE_RESET_REASON_UNSPECIFIED: BackplateInfoTrait.BackplateResetReason
    BACKPLATE_RESET_REASON_INVALID: BackplateInfoTrait.BackplateResetReason
    BACKPLATE_RESET_REASON_INIT: BackplateInfoTrait.BackplateResetReason
    BACKPLATE_RESET_REASON_TIMEOUT_COMMS: BackplateInfoTrait.BackplateResetReason
    BACKPLATE_RESET_REASON_EXIT: BackplateInfoTrait.BackplateResetReason
    BACKPLATE_RESET_REASON_CORRUPT_TYPE: BackplateInfoTrait.BackplateResetReason
    BACKPLATE_RESET_REASON_CORRUPT_MESSAGES: BackplateInfoTrait.BackplateResetReason
    BACKPLATE_RESET_REASON_TIMEOUT_MESSAGE: BackplateInfoTrait.BackplateResetReason
    BACKPLATE_RESET_REASON_RETRIES: BackplateInfoTrait.BackplateResetReason
    BACKPLATE_RESET_REASON_ASYNC: BackplateInfoTrait.BackplateResetReason
    BACKPLATE_RESET_REASON_UPDATE_COMPLETE: BackplateInfoTrait.BackplateResetReason
    BACKPLATE_RESET_REASON_ATTACH: BackplateInfoTrait.BackplateResetReason
    BACKPLATE_RESET_REASON_MISSED_TEMP: BackplateInfoTrait.BackplateResetReason
    BACKPLATE_RESET_REASON_I2C_DOWN: BackplateInfoTrait.BackplateResetReason
    BACKPLATE_RESET_REASON_TP_ERROR: BackplateInfoTrait.BackplateResetReason
    BACKPLATE_RESET_REASON_CORRUPTED_TEMP_MSG: BackplateInfoTrait.BackplateResetReason
    BACKPLATE_RESET_REASON_BP_POWER_MISMATCH: BackplateInfoTrait.BackplateResetReason
    class BackplateResetEvent(_message.Message):
        __slots__ = ("backplateResetReason",)
        BACKPLATERESETREASON_FIELD_NUMBER: _ClassVar[int]
        backplateResetReason: BackplateInfoTrait.BackplateResetReason
        def __init__(self, backplateResetReason: _Optional[_Union[BackplateInfoTrait.BackplateResetReason, str]] = ...) -> None: ...
    SERIALNUMBER_FIELD_NUMBER: _ClassVar[int]
    MODEL_FIELD_NUMBER: _ClassVar[int]
    MONOVERSION_FIELD_NUMBER: _ClassVar[int]
    MONOINFO_FIELD_NUMBER: _ClassVar[int]
    BSLVERSION_FIELD_NUMBER: _ClassVar[int]
    BSLINFO_FIELD_NUMBER: _ClassVar[int]
    serialNumber: str
    model: str
    monoVersion: str
    monoInfo: str
    bslVersion: str
    bslInfo: str
    def __init__(self, serialNumber: _Optional[str] = ..., model: _Optional[str] = ..., monoVersion: _Optional[str] = ..., monoInfo: _Optional[str] = ..., bslVersion: _Optional[str] = ..., bslInfo: _Optional[str] = ...) -> None: ...

class DemandResponseActionTrait(_message.Message):
    __slots__ = ("actionItems",)
    class DemandResponseAction(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        DEMAND_RESPONSE_ACTION_UNSPECIFIED: _ClassVar[DemandResponseActionTrait.DemandResponseAction]
        DEMAND_RESPONSE_ACTION_KILL_EVENT: _ClassVar[DemandResponseActionTrait.DemandResponseAction]
        DEMAND_RESPONSE_ACTION_STOP: _ClassVar[DemandResponseActionTrait.DemandResponseAction]
        DEMAND_RESPONSE_ACTION_EVENT_RECEIVED: _ClassVar[DemandResponseActionTrait.DemandResponseAction]
        DEMAND_RESPONSE_ACTION_QUALIFIED: _ClassVar[DemandResponseActionTrait.DemandResponseAction]
        DEMAND_RESPONSE_ACTION_CROSSED_EVENT_START_TIME: _ClassVar[DemandResponseActionTrait.DemandResponseAction]
        DEMAND_RESPONSE_ACTION_CROSSED_EVENT_END_TIME: _ClassVar[DemandResponseActionTrait.DemandResponseAction]
        DEMAND_RESPONSE_ACTION_CROSSED_PEAK_PERIOD_START_TIME: _ClassVar[DemandResponseActionTrait.DemandResponseAction]
        DEMAND_RESPONSE_ACTION_TEMPERATURE_CHANGE: _ClassVar[DemandResponseActionTrait.DemandResponseAction]
        DEMAND_RESPONSE_ACTION_TEMPERATURE_CHANGE_EFFICIENT: _ClassVar[DemandResponseActionTrait.DemandResponseAction]
    DEMAND_RESPONSE_ACTION_UNSPECIFIED: DemandResponseActionTrait.DemandResponseAction
    DEMAND_RESPONSE_ACTION_KILL_EVENT: DemandResponseActionTrait.DemandResponseAction
    DEMAND_RESPONSE_ACTION_STOP: DemandResponseActionTrait.DemandResponseAction
    DEMAND_RESPONSE_ACTION_EVENT_RECEIVED: DemandResponseActionTrait.DemandResponseAction
    DEMAND_RESPONSE_ACTION_QUALIFIED: DemandResponseActionTrait.DemandResponseAction
    DEMAND_RESPONSE_ACTION_CROSSED_EVENT_START_TIME: DemandResponseActionTrait.DemandResponseAction
    DEMAND_RESPONSE_ACTION_CROSSED_EVENT_END_TIME: DemandResponseActionTrait.DemandResponseAction
    DEMAND_RESPONSE_ACTION_CROSSED_PEAK_PERIOD_START_TIME: DemandResponseActionTrait.DemandResponseAction
    DEMAND_RESPONSE_ACTION_TEMPERATURE_CHANGE: DemandResponseActionTrait.DemandResponseAction
    DEMAND_RESPONSE_ACTION_TEMPERATURE_CHANGE_EFFICIENT: DemandResponseActionTrait.DemandResponseAction
    class ActionItemsEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: int
        value: DemandResponseActionTrait.DemandResponseEventActionItem
        def __init__(self, key: _Optional[int] = ..., value: _Optional[_Union[DemandResponseActionTrait.DemandResponseEventActionItem, _Mapping]] = ...) -> None: ...
    class DemandResponseEventActionItem(_message.Message):
        __slots__ = ("eventGuid", "requestedAction")
        EVENTGUID_FIELD_NUMBER: _ClassVar[int]
        REQUESTEDACTION_FIELD_NUMBER: _ClassVar[int]
        eventGuid: str
        requestedAction: DemandResponseActionTrait.DemandResponseAction
        def __init__(self, eventGuid: _Optional[str] = ..., requestedAction: _Optional[_Union[DemandResponseActionTrait.DemandResponseAction, str]] = ...) -> None: ...
    ACTIONITEMS_FIELD_NUMBER: _ClassVar[int]
    actionItems: _containers.MessageMap[int, DemandResponseActionTrait.DemandResponseEventActionItem]
    def __init__(self, actionItems: _Optional[_Mapping[int, DemandResponseActionTrait.DemandResponseEventActionItem]] = ...) -> None: ...

class FanControlSettingsTrait(_message.Message):
    __slots__ = ("mode", "hvacOverrideSpeed", "scheduleSpeed", "scheduleDutyCycle", "scheduleStartTime", "scheduleEndTime", "timerSpeed", "timerEnd", "timerDuration", "timerEquipment", "ventilationOnTimePerDay", "smartVentilationEnabled", "timerIsIndefinite", "ventilationEnabled", "ventilationForHeatingAndCoolingEnabled")
    class FanMode(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        FAN_MODE_UNSPECIFIED: _ClassVar[FanControlSettingsTrait.FanMode]
        FAN_MODE_AUTO: _ClassVar[FanControlSettingsTrait.FanMode]
        FAN_MODE_CONTINUOUS_ON: _ClassVar[FanControlSettingsTrait.FanMode]
        FAN_MODE_DUTY_CYCLE: _ClassVar[FanControlSettingsTrait.FanMode]
    FAN_MODE_UNSPECIFIED: FanControlSettingsTrait.FanMode
    FAN_MODE_AUTO: FanControlSettingsTrait.FanMode
    FAN_MODE_CONTINUOUS_ON: FanControlSettingsTrait.FanMode
    FAN_MODE_DUTY_CYCLE: FanControlSettingsTrait.FanMode
    class FanEquipment(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        FAN_EQUIPMENT_UNSPECIFIED: _ClassVar[FanControlSettingsTrait.FanEquipment]
        FAN_EQUIPMENT_FAN_ONLY: _ClassVar[FanControlSettingsTrait.FanEquipment]
        FAN_EQUIPMENT_VENT_ONLY: _ClassVar[FanControlSettingsTrait.FanEquipment]
        FAN_EQUIPMENT_FAN_AND_VENT: _ClassVar[FanControlSettingsTrait.FanEquipment]
    FAN_EQUIPMENT_UNSPECIFIED: FanControlSettingsTrait.FanEquipment
    FAN_EQUIPMENT_FAN_ONLY: FanControlSettingsTrait.FanEquipment
    FAN_EQUIPMENT_VENT_ONLY: FanControlSettingsTrait.FanEquipment
    FAN_EQUIPMENT_FAN_AND_VENT: FanControlSettingsTrait.FanEquipment
    MODE_FIELD_NUMBER: _ClassVar[int]
    HVACOVERRIDESPEED_FIELD_NUMBER: _ClassVar[int]
    SCHEDULESPEED_FIELD_NUMBER: _ClassVar[int]
    SCHEDULEDUTYCYCLE_FIELD_NUMBER: _ClassVar[int]
    SCHEDULESTARTTIME_FIELD_NUMBER: _ClassVar[int]
    SCHEDULEENDTIME_FIELD_NUMBER: _ClassVar[int]
    TIMERSPEED_FIELD_NUMBER: _ClassVar[int]
    TIMEREND_FIELD_NUMBER: _ClassVar[int]
    TIMERDURATION_FIELD_NUMBER: _ClassVar[int]
    TIMEREQUIPMENT_FIELD_NUMBER: _ClassVar[int]
    VENTILATIONONTIMEPERDAY_FIELD_NUMBER: _ClassVar[int]
    SMARTVENTILATIONENABLED_FIELD_NUMBER: _ClassVar[int]
    TIMERISINDEFINITE_FIELD_NUMBER: _ClassVar[int]
    VENTILATIONENABLED_FIELD_NUMBER: _ClassVar[int]
    VENTILATIONFORHEATINGANDCOOLINGENABLED_FIELD_NUMBER: _ClassVar[int]
    mode: FanControlSettingsTrait.FanMode
    hvacOverrideSpeed: FanControlTrait.FanSpeedSetting
    scheduleSpeed: FanControlTrait.FanSpeedSetting
    scheduleDutyCycle: int
    scheduleStartTime: int
    scheduleEndTime: int
    timerSpeed: FanControlTrait.FanSpeedSetting
    timerEnd: _timestamp_pb2.Timestamp
    timerDuration: _duration_pb2.Duration
    timerEquipment: FanControlSettingsTrait.FanEquipment
    ventilationOnTimePerDay: _duration_pb2.Duration
    smartVentilationEnabled: bool
    timerIsIndefinite: bool
    ventilationEnabled: bool
    ventilationForHeatingAndCoolingEnabled: bool
    def __init__(self, mode: _Optional[_Union[FanControlSettingsTrait.FanMode, str]] = ..., hvacOverrideSpeed: _Optional[_Union[FanControlTrait.FanSpeedSetting, str]] = ..., scheduleSpeed: _Optional[_Union[FanControlTrait.FanSpeedSetting, str]] = ..., scheduleDutyCycle: _Optional[int] = ..., scheduleStartTime: _Optional[int] = ..., scheduleEndTime: _Optional[int] = ..., timerSpeed: _Optional[_Union[FanControlTrait.FanSpeedSetting, str]] = ..., timerEnd: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., timerDuration: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ..., timerEquipment: _Optional[_Union[FanControlSettingsTrait.FanEquipment, str]] = ..., ventilationOnTimePerDay: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ..., smartVentilationEnabled: bool = ..., timerIsIndefinite: bool = ..., ventilationEnabled: bool = ..., ventilationForHeatingAndCoolingEnabled: bool = ...) -> None: ...

class HeatPumpControlSettingsTrait(_message.Message):
    __slots__ = ("heatPumpAuxThreshold", "heatPumpCompThreshold", "heatPumpSavingsMode", "auxMinDelta", "auxMinDelay", "auxUpstageThreshold", "dualFuelChangeoverThreshold")
    class HeatPumpSavingsMode(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        HEAT_PUMP_SAVINGS_MODE_UNSPECIFIED: _ClassVar[HeatPumpControlSettingsTrait.HeatPumpSavingsMode]
        HEAT_PUMP_SAVINGS_MODE_MAX_SAVINGS: _ClassVar[HeatPumpControlSettingsTrait.HeatPumpSavingsMode]
        HEAT_PUMP_SAVINGS_MODE_BALANCED: _ClassVar[HeatPumpControlSettingsTrait.HeatPumpSavingsMode]
        HEAT_PUMP_SAVINGS_MODE_MAX_COMFORT: _ClassVar[HeatPumpControlSettingsTrait.HeatPumpSavingsMode]
        HEAT_PUMP_SAVINGS_MODE_OFF: _ClassVar[HeatPumpControlSettingsTrait.HeatPumpSavingsMode]
    HEAT_PUMP_SAVINGS_MODE_UNSPECIFIED: HeatPumpControlSettingsTrait.HeatPumpSavingsMode
    HEAT_PUMP_SAVINGS_MODE_MAX_SAVINGS: HeatPumpControlSettingsTrait.HeatPumpSavingsMode
    HEAT_PUMP_SAVINGS_MODE_BALANCED: HeatPumpControlSettingsTrait.HeatPumpSavingsMode
    HEAT_PUMP_SAVINGS_MODE_MAX_COMFORT: HeatPumpControlSettingsTrait.HeatPumpSavingsMode
    HEAT_PUMP_SAVINGS_MODE_OFF: HeatPumpControlSettingsTrait.HeatPumpSavingsMode
    HEATPUMPAUXTHRESHOLD_FIELD_NUMBER: _ClassVar[int]
    HEATPUMPCOMPTHRESHOLD_FIELD_NUMBER: _ClassVar[int]
    HEATPUMPSAVINGSMODE_FIELD_NUMBER: _ClassVar[int]
    AUXMINDELTA_FIELD_NUMBER: _ClassVar[int]
    AUXMINDELAY_FIELD_NUMBER: _ClassVar[int]
    AUXUPSTAGETHRESHOLD_FIELD_NUMBER: _ClassVar[int]
    DUALFUELCHANGEOVERTHRESHOLD_FIELD_NUMBER: _ClassVar[int]
    heatPumpAuxThreshold: HvacControl.TemperatureThreshold
    heatPumpCompThreshold: HvacControl.TemperatureThreshold
    heatPumpSavingsMode: HeatPumpControlSettingsTrait.HeatPumpSavingsMode
    auxMinDelta: _wrappers_pb2.FloatValue
    auxMinDelay: _duration_pb2.Duration
    auxUpstageThreshold: _duration_pb2.Duration
    dualFuelChangeoverThreshold: _duration_pb2.Duration
    def __init__(self, heatPumpAuxThreshold: _Optional[_Union[HvacControl.TemperatureThreshold, _Mapping]] = ..., heatPumpCompThreshold: _Optional[_Union[HvacControl.TemperatureThreshold, _Mapping]] = ..., heatPumpSavingsMode: _Optional[_Union[HeatPumpControlSettingsTrait.HeatPumpSavingsMode, str]] = ..., auxMinDelta: _Optional[_Union[_wrappers_pb2.FloatValue, _Mapping]] = ..., auxMinDelay: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ..., auxUpstageThreshold: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ..., dualFuelChangeoverThreshold: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ...) -> None: ...

class HvacVendorPartnerInfoTrait(_message.Message):
    __slots__ = ("hvacVendorPartner",)
    class HvacVendorPartner(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        HVAC_VENDOR_PARTNER_UNSPECIFIED: _ClassVar[HvacVendorPartnerInfoTrait.HvacVendorPartner]
        HVAC_VENDOR_PARTNER_GOODMAN: _ClassVar[HvacVendorPartnerInfoTrait.HvacVendorPartner]
    HVAC_VENDOR_PARTNER_UNSPECIFIED: HvacVendorPartnerInfoTrait.HvacVendorPartner
    HVAC_VENDOR_PARTNER_GOODMAN: HvacVendorPartnerInfoTrait.HvacVendorPartner
    HVACVENDORPARTNER_FIELD_NUMBER: _ClassVar[int]
    hvacVendorPartner: HvacVendorPartnerInfoTrait.HvacVendorPartner
    def __init__(self, hvacVendorPartner: _Optional[_Union[HvacVendorPartnerInfoTrait.HvacVendorPartner, str]] = ...) -> None: ...

class NestProtectAlarmingTrait(_message.Message):
    __slots__ = ("nestProtect", "transientProtectItem")
    class AlarmingStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        ALARMING_STATUS_UNSPECIFIED: _ClassVar[NestProtectAlarmingTrait.AlarmingStatus]
        ALARMING_STATUS_HEADSUP_ONE: _ClassVar[NestProtectAlarmingTrait.AlarmingStatus]
        ALARMING_STATUS_HEADSUP_TWO: _ClassVar[NestProtectAlarmingTrait.AlarmingStatus]
        ALARMING_STATUS_ALARMING: _ClassVar[NestProtectAlarmingTrait.AlarmingStatus]
        ALARMING_STATUS_NOT_ALARMING: _ClassVar[NestProtectAlarmingTrait.AlarmingStatus]
    ALARMING_STATUS_UNSPECIFIED: NestProtectAlarmingTrait.AlarmingStatus
    ALARMING_STATUS_HEADSUP_ONE: NestProtectAlarmingTrait.AlarmingStatus
    ALARMING_STATUS_HEADSUP_TWO: NestProtectAlarmingTrait.AlarmingStatus
    ALARMING_STATUS_ALARMING: NestProtectAlarmingTrait.AlarmingStatus
    ALARMING_STATUS_NOT_ALARMING: NestProtectAlarmingTrait.AlarmingStatus
    class NestProtectEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: int
        value: NestProtectAlarmingTrait.NestProtectItem
        def __init__(self, key: _Optional[int] = ..., value: _Optional[_Union[NestProtectAlarmingTrait.NestProtectItem, _Mapping]] = ...) -> None: ...
    class TransientProtectItemEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: int
        value: NestProtectAlarmingTrait.NestProtectItem
        def __init__(self, key: _Optional[int] = ..., value: _Optional[_Union[NestProtectAlarmingTrait.NestProtectItem, _Mapping]] = ...) -> None: ...
    class NestProtectItem(_message.Message):
        __slots__ = ("deviceId", "smokeStatus", "coStatus", "hushedState", "spokenWhereId")
        DEVICEID_FIELD_NUMBER: _ClassVar[int]
        SMOKESTATUS_FIELD_NUMBER: _ClassVar[int]
        COSTATUS_FIELD_NUMBER: _ClassVar[int]
        HUSHEDSTATE_FIELD_NUMBER: _ClassVar[int]
        SPOKENWHEREID_FIELD_NUMBER: _ClassVar[int]
        deviceId: _common_pb2.StringRef
        smokeStatus: NestProtectAlarmingTrait.AlarmingStatus
        coStatus: NestProtectAlarmingTrait.AlarmingStatus
        hushedState: bool
        spokenWhereId: _common_pb2.StringRef
        def __init__(self, deviceId: _Optional[_Union[_common_pb2.StringRef, _Mapping]] = ..., smokeStatus: _Optional[_Union[NestProtectAlarmingTrait.AlarmingStatus, str]] = ..., coStatus: _Optional[_Union[NestProtectAlarmingTrait.AlarmingStatus, str]] = ..., hushedState: bool = ..., spokenWhereId: _Optional[_Union[_common_pb2.StringRef, _Mapping]] = ...) -> None: ...
    NESTPROTECT_FIELD_NUMBER: _ClassVar[int]
    TRANSIENTPROTECTITEM_FIELD_NUMBER: _ClassVar[int]
    nestProtect: _containers.MessageMap[int, NestProtectAlarmingTrait.NestProtectItem]
    transientProtectItem: _containers.MessageMap[int, NestProtectAlarmingTrait.NestProtectItem]
    def __init__(self, nestProtect: _Optional[_Mapping[int, NestProtectAlarmingTrait.NestProtectItem]] = ..., transientProtectItem: _Optional[_Mapping[int, NestProtectAlarmingTrait.NestProtectItem]] = ...) -> None: ...

class PreconditioningTrait(_message.Message):
    __slots__ = ("preconditioningActive", "state")
    class PreconditioningState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        PRECONDITIONING_STATE_UNSPECIFIED: _ClassVar[PreconditioningTrait.PreconditioningState]
        PRECONDITIONING_STATE_NONE: _ClassVar[PreconditioningTrait.PreconditioningState]
        PRECONDITIONING_STATE_HEAT: _ClassVar[PreconditioningTrait.PreconditioningState]
        PRECONDITIONING_STATE_COOL: _ClassVar[PreconditioningTrait.PreconditioningState]
    PRECONDITIONING_STATE_UNSPECIFIED: PreconditioningTrait.PreconditioningState
    PRECONDITIONING_STATE_NONE: PreconditioningTrait.PreconditioningState
    PRECONDITIONING_STATE_HEAT: PreconditioningTrait.PreconditioningState
    PRECONDITIONING_STATE_COOL: PreconditioningTrait.PreconditioningState
    class PreconditioningChangeEvent(_message.Message):
        __slots__ = ("preconditioningActive", "state", "priorState")
        PRECONDITIONINGACTIVE_FIELD_NUMBER: _ClassVar[int]
        STATE_FIELD_NUMBER: _ClassVar[int]
        PRIORSTATE_FIELD_NUMBER: _ClassVar[int]
        preconditioningActive: bool
        state: PreconditioningTrait.PreconditioningState
        priorState: PreconditioningTrait.PreconditioningState
        def __init__(self, preconditioningActive: bool = ..., state: _Optional[_Union[PreconditioningTrait.PreconditioningState, str]] = ..., priorState: _Optional[_Union[PreconditioningTrait.PreconditioningState, str]] = ...) -> None: ...
    PRECONDITIONINGACTIVE_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    preconditioningActive: bool
    state: PreconditioningTrait.PreconditioningState
    def __init__(self, preconditioningActive: bool = ..., state: _Optional[_Union[PreconditioningTrait.PreconditioningState, str]] = ...) -> None: ...

class ResetTrait(_message.Message):
    __slots__ = ()
    class ResetScheduleTo(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        RESET_SCHEDULE_TO_UNSPECIFIED: _ClassVar[ResetTrait.ResetScheduleTo]
        RESET_SCHEDULE_TO_BLANK: _ClassVar[ResetTrait.ResetScheduleTo]
        RESET_SCHEDULE_TO_BASIC: _ClassVar[ResetTrait.ResetScheduleTo]
        RESET_SCHEDULE_TO_RELEARNABLE_BASIC: _ClassVar[ResetTrait.ResetScheduleTo]
    RESET_SCHEDULE_TO_UNSPECIFIED: ResetTrait.ResetScheduleTo
    RESET_SCHEDULE_TO_BLANK: ResetTrait.ResetScheduleTo
    RESET_SCHEDULE_TO_BASIC: ResetTrait.ResetScheduleTo
    RESET_SCHEDULE_TO_RELEARNABLE_BASIC: ResetTrait.ResetScheduleTo
    class ResetTemperatureSchedulesRequest(_message.Message):
        __slots__ = ("resetTo",)
        RESETTO_FIELD_NUMBER: _ClassVar[int]
        resetTo: ResetTrait.ResetScheduleTo
        def __init__(self, resetTo: _Optional[_Union[ResetTrait.ResetScheduleTo, str]] = ...) -> None: ...
    def __init__(self) -> None: ...

class SafetyTemperatureTrait(_message.Message):
    __slots__ = ("safetyTempActivatingHvac", "state")
    class SafetyTempState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        SAFETY_TEMP_STATE_UNSPECIFIED: _ClassVar[SafetyTemperatureTrait.SafetyTempState]
        SAFETY_TEMP_STATE_NONE: _ClassVar[SafetyTemperatureTrait.SafetyTempState]
        SAFETY_TEMP_STATE_HEAT: _ClassVar[SafetyTemperatureTrait.SafetyTempState]
        SAFETY_TEMP_STATE_COOL: _ClassVar[SafetyTemperatureTrait.SafetyTempState]
    SAFETY_TEMP_STATE_UNSPECIFIED: SafetyTemperatureTrait.SafetyTempState
    SAFETY_TEMP_STATE_NONE: SafetyTemperatureTrait.SafetyTempState
    SAFETY_TEMP_STATE_HEAT: SafetyTemperatureTrait.SafetyTempState
    SAFETY_TEMP_STATE_COOL: SafetyTemperatureTrait.SafetyTempState
    class SafetyTempEvent(_message.Message):
        __slots__ = ("state", "priorState", "safetyTemp")
        STATE_FIELD_NUMBER: _ClassVar[int]
        PRIORSTATE_FIELD_NUMBER: _ClassVar[int]
        SAFETYTEMP_FIELD_NUMBER: _ClassVar[int]
        state: SafetyTemperatureTrait.SafetyTempState
        priorState: SafetyTemperatureTrait.SafetyTempState
        safetyTemp: HvacControl.Temperature
        def __init__(self, state: _Optional[_Union[SafetyTemperatureTrait.SafetyTempState, str]] = ..., priorState: _Optional[_Union[SafetyTemperatureTrait.SafetyTempState, str]] = ..., safetyTemp: _Optional[_Union[HvacControl.Temperature, _Mapping]] = ...) -> None: ...
    SAFETYTEMPACTIVATINGHVAC_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    safetyTempActivatingHvac: bool
    state: SafetyTemperatureTrait.SafetyTempState
    def __init__(self, safetyTempActivatingHvac: bool = ..., state: _Optional[_Union[SafetyTemperatureTrait.SafetyTempState, str]] = ...) -> None: ...

class TargetTemperatureSettingsTrait(_message.Message):
    __slots__ = ("targetTemperature", "enabled")
    class SystemModeChangeEvent(_message.Message):
        __slots__ = ("systemEnabled", "method", "originator")
        SYSTEMENABLED_FIELD_NUMBER: _ClassVar[int]
        METHOD_FIELD_NUMBER: _ClassVar[int]
        ORIGINATOR_FIELD_NUMBER: _ClassVar[int]
        systemEnabled: bool
        method: HvacActor.HvacActorMethod
        originator: _common_pb2.ResourceId
        def __init__(self, systemEnabled: bool = ..., method: _Optional[_Union[HvacActor.HvacActorMethod, str]] = ..., originator: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ...) -> None: ...
    class SetPointChangeEvent(_message.Message):
        __slots__ = ("heatingTarget", "coolingTarget", "setpointType", "actor", "changeReason")
        HEATINGTARGET_FIELD_NUMBER: _ClassVar[int]
        COOLINGTARGET_FIELD_NUMBER: _ClassVar[int]
        SETPOINTTYPE_FIELD_NUMBER: _ClassVar[int]
        ACTOR_FIELD_NUMBER: _ClassVar[int]
        CHANGEREASON_FIELD_NUMBER: _ClassVar[int]
        heatingTarget: HvacControl.Temperature
        coolingTarget: HvacControl.Temperature
        setpointType: SetPointScheduleSettingsTrait.SetPointType
        actor: HvacActor.HvacActorStruct
        changeReason: HvacControl.TargetChangeReason
        def __init__(self, heatingTarget: _Optional[_Union[HvacControl.Temperature, _Mapping]] = ..., coolingTarget: _Optional[_Union[HvacControl.Temperature, _Mapping]] = ..., setpointType: _Optional[_Union[SetPointScheduleSettingsTrait.SetPointType, str]] = ..., actor: _Optional[_Union[HvacActor.HvacActorStruct, _Mapping]] = ..., changeReason: _Optional[_Union[HvacControl.TargetChangeReason, str]] = ...) -> None: ...
    TARGETTEMPERATURE_FIELD_NUMBER: _ClassVar[int]
    ENABLED_FIELD_NUMBER: _ClassVar[int]
    targetTemperature: SetPointScheduleSettingsTrait.TemperatureSetPoint
    enabled: _wrappers_pb2.BoolValue
    def __init__(self, targetTemperature: _Optional[_Union[SetPointScheduleSettingsTrait.TemperatureSetPoint, _Mapping]] = ..., enabled: _Optional[_Union[_wrappers_pb2.BoolValue, _Mapping]] = ...) -> None: ...

class AirwaveTrait(_message.Message):
    __slots__ = ("fanCoolingActive", "fanCoolingReadiness")
    class AirwaveChangeEvent(_message.Message):
        __slots__ = ("fanCoolingActive",)
        FANCOOLINGACTIVE_FIELD_NUMBER: _ClassVar[int]
        fanCoolingActive: bool
        def __init__(self, fanCoolingActive: bool = ...) -> None: ...
    FANCOOLINGACTIVE_FIELD_NUMBER: _ClassVar[int]
    FANCOOLINGREADINESS_FIELD_NUMBER: _ClassVar[int]
    fanCoolingActive: bool
    fanCoolingReadiness: bool
    def __init__(self, fanCoolingActive: bool = ..., fanCoolingReadiness: bool = ...) -> None: ...

class CoolToDryTrait(_message.Message):
    __slots__ = ("isActive", "state")
    class CoolToDryState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        COOL_TO_DRY_STATE_UNSPECIFIED: _ClassVar[CoolToDryTrait.CoolToDryState]
        COOL_TO_DRY_STATE_OFF: _ClassVar[CoolToDryTrait.CoolToDryState]
        COOL_TO_DRY_STATE_ON_MOLD_PREVENTION: _ClassVar[CoolToDryTrait.CoolToDryState]
        COOL_TO_DRY_STATE_ON_AC_INTEGRATED: _ClassVar[CoolToDryTrait.CoolToDryState]
    COOL_TO_DRY_STATE_UNSPECIFIED: CoolToDryTrait.CoolToDryState
    COOL_TO_DRY_STATE_OFF: CoolToDryTrait.CoolToDryState
    COOL_TO_DRY_STATE_ON_MOLD_PREVENTION: CoolToDryTrait.CoolToDryState
    COOL_TO_DRY_STATE_ON_AC_INTEGRATED: CoolToDryTrait.CoolToDryState
    ISACTIVE_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    isActive: bool
    state: CoolToDryTrait.CoolToDryState
    def __init__(self, isActive: bool = ..., state: _Optional[_Union[CoolToDryTrait.CoolToDryState, str]] = ...) -> None: ...

class EnterpriseProgramsEntitlementsTrait(_message.Message):
    __slots__ = ("supportedPrograms",)
    class EnterpriseProgram(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        ENTERPRISE_PROGRAM_UNSPECIFIED: _ClassVar[EnterpriseProgramsEntitlementsTrait.EnterpriseProgram]
        ENTERPRISE_PROGRAM_SEASONAL_SAVINGS: _ClassVar[EnterpriseProgramsEntitlementsTrait.EnterpriseProgram]
        ENTERPRISE_PROGRAM_RUSH_HOUR_REWARDS: _ClassVar[EnterpriseProgramsEntitlementsTrait.EnterpriseProgram]
        ENTERPRISE_PROGRAM_TIME_OF_SAVINGS: _ClassVar[EnterpriseProgramsEntitlementsTrait.EnterpriseProgram]
    ENTERPRISE_PROGRAM_UNSPECIFIED: EnterpriseProgramsEntitlementsTrait.EnterpriseProgram
    ENTERPRISE_PROGRAM_SEASONAL_SAVINGS: EnterpriseProgramsEntitlementsTrait.EnterpriseProgram
    ENTERPRISE_PROGRAM_RUSH_HOUR_REWARDS: EnterpriseProgramsEntitlementsTrait.EnterpriseProgram
    ENTERPRISE_PROGRAM_TIME_OF_SAVINGS: EnterpriseProgramsEntitlementsTrait.EnterpriseProgram
    SUPPORTEDPROGRAMS_FIELD_NUMBER: _ClassVar[int]
    supportedPrograms: _containers.RepeatedScalarFieldContainer[EnterpriseProgramsEntitlementsTrait.EnterpriseProgram]
    def __init__(self, supportedPrograms: _Optional[_Iterable[_Union[EnterpriseProgramsEntitlementsTrait.EnterpriseProgram, str]]] = ...) -> None: ...

class FanControlCapabilitiesTrait(_message.Message):
    __slots__ = ("maxAvailableSpeed", "supportsIndefiniteTimer", "supportsTimerInOffMode", "maxTimerDuration")
    class FanTotalStages(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        FAN_TOTAL_STAGES_UNSPECIFIED: _ClassVar[FanControlCapabilitiesTrait.FanTotalStages]
        FAN_TOTAL_STAGES_STAGE1: _ClassVar[FanControlCapabilitiesTrait.FanTotalStages]
        FAN_TOTAL_STAGES_STAGE2: _ClassVar[FanControlCapabilitiesTrait.FanTotalStages]
        FAN_TOTAL_STAGES_STAGE3: _ClassVar[FanControlCapabilitiesTrait.FanTotalStages]
        FAN_TOTAL_STAGES_NONE: _ClassVar[FanControlCapabilitiesTrait.FanTotalStages]
    FAN_TOTAL_STAGES_UNSPECIFIED: FanControlCapabilitiesTrait.FanTotalStages
    FAN_TOTAL_STAGES_STAGE1: FanControlCapabilitiesTrait.FanTotalStages
    FAN_TOTAL_STAGES_STAGE2: FanControlCapabilitiesTrait.FanTotalStages
    FAN_TOTAL_STAGES_STAGE3: FanControlCapabilitiesTrait.FanTotalStages
    FAN_TOTAL_STAGES_NONE: FanControlCapabilitiesTrait.FanTotalStages
    MAXAVAILABLESPEED_FIELD_NUMBER: _ClassVar[int]
    SUPPORTSINDEFINITETIMER_FIELD_NUMBER: _ClassVar[int]
    SUPPORTSTIMERINOFFMODE_FIELD_NUMBER: _ClassVar[int]
    MAXTIMERDURATION_FIELD_NUMBER: _ClassVar[int]
    maxAvailableSpeed: FanControlTrait.FanSpeedSetting
    supportsIndefiniteTimer: bool
    supportsTimerInOffMode: bool
    maxTimerDuration: _duration_pb2.Duration
    def __init__(self, maxAvailableSpeed: _Optional[_Union[FanControlTrait.FanSpeedSetting, str]] = ..., supportsIndefiniteTimer: bool = ..., supportsTimerInOffMode: bool = ..., maxTimerDuration: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ...) -> None: ...

class FilterReminderSettingsTrait(_message.Message):
    __slots__ = ("filterChangedDate", "filterChangedSetDate", "filterReminderEnabled", "filterReplacementThreshold")
    class FilterChangedEvent(_message.Message):
        __slots__ = ("filterChangedDate", "filterChangedSetDate")
        FILTERCHANGEDDATE_FIELD_NUMBER: _ClassVar[int]
        FILTERCHANGEDSETDATE_FIELD_NUMBER: _ClassVar[int]
        filterChangedDate: _timestamp_pb2.Timestamp
        filterChangedSetDate: _timestamp_pb2.Timestamp
        def __init__(self, filterChangedDate: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., filterChangedSetDate: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...
    FILTERCHANGEDDATE_FIELD_NUMBER: _ClassVar[int]
    FILTERCHANGEDSETDATE_FIELD_NUMBER: _ClassVar[int]
    FILTERREMINDERENABLED_FIELD_NUMBER: _ClassVar[int]
    FILTERREPLACEMENTTHRESHOLD_FIELD_NUMBER: _ClassVar[int]
    filterChangedDate: _timestamp_pb2.Timestamp
    filterChangedSetDate: _timestamp_pb2.Timestamp
    filterReminderEnabled: bool
    filterReplacementThreshold: _duration_pb2.Duration
    def __init__(self, filterChangedDate: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., filterChangedSetDate: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., filterReminderEnabled: bool = ..., filterReplacementThreshold: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ...) -> None: ...

class HeatLinkSettingsTrait(_message.Message):
    __slots__ = ("manualModeActive", "heatConnectionType", "hotWaterConnectionType")
    class HeatLinkConnectionType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        HEAT_LINK_CONNECTION_TYPE_UNSPECIFIED: _ClassVar[HeatLinkSettingsTrait.HeatLinkConnectionType]
        HEAT_LINK_CONNECTION_TYPE_ON_OFF: _ClassVar[HeatLinkSettingsTrait.HeatLinkConnectionType]
        HEAT_LINK_CONNECTION_TYPE_OPENTHERM: _ClassVar[HeatLinkSettingsTrait.HeatLinkConnectionType]
        HEAT_LINK_CONNECTION_TYPE_NOT_CONNECTED: _ClassVar[HeatLinkSettingsTrait.HeatLinkConnectionType]
    HEAT_LINK_CONNECTION_TYPE_UNSPECIFIED: HeatLinkSettingsTrait.HeatLinkConnectionType
    HEAT_LINK_CONNECTION_TYPE_ON_OFF: HeatLinkSettingsTrait.HeatLinkConnectionType
    HEAT_LINK_CONNECTION_TYPE_OPENTHERM: HeatLinkSettingsTrait.HeatLinkConnectionType
    HEAT_LINK_CONNECTION_TYPE_NOT_CONNECTED: HeatLinkSettingsTrait.HeatLinkConnectionType
    MANUALMODEACTIVE_FIELD_NUMBER: _ClassVar[int]
    HEATCONNECTIONTYPE_FIELD_NUMBER: _ClassVar[int]
    HOTWATERCONNECTIONTYPE_FIELD_NUMBER: _ClassVar[int]
    manualModeActive: bool
    heatConnectionType: HeatLinkSettingsTrait.HeatLinkConnectionType
    hotWaterConnectionType: HeatLinkSettingsTrait.HeatLinkConnectionType
    def __init__(self, manualModeActive: bool = ..., heatConnectionType: _Optional[_Union[HeatLinkSettingsTrait.HeatLinkConnectionType, str]] = ..., hotWaterConnectionType: _Optional[_Union[HeatLinkSettingsTrait.HeatLinkConnectionType, str]] = ...) -> None: ...

class HeatLinkTrait(_message.Message):
    __slots__ = ("connectionStatus", "heatLinkModel", "heatLinkSerialNumber", "heatLinkSwVersion")
    class HvacConnectionState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        HVAC_CONNECTION_STATE_UNSPECIFIED: _ClassVar[HeatLinkTrait.HvacConnectionState]
        HVAC_CONNECTION_STATE_DISCONNECTED: _ClassVar[HeatLinkTrait.HvacConnectionState]
        HVAC_CONNECTION_STATE_WIRED: _ClassVar[HeatLinkTrait.HvacConnectionState]
        HVAC_CONNECTION_STATE_WIRELESS: _ClassVar[HeatLinkTrait.HvacConnectionState]
        HVAC_CONNECTION_STATE_WIRED_AND_WIRELESS: _ClassVar[HeatLinkTrait.HvacConnectionState]
    HVAC_CONNECTION_STATE_UNSPECIFIED: HeatLinkTrait.HvacConnectionState
    HVAC_CONNECTION_STATE_DISCONNECTED: HeatLinkTrait.HvacConnectionState
    HVAC_CONNECTION_STATE_WIRED: HeatLinkTrait.HvacConnectionState
    HVAC_CONNECTION_STATE_WIRELESS: HeatLinkTrait.HvacConnectionState
    HVAC_CONNECTION_STATE_WIRED_AND_WIRELESS: HeatLinkTrait.HvacConnectionState
    CONNECTIONSTATUS_FIELD_NUMBER: _ClassVar[int]
    HEATLINKMODEL_FIELD_NUMBER: _ClassVar[int]
    HEATLINKSERIALNUMBER_FIELD_NUMBER: _ClassVar[int]
    HEATLINKSWVERSION_FIELD_NUMBER: _ClassVar[int]
    connectionStatus: HeatLinkTrait.HvacConnectionState
    heatLinkModel: _wrappers_pb2.StringValue
    heatLinkSerialNumber: _wrappers_pb2.StringValue
    heatLinkSwVersion: _wrappers_pb2.StringValue
    def __init__(self, connectionStatus: _Optional[_Union[HeatLinkTrait.HvacConnectionState, str]] = ..., heatLinkModel: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., heatLinkSerialNumber: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., heatLinkSwVersion: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ...) -> None: ...

class HotWaterSettingsTrait(_message.Message):
    __slots__ = ("structureModeFollowEnabled", "boostTimerEnd", "mode", "temperature")
    class HotWaterMode(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        HOT_WATER_MODE_UNSPECIFIED: _ClassVar[HotWaterSettingsTrait.HotWaterMode]
        HOT_WATER_MODE_SCHEDULE: _ClassVar[HotWaterSettingsTrait.HotWaterMode]
        HOT_WATER_MODE_OFF: _ClassVar[HotWaterSettingsTrait.HotWaterMode]
    HOT_WATER_MODE_UNSPECIFIED: HotWaterSettingsTrait.HotWaterMode
    HOT_WATER_MODE_SCHEDULE: HotWaterSettingsTrait.HotWaterMode
    HOT_WATER_MODE_OFF: HotWaterSettingsTrait.HotWaterMode
    STRUCTUREMODEFOLLOWENABLED_FIELD_NUMBER: _ClassVar[int]
    BOOSTTIMEREND_FIELD_NUMBER: _ClassVar[int]
    MODE_FIELD_NUMBER: _ClassVar[int]
    TEMPERATURE_FIELD_NUMBER: _ClassVar[int]
    structureModeFollowEnabled: bool
    boostTimerEnd: _timestamp_pb2.Timestamp
    mode: HotWaterSettingsTrait.HotWaterMode
    temperature: HvacControl.Temperature
    def __init__(self, structureModeFollowEnabled: bool = ..., boostTimerEnd: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., mode: _Optional[_Union[HotWaterSettingsTrait.HotWaterMode, str]] = ..., temperature: _Optional[_Union[HvacControl.Temperature, _Mapping]] = ...) -> None: ...

class HvacSensor(_message.Message):
    __slots__ = ()
    class SensorSelection(_message.Message):
        __slots__ = ("isThermostatSelected", "sensorsWithWeaveIds")
        ISTHERMOSTATSELECTED_FIELD_NUMBER: _ClassVar[int]
        SENSORSWITHWEAVEIDS_FIELD_NUMBER: _ClassVar[int]
        isThermostatSelected: bool
        sensorsWithWeaveIds: _containers.RepeatedCompositeFieldContainer[_common_pb2.ResourceId]
        def __init__(self, isThermostatSelected: bool = ..., sensorsWithWeaveIds: _Optional[_Iterable[_Union[_common_pb2.ResourceId, _Mapping]]] = ...) -> None: ...
    def __init__(self) -> None: ...

class LeafTrait(_message.Message):
    __slots__ = ("active", "ecoThresholdHeat", "ecoThresholdCool", "setpointThresholdHeat", "setpointThresholdCool", "scheduleDelta")
    class LeafModeChangeEvent(_message.Message):
        __slots__ = ("active",)
        ACTIVE_FIELD_NUMBER: _ClassVar[int]
        active: bool
        def __init__(self, active: bool = ...) -> None: ...
    ACTIVE_FIELD_NUMBER: _ClassVar[int]
    ECOTHRESHOLDHEAT_FIELD_NUMBER: _ClassVar[int]
    ECOTHRESHOLDCOOL_FIELD_NUMBER: _ClassVar[int]
    SETPOINTTHRESHOLDHEAT_FIELD_NUMBER: _ClassVar[int]
    SETPOINTTHRESHOLDCOOL_FIELD_NUMBER: _ClassVar[int]
    SCHEDULEDELTA_FIELD_NUMBER: _ClassVar[int]
    active: bool
    ecoThresholdHeat: HvacControl.Temperature
    ecoThresholdCool: HvacControl.Temperature
    setpointThresholdHeat: HvacControl.Temperature
    setpointThresholdCool: HvacControl.Temperature
    scheduleDelta: HvacControl.Temperature
    def __init__(self, active: bool = ..., ecoThresholdHeat: _Optional[_Union[HvacControl.Temperature, _Mapping]] = ..., ecoThresholdCool: _Optional[_Union[HvacControl.Temperature, _Mapping]] = ..., setpointThresholdHeat: _Optional[_Union[HvacControl.Temperature, _Mapping]] = ..., setpointThresholdCool: _Optional[_Union[HvacControl.Temperature, _Mapping]] = ..., scheduleDelta: _Optional[_Union[HvacControl.Temperature, _Mapping]] = ...) -> None: ...

class SunblockTrait(_message.Message):
    __slots__ = ("ready", "active")
    class SunblockChangeEvent(_message.Message):
        __slots__ = ("active", "lastChangeTime")
        ACTIVE_FIELD_NUMBER: _ClassVar[int]
        LASTCHANGETIME_FIELD_NUMBER: _ClassVar[int]
        active: bool
        lastChangeTime: _timestamp_pb2.Timestamp
        def __init__(self, active: bool = ..., lastChangeTime: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...
    READY_FIELD_NUMBER: _ClassVar[int]
    ACTIVE_FIELD_NUMBER: _ClassVar[int]
    ready: bool
    active: bool
    def __init__(self, ready: bool = ..., active: bool = ...) -> None: ...

class AirwaveSettingsTrait(_message.Message):
    __slots__ = ("fanCoolingEnabled",)
    FANCOOLINGENABLED_FIELD_NUMBER: _ClassVar[int]
    fanCoolingEnabled: bool
    def __init__(self, fanCoolingEnabled: bool = ...) -> None: ...

class CoolToDrySettingsTrait(_message.Message):
    __slots__ = ("enabled", "overcoolMaxDelta", "minTemperature", "targetHumidity")
    ENABLED_FIELD_NUMBER: _ClassVar[int]
    OVERCOOLMAXDELTA_FIELD_NUMBER: _ClassVar[int]
    MINTEMPERATURE_FIELD_NUMBER: _ClassVar[int]
    TARGETHUMIDITY_FIELD_NUMBER: _ClassVar[int]
    enabled: bool
    overcoolMaxDelta: _wrappers_pb2.FloatValue
    minTemperature: _wrappers_pb2.FloatValue
    targetHumidity: _wrappers_pb2.FloatValue
    def __init__(self, enabled: bool = ..., overcoolMaxDelta: _Optional[_Union[_wrappers_pb2.FloatValue, _Mapping]] = ..., minTemperature: _Optional[_Union[_wrappers_pb2.FloatValue, _Mapping]] = ..., targetHumidity: _Optional[_Union[_wrappers_pb2.FloatValue, _Mapping]] = ...) -> None: ...

class EcoModeSettingsTrait(_message.Message):
    __slots__ = ("structureModeFollowEnabled", "ecoTemperatureHeat", "ecoTemperatureCool", "suppressAutoEcoDuration", "suppressAutoEcoTimeout")
    STRUCTUREMODEFOLLOWENABLED_FIELD_NUMBER: _ClassVar[int]
    ECOTEMPERATUREHEAT_FIELD_NUMBER: _ClassVar[int]
    ECOTEMPERATURECOOL_FIELD_NUMBER: _ClassVar[int]
    SUPPRESSAUTOECODURATION_FIELD_NUMBER: _ClassVar[int]
    SUPPRESSAUTOECOTIMEOUT_FIELD_NUMBER: _ClassVar[int]
    structureModeFollowEnabled: bool
    ecoTemperatureHeat: HvacControl.TemperatureThreshold
    ecoTemperatureCool: HvacControl.TemperatureThreshold
    suppressAutoEcoDuration: _duration_pb2.Duration
    suppressAutoEcoTimeout: _timestamp_pb2.Timestamp
    def __init__(self, structureModeFollowEnabled: bool = ..., ecoTemperatureHeat: _Optional[_Union[HvacControl.TemperatureThreshold, _Mapping]] = ..., ecoTemperatureCool: _Optional[_Union[HvacControl.TemperatureThreshold, _Mapping]] = ..., suppressAutoEcoDuration: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ..., suppressAutoEcoTimeout: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class EcoModeTrait(_message.Message):
    __slots__ = ("currentEcoTemperatureHeat", "currentEcoTemperatureCool")
    CURRENTECOTEMPERATUREHEAT_FIELD_NUMBER: _ClassVar[int]
    CURRENTECOTEMPERATURECOOL_FIELD_NUMBER: _ClassVar[int]
    currentEcoTemperatureHeat: HvacControl.Temperature
    currentEcoTemperatureCool: HvacControl.Temperature
    def __init__(self, currentEcoTemperatureHeat: _Optional[_Union[HvacControl.Temperature, _Mapping]] = ..., currentEcoTemperatureCool: _Optional[_Union[HvacControl.Temperature, _Mapping]] = ...) -> None: ...

class EmergencyHeatSettingsTrait(_message.Message):
    __slots__ = ("emergencyHeatEnabled",)
    EMERGENCYHEATENABLED_FIELD_NUMBER: _ClassVar[int]
    emergencyHeatEnabled: bool
    def __init__(self, emergencyHeatEnabled: bool = ...) -> None: ...

class HeatPumpControlTrait(_message.Message):
    __slots__ = ("heatPumpReady", "heatPumpSetbackActive")
    HEATPUMPREADY_FIELD_NUMBER: _ClassVar[int]
    HEATPUMPSETBACKACTIVE_FIELD_NUMBER: _ClassVar[int]
    heatPumpReady: bool
    heatPumpSetbackActive: bool
    def __init__(self, heatPumpReady: bool = ..., heatPumpSetbackActive: bool = ...) -> None: ...

class HotWaterTrait(_message.Message):
    __slots__ = ("controlActive", "awayActive", "boilerActive", "nextTransitionTime", "temperature")
    CONTROLACTIVE_FIELD_NUMBER: _ClassVar[int]
    AWAYACTIVE_FIELD_NUMBER: _ClassVar[int]
    BOILERACTIVE_FIELD_NUMBER: _ClassVar[int]
    NEXTTRANSITIONTIME_FIELD_NUMBER: _ClassVar[int]
    TEMPERATURE_FIELD_NUMBER: _ClassVar[int]
    controlActive: bool
    awayActive: bool
    boilerActive: bool
    nextTransitionTime: _timestamp_pb2.Timestamp
    temperature: HvacControl.Temperature
    def __init__(self, controlActive: bool = ..., awayActive: bool = ..., boilerActive: bool = ..., nextTransitionTime: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., temperature: _Optional[_Union[HvacControl.Temperature, _Mapping]] = ...) -> None: ...

class HumidityControlSettingsTrait(_message.Message):
    __slots__ = ("targetHumidity", "quietTimesEnabled", "quietStartSecondsInDay", "quietEndSecondsInDay", "humidifierTargetHumidity", "dehumidifierTargetHumidity")
    TARGETHUMIDITY_FIELD_NUMBER: _ClassVar[int]
    QUIETTIMESENABLED_FIELD_NUMBER: _ClassVar[int]
    QUIETSTARTSECONDSINDAY_FIELD_NUMBER: _ClassVar[int]
    QUIETENDSECONDSINDAY_FIELD_NUMBER: _ClassVar[int]
    HUMIDIFIERTARGETHUMIDITY_FIELD_NUMBER: _ClassVar[int]
    DEHUMIDIFIERTARGETHUMIDITY_FIELD_NUMBER: _ClassVar[int]
    targetHumidity: HvacControl.HumidityThreshold
    quietTimesEnabled: bool
    quietStartSecondsInDay: int
    quietEndSecondsInDay: int
    humidifierTargetHumidity: HvacControl.HumidityThreshold
    dehumidifierTargetHumidity: HvacControl.HumidityThreshold
    def __init__(self, targetHumidity: _Optional[_Union[HvacControl.HumidityThreshold, _Mapping]] = ..., quietTimesEnabled: bool = ..., quietStartSecondsInDay: _Optional[int] = ..., quietEndSecondsInDay: _Optional[int] = ..., humidifierTargetHumidity: _Optional[_Union[HvacControl.HumidityThreshold, _Mapping]] = ..., dehumidifierTargetHumidity: _Optional[_Union[HvacControl.HumidityThreshold, _Mapping]] = ...) -> None: ...

class HvacDisplayTrait(_message.Message):
    __slots__ = ("ignoreHvacStaging", "thermostatState")
    IGNOREHVACSTAGING_FIELD_NUMBER: _ClassVar[int]
    THERMOSTATSTATE_FIELD_NUMBER: _ClassVar[int]
    ignoreHvacStaging: bool
    thermostatState: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, ignoreHvacStaging: bool = ..., thermostatState: _Optional[_Iterable[str]] = ...) -> None: ...

class HvacEquipmentCapabilitiesTrait(_message.Message):
    __slots__ = ("hasStage1Cool", "hasStage2Cool", "hasStage3Cool", "hasStage1Heat", "hasStage2Heat", "hasStage3Heat", "hasStage1AlternateHeat", "hasStage2AlternateHeat", "hasHumidifier", "hasDehumidifier", "hasDualFuel", "hasAuxHeat", "hasEmergencyHeat", "hasAirFilter", "hasFossilFuel", "hasHotWaterControl", "hasHeatPump", "hasHotWaterTemperature", "hasBoilerSupplyTemperature", "hasVentilator")
    HASSTAGE1COOL_FIELD_NUMBER: _ClassVar[int]
    HASSTAGE2COOL_FIELD_NUMBER: _ClassVar[int]
    HASSTAGE3COOL_FIELD_NUMBER: _ClassVar[int]
    HASSTAGE1HEAT_FIELD_NUMBER: _ClassVar[int]
    HASSTAGE2HEAT_FIELD_NUMBER: _ClassVar[int]
    HASSTAGE3HEAT_FIELD_NUMBER: _ClassVar[int]
    HASSTAGE1ALTERNATEHEAT_FIELD_NUMBER: _ClassVar[int]
    HASSTAGE2ALTERNATEHEAT_FIELD_NUMBER: _ClassVar[int]
    HASHUMIDIFIER_FIELD_NUMBER: _ClassVar[int]
    HASDEHUMIDIFIER_FIELD_NUMBER: _ClassVar[int]
    HASDUALFUEL_FIELD_NUMBER: _ClassVar[int]
    HASAUXHEAT_FIELD_NUMBER: _ClassVar[int]
    HASEMERGENCYHEAT_FIELD_NUMBER: _ClassVar[int]
    HASAIRFILTER_FIELD_NUMBER: _ClassVar[int]
    HASFOSSILFUEL_FIELD_NUMBER: _ClassVar[int]
    HASHOTWATERCONTROL_FIELD_NUMBER: _ClassVar[int]
    HASHEATPUMP_FIELD_NUMBER: _ClassVar[int]
    HASHOTWATERTEMPERATURE_FIELD_NUMBER: _ClassVar[int]
    HASBOILERSUPPLYTEMPERATURE_FIELD_NUMBER: _ClassVar[int]
    HASVENTILATOR_FIELD_NUMBER: _ClassVar[int]
    hasStage1Cool: bool
    hasStage2Cool: bool
    hasStage3Cool: bool
    hasStage1Heat: bool
    hasStage2Heat: bool
    hasStage3Heat: bool
    hasStage1AlternateHeat: bool
    hasStage2AlternateHeat: bool
    hasHumidifier: bool
    hasDehumidifier: bool
    hasDualFuel: bool
    hasAuxHeat: bool
    hasEmergencyHeat: bool
    hasAirFilter: bool
    hasFossilFuel: bool
    hasHotWaterControl: bool
    hasHeatPump: bool
    hasHotWaterTemperature: bool
    hasBoilerSupplyTemperature: bool
    hasVentilator: bool
    def __init__(self, hasStage1Cool: bool = ..., hasStage2Cool: bool = ..., hasStage3Cool: bool = ..., hasStage1Heat: bool = ..., hasStage2Heat: bool = ..., hasStage3Heat: bool = ..., hasStage1AlternateHeat: bool = ..., hasStage2AlternateHeat: bool = ..., hasHumidifier: bool = ..., hasDehumidifier: bool = ..., hasDualFuel: bool = ..., hasAuxHeat: bool = ..., hasEmergencyHeat: bool = ..., hasAirFilter: bool = ..., hasFossilFuel: bool = ..., hasHotWaterControl: bool = ..., hasHeatPump: bool = ..., hasHotWaterTemperature: bool = ..., hasBoilerSupplyTemperature: bool = ..., hasVentilator: bool = ...) -> None: ...

class InstallationSettingsTrait(_message.Message):
    __slots__ = ("oobWifiCompleted", "oobHomeInfoCompleted", "oobWhereCompleted", "oobWiresCompleted", "oobTempCompleted", "oobTestCompleted", "oobSummaryCompleted", "oobStartupCompleted", "proId")
    OOBWIFICOMPLETED_FIELD_NUMBER: _ClassVar[int]
    OOBHOMEINFOCOMPLETED_FIELD_NUMBER: _ClassVar[int]
    OOBWHERECOMPLETED_FIELD_NUMBER: _ClassVar[int]
    OOBWIRESCOMPLETED_FIELD_NUMBER: _ClassVar[int]
    OOBTEMPCOMPLETED_FIELD_NUMBER: _ClassVar[int]
    OOBTESTCOMPLETED_FIELD_NUMBER: _ClassVar[int]
    OOBSUMMARYCOMPLETED_FIELD_NUMBER: _ClassVar[int]
    OOBSTARTUPCOMPLETED_FIELD_NUMBER: _ClassVar[int]
    PROID_FIELD_NUMBER: _ClassVar[int]
    oobWifiCompleted: bool
    oobHomeInfoCompleted: bool
    oobWhereCompleted: bool
    oobWiresCompleted: bool
    oobTempCompleted: bool
    oobTestCompleted: bool
    oobSummaryCompleted: bool
    oobStartupCompleted: bool
    proId: _wrappers_pb2.StringValue
    def __init__(self, oobWifiCompleted: bool = ..., oobHomeInfoCompleted: bool = ..., oobWhereCompleted: bool = ..., oobWiresCompleted: bool = ..., oobTempCompleted: bool = ..., oobTestCompleted: bool = ..., oobSummaryCompleted: bool = ..., oobStartupCompleted: bool = ..., proId: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ...) -> None: ...

class PreconditioningSettingsTrait(_message.Message):
    __slots__ = ("preconditioningEnabled", "maxNighttimeSeconds", "heatPreconditioningEnabled", "coolPreconditioningEnabled", "returnHomePreconditioningEnabled")
    PRECONDITIONINGENABLED_FIELD_NUMBER: _ClassVar[int]
    MAXNIGHTTIMESECONDS_FIELD_NUMBER: _ClassVar[int]
    HEATPRECONDITIONINGENABLED_FIELD_NUMBER: _ClassVar[int]
    COOLPRECONDITIONINGENABLED_FIELD_NUMBER: _ClassVar[int]
    RETURNHOMEPRECONDITIONINGENABLED_FIELD_NUMBER: _ClassVar[int]
    preconditioningEnabled: bool
    maxNighttimeSeconds: _duration_pb2.Duration
    heatPreconditioningEnabled: bool
    coolPreconditioningEnabled: bool
    returnHomePreconditioningEnabled: bool
    def __init__(self, preconditioningEnabled: bool = ..., maxNighttimeSeconds: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ..., heatPreconditioningEnabled: bool = ..., coolPreconditioningEnabled: bool = ..., returnHomePreconditioningEnabled: bool = ...) -> None: ...

class RadiantControlSettingsTrait(_message.Message):
    __slots__ = ("radiantControlEnabled",)
    RADIANTCONTROLENABLED_FIELD_NUMBER: _ClassVar[int]
    radiantControlEnabled: bool
    def __init__(self, radiantControlEnabled: bool = ...) -> None: ...

class SafetyShutoffCapabilitiesTrait(_message.Message):
    __slots__ = ("smokeShutoffSupported",)
    SMOKESHUTOFFSUPPORTED_FIELD_NUMBER: _ClassVar[int]
    smokeShutoffSupported: bool
    def __init__(self, smokeShutoffSupported: bool = ...) -> None: ...

class SafetyShutoffSettingsTrait(_message.Message):
    __slots__ = ("hvacCoSafetyShutoffEnabled", "hvacSmokeSafetyShutoffEnabled")
    HVACCOSAFETYSHUTOFFENABLED_FIELD_NUMBER: _ClassVar[int]
    HVACSMOKESAFETYSHUTOFFENABLED_FIELD_NUMBER: _ClassVar[int]
    hvacCoSafetyShutoffEnabled: bool
    hvacSmokeSafetyShutoffEnabled: bool
    def __init__(self, hvacCoSafetyShutoffEnabled: bool = ..., hvacSmokeSafetyShutoffEnabled: bool = ...) -> None: ...

class SafetyTemperatureSettingsTrait(_message.Message):
    __slots__ = ("lowerSafetyTemp", "upperSafetyTemp")
    LOWERSAFETYTEMP_FIELD_NUMBER: _ClassVar[int]
    UPPERSAFETYTEMP_FIELD_NUMBER: _ClassVar[int]
    lowerSafetyTemp: HvacControl.TemperatureThreshold
    upperSafetyTemp: HvacControl.TemperatureThreshold
    def __init__(self, lowerSafetyTemp: _Optional[_Union[HvacControl.TemperatureThreshold, _Mapping]] = ..., upperSafetyTemp: _Optional[_Union[HvacControl.TemperatureThreshold, _Mapping]] = ...) -> None: ...

class ScheduleLearningSettingsTrait(_message.Message):
    __slots__ = ("scheduleLearningEnabled",)
    SCHEDULELEARNINGENABLED_FIELD_NUMBER: _ClassVar[int]
    scheduleLearningEnabled: bool
    def __init__(self, scheduleLearningEnabled: bool = ...) -> None: ...

class SunblockSettingsTrait(_message.Message):
    __slots__ = ("enabled",)
    ENABLED_FIELD_NUMBER: _ClassVar[int]
    enabled: bool
    def __init__(self, enabled: bool = ...) -> None: ...

class TemperatureLockSettingsTrait(_message.Message):
    __slots__ = ("enabled", "temperatureHigh", "temperatureLow", "pinHash")
    ENABLED_FIELD_NUMBER: _ClassVar[int]
    TEMPERATUREHIGH_FIELD_NUMBER: _ClassVar[int]
    TEMPERATURELOW_FIELD_NUMBER: _ClassVar[int]
    PINHASH_FIELD_NUMBER: _ClassVar[int]
    enabled: bool
    temperatureHigh: HvacControl.Temperature
    temperatureLow: HvacControl.Temperature
    pinHash: str
    def __init__(self, enabled: bool = ..., temperatureHigh: _Optional[_Union[HvacControl.Temperature, _Mapping]] = ..., temperatureLow: _Optional[_Union[HvacControl.Temperature, _Mapping]] = ..., pinHash: _Optional[str] = ...) -> None: ...

class TimeToTemperatureTrait(_message.Message):
    __slots__ = ("timeToTargetTemperature", "predictedTimeOfReachingTarget")
    TIMETOTARGETTEMPERATURE_FIELD_NUMBER: _ClassVar[int]
    PREDICTEDTIMEOFREACHINGTARGET_FIELD_NUMBER: _ClassVar[int]
    timeToTargetTemperature: _duration_pb2.Duration
    predictedTimeOfReachingTarget: _timestamp_pb2.Timestamp
    def __init__(self, timeToTargetTemperature: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ..., predictedTimeOfReachingTarget: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class UtilitySettingsTrait(_message.Message):
    __slots__ = ("demandResponseEnabled", "touEnabled", "demandChargeEnabled")
    DEMANDRESPONSEENABLED_FIELD_NUMBER: _ClassVar[int]
    TOUENABLED_FIELD_NUMBER: _ClassVar[int]
    DEMANDCHARGEENABLED_FIELD_NUMBER: _ClassVar[int]
    demandResponseEnabled: bool
    touEnabled: bool
    demandChargeEnabled: bool
    def __init__(self, demandResponseEnabled: bool = ..., touEnabled: bool = ..., demandChargeEnabled: bool = ...) -> None: ...

class WakeOnApproachSettingsTrait(_message.Message):
    __slots__ = ("enabled",)
    ENABLED_FIELD_NUMBER: _ClassVar[int]
    enabled: bool
    def __init__(self, enabled: bool = ...) -> None: ...

class KryptoniteObservedBeaconTrait(_message.Message):
    __slots__ = ("lastBeaconTime",)
    LASTBEACONTIME_FIELD_NUMBER: _ClassVar[int]
    lastBeaconTime: _timestamp_pb2.Timestamp
    def __init__(self, lastBeaconTime: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...
