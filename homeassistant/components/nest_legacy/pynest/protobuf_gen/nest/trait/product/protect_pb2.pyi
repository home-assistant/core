import datetime

from google.protobuf import duration_pb2 as _duration_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf import wrappers_pb2 as _wrappers_pb2
from ....nest.trait import selftest_pb2 as _selftest_pb2
from ....weave import common_pb2 as _common_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class LegacyStructureSelfTestTrait(_message.Message):
    __slots__ = ("lastMstCancelled", "mstInProgress", "lastMstStartUtcSecs", "lastMstEndUtcSecs", "lastMstSuccessUtcSecs", "astInProgress", "lastAstStartUtcSecs", "lastAstEndUtcSecs", "astRequestUtcSecs", "astSkipUtcSecs", "astParticipants")
    class SelfTestType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        SELF_TEST_TYPE_UNSPECIFIED: _ClassVar[LegacyStructureSelfTestTrait.SelfTestType]
        SELF_TEST_TYPE_AST: _ClassVar[LegacyStructureSelfTestTrait.SelfTestType]
        SELF_TEST_TYPE_MST: _ClassVar[LegacyStructureSelfTestTrait.SelfTestType]
    SELF_TEST_TYPE_UNSPECIFIED: LegacyStructureSelfTestTrait.SelfTestType
    SELF_TEST_TYPE_AST: LegacyStructureSelfTestTrait.SelfTestType
    SELF_TEST_TYPE_MST: LegacyStructureSelfTestTrait.SelfTestType
    class StartSelfTestStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        START_SELF_TEST_STATUS_UNSPECIFIED: _ClassVar[LegacyStructureSelfTestTrait.StartSelfTestStatus]
        START_SELF_TEST_STATUS_OK: _ClassVar[LegacyStructureSelfTestTrait.StartSelfTestStatus]
        START_SELF_TEST_STATUS_FAILED: _ClassVar[LegacyStructureSelfTestTrait.StartSelfTestStatus]
    START_SELF_TEST_STATUS_UNSPECIFIED: LegacyStructureSelfTestTrait.StartSelfTestStatus
    START_SELF_TEST_STATUS_OK: LegacyStructureSelfTestTrait.StartSelfTestStatus
    START_SELF_TEST_STATUS_FAILED: LegacyStructureSelfTestTrait.StartSelfTestStatus
    class EndSelfTestStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        END_SELF_TEST_STATUS_UNSPECIFIED: _ClassVar[LegacyStructureSelfTestTrait.EndSelfTestStatus]
        END_SELF_TEST_STATUS_OK: _ClassVar[LegacyStructureSelfTestTrait.EndSelfTestStatus]
        END_SELF_TEST_STATUS_FAILED: _ClassVar[LegacyStructureSelfTestTrait.EndSelfTestStatus]
    END_SELF_TEST_STATUS_UNSPECIFIED: LegacyStructureSelfTestTrait.EndSelfTestStatus
    END_SELF_TEST_STATUS_OK: LegacyStructureSelfTestTrait.EndSelfTestStatus
    END_SELF_TEST_STATUS_FAILED: LegacyStructureSelfTestTrait.EndSelfTestStatus
    class StartSelfTestRequest(_message.Message):
        __slots__ = ("type", "testId")
        TYPE_FIELD_NUMBER: _ClassVar[int]
        TESTID_FIELD_NUMBER: _ClassVar[int]
        type: LegacyStructureSelfTestTrait.SelfTestType
        testId: _selftest_pb2.SelfTestRunnerTrait.TestId
        def __init__(self, type: _Optional[_Union[LegacyStructureSelfTestTrait.SelfTestType, str]] = ..., testId: _Optional[_Union[_selftest_pb2.SelfTestRunnerTrait.TestId, _Mapping]] = ...) -> None: ...
    class StartSelfTestResponse(_message.Message):
        __slots__ = ("status",)
        STATUS_FIELD_NUMBER: _ClassVar[int]
        status: LegacyStructureSelfTestTrait.StartSelfTestStatus
        def __init__(self, status: _Optional[_Union[LegacyStructureSelfTestTrait.StartSelfTestStatus, str]] = ...) -> None: ...
    class EndSelfTestRequest(_message.Message):
        __slots__ = ("type", "testId")
        TYPE_FIELD_NUMBER: _ClassVar[int]
        TESTID_FIELD_NUMBER: _ClassVar[int]
        type: LegacyStructureSelfTestTrait.SelfTestType
        testId: _selftest_pb2.SelfTestRunnerTrait.TestId
        def __init__(self, type: _Optional[_Union[LegacyStructureSelfTestTrait.SelfTestType, str]] = ..., testId: _Optional[_Union[_selftest_pb2.SelfTestRunnerTrait.TestId, _Mapping]] = ...) -> None: ...
    class EndSelfTestResponse(_message.Message):
        __slots__ = ("status",)
        STATUS_FIELD_NUMBER: _ClassVar[int]
        status: LegacyStructureSelfTestTrait.EndSelfTestStatus
        def __init__(self, status: _Optional[_Union[LegacyStructureSelfTestTrait.EndSelfTestStatus, str]] = ...) -> None: ...
    class AutomatedSelfTestSkipEvent(_message.Message):
        __slots__ = ()
        def __init__(self) -> None: ...
    class AutomatedSelfTestCompleteEvent(_message.Message):
        __slots__ = ()
        def __init__(self) -> None: ...
    class ManualSelfTestCompleteEvent(_message.Message):
        __slots__ = ()
        def __init__(self) -> None: ...
    LASTMSTCANCELLED_FIELD_NUMBER: _ClassVar[int]
    MSTINPROGRESS_FIELD_NUMBER: _ClassVar[int]
    LASTMSTSTARTUTCSECS_FIELD_NUMBER: _ClassVar[int]
    LASTMSTENDUTCSECS_FIELD_NUMBER: _ClassVar[int]
    LASTMSTSUCCESSUTCSECS_FIELD_NUMBER: _ClassVar[int]
    ASTINPROGRESS_FIELD_NUMBER: _ClassVar[int]
    LASTASTSTARTUTCSECS_FIELD_NUMBER: _ClassVar[int]
    LASTASTENDUTCSECS_FIELD_NUMBER: _ClassVar[int]
    ASTREQUESTUTCSECS_FIELD_NUMBER: _ClassVar[int]
    ASTSKIPUTCSECS_FIELD_NUMBER: _ClassVar[int]
    ASTPARTICIPANTS_FIELD_NUMBER: _ClassVar[int]
    lastMstCancelled: bool
    mstInProgress: bool
    lastMstStartUtcSecs: _timestamp_pb2.Timestamp
    lastMstEndUtcSecs: _timestamp_pb2.Timestamp
    lastMstSuccessUtcSecs: _timestamp_pb2.Timestamp
    astInProgress: bool
    lastAstStartUtcSecs: _timestamp_pb2.Timestamp
    lastAstEndUtcSecs: _timestamp_pb2.Timestamp
    astRequestUtcSecs: _timestamp_pb2.Timestamp
    astSkipUtcSecs: _timestamp_pb2.Timestamp
    astParticipants: _containers.RepeatedScalarFieldContainer[int]
    def __init__(self, lastMstCancelled: bool = ..., mstInProgress: bool = ..., lastMstStartUtcSecs: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., lastMstEndUtcSecs: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., lastMstSuccessUtcSecs: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., astInProgress: bool = ..., lastAstStartUtcSecs: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., lastAstEndUtcSecs: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., astRequestUtcSecs: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., astSkipUtcSecs: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., astParticipants: _Optional[_Iterable[int]] = ...) -> None: ...

class SelfTestTrait(_message.Message):
    __slots__ = ("lastMstStart", "lastMstEnd", "lastMstCancelled", "lastAstStart", "lastAstEnd")
    class SelfTestType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        SELF_TEST_TYPE_UNSPECIFIED: _ClassVar[SelfTestTrait.SelfTestType]
        SELF_TEST_TYPE_AST: _ClassVar[SelfTestTrait.SelfTestType]
        SELF_TEST_TYPE_MST: _ClassVar[SelfTestTrait.SelfTestType]
    SELF_TEST_TYPE_UNSPECIFIED: SelfTestTrait.SelfTestType
    SELF_TEST_TYPE_AST: SelfTestTrait.SelfTestType
    SELF_TEST_TYPE_MST: SelfTestTrait.SelfTestType
    class StartSelfTestStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        START_SELF_TEST_STATUS_UNSPECIFIED: _ClassVar[SelfTestTrait.StartSelfTestStatus]
        START_SELF_TEST_STATUS_OK: _ClassVar[SelfTestTrait.StartSelfTestStatus]
        START_SELF_TEST_STATUS_FAILED: _ClassVar[SelfTestTrait.StartSelfTestStatus]
    START_SELF_TEST_STATUS_UNSPECIFIED: SelfTestTrait.StartSelfTestStatus
    START_SELF_TEST_STATUS_OK: SelfTestTrait.StartSelfTestStatus
    START_SELF_TEST_STATUS_FAILED: SelfTestTrait.StartSelfTestStatus
    class EndSelfTestStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        END_SELF_TEST_STATUS_UNSPECIFIED: _ClassVar[SelfTestTrait.EndSelfTestStatus]
        END_SELF_TEST_STATUS_OK: _ClassVar[SelfTestTrait.EndSelfTestStatus]
        END_SELF_TEST_STATUS_FAILED: _ClassVar[SelfTestTrait.EndSelfTestStatus]
    END_SELF_TEST_STATUS_UNSPECIFIED: SelfTestTrait.EndSelfTestStatus
    END_SELF_TEST_STATUS_OK: SelfTestTrait.EndSelfTestStatus
    END_SELF_TEST_STATUS_FAILED: SelfTestTrait.EndSelfTestStatus
    class MstTrigger(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        MST_TRIGGER_UNSPECIFIED: _ClassVar[SelfTestTrait.MstTrigger]
        MST_TRIGGER_BUTTON: _ClassVar[SelfTestTrait.MstTrigger]
        MST_TRIGGER_REMOTE: _ClassVar[SelfTestTrait.MstTrigger]
        MST_TRIGGER_APP: _ClassVar[SelfTestTrait.MstTrigger]
    MST_TRIGGER_UNSPECIFIED: SelfTestTrait.MstTrigger
    MST_TRIGGER_BUTTON: SelfTestTrait.MstTrigger
    MST_TRIGGER_REMOTE: SelfTestTrait.MstTrigger
    MST_TRIGGER_APP: SelfTestTrait.MstTrigger
    class StartSelfTestRequest(_message.Message):
        __slots__ = ("type", "testId")
        TYPE_FIELD_NUMBER: _ClassVar[int]
        TESTID_FIELD_NUMBER: _ClassVar[int]
        type: SelfTestTrait.SelfTestType
        testId: _selftest_pb2.SelfTestRunnerTrait.TestId
        def __init__(self, type: _Optional[_Union[SelfTestTrait.SelfTestType, str]] = ..., testId: _Optional[_Union[_selftest_pb2.SelfTestRunnerTrait.TestId, _Mapping]] = ...) -> None: ...
    class StartSelfTestResponse(_message.Message):
        __slots__ = ("status",)
        STATUS_FIELD_NUMBER: _ClassVar[int]
        status: SelfTestTrait.StartSelfTestStatus
        def __init__(self, status: _Optional[_Union[SelfTestTrait.StartSelfTestStatus, str]] = ...) -> None: ...
    class EndSelfTestRequest(_message.Message):
        __slots__ = ("type", "testId")
        TYPE_FIELD_NUMBER: _ClassVar[int]
        TESTID_FIELD_NUMBER: _ClassVar[int]
        type: SelfTestTrait.SelfTestType
        testId: _selftest_pb2.SelfTestRunnerTrait.TestId
        def __init__(self, type: _Optional[_Union[SelfTestTrait.SelfTestType, str]] = ..., testId: _Optional[_Union[_selftest_pb2.SelfTestRunnerTrait.TestId, _Mapping]] = ...) -> None: ...
    class EndSelfTestResponse(_message.Message):
        __slots__ = ("status",)
        STATUS_FIELD_NUMBER: _ClassVar[int]
        status: SelfTestTrait.EndSelfTestStatus
        def __init__(self, status: _Optional[_Union[SelfTestTrait.EndSelfTestStatus, str]] = ...) -> None: ...
    class MstTransitionEvent(_message.Message):
        __slots__ = ("trigger", "newState", "oldState")
        TRIGGER_FIELD_NUMBER: _ClassVar[int]
        NEWSTATE_FIELD_NUMBER: _ClassVar[int]
        OLDSTATE_FIELD_NUMBER: _ClassVar[int]
        trigger: SelfTestTrait.MstTrigger
        newState: int
        oldState: int
        def __init__(self, trigger: _Optional[_Union[SelfTestTrait.MstTrigger, str]] = ..., newState: _Optional[int] = ..., oldState: _Optional[int] = ...) -> None: ...
    class AstTransitionEvent(_message.Message):
        __slots__ = ("orchestrator", "newState", "oldState")
        ORCHESTRATOR_FIELD_NUMBER: _ClassVar[int]
        NEWSTATE_FIELD_NUMBER: _ClassVar[int]
        OLDSTATE_FIELD_NUMBER: _ClassVar[int]
        orchestrator: bool
        newState: int
        oldState: int
        def __init__(self, orchestrator: bool = ..., newState: _Optional[int] = ..., oldState: _Optional[int] = ...) -> None: ...
    LASTMSTSTART_FIELD_NUMBER: _ClassVar[int]
    LASTMSTEND_FIELD_NUMBER: _ClassVar[int]
    LASTMSTCANCELLED_FIELD_NUMBER: _ClassVar[int]
    LASTASTSTART_FIELD_NUMBER: _ClassVar[int]
    LASTASTEND_FIELD_NUMBER: _ClassVar[int]
    lastMstStart: _timestamp_pb2.Timestamp
    lastMstEnd: _timestamp_pb2.Timestamp
    lastMstCancelled: bool
    lastAstStart: _timestamp_pb2.Timestamp
    lastAstEnd: _timestamp_pb2.Timestamp
    def __init__(self, lastMstStart: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., lastMstEnd: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., lastMstCancelled: bool = ..., lastAstStart: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., lastAstEnd: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class AudioTestTrait(_message.Message):
    __slots__ = ("speakerResult", "buzzerResult")
    class AudioTestSource(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        AUDIO_TEST_SOURCE_UNSPECIFIED: _ClassVar[AudioTestTrait.AudioTestSource]
        AUDIO_TEST_SOURCE_AUTOMATIC: _ClassVar[AudioTestTrait.AudioTestSource]
        AUDIO_TEST_SOURCE_MANUAL: _ClassVar[AudioTestTrait.AudioTestSource]
    AUDIO_TEST_SOURCE_UNSPECIFIED: AudioTestTrait.AudioTestSource
    AUDIO_TEST_SOURCE_AUTOMATIC: AudioTestTrait.AudioTestSource
    AUDIO_TEST_SOURCE_MANUAL: AudioTestTrait.AudioTestSource
    class AudioFaultType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        AUDIO_FAULT_TYPE_UNSPECIFIED: _ClassVar[AudioTestTrait.AudioFaultType]
        AUDIO_FAULT_TYPE_INCONCLUSIVE_OTHER: _ClassVar[AudioTestTrait.AudioFaultType]
        AUDIO_FAULT_TYPE_INCONCLUSIVE_AMBIENT_NOISE: _ClassVar[AudioTestTrait.AudioFaultType]
        AUDIO_FAULT_TYPE_INCONCLUSIVE_ASYNC_INTER: _ClassVar[AudioTestTrait.AudioFaultType]
        AUDIO_FAULT_TYPE_INCONCLUSIVE_DID_NOT_RUN: _ClassVar[AudioTestTrait.AudioFaultType]
        AUDIO_FAULT_TYPE_INCONCLUSIVE_DROPPED_BUFFER: _ClassVar[AudioTestTrait.AudioFaultType]
    AUDIO_FAULT_TYPE_UNSPECIFIED: AudioTestTrait.AudioFaultType
    AUDIO_FAULT_TYPE_INCONCLUSIVE_OTHER: AudioTestTrait.AudioFaultType
    AUDIO_FAULT_TYPE_INCONCLUSIVE_AMBIENT_NOISE: AudioTestTrait.AudioFaultType
    AUDIO_FAULT_TYPE_INCONCLUSIVE_ASYNC_INTER: AudioTestTrait.AudioFaultType
    AUDIO_FAULT_TYPE_INCONCLUSIVE_DID_NOT_RUN: AudioTestTrait.AudioFaultType
    AUDIO_FAULT_TYPE_INCONCLUSIVE_DROPPED_BUFFER: AudioTestTrait.AudioFaultType
    class AudioTestResult(_message.Message):
        __slots__ = ("source", "testPassed", "types")
        SOURCE_FIELD_NUMBER: _ClassVar[int]
        TESTPASSED_FIELD_NUMBER: _ClassVar[int]
        TYPES_FIELD_NUMBER: _ClassVar[int]
        source: AudioTestTrait.AudioTestSource
        testPassed: bool
        types: _containers.RepeatedScalarFieldContainer[AudioTestTrait.AudioFaultType]
        def __init__(self, source: _Optional[_Union[AudioTestTrait.AudioTestSource, str]] = ..., testPassed: bool = ..., types: _Optional[_Iterable[_Union[AudioTestTrait.AudioFaultType, str]]] = ...) -> None: ...
    class AudioTestStartEvent(_message.Message):
        __slots__ = ("source",)
        SOURCE_FIELD_NUMBER: _ClassVar[int]
        source: AudioTestTrait.AudioTestSource
        def __init__(self, source: _Optional[_Union[AudioTestTrait.AudioTestSource, str]] = ...) -> None: ...
    class AudioTestEndEvent(_message.Message):
        __slots__ = ("speakerResult", "buzzerResult")
        SPEAKERRESULT_FIELD_NUMBER: _ClassVar[int]
        BUZZERRESULT_FIELD_NUMBER: _ClassVar[int]
        speakerResult: AudioTestTrait.AudioTestResult
        buzzerResult: AudioTestTrait.AudioTestResult
        def __init__(self, speakerResult: _Optional[_Union[AudioTestTrait.AudioTestResult, _Mapping]] = ..., buzzerResult: _Optional[_Union[AudioTestTrait.AudioTestResult, _Mapping]] = ...) -> None: ...
    SPEAKERRESULT_FIELD_NUMBER: _ClassVar[int]
    BUZZERRESULT_FIELD_NUMBER: _ClassVar[int]
    speakerResult: AudioTestTrait.AudioTestResult
    buzzerResult: AudioTestTrait.AudioTestResult
    def __init__(self, speakerResult: _Optional[_Union[AudioTestTrait.AudioTestResult, _Mapping]] = ..., buzzerResult: _Optional[_Union[AudioTestTrait.AudioTestResult, _Mapping]] = ...) -> None: ...

class ReadyActionTrait(_message.Message):
    __slots__ = ()
    class ReadyActionState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        READY_ACTION_STATE_UNSPECIFIED: _ClassVar[ReadyActionTrait.ReadyActionState]
        READY_ACTION_STATE_IDLE: _ClassVar[ReadyActionTrait.ReadyActionState]
        READY_ACTION_STATE_START_UX: _ClassVar[ReadyActionTrait.ReadyActionState]
        READY_ACTION_STATE_PAIRING_UX: _ClassVar[ReadyActionTrait.ReadyActionState]
    READY_ACTION_STATE_UNSPECIFIED: ReadyActionTrait.ReadyActionState
    READY_ACTION_STATE_IDLE: ReadyActionTrait.ReadyActionState
    READY_ACTION_STATE_START_UX: ReadyActionTrait.ReadyActionState
    READY_ACTION_STATE_PAIRING_UX: ReadyActionTrait.ReadyActionState
    class ReadyStateChangeReason(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        READY_STATE_CHANGE_REASON_UNSPECIFIED: _ClassVar[ReadyActionTrait.ReadyStateChangeReason]
        READY_STATE_CHANGE_REASON_TIMEOUT: _ClassVar[ReadyActionTrait.ReadyStateChangeReason]
        READY_STATE_CHANGE_REASON_BUTTON_PRESS: _ClassVar[ReadyActionTrait.ReadyStateChangeReason]
        READY_STATE_CHANGE_REASON_BLE_TRIGGER: _ClassVar[ReadyActionTrait.ReadyStateChangeReason]
    READY_STATE_CHANGE_REASON_UNSPECIFIED: ReadyActionTrait.ReadyStateChangeReason
    READY_STATE_CHANGE_REASON_TIMEOUT: ReadyActionTrait.ReadyStateChangeReason
    READY_STATE_CHANGE_REASON_BUTTON_PRESS: ReadyActionTrait.ReadyStateChangeReason
    READY_STATE_CHANGE_REASON_BLE_TRIGGER: ReadyActionTrait.ReadyStateChangeReason
    class ReadyActionStateChangeEvent(_message.Message):
        __slots__ = ("newReadyActionState", "previousReadyActionState", "changeReason")
        NEWREADYACTIONSTATE_FIELD_NUMBER: _ClassVar[int]
        PREVIOUSREADYACTIONSTATE_FIELD_NUMBER: _ClassVar[int]
        CHANGEREASON_FIELD_NUMBER: _ClassVar[int]
        newReadyActionState: ReadyActionTrait.ReadyActionState
        previousReadyActionState: ReadyActionTrait.ReadyActionState
        changeReason: ReadyActionTrait.ReadyStateChangeReason
        def __init__(self, newReadyActionState: _Optional[_Union[ReadyActionTrait.ReadyActionState, str]] = ..., previousReadyActionState: _Optional[_Union[ReadyActionTrait.ReadyActionState, str]] = ..., changeReason: _Optional[_Union[ReadyActionTrait.ReadyStateChangeReason, str]] = ...) -> None: ...
    def __init__(self) -> None: ...

class TrapActionTrait(_message.Message):
    __slots__ = ()
    class TrapStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        TRAP_STATUS_UNSPECIFIED: _ClassVar[TrapActionTrait.TrapStatus]
        TRAP_STATUS_NONE: _ClassVar[TrapActionTrait.TrapStatus]
        TRAP_STATUS_LAST_GASP_BEGIN: _ClassVar[TrapActionTrait.TrapStatus]
        TRAP_STATUS_SAFETY_MCU: _ClassVar[TrapActionTrait.TrapStatus]
    TRAP_STATUS_UNSPECIFIED: TrapActionTrait.TrapStatus
    TRAP_STATUS_NONE: TrapActionTrait.TrapStatus
    TRAP_STATUS_LAST_GASP_BEGIN: TrapActionTrait.TrapStatus
    TRAP_STATUS_SAFETY_MCU: TrapActionTrait.TrapStatus
    class TrapStatusUpdateEvent(_message.Message):
        __slots__ = ("newTrapStatus", "previousTrapStatus")
        NEWTRAPSTATUS_FIELD_NUMBER: _ClassVar[int]
        PREVIOUSTRAPSTATUS_FIELD_NUMBER: _ClassVar[int]
        newTrapStatus: TrapActionTrait.TrapStatus
        previousTrapStatus: TrapActionTrait.TrapStatus
        def __init__(self, newTrapStatus: _Optional[_Union[TrapActionTrait.TrapStatus, str]] = ..., previousTrapStatus: _Optional[_Union[TrapActionTrait.TrapStatus, str]] = ...) -> None: ...
    class SafetyMCUFaultEvent(_message.Message):
        __slots__ = ("asserted",)
        ASSERTED_FIELD_NUMBER: _ClassVar[int]
        asserted: bool
        def __init__(self, asserted: bool = ...) -> None: ...
    def __init__(self) -> None: ...

class NightTimePromiseTrait(_message.Message):
    __slots__ = ()
    class NtpState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        NTP_STATE_UNSPECIFIED: _ClassVar[NightTimePromiseTrait.NtpState]
        NTP_STATE_ALL_CLEAR_NTP_ENABLED: _ClassVar[NightTimePromiseTrait.NtpState]
        NTP_STATE_ALL_CLEAR_NTP_DISABLED: _ClassVar[NightTimePromiseTrait.NtpState]
        NTP_STATE_WARNINGS_DISPLAYED: _ClassVar[NightTimePromiseTrait.NtpState]
        NTP_STATE_WARNINGS_SPOKEN: _ClassVar[NightTimePromiseTrait.NtpState]
        NTP_STATE_CRITICAL_WARNINGS_SPOKEN: _ClassVar[NightTimePromiseTrait.NtpState]
        NTP_STATE_DONE: _ClassVar[NightTimePromiseTrait.NtpState]
    NTP_STATE_UNSPECIFIED: NightTimePromiseTrait.NtpState
    NTP_STATE_ALL_CLEAR_NTP_ENABLED: NightTimePromiseTrait.NtpState
    NTP_STATE_ALL_CLEAR_NTP_DISABLED: NightTimePromiseTrait.NtpState
    NTP_STATE_WARNINGS_DISPLAYED: NightTimePromiseTrait.NtpState
    NTP_STATE_WARNINGS_SPOKEN: NightTimePromiseTrait.NtpState
    NTP_STATE_CRITICAL_WARNINGS_SPOKEN: NightTimePromiseTrait.NtpState
    NTP_STATE_DONE: NightTimePromiseTrait.NtpState
    class NightTimePromiseEvent(_message.Message):
        __slots__ = ("state", "usingRemote", "criticalWarnings", "warningCount")
        STATE_FIELD_NUMBER: _ClassVar[int]
        USINGREMOTE_FIELD_NUMBER: _ClassVar[int]
        CRITICALWARNINGS_FIELD_NUMBER: _ClassVar[int]
        WARNINGCOUNT_FIELD_NUMBER: _ClassVar[int]
        state: NightTimePromiseTrait.NtpState
        usingRemote: bool
        criticalWarnings: bool
        warningCount: int
        def __init__(self, state: _Optional[_Union[NightTimePromiseTrait.NtpState, str]] = ..., usingRemote: bool = ..., criticalWarnings: bool = ..., warningCount: _Optional[int] = ...) -> None: ...
    def __init__(self) -> None: ...

class ProtectDeviceInfoTrait(_message.Message):
    __slots__ = ("deviceExternalColor", "certificationBody")
    class CertRegion(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        CERT_REGION_UNSPECIFIED: _ClassVar[ProtectDeviceInfoTrait.CertRegion]
        CERT_REGION_US: _ClassVar[ProtectDeviceInfoTrait.CertRegion]
        CERT_REGION_EU: _ClassVar[ProtectDeviceInfoTrait.CertRegion]
        CERT_REGION_AU: _ClassVar[ProtectDeviceInfoTrait.CertRegion]
    CERT_REGION_UNSPECIFIED: ProtectDeviceInfoTrait.CertRegion
    CERT_REGION_US: ProtectDeviceInfoTrait.CertRegion
    CERT_REGION_EU: ProtectDeviceInfoTrait.CertRegion
    CERT_REGION_AU: ProtectDeviceInfoTrait.CertRegion
    class AppDailyConnectionStatusEvent(_message.Message):
        __slots__ = ("wdmDisconnectTime",)
        WDMDISCONNECTTIME_FIELD_NUMBER: _ClassVar[int]
        wdmDisconnectTime: _timestamp_pb2.Timestamp
        def __init__(self, wdmDisconnectTime: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...
    DEVICEEXTERNALCOLOR_FIELD_NUMBER: _ClassVar[int]
    CERTIFICATIONBODY_FIELD_NUMBER: _ClassVar[int]
    deviceExternalColor: str
    certificationBody: ProtectDeviceInfoTrait.CertRegion
    def __init__(self, deviceExternalColor: _Optional[str] = ..., certificationBody: _Optional[_Union[ProtectDeviceInfoTrait.CertRegion, str]] = ...) -> None: ...

class SafetySummaryTrait(_message.Message):
    __slots__ = ("criticalDevices", "warningDevices", "totalCriticalFailures", "totalWarnings", "testId")
    class FailureType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        FAILURE_TYPE_UNSPECIFIED: _ClassVar[SafetySummaryTrait.FailureType]
        FAILURE_TYPE_SMOKE: _ClassVar[SafetySummaryTrait.FailureType]
        FAILURE_TYPE_CO: _ClassVar[SafetySummaryTrait.FailureType]
        FAILURE_TYPE_TEMP: _ClassVar[SafetySummaryTrait.FailureType]
        FAILURE_TYPE_HUM: _ClassVar[SafetySummaryTrait.FailureType]
        FAILURE_TYPE_ALS: _ClassVar[SafetySummaryTrait.FailureType]
        FAILURE_TYPE_US: _ClassVar[SafetySummaryTrait.FailureType]
        FAILURE_TYPE_PIR: _ClassVar[SafetySummaryTrait.FailureType]
        FAILURE_TYPE_BUZZER: _ClassVar[SafetySummaryTrait.FailureType]
        FAILURE_TYPE_EXPIRED: _ClassVar[SafetySummaryTrait.FailureType]
        FAILURE_TYPE_EXPIRING: _ClassVar[SafetySummaryTrait.FailureType]
        FAILURE_TYPE_BATT_VERYLOW: _ClassVar[SafetySummaryTrait.FailureType]
        FAILURE_TYPE_BATT_LOW: _ClassVar[SafetySummaryTrait.FailureType]
        FAILURE_TYPE_WIFI: _ClassVar[SafetySummaryTrait.FailureType]
        FAILURE_TYPE_LED: _ClassVar[SafetySummaryTrait.FailureType]
        FAILURE_TYPE_AUDIO: _ClassVar[SafetySummaryTrait.FailureType]
        FAILURE_TYPE_POWEROUT: _ClassVar[SafetySummaryTrait.FailureType]
        FAILURE_TYPE_OFFLINE: _ClassVar[SafetySummaryTrait.FailureType]
    FAILURE_TYPE_UNSPECIFIED: SafetySummaryTrait.FailureType
    FAILURE_TYPE_SMOKE: SafetySummaryTrait.FailureType
    FAILURE_TYPE_CO: SafetySummaryTrait.FailureType
    FAILURE_TYPE_TEMP: SafetySummaryTrait.FailureType
    FAILURE_TYPE_HUM: SafetySummaryTrait.FailureType
    FAILURE_TYPE_ALS: SafetySummaryTrait.FailureType
    FAILURE_TYPE_US: SafetySummaryTrait.FailureType
    FAILURE_TYPE_PIR: SafetySummaryTrait.FailureType
    FAILURE_TYPE_BUZZER: SafetySummaryTrait.FailureType
    FAILURE_TYPE_EXPIRED: SafetySummaryTrait.FailureType
    FAILURE_TYPE_EXPIRING: SafetySummaryTrait.FailureType
    FAILURE_TYPE_BATT_VERYLOW: SafetySummaryTrait.FailureType
    FAILURE_TYPE_BATT_LOW: SafetySummaryTrait.FailureType
    FAILURE_TYPE_WIFI: SafetySummaryTrait.FailureType
    FAILURE_TYPE_LED: SafetySummaryTrait.FailureType
    FAILURE_TYPE_AUDIO: SafetySummaryTrait.FailureType
    FAILURE_TYPE_POWEROUT: SafetySummaryTrait.FailureType
    FAILURE_TYPE_OFFLINE: SafetySummaryTrait.FailureType
    class DeviceStatus(_message.Message):
        __slots__ = ("resourceId", "spokenWhereAnnotation", "failures", "criticalMask", "productId", "vendorId")
        RESOURCEID_FIELD_NUMBER: _ClassVar[int]
        SPOKENWHEREANNOTATION_FIELD_NUMBER: _ClassVar[int]
        FAILURES_FIELD_NUMBER: _ClassVar[int]
        CRITICALMASK_FIELD_NUMBER: _ClassVar[int]
        PRODUCTID_FIELD_NUMBER: _ClassVar[int]
        VENDORID_FIELD_NUMBER: _ClassVar[int]
        resourceId: _common_pb2.ResourceId
        spokenWhereAnnotation: _common_pb2.ResourceId
        failures: _containers.RepeatedScalarFieldContainer[SafetySummaryTrait.FailureType]
        criticalMask: _containers.RepeatedScalarFieldContainer[SafetySummaryTrait.FailureType]
        productId: int
        vendorId: int
        def __init__(self, resourceId: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ..., spokenWhereAnnotation: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ..., failures: _Optional[_Iterable[_Union[SafetySummaryTrait.FailureType, str]]] = ..., criticalMask: _Optional[_Iterable[_Union[SafetySummaryTrait.FailureType, str]]] = ..., productId: _Optional[int] = ..., vendorId: _Optional[int] = ...) -> None: ...
    CRITICALDEVICES_FIELD_NUMBER: _ClassVar[int]
    WARNINGDEVICES_FIELD_NUMBER: _ClassVar[int]
    TOTALCRITICALFAILURES_FIELD_NUMBER: _ClassVar[int]
    TOTALWARNINGS_FIELD_NUMBER: _ClassVar[int]
    TESTID_FIELD_NUMBER: _ClassVar[int]
    criticalDevices: _containers.RepeatedCompositeFieldContainer[SafetySummaryTrait.DeviceStatus]
    warningDevices: _containers.RepeatedCompositeFieldContainer[SafetySummaryTrait.DeviceStatus]
    totalCriticalFailures: int
    totalWarnings: int
    testId: _selftest_pb2.SelfTestRunnerTrait.TestId
    def __init__(self, criticalDevices: _Optional[_Iterable[_Union[SafetySummaryTrait.DeviceStatus, _Mapping]]] = ..., warningDevices: _Optional[_Iterable[_Union[SafetySummaryTrait.DeviceStatus, _Mapping]]] = ..., totalCriticalFailures: _Optional[int] = ..., totalWarnings: _Optional[int] = ..., testId: _Optional[_Union[_selftest_pb2.SelfTestRunnerTrait.TestId, _Mapping]] = ...) -> None: ...

class ActionSchedulerTrait(_message.Message):
    __slots__ = ()
    class ActionSchedulerOpEvent(_message.Message):
        __slots__ = ("opId", "actionId")
        OPID_FIELD_NUMBER: _ClassVar[int]
        ACTIONID_FIELD_NUMBER: _ClassVar[int]
        opId: int
        actionId: int
        def __init__(self, opId: _Optional[int] = ..., actionId: _Optional[int] = ...) -> None: ...
    def __init__(self) -> None: ...

class AudioPlayTrait(_message.Message):
    __slots__ = ()
    class AudioPlayEvent(_message.Message):
        __slots__ = ("sentenceId", "sentenceString", "sentenceArgIds")
        SENTENCEID_FIELD_NUMBER: _ClassVar[int]
        SENTENCESTRING_FIELD_NUMBER: _ClassVar[int]
        SENTENCEARGIDS_FIELD_NUMBER: _ClassVar[int]
        sentenceId: _wrappers_pb2.UInt32Value
        sentenceString: _wrappers_pb2.StringValue
        sentenceArgIds: _containers.RepeatedScalarFieldContainer[int]
        def __init__(self, sentenceId: _Optional[_Union[_wrappers_pb2.UInt32Value, _Mapping]] = ..., sentenceString: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., sentenceArgIds: _Optional[_Iterable[int]] = ...) -> None: ...
    def __init__(self) -> None: ...

class LegacyAlarmHistoryTrait(_message.Message):
    __slots__ = ("smokeHistory", "coHistory")
    class AlarmStatus(_message.Message):
        __slots__ = ("timestamp", "status", "synced")
        TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
        STATUS_FIELD_NUMBER: _ClassVar[int]
        SYNCED_FIELD_NUMBER: _ClassVar[int]
        timestamp: _timestamp_pb2.Timestamp
        status: int
        synced: bool
        def __init__(self, timestamp: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., status: _Optional[int] = ..., synced: bool = ...) -> None: ...
    SMOKEHISTORY_FIELD_NUMBER: _ClassVar[int]
    COHISTORY_FIELD_NUMBER: _ClassVar[int]
    smokeHistory: _containers.RepeatedCompositeFieldContainer[LegacyAlarmHistoryTrait.AlarmStatus]
    coHistory: _containers.RepeatedCompositeFieldContainer[LegacyAlarmHistoryTrait.AlarmStatus]
    def __init__(self, smokeHistory: _Optional[_Iterable[_Union[LegacyAlarmHistoryTrait.AlarmStatus, _Mapping]]] = ..., coHistory: _Optional[_Iterable[_Union[LegacyAlarmHistoryTrait.AlarmStatus, _Mapping]]] = ...) -> None: ...

class LegacySelfTestSettingsTrait(_message.Message):
    __slots__ = ("astEnabled", "astNotify", "astRepeatSecs", "astForceSecs", "astStartOffsetUtcSecs", "astEndOffsetUtcSecs")
    class AutomatedSelfTestScheduleChangeEvent(_message.Message):
        __slots__ = ("astStartOffsetUtcSecs", "astEndOffsetUtcSecs")
        ASTSTARTOFFSETUTCSECS_FIELD_NUMBER: _ClassVar[int]
        ASTENDOFFSETUTCSECS_FIELD_NUMBER: _ClassVar[int]
        astStartOffsetUtcSecs: _duration_pb2.Duration
        astEndOffsetUtcSecs: _duration_pb2.Duration
        def __init__(self, astStartOffsetUtcSecs: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ..., astEndOffsetUtcSecs: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ...) -> None: ...
    ASTENABLED_FIELD_NUMBER: _ClassVar[int]
    ASTNOTIFY_FIELD_NUMBER: _ClassVar[int]
    ASTREPEATSECS_FIELD_NUMBER: _ClassVar[int]
    ASTFORCESECS_FIELD_NUMBER: _ClassVar[int]
    ASTSTARTOFFSETUTCSECS_FIELD_NUMBER: _ClassVar[int]
    ASTENDOFFSETUTCSECS_FIELD_NUMBER: _ClassVar[int]
    astEnabled: bool
    astNotify: bool
    astRepeatSecs: _duration_pb2.Duration
    astForceSecs: _duration_pb2.Duration
    astStartOffsetUtcSecs: _duration_pb2.Duration
    astEndOffsetUtcSecs: _duration_pb2.Duration
    def __init__(self, astEnabled: bool = ..., astNotify: bool = ..., astRepeatSecs: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ..., astForceSecs: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ..., astStartOffsetUtcSecs: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ..., astEndOffsetUtcSecs: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ...) -> None: ...

class NightTimePromiseSettingsTrait(_message.Message):
    __slots__ = ("greenLedEnabled", "greenLedBrightness")
    class NightTimePromiseBrightness(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        NIGHT_TIME_PROMISE_BRIGHTNESS_UNSPECIFIED: _ClassVar[NightTimePromiseSettingsTrait.NightTimePromiseBrightness]
        NIGHT_TIME_PROMISE_BRIGHTNESS_LOW: _ClassVar[NightTimePromiseSettingsTrait.NightTimePromiseBrightness]
        NIGHT_TIME_PROMISE_BRIGHTNESS_MEDIUM: _ClassVar[NightTimePromiseSettingsTrait.NightTimePromiseBrightness]
        NIGHT_TIME_PROMISE_BRIGHTNESS_HIGH: _ClassVar[NightTimePromiseSettingsTrait.NightTimePromiseBrightness]
    NIGHT_TIME_PROMISE_BRIGHTNESS_UNSPECIFIED: NightTimePromiseSettingsTrait.NightTimePromiseBrightness
    NIGHT_TIME_PROMISE_BRIGHTNESS_LOW: NightTimePromiseSettingsTrait.NightTimePromiseBrightness
    NIGHT_TIME_PROMISE_BRIGHTNESS_MEDIUM: NightTimePromiseSettingsTrait.NightTimePromiseBrightness
    NIGHT_TIME_PROMISE_BRIGHTNESS_HIGH: NightTimePromiseSettingsTrait.NightTimePromiseBrightness
    GREENLEDENABLED_FIELD_NUMBER: _ClassVar[int]
    GREENLEDBRIGHTNESS_FIELD_NUMBER: _ClassVar[int]
    greenLedEnabled: bool
    greenLedBrightness: NightTimePromiseSettingsTrait.NightTimePromiseBrightness
    def __init__(self, greenLedEnabled: bool = ..., greenLedBrightness: _Optional[_Union[NightTimePromiseSettingsTrait.NightTimePromiseBrightness, str]] = ...) -> None: ...

class OutOfBoxTrait(_message.Message):
    __slots__ = ()
    class OutOfBoxFinishedEvent(_message.Message):
        __slots__ = ("success", "defaultLanguageSelected", "currentLanguage", "osmSwapPossible", "repeatCount")
        SUCCESS_FIELD_NUMBER: _ClassVar[int]
        DEFAULTLANGUAGESELECTED_FIELD_NUMBER: _ClassVar[int]
        CURRENTLANGUAGE_FIELD_NUMBER: _ClassVar[int]
        OSMSWAPPOSSIBLE_FIELD_NUMBER: _ClassVar[int]
        REPEATCOUNT_FIELD_NUMBER: _ClassVar[int]
        success: bool
        defaultLanguageSelected: bool
        currentLanguage: bool
        osmSwapPossible: bool
        repeatCount: int
        def __init__(self, success: bool = ..., defaultLanguageSelected: bool = ..., currentLanguage: bool = ..., osmSwapPossible: bool = ..., repeatCount: _Optional[int] = ...) -> None: ...
    def __init__(self) -> None: ...

class LegacyProtectDeviceInfoTrait(_message.Message):
    __slots__ = ("capabilityIdx", "autoAway", "capabilityLevel", "linePowerCapable", "spSoftwareVersion")
    CAPABILITYIDX_FIELD_NUMBER: _ClassVar[int]
    AUTOAWAY_FIELD_NUMBER: _ClassVar[int]
    CAPABILITYLEVEL_FIELD_NUMBER: _ClassVar[int]
    LINEPOWERCAPABLE_FIELD_NUMBER: _ClassVar[int]
    SPSOFTWAREVERSION_FIELD_NUMBER: _ClassVar[int]
    capabilityIdx: str
    autoAway: bool
    capabilityLevel: _wrappers_pb2.FloatValue
    linePowerCapable: bool
    spSoftwareVersion: str
    def __init__(self, capabilityIdx: _Optional[str] = ..., autoAway: bool = ..., capabilityLevel: _Optional[_Union[_wrappers_pb2.FloatValue, _Mapping]] = ..., linePowerCapable: bool = ..., spSoftwareVersion: _Optional[str] = ...) -> None: ...

class LegacyProtectDeviceSettingsTrait(_message.Message):
    __slots__ = ("replaceByDate",)
    REPLACEBYDATE_FIELD_NUMBER: _ClassVar[int]
    replaceByDate: _timestamp_pb2.Timestamp
    def __init__(self, replaceByDate: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class SafetyStructureSettingsTrait(_message.Message):
    __slots__ = ("structureHushKey", "phoneHushEnabled")
    STRUCTUREHUSHKEY_FIELD_NUMBER: _ClassVar[int]
    PHONEHUSHENABLED_FIELD_NUMBER: _ClassVar[int]
    structureHushKey: str
    phoneHushEnabled: bool
    def __init__(self, structureHushKey: _Optional[str] = ..., phoneHushEnabled: bool = ...) -> None: ...
