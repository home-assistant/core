import datetime

from google.protobuf import duration_pb2 as _duration_pb2
from ...weave import common_pb2 as _common_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class SelfTestRunnerTrait(_message.Message):
    __slots__ = ("currentSelfTestId", "previousSelfTestId")
    class SelfTestType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        SELF_TEST_TYPE_UNSPECIFIED: _ClassVar[SelfTestRunnerTrait.SelfTestType]
        SELF_TEST_TYPE_SOUND_CHECK: _ClassVar[SelfTestRunnerTrait.SelfTestType]
        SELF_TEST_TYPE_SAFETY_CHECK: _ClassVar[SelfTestRunnerTrait.SelfTestType]
        SELF_TEST_TYPE_SECURITY_CHECK: _ClassVar[SelfTestRunnerTrait.SelfTestType]
    SELF_TEST_TYPE_UNSPECIFIED: SelfTestRunnerTrait.SelfTestType
    SELF_TEST_TYPE_SOUND_CHECK: SelfTestRunnerTrait.SelfTestType
    SELF_TEST_TYPE_SAFETY_CHECK: SelfTestRunnerTrait.SelfTestType
    SELF_TEST_TYPE_SECURITY_CHECK: SelfTestRunnerTrait.SelfTestType
    class SelfTestResult(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        SELF_TEST_RESULT_UNSPECIFIED: _ClassVar[SelfTestRunnerTrait.SelfTestResult]
        SELF_TEST_RESULT_PASS: _ClassVar[SelfTestRunnerTrait.SelfTestResult]
        SELF_TEST_RESULT_FAIL_WARN: _ClassVar[SelfTestRunnerTrait.SelfTestResult]
        SELF_TEST_RESULT_FAIL_CRITICAL: _ClassVar[SelfTestRunnerTrait.SelfTestResult]
    SELF_TEST_RESULT_UNSPECIFIED: SelfTestRunnerTrait.SelfTestResult
    SELF_TEST_RESULT_PASS: SelfTestRunnerTrait.SelfTestResult
    SELF_TEST_RESULT_FAIL_WARN: SelfTestRunnerTrait.SelfTestResult
    SELF_TEST_RESULT_FAIL_CRITICAL: SelfTestRunnerTrait.SelfTestResult
    class RunSelfTestStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        RUN_SELF_TEST_STATUS_UNSPECIFIED: _ClassVar[SelfTestRunnerTrait.RunSelfTestStatus]
        RUN_SELF_TEST_STATUS_SUCCESS: _ClassVar[SelfTestRunnerTrait.RunSelfTestStatus]
        RUN_SELF_TEST_STATUS_WILL_NOT_RUN: _ClassVar[SelfTestRunnerTrait.RunSelfTestStatus]
        RUN_SELF_TEST_STATUS_EXCEEDS_TIMEOUT: _ClassVar[SelfTestRunnerTrait.RunSelfTestStatus]
        RUN_SELF_TEST_STATUS_ALREADY_RUN: _ClassVar[SelfTestRunnerTrait.RunSelfTestStatus]
        RUN_SELF_TEST_STATUS_BUSY: _ClassVar[SelfTestRunnerTrait.RunSelfTestStatus]
        RUN_SELF_TEST_STATUS_INTERNAL_ERROR: _ClassVar[SelfTestRunnerTrait.RunSelfTestStatus]
    RUN_SELF_TEST_STATUS_UNSPECIFIED: SelfTestRunnerTrait.RunSelfTestStatus
    RUN_SELF_TEST_STATUS_SUCCESS: SelfTestRunnerTrait.RunSelfTestStatus
    RUN_SELF_TEST_STATUS_WILL_NOT_RUN: SelfTestRunnerTrait.RunSelfTestStatus
    RUN_SELF_TEST_STATUS_EXCEEDS_TIMEOUT: SelfTestRunnerTrait.RunSelfTestStatus
    RUN_SELF_TEST_STATUS_ALREADY_RUN: SelfTestRunnerTrait.RunSelfTestStatus
    RUN_SELF_TEST_STATUS_BUSY: SelfTestRunnerTrait.RunSelfTestStatus
    RUN_SELF_TEST_STATUS_INTERNAL_ERROR: SelfTestRunnerTrait.RunSelfTestStatus
    class TestId(_message.Message):
        __slots__ = ("rootOrchestratorId", "instanceId")
        ROOTORCHESTRATORID_FIELD_NUMBER: _ClassVar[int]
        INSTANCEID_FIELD_NUMBER: _ClassVar[int]
        rootOrchestratorId: _common_pb2.ResourceId
        instanceId: int
        def __init__(self, rootOrchestratorId: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ..., instanceId: _Optional[int] = ...) -> None: ...
    class SelfTestStartedEvent(_message.Message):
        __slots__ = ("testId", "orchestratorId")
        TESTID_FIELD_NUMBER: _ClassVar[int]
        ORCHESTRATORID_FIELD_NUMBER: _ClassVar[int]
        testId: SelfTestRunnerTrait.TestId
        orchestratorId: _common_pb2.ResourceId
        def __init__(self, testId: _Optional[_Union[SelfTestRunnerTrait.TestId, _Mapping]] = ..., orchestratorId: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ...) -> None: ...
    class SelfTestEndedEvent(_message.Message):
        __slots__ = ("testId", "result", "testStatus", "relatedResults")
        TESTID_FIELD_NUMBER: _ClassVar[int]
        RESULT_FIELD_NUMBER: _ClassVar[int]
        TESTSTATUS_FIELD_NUMBER: _ClassVar[int]
        RELATEDRESULTS_FIELD_NUMBER: _ClassVar[int]
        testId: SelfTestRunnerTrait.TestId
        result: SelfTestRunnerTrait.SelfTestResult
        testStatus: SelfTestRunnerTrait.RunSelfTestStatus
        relatedResults: _containers.RepeatedCompositeFieldContainer[_common_pb2.EventId]
        def __init__(self, testId: _Optional[_Union[SelfTestRunnerTrait.TestId, _Mapping]] = ..., result: _Optional[_Union[SelfTestRunnerTrait.SelfTestResult, str]] = ..., testStatus: _Optional[_Union[SelfTestRunnerTrait.RunSelfTestStatus, str]] = ..., relatedResults: _Optional[_Iterable[_Union[_common_pb2.EventId, _Mapping]]] = ...) -> None: ...
    class OrchestrationStartedEvent(_message.Message):
        __slots__ = ("testId", "parentId")
        TESTID_FIELD_NUMBER: _ClassVar[int]
        PARENTID_FIELD_NUMBER: _ClassVar[int]
        testId: SelfTestRunnerTrait.TestId
        parentId: _common_pb2.ResourceId
        def __init__(self, testId: _Optional[_Union[SelfTestRunnerTrait.TestId, _Mapping]] = ..., parentId: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ...) -> None: ...
    class OrchestrationEndedEvent(_message.Message):
        __slots__ = ("testId", "result")
        TESTID_FIELD_NUMBER: _ClassVar[int]
        RESULT_FIELD_NUMBER: _ClassVar[int]
        testId: SelfTestRunnerTrait.TestId
        result: SelfTestRunnerTrait.SelfTestResult
        def __init__(self, testId: _Optional[_Union[SelfTestRunnerTrait.TestId, _Mapping]] = ..., result: _Optional[_Union[SelfTestRunnerTrait.SelfTestResult, str]] = ...) -> None: ...
    class RunnerTimoutEvent(_message.Message):
        __slots__ = ("testId", "runnerId")
        TESTID_FIELD_NUMBER: _ClassVar[int]
        RUNNERID_FIELD_NUMBER: _ClassVar[int]
        testId: SelfTestRunnerTrait.TestId
        runnerId: _common_pb2.ResourceId
        def __init__(self, testId: _Optional[_Union[SelfTestRunnerTrait.TestId, _Mapping]] = ..., runnerId: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ...) -> None: ...
    class RunSelfTestRequest(_message.Message):
        __slots__ = ("testId", "testTimeout", "testTypes")
        TESTID_FIELD_NUMBER: _ClassVar[int]
        TESTTIMEOUT_FIELD_NUMBER: _ClassVar[int]
        TESTTYPES_FIELD_NUMBER: _ClassVar[int]
        testId: SelfTestRunnerTrait.TestId
        testTimeout: _duration_pb2.Duration
        testTypes: _containers.RepeatedScalarFieldContainer[SelfTestRunnerTrait.SelfTestType]
        def __init__(self, testId: _Optional[_Union[SelfTestRunnerTrait.TestId, _Mapping]] = ..., testTimeout: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ..., testTypes: _Optional[_Iterable[_Union[SelfTestRunnerTrait.SelfTestType, str]]] = ...) -> None: ...
    class RunSelfTestResponse(_message.Message):
        __slots__ = ("result", "testStatus")
        RESULT_FIELD_NUMBER: _ClassVar[int]
        TESTSTATUS_FIELD_NUMBER: _ClassVar[int]
        result: SelfTestRunnerTrait.SelfTestResult
        testStatus: SelfTestRunnerTrait.RunSelfTestStatus
        def __init__(self, result: _Optional[_Union[SelfTestRunnerTrait.SelfTestResult, str]] = ..., testStatus: _Optional[_Union[SelfTestRunnerTrait.RunSelfTestStatus, str]] = ...) -> None: ...
    CURRENTSELFTESTID_FIELD_NUMBER: _ClassVar[int]
    PREVIOUSSELFTESTID_FIELD_NUMBER: _ClassVar[int]
    currentSelfTestId: SelfTestRunnerTrait.TestId
    previousSelfTestId: SelfTestRunnerTrait.TestId
    def __init__(self, currentSelfTestId: _Optional[_Union[SelfTestRunnerTrait.TestId, _Mapping]] = ..., previousSelfTestId: _Optional[_Union[SelfTestRunnerTrait.TestId, _Mapping]] = ...) -> None: ...
