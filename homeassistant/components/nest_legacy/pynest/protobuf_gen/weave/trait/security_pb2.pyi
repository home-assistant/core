import datetime

from google.protobuf import duration_pb2 as _duration_pb2
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

class UserPincodesSettingsTrait(_message.Message):
    __slots__ = ("userPincodes",)
    class PincodeErrorCodes(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        PINCODE_ERROR_CODES_UNSPECIFIED: _ClassVar[UserPincodesSettingsTrait.PincodeErrorCodes]
        PINCODE_ERROR_CODES_DUPLICATE_PINCODE: _ClassVar[UserPincodesSettingsTrait.PincodeErrorCodes]
        PINCODE_ERROR_CODES_TOO_MANY_PINCODES: _ClassVar[UserPincodesSettingsTrait.PincodeErrorCodes]
        PINCODE_ERROR_CODES_INVALID_PINCODE: _ClassVar[UserPincodesSettingsTrait.PincodeErrorCodes]
        PINCODE_ERROR_CODES_SUCCESS_PINCODE_DELETED: _ClassVar[UserPincodesSettingsTrait.PincodeErrorCodes]
        PINCODE_ERROR_CODES_SUCCESS_PINCODE_STATUS: _ClassVar[UserPincodesSettingsTrait.PincodeErrorCodes]
        PINCODE_ERROR_CODES_DUPLICATE_NONCE: _ClassVar[UserPincodesSettingsTrait.PincodeErrorCodes]
        PINCODE_ERROR_CODES_EXCEEDED_RATE_LIMIT: _ClassVar[UserPincodesSettingsTrait.PincodeErrorCodes]
    PINCODE_ERROR_CODES_UNSPECIFIED: UserPincodesSettingsTrait.PincodeErrorCodes
    PINCODE_ERROR_CODES_DUPLICATE_PINCODE: UserPincodesSettingsTrait.PincodeErrorCodes
    PINCODE_ERROR_CODES_TOO_MANY_PINCODES: UserPincodesSettingsTrait.PincodeErrorCodes
    PINCODE_ERROR_CODES_INVALID_PINCODE: UserPincodesSettingsTrait.PincodeErrorCodes
    PINCODE_ERROR_CODES_SUCCESS_PINCODE_DELETED: UserPincodesSettingsTrait.PincodeErrorCodes
    PINCODE_ERROR_CODES_SUCCESS_PINCODE_STATUS: UserPincodesSettingsTrait.PincodeErrorCodes
    PINCODE_ERROR_CODES_DUPLICATE_NONCE: UserPincodesSettingsTrait.PincodeErrorCodes
    PINCODE_ERROR_CODES_EXCEEDED_RATE_LIMIT: UserPincodesSettingsTrait.PincodeErrorCodes
    class PincodeChangeReason(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        PINCODE_CHANGE_REASON_UNSPECIFIED: _ClassVar[UserPincodesSettingsTrait.PincodeChangeReason]
        PINCODE_CHANGE_REASON_UPDATE: _ClassVar[UserPincodesSettingsTrait.PincodeChangeReason]
        PINCODE_CHANGE_REASON_DELETION: _ClassVar[UserPincodesSettingsTrait.PincodeChangeReason]
    PINCODE_CHANGE_REASON_UNSPECIFIED: UserPincodesSettingsTrait.PincodeChangeReason
    PINCODE_CHANGE_REASON_UPDATE: UserPincodesSettingsTrait.PincodeChangeReason
    PINCODE_CHANGE_REASON_DELETION: UserPincodesSettingsTrait.PincodeChangeReason
    class UserPincodesEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: int
        value: UserPincodesSettingsTrait.UserPincode
        def __init__(self, key: _Optional[int] = ..., value: _Optional[_Union[UserPincodesSettingsTrait.UserPincode, _Mapping]] = ...) -> None: ...
    class UserPincode(_message.Message):
        __slots__ = ("userId", "pincode", "pincodeCredentialEnabled")
        USERID_FIELD_NUMBER: _ClassVar[int]
        PINCODE_FIELD_NUMBER: _ClassVar[int]
        PINCODECREDENTIALENABLED_FIELD_NUMBER: _ClassVar[int]
        userId: _common_pb2.ResourceId
        pincode: bytes
        pincodeCredentialEnabled: _wrappers_pb2.BoolValue
        def __init__(self, userId: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ..., pincode: _Optional[bytes] = ..., pincodeCredentialEnabled: _Optional[_Union[_wrappers_pb2.BoolValue, _Mapping]] = ...) -> None: ...
    class SetUserPincodeRequest(_message.Message):
        __slots__ = ("userPincode",)
        USERPINCODE_FIELD_NUMBER: _ClassVar[int]
        userPincode: UserPincodesSettingsTrait.UserPincode
        def __init__(self, userPincode: _Optional[_Union[UserPincodesSettingsTrait.UserPincode, _Mapping]] = ...) -> None: ...
    class SetUserPincodeResponse(_message.Message):
        __slots__ = ("status",)
        STATUS_FIELD_NUMBER: _ClassVar[int]
        status: UserPincodesSettingsTrait.PincodeErrorCodes
        def __init__(self, status: _Optional[_Union[UserPincodesSettingsTrait.PincodeErrorCodes, str]] = ...) -> None: ...
    class GetUserPincodeRequest(_message.Message):
        __slots__ = ("userId",)
        USERID_FIELD_NUMBER: _ClassVar[int]
        userId: _common_pb2.ResourceId
        def __init__(self, userId: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ...) -> None: ...
    class GetUserPincodeResponse(_message.Message):
        __slots__ = ("userPincode",)
        USERPINCODE_FIELD_NUMBER: _ClassVar[int]
        userPincode: UserPincodesSettingsTrait.UserPincode
        def __init__(self, userPincode: _Optional[_Union[UserPincodesSettingsTrait.UserPincode, _Mapping]] = ...) -> None: ...
    class DeleteUserPincodeRequest(_message.Message):
        __slots__ = ("userId",)
        USERID_FIELD_NUMBER: _ClassVar[int]
        userId: _common_pb2.ResourceId
        def __init__(self, userId: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ...) -> None: ...
    class DeleteUserPincodeResponse(_message.Message):
        __slots__ = ("status",)
        STATUS_FIELD_NUMBER: _ClassVar[int]
        status: UserPincodesSettingsTrait.PincodeErrorCodes
        def __init__(self, status: _Optional[_Union[UserPincodesSettingsTrait.PincodeErrorCodes, str]] = ...) -> None: ...
    class UserPincodeChangeEvent(_message.Message):
        __slots__ = ("userId", "reason")
        USERID_FIELD_NUMBER: _ClassVar[int]
        REASON_FIELD_NUMBER: _ClassVar[int]
        userId: _common_pb2.ResourceId
        reason: UserPincodesSettingsTrait.PincodeChangeReason
        def __init__(self, userId: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ..., reason: _Optional[_Union[UserPincodesSettingsTrait.PincodeChangeReason, str]] = ...) -> None: ...
    USERPINCODES_FIELD_NUMBER: _ClassVar[int]
    userPincodes: _containers.MessageMap[int, UserPincodesSettingsTrait.UserPincode]
    def __init__(self, userPincodes: _Optional[_Mapping[int, UserPincodesSettingsTrait.UserPincode]] = ...) -> None: ...

class BoltLockTrait(_message.Message):
    __slots__ = ("state", "actuatorState", "lockedState", "boltLockActor", "lockedStateLastChangedAt")
    class BoltState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        BOLT_STATE_UNSPECIFIED: _ClassVar[BoltLockTrait.BoltState]
        BOLT_STATE_RETRACTED: _ClassVar[BoltLockTrait.BoltState]
        BOLT_STATE_EXTENDED: _ClassVar[BoltLockTrait.BoltState]
    BOLT_STATE_UNSPECIFIED: BoltLockTrait.BoltState
    BOLT_STATE_RETRACTED: BoltLockTrait.BoltState
    BOLT_STATE_EXTENDED: BoltLockTrait.BoltState
    class BoltLockActorMethod(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        BOLT_LOCK_ACTOR_METHOD_UNSPECIFIED: _ClassVar[BoltLockTrait.BoltLockActorMethod]
        BOLT_LOCK_ACTOR_METHOD_OTHER: _ClassVar[BoltLockTrait.BoltLockActorMethod]
        BOLT_LOCK_ACTOR_METHOD_PHYSICAL: _ClassVar[BoltLockTrait.BoltLockActorMethod]
        BOLT_LOCK_ACTOR_METHOD_KEYPAD_PIN: _ClassVar[BoltLockTrait.BoltLockActorMethod]
        BOLT_LOCK_ACTOR_METHOD_LOCAL_IMPLICIT: _ClassVar[BoltLockTrait.BoltLockActorMethod]
        BOLT_LOCK_ACTOR_METHOD_REMOTE_USER_EXPLICIT: _ClassVar[BoltLockTrait.BoltLockActorMethod]
        BOLT_LOCK_ACTOR_METHOD_REMOTE_USER_IMPLICIT: _ClassVar[BoltLockTrait.BoltLockActorMethod]
        BOLT_LOCK_ACTOR_METHOD_REMOTE_USER_OTHER: _ClassVar[BoltLockTrait.BoltLockActorMethod]
        BOLT_LOCK_ACTOR_METHOD_REMOTE_DELEGATE: _ClassVar[BoltLockTrait.BoltLockActorMethod]
        BOLT_LOCK_ACTOR_METHOD_LOW_POWER_SHUTDOWN: _ClassVar[BoltLockTrait.BoltLockActorMethod]
        BOLT_LOCK_ACTOR_METHOD_VOICE_ASSISTANT: _ClassVar[BoltLockTrait.BoltLockActorMethod]
    BOLT_LOCK_ACTOR_METHOD_UNSPECIFIED: BoltLockTrait.BoltLockActorMethod
    BOLT_LOCK_ACTOR_METHOD_OTHER: BoltLockTrait.BoltLockActorMethod
    BOLT_LOCK_ACTOR_METHOD_PHYSICAL: BoltLockTrait.BoltLockActorMethod
    BOLT_LOCK_ACTOR_METHOD_KEYPAD_PIN: BoltLockTrait.BoltLockActorMethod
    BOLT_LOCK_ACTOR_METHOD_LOCAL_IMPLICIT: BoltLockTrait.BoltLockActorMethod
    BOLT_LOCK_ACTOR_METHOD_REMOTE_USER_EXPLICIT: BoltLockTrait.BoltLockActorMethod
    BOLT_LOCK_ACTOR_METHOD_REMOTE_USER_IMPLICIT: BoltLockTrait.BoltLockActorMethod
    BOLT_LOCK_ACTOR_METHOD_REMOTE_USER_OTHER: BoltLockTrait.BoltLockActorMethod
    BOLT_LOCK_ACTOR_METHOD_REMOTE_DELEGATE: BoltLockTrait.BoltLockActorMethod
    BOLT_LOCK_ACTOR_METHOD_LOW_POWER_SHUTDOWN: BoltLockTrait.BoltLockActorMethod
    BOLT_LOCK_ACTOR_METHOD_VOICE_ASSISTANT: BoltLockTrait.BoltLockActorMethod
    class BoltActuatorState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        BOLT_ACTUATOR_STATE_UNSPECIFIED: _ClassVar[BoltLockTrait.BoltActuatorState]
        BOLT_ACTUATOR_STATE_OK: _ClassVar[BoltLockTrait.BoltActuatorState]
        BOLT_ACTUATOR_STATE_LOCKING: _ClassVar[BoltLockTrait.BoltActuatorState]
        BOLT_ACTUATOR_STATE_UNLOCKING: _ClassVar[BoltLockTrait.BoltActuatorState]
        BOLT_ACTUATOR_STATE_MOVING: _ClassVar[BoltLockTrait.BoltActuatorState]
        BOLT_ACTUATOR_STATE_JAMMED_LOCKING: _ClassVar[BoltLockTrait.BoltActuatorState]
        BOLT_ACTUATOR_STATE_JAMMED_UNLOCKING: _ClassVar[BoltLockTrait.BoltActuatorState]
        BOLT_ACTUATOR_STATE_JAMMED_OTHER: _ClassVar[BoltLockTrait.BoltActuatorState]
    BOLT_ACTUATOR_STATE_UNSPECIFIED: BoltLockTrait.BoltActuatorState
    BOLT_ACTUATOR_STATE_OK: BoltLockTrait.BoltActuatorState
    BOLT_ACTUATOR_STATE_LOCKING: BoltLockTrait.BoltActuatorState
    BOLT_ACTUATOR_STATE_UNLOCKING: BoltLockTrait.BoltActuatorState
    BOLT_ACTUATOR_STATE_MOVING: BoltLockTrait.BoltActuatorState
    BOLT_ACTUATOR_STATE_JAMMED_LOCKING: BoltLockTrait.BoltActuatorState
    BOLT_ACTUATOR_STATE_JAMMED_UNLOCKING: BoltLockTrait.BoltActuatorState
    BOLT_ACTUATOR_STATE_JAMMED_OTHER: BoltLockTrait.BoltActuatorState
    class BoltLockedState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        BOLT_LOCKED_STATE_UNSPECIFIED: _ClassVar[BoltLockTrait.BoltLockedState]
        BOLT_LOCKED_STATE_UNLOCKED: _ClassVar[BoltLockTrait.BoltLockedState]
        BOLT_LOCKED_STATE_LOCKED: _ClassVar[BoltLockTrait.BoltLockedState]
        BOLT_LOCKED_STATE_UNKNOWN: _ClassVar[BoltLockTrait.BoltLockedState]
    BOLT_LOCKED_STATE_UNSPECIFIED: BoltLockTrait.BoltLockedState
    BOLT_LOCKED_STATE_UNLOCKED: BoltLockTrait.BoltLockedState
    BOLT_LOCKED_STATE_LOCKED: BoltLockTrait.BoltLockedState
    BOLT_LOCKED_STATE_UNKNOWN: BoltLockTrait.BoltLockedState
    class BoltLockActorStruct(_message.Message):
        __slots__ = ("method", "originator", "agent")
        METHOD_FIELD_NUMBER: _ClassVar[int]
        ORIGINATOR_FIELD_NUMBER: _ClassVar[int]
        AGENT_FIELD_NUMBER: _ClassVar[int]
        method: BoltLockTrait.BoltLockActorMethod
        originator: _common_pb2.ResourceId
        agent: _common_pb2.ResourceId
        def __init__(self, method: _Optional[_Union[BoltLockTrait.BoltLockActorMethod, str]] = ..., originator: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ..., agent: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ...) -> None: ...
    class BoltLockChangeRequest(_message.Message):
        __slots__ = ("state", "boltLockActor")
        STATE_FIELD_NUMBER: _ClassVar[int]
        BOLTLOCKACTOR_FIELD_NUMBER: _ClassVar[int]
        state: BoltLockTrait.BoltState
        boltLockActor: BoltLockTrait.BoltLockActorStruct
        def __init__(self, state: _Optional[_Union[BoltLockTrait.BoltState, str]] = ..., boltLockActor: _Optional[_Union[BoltLockTrait.BoltLockActorStruct, _Mapping]] = ...) -> None: ...
    class BoltLockProximityChangeRequest(_message.Message):
        __slots__ = ("state", "boltLockActor", "token")
        STATE_FIELD_NUMBER: _ClassVar[int]
        BOLTLOCKACTOR_FIELD_NUMBER: _ClassVar[int]
        TOKEN_FIELD_NUMBER: _ClassVar[int]
        state: BoltLockTrait.BoltState
        boltLockActor: BoltLockTrait.BoltLockActorStruct
        token: bytes
        def __init__(self, state: _Optional[_Union[BoltLockTrait.BoltState, str]] = ..., boltLockActor: _Optional[_Union[BoltLockTrait.BoltLockActorStruct, _Mapping]] = ..., token: _Optional[bytes] = ...) -> None: ...
    class BoltActuatorStateChangeEvent(_message.Message):
        __slots__ = ("state", "actuatorState", "lockedState", "boltLockActor")
        STATE_FIELD_NUMBER: _ClassVar[int]
        ACTUATORSTATE_FIELD_NUMBER: _ClassVar[int]
        LOCKEDSTATE_FIELD_NUMBER: _ClassVar[int]
        BOLTLOCKACTOR_FIELD_NUMBER: _ClassVar[int]
        state: BoltLockTrait.BoltState
        actuatorState: BoltLockTrait.BoltActuatorState
        lockedState: BoltLockTrait.BoltLockedState
        boltLockActor: BoltLockTrait.BoltLockActorStruct
        def __init__(self, state: _Optional[_Union[BoltLockTrait.BoltState, str]] = ..., actuatorState: _Optional[_Union[BoltLockTrait.BoltActuatorState, str]] = ..., lockedState: _Optional[_Union[BoltLockTrait.BoltLockedState, str]] = ..., boltLockActor: _Optional[_Union[BoltLockTrait.BoltLockActorStruct, _Mapping]] = ...) -> None: ...
    STATE_FIELD_NUMBER: _ClassVar[int]
    ACTUATORSTATE_FIELD_NUMBER: _ClassVar[int]
    LOCKEDSTATE_FIELD_NUMBER: _ClassVar[int]
    BOLTLOCKACTOR_FIELD_NUMBER: _ClassVar[int]
    LOCKEDSTATELASTCHANGEDAT_FIELD_NUMBER: _ClassVar[int]
    state: BoltLockTrait.BoltState
    actuatorState: BoltLockTrait.BoltActuatorState
    lockedState: BoltLockTrait.BoltLockedState
    boltLockActor: BoltLockTrait.BoltLockActorStruct
    lockedStateLastChangedAt: _timestamp_pb2.Timestamp
    def __init__(self, state: _Optional[_Union[BoltLockTrait.BoltState, str]] = ..., actuatorState: _Optional[_Union[BoltLockTrait.BoltActuatorState, str]] = ..., lockedState: _Optional[_Union[BoltLockTrait.BoltLockedState, str]] = ..., boltLockActor: _Optional[_Union[BoltLockTrait.BoltLockActorStruct, _Mapping]] = ..., lockedStateLastChangedAt: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class SensorAssociationTrait(_message.Message):
    __slots__ = ("sensors", "associatedSensorDeviceId")
    class StatusCode(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        STATUS_CODE_UNSPECIFIED: _ClassVar[SensorAssociationTrait.StatusCode]
        STATUS_CODE_SUCCESS: _ClassVar[SensorAssociationTrait.StatusCode]
        STATUS_CODE_FAILURE: _ClassVar[SensorAssociationTrait.StatusCode]
        STATUS_CODE_SENSOR_ALREADY_ASSOCIATED_OTHER: _ClassVar[SensorAssociationTrait.StatusCode]
        STATUS_CODE_SENSOR_ALREADY_ASSOCIATED_SELF: _ClassVar[SensorAssociationTrait.StatusCode]
        STATUS_CODE_SENSOR_INVALID: _ClassVar[SensorAssociationTrait.StatusCode]
        STATUS_CODE_USER_SETTING_INVALID: _ClassVar[SensorAssociationTrait.StatusCode]
    STATUS_CODE_UNSPECIFIED: SensorAssociationTrait.StatusCode
    STATUS_CODE_SUCCESS: SensorAssociationTrait.StatusCode
    STATUS_CODE_FAILURE: SensorAssociationTrait.StatusCode
    STATUS_CODE_SENSOR_ALREADY_ASSOCIATED_OTHER: SensorAssociationTrait.StatusCode
    STATUS_CODE_SENSOR_ALREADY_ASSOCIATED_SELF: SensorAssociationTrait.StatusCode
    STATUS_CODE_SENSOR_INVALID: SensorAssociationTrait.StatusCode
    STATUS_CODE_USER_SETTING_INVALID: SensorAssociationTrait.StatusCode
    class SensorAssociationStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        SENSOR_ASSOCIATION_STATUS_UNSPECIFIED: _ClassVar[SensorAssociationTrait.SensorAssociationStatus]
        SENSOR_ASSOCIATION_STATUS_ASSOCIATED_SELF: _ClassVar[SensorAssociationTrait.SensorAssociationStatus]
        SENSOR_ASSOCIATION_STATUS_ASSOCIATED_OTHER: _ClassVar[SensorAssociationTrait.SensorAssociationStatus]
        SENSOR_ASSOCIATION_STATUS_DEFAULT: _ClassVar[SensorAssociationTrait.SensorAssociationStatus]
        SENSOR_ASSOCIATION_STATUS_ELIGIBLE: _ClassVar[SensorAssociationTrait.SensorAssociationStatus]
        SENSOR_ASSOCIATION_STATUS_INELIGIBLE: _ClassVar[SensorAssociationTrait.SensorAssociationStatus]
    SENSOR_ASSOCIATION_STATUS_UNSPECIFIED: SensorAssociationTrait.SensorAssociationStatus
    SENSOR_ASSOCIATION_STATUS_ASSOCIATED_SELF: SensorAssociationTrait.SensorAssociationStatus
    SENSOR_ASSOCIATION_STATUS_ASSOCIATED_OTHER: SensorAssociationTrait.SensorAssociationStatus
    SENSOR_ASSOCIATION_STATUS_DEFAULT: SensorAssociationTrait.SensorAssociationStatus
    SENSOR_ASSOCIATION_STATUS_ELIGIBLE: SensorAssociationTrait.SensorAssociationStatus
    SENSOR_ASSOCIATION_STATUS_INELIGIBLE: SensorAssociationTrait.SensorAssociationStatus
    class SetUserSensorAssociationRequest(_message.Message):
        __slots__ = ("sensorDeviceId",)
        SENSORDEVICEID_FIELD_NUMBER: _ClassVar[int]
        sensorDeviceId: _common_pb2.ResourceId
        def __init__(self, sensorDeviceId: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ...) -> None: ...
    class SetUserSensorAssociationResponse(_message.Message):
        __slots__ = ("status",)
        STATUS_FIELD_NUMBER: _ClassVar[int]
        status: SensorAssociationTrait.StatusCode
        def __init__(self, status: _Optional[_Union[SensorAssociationTrait.StatusCode, str]] = ...) -> None: ...
    class SensorDeviceStatus(_message.Message):
        __slots__ = ("deviceId", "sensorAssociationStatus", "sensorAssociationStatusList")
        DEVICEID_FIELD_NUMBER: _ClassVar[int]
        SENSORASSOCIATIONSTATUS_FIELD_NUMBER: _ClassVar[int]
        SENSORASSOCIATIONSTATUSLIST_FIELD_NUMBER: _ClassVar[int]
        deviceId: _common_pb2.ResourceId
        sensorAssociationStatus: SensorAssociationTrait.SensorAssociationStatus
        sensorAssociationStatusList: _containers.RepeatedScalarFieldContainer[SensorAssociationTrait.SensorAssociationStatus]
        def __init__(self, deviceId: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ..., sensorAssociationStatus: _Optional[_Union[SensorAssociationTrait.SensorAssociationStatus, str]] = ..., sensorAssociationStatusList: _Optional[_Iterable[_Union[SensorAssociationTrait.SensorAssociationStatus, str]]] = ...) -> None: ...
    SENSORS_FIELD_NUMBER: _ClassVar[int]
    ASSOCIATEDSENSORDEVICEID_FIELD_NUMBER: _ClassVar[int]
    sensors: _containers.RepeatedCompositeFieldContainer[SensorAssociationTrait.SensorDeviceStatus]
    associatedSensorDeviceId: _common_pb2.ResourceId
    def __init__(self, sensors: _Optional[_Iterable[_Union[SensorAssociationTrait.SensorDeviceStatus, _Mapping]]] = ..., associatedSensorDeviceId: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ...) -> None: ...

class UserNFCTokenManagementTrait(_message.Message):
    __slots__ = ()
    class NFCTokenEvent(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        NFC_TOKEN_EVENT_UNSPECIFIED: _ClassVar[UserNFCTokenManagementTrait.NFCTokenEvent]
        NFC_TOKEN_EVENT_PAIRED: _ClassVar[UserNFCTokenManagementTrait.NFCTokenEvent]
        NFC_TOKEN_EVENT_UNPAIRED: _ClassVar[UserNFCTokenManagementTrait.NFCTokenEvent]
        NFC_TOKEN_EVENT_STRUCTURE_AUTH: _ClassVar[UserNFCTokenManagementTrait.NFCTokenEvent]
        NFC_TOKEN_EVENT_STRUCTURE_UNAUTH: _ClassVar[UserNFCTokenManagementTrait.NFCTokenEvent]
        NFC_TOKEN_EVENT_TRANSFERRED: _ClassVar[UserNFCTokenManagementTrait.NFCTokenEvent]
        NFC_TOKEN_EVENT_DISABLED: _ClassVar[UserNFCTokenManagementTrait.NFCTokenEvent]
        NFC_TOKEN_EVENT_ENABLED: _ClassVar[UserNFCTokenManagementTrait.NFCTokenEvent]
    NFC_TOKEN_EVENT_UNSPECIFIED: UserNFCTokenManagementTrait.NFCTokenEvent
    NFC_TOKEN_EVENT_PAIRED: UserNFCTokenManagementTrait.NFCTokenEvent
    NFC_TOKEN_EVENT_UNPAIRED: UserNFCTokenManagementTrait.NFCTokenEvent
    NFC_TOKEN_EVENT_STRUCTURE_AUTH: UserNFCTokenManagementTrait.NFCTokenEvent
    NFC_TOKEN_EVENT_STRUCTURE_UNAUTH: UserNFCTokenManagementTrait.NFCTokenEvent
    NFC_TOKEN_EVENT_TRANSFERRED: UserNFCTokenManagementTrait.NFCTokenEvent
    NFC_TOKEN_EVENT_DISABLED: UserNFCTokenManagementTrait.NFCTokenEvent
    NFC_TOKEN_EVENT_ENABLED: UserNFCTokenManagementTrait.NFCTokenEvent
    class TransferUserNFCTokenRequest(_message.Message):
        __slots__ = ("targetUserId", "tokenDeviceId")
        TARGETUSERID_FIELD_NUMBER: _ClassVar[int]
        TOKENDEVICEID_FIELD_NUMBER: _ClassVar[int]
        targetUserId: _common_pb2.ResourceId
        tokenDeviceId: _common_pb2.ResourceId
        def __init__(self, targetUserId: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ..., tokenDeviceId: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ...) -> None: ...
    class SetUserNFCTokenEnableStateRequest(_message.Message):
        __slots__ = ("tokenDeviceId", "enabled")
        TOKENDEVICEID_FIELD_NUMBER: _ClassVar[int]
        ENABLED_FIELD_NUMBER: _ClassVar[int]
        tokenDeviceId: _common_pb2.ResourceId
        enabled: bool
        def __init__(self, tokenDeviceId: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ..., enabled: bool = ...) -> None: ...
    class AuthUserNFCTokenToStructureRequest(_message.Message):
        __slots__ = ("tokenDeviceId", "authorized", "structureId")
        TOKENDEVICEID_FIELD_NUMBER: _ClassVar[int]
        AUTHORIZED_FIELD_NUMBER: _ClassVar[int]
        STRUCTUREID_FIELD_NUMBER: _ClassVar[int]
        tokenDeviceId: _common_pb2.ResourceId
        authorized: bool
        structureId: _common_pb2.ResourceId
        def __init__(self, tokenDeviceId: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ..., authorized: bool = ..., structureId: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ...) -> None: ...
    class UserNFCTokenManagementEvent(_message.Message):
        __slots__ = ("nfcTokenManagementEvent", "userNfcToken", "initiatingUserId", "previousUserId")
        NFCTOKENMANAGEMENTEVENT_FIELD_NUMBER: _ClassVar[int]
        USERNFCTOKEN_FIELD_NUMBER: _ClassVar[int]
        INITIATINGUSERID_FIELD_NUMBER: _ClassVar[int]
        PREVIOUSUSERID_FIELD_NUMBER: _ClassVar[int]
        nfcTokenManagementEvent: UserNFCTokenManagementTrait.NFCTokenEvent
        userNfcToken: UserNFCTokensTrait.UserNFCTokenData
        initiatingUserId: _common_pb2.ResourceId
        previousUserId: _common_pb2.ResourceId
        def __init__(self, nfcTokenManagementEvent: _Optional[_Union[UserNFCTokenManagementTrait.NFCTokenEvent, str]] = ..., userNfcToken: _Optional[_Union[UserNFCTokensTrait.UserNFCTokenData, _Mapping]] = ..., initiatingUserId: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ..., previousUserId: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ...) -> None: ...
    def __init__(self) -> None: ...

class PincodeInputTrait(_message.Message):
    __slots__ = ("pincodeInputState",)
    class PincodeEntryResult(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        PINCODE_ENTRY_RESULT_UNSPECIFIED: _ClassVar[PincodeInputTrait.PincodeEntryResult]
        PINCODE_ENTRY_RESULT_FAILURE_INVALID_PINCODE: _ClassVar[PincodeInputTrait.PincodeEntryResult]
        PINCODE_ENTRY_RESULT_FAILURE_OUT_OF_SCHEDULE: _ClassVar[PincodeInputTrait.PincodeEntryResult]
        PINCODE_ENTRY_RESULT_FAILURE_PINCODE_DISABLED: _ClassVar[PincodeInputTrait.PincodeEntryResult]
        PINCODE_ENTRY_RESULT_SUCCESS: _ClassVar[PincodeInputTrait.PincodeEntryResult]
    PINCODE_ENTRY_RESULT_UNSPECIFIED: PincodeInputTrait.PincodeEntryResult
    PINCODE_ENTRY_RESULT_FAILURE_INVALID_PINCODE: PincodeInputTrait.PincodeEntryResult
    PINCODE_ENTRY_RESULT_FAILURE_OUT_OF_SCHEDULE: PincodeInputTrait.PincodeEntryResult
    PINCODE_ENTRY_RESULT_FAILURE_PINCODE_DISABLED: PincodeInputTrait.PincodeEntryResult
    PINCODE_ENTRY_RESULT_SUCCESS: PincodeInputTrait.PincodeEntryResult
    class PincodeInputState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        PINCODE_INPUT_STATE_UNSPECIFIED: _ClassVar[PincodeInputTrait.PincodeInputState]
        PINCODE_INPUT_STATE_ENABLED: _ClassVar[PincodeInputTrait.PincodeInputState]
        PINCODE_INPUT_STATE_DISABLED: _ClassVar[PincodeInputTrait.PincodeInputState]
    PINCODE_INPUT_STATE_UNSPECIFIED: PincodeInputTrait.PincodeInputState
    PINCODE_INPUT_STATE_ENABLED: PincodeInputTrait.PincodeInputState
    PINCODE_INPUT_STATE_DISABLED: PincodeInputTrait.PincodeInputState
    class KeypadEntryEvent(_message.Message):
        __slots__ = ("pincodeCredentialEnabled", "userId", "invalidEntryCount", "pincodeEntryResult")
        PINCODECREDENTIALENABLED_FIELD_NUMBER: _ClassVar[int]
        USERID_FIELD_NUMBER: _ClassVar[int]
        INVALIDENTRYCOUNT_FIELD_NUMBER: _ClassVar[int]
        PINCODEENTRYRESULT_FIELD_NUMBER: _ClassVar[int]
        pincodeCredentialEnabled: _wrappers_pb2.BoolValue
        userId: _common_pb2.ResourceId
        invalidEntryCount: int
        pincodeEntryResult: PincodeInputTrait.PincodeEntryResult
        def __init__(self, pincodeCredentialEnabled: _Optional[_Union[_wrappers_pb2.BoolValue, _Mapping]] = ..., userId: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ..., invalidEntryCount: _Optional[int] = ..., pincodeEntryResult: _Optional[_Union[PincodeInputTrait.PincodeEntryResult, str]] = ...) -> None: ...
    class PincodeInputStateChangeEvent(_message.Message):
        __slots__ = ("pincodeInputState", "userId")
        PINCODEINPUTSTATE_FIELD_NUMBER: _ClassVar[int]
        USERID_FIELD_NUMBER: _ClassVar[int]
        pincodeInputState: PincodeInputTrait.PincodeInputState
        userId: _common_pb2.ResourceId
        def __init__(self, pincodeInputState: _Optional[_Union[PincodeInputTrait.PincodeInputState, str]] = ..., userId: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ...) -> None: ...
    PINCODEINPUTSTATE_FIELD_NUMBER: _ClassVar[int]
    pincodeInputState: PincodeInputTrait.PincodeInputState
    def __init__(self, pincodeInputState: _Optional[_Union[PincodeInputTrait.PincodeInputState, str]] = ...) -> None: ...

class TamperTrait(_message.Message):
    __slots__ = ("tamperState", "firstObservedAt", "firstObservedAtMs")
    class TamperState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        TAMPER_STATE_UNSPECIFIED: _ClassVar[TamperTrait.TamperState]
        TAMPER_STATE_CLEAR: _ClassVar[TamperTrait.TamperState]
        TAMPER_STATE_TAMPERED: _ClassVar[TamperTrait.TamperState]
        TAMPER_STATE_UNKNOWN: _ClassVar[TamperTrait.TamperState]
    TAMPER_STATE_UNSPECIFIED: TamperTrait.TamperState
    TAMPER_STATE_CLEAR: TamperTrait.TamperState
    TAMPER_STATE_TAMPERED: TamperTrait.TamperState
    TAMPER_STATE_UNKNOWN: TamperTrait.TamperState
    class TamperStateChangeReason(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        TAMPER_STATE_CHANGE_REASON_UNSPECIFIED: _ClassVar[TamperTrait.TamperStateChangeReason]
        TAMPER_STATE_CHANGE_REASON_CLEAR_SECURE: _ClassVar[TamperTrait.TamperStateChangeReason]
        TAMPER_STATE_CHANGE_REASON_CLEAR_DISARM: _ClassVar[TamperTrait.TamperStateChangeReason]
        TAMPER_STATE_CHANGE_REASON_CLEAR_SNOOZE: _ClassVar[TamperTrait.TamperStateChangeReason]
    TAMPER_STATE_CHANGE_REASON_UNSPECIFIED: TamperTrait.TamperStateChangeReason
    TAMPER_STATE_CHANGE_REASON_CLEAR_SECURE: TamperTrait.TamperStateChangeReason
    TAMPER_STATE_CHANGE_REASON_CLEAR_DISARM: TamperTrait.TamperStateChangeReason
    TAMPER_STATE_CHANGE_REASON_CLEAR_SNOOZE: TamperTrait.TamperStateChangeReason
    class ResetTamperRequest(_message.Message):
        __slots__ = ()
        def __init__(self) -> None: ...
    class TamperStateChangeEvent(_message.Message):
        __slots__ = ("tamperState", "priorTamperState", "reason", "tamperStateChangeTime")
        TAMPERSTATE_FIELD_NUMBER: _ClassVar[int]
        PRIORTAMPERSTATE_FIELD_NUMBER: _ClassVar[int]
        REASON_FIELD_NUMBER: _ClassVar[int]
        TAMPERSTATECHANGETIME_FIELD_NUMBER: _ClassVar[int]
        tamperState: TamperTrait.TamperState
        priorTamperState: TamperTrait.TamperState
        reason: TamperTrait.TamperStateChangeReason
        tamperStateChangeTime: _timestamp_pb2.Timestamp
        def __init__(self, tamperState: _Optional[_Union[TamperTrait.TamperState, str]] = ..., priorTamperState: _Optional[_Union[TamperTrait.TamperState, str]] = ..., reason: _Optional[_Union[TamperTrait.TamperStateChangeReason, str]] = ..., tamperStateChangeTime: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...
    TAMPERSTATE_FIELD_NUMBER: _ClassVar[int]
    FIRSTOBSERVEDAT_FIELD_NUMBER: _ClassVar[int]
    FIRSTOBSERVEDATMS_FIELD_NUMBER: _ClassVar[int]
    tamperState: TamperTrait.TamperState
    firstObservedAt: _timestamp_pb2.Timestamp
    firstObservedAtMs: _timestamp_pb2.Timestamp
    def __init__(self, tamperState: _Optional[_Union[TamperTrait.TamperState, str]] = ..., firstObservedAt: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., firstObservedAtMs: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class UserNFCTokenAccessTrait(_message.Message):
    __slots__ = ()
    class UserNFCTokenAccessResult(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        USER_NFC_TOKEN_ACCESS_RESULT_UNSPECIFIED: _ClassVar[UserNFCTokenAccessTrait.UserNFCTokenAccessResult]
        USER_NFC_TOKEN_ACCESS_RESULT_SUCCESS: _ClassVar[UserNFCTokenAccessTrait.UserNFCTokenAccessResult]
        USER_NFC_TOKEN_ACCESS_RESULT_FAILURE_UNKNOWN_TOKEN: _ClassVar[UserNFCTokenAccessTrait.UserNFCTokenAccessResult]
        USER_NFC_TOKEN_ACCESS_RESULT_FAILURE_INVALID_TOKEN: _ClassVar[UserNFCTokenAccessTrait.UserNFCTokenAccessResult]
        USER_NFC_TOKEN_ACCESS_RESULT_FAILURE_OUT_OF_SCHEDULE: _ClassVar[UserNFCTokenAccessTrait.UserNFCTokenAccessResult]
        USER_NFC_TOKEN_ACCESS_RESULT_FAILURE_TOKEN_DISABLED: _ClassVar[UserNFCTokenAccessTrait.UserNFCTokenAccessResult]
        USER_NFC_TOKEN_ACCESS_RESULT_FAILURE_INVALID_VERSION: _ClassVar[UserNFCTokenAccessTrait.UserNFCTokenAccessResult]
        USER_NFC_TOKEN_ACCESS_RESULT_FAILURE_OTHER_REASON: _ClassVar[UserNFCTokenAccessTrait.UserNFCTokenAccessResult]
    USER_NFC_TOKEN_ACCESS_RESULT_UNSPECIFIED: UserNFCTokenAccessTrait.UserNFCTokenAccessResult
    USER_NFC_TOKEN_ACCESS_RESULT_SUCCESS: UserNFCTokenAccessTrait.UserNFCTokenAccessResult
    USER_NFC_TOKEN_ACCESS_RESULT_FAILURE_UNKNOWN_TOKEN: UserNFCTokenAccessTrait.UserNFCTokenAccessResult
    USER_NFC_TOKEN_ACCESS_RESULT_FAILURE_INVALID_TOKEN: UserNFCTokenAccessTrait.UserNFCTokenAccessResult
    USER_NFC_TOKEN_ACCESS_RESULT_FAILURE_OUT_OF_SCHEDULE: UserNFCTokenAccessTrait.UserNFCTokenAccessResult
    USER_NFC_TOKEN_ACCESS_RESULT_FAILURE_TOKEN_DISABLED: UserNFCTokenAccessTrait.UserNFCTokenAccessResult
    USER_NFC_TOKEN_ACCESS_RESULT_FAILURE_INVALID_VERSION: UserNFCTokenAccessTrait.UserNFCTokenAccessResult
    USER_NFC_TOKEN_ACCESS_RESULT_FAILURE_OTHER_REASON: UserNFCTokenAccessTrait.UserNFCTokenAccessResult
    class UserNFCTokenAccessEvent(_message.Message):
        __slots__ = ("result", "tokenId", "userId")
        RESULT_FIELD_NUMBER: _ClassVar[int]
        TOKENID_FIELD_NUMBER: _ClassVar[int]
        USERID_FIELD_NUMBER: _ClassVar[int]
        result: UserNFCTokenAccessTrait.UserNFCTokenAccessResult
        tokenId: _common_pb2.ResourceId
        userId: _common_pb2.ResourceId
        def __init__(self, result: _Optional[_Union[UserNFCTokenAccessTrait.UserNFCTokenAccessResult, str]] = ..., tokenId: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ..., userId: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ...) -> None: ...
    def __init__(self) -> None: ...

class UserNFCTokensTrait(_message.Message):
    __slots__ = ("userNfcTokens",)
    class UserNFCTokenData(_message.Message):
        __slots__ = ("userId", "tokenDeviceId", "enabled", "structureIds", "label", "metadata")
        USERID_FIELD_NUMBER: _ClassVar[int]
        TOKENDEVICEID_FIELD_NUMBER: _ClassVar[int]
        ENABLED_FIELD_NUMBER: _ClassVar[int]
        STRUCTUREIDS_FIELD_NUMBER: _ClassVar[int]
        LABEL_FIELD_NUMBER: _ClassVar[int]
        METADATA_FIELD_NUMBER: _ClassVar[int]
        userId: _common_pb2.ResourceId
        tokenDeviceId: _common_pb2.ResourceId
        enabled: bool
        structureIds: _containers.RepeatedCompositeFieldContainer[_common_pb2.ResourceId]
        label: str
        metadata: UserNFCTokenMetadataTrait.Metadata
        def __init__(self, userId: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ..., tokenDeviceId: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ..., enabled: bool = ..., structureIds: _Optional[_Iterable[_Union[_common_pb2.ResourceId, _Mapping]]] = ..., label: _Optional[str] = ..., metadata: _Optional[_Union[UserNFCTokenMetadataTrait.Metadata, _Mapping]] = ...) -> None: ...
    USERNFCTOKENS_FIELD_NUMBER: _ClassVar[int]
    userNfcTokens: _containers.RepeatedCompositeFieldContainer[UserNFCTokensTrait.UserNFCTokenData]
    def __init__(self, userNfcTokens: _Optional[_Iterable[_Union[UserNFCTokensTrait.UserNFCTokenData, _Mapping]]] = ...) -> None: ...

class UserNFCTokenMetadataTrait(_message.Message):
    __slots__ = ("metadata",)
    class Metadata(_message.Message):
        __slots__ = ("serialNumber", "tagNumber")
        SERIALNUMBER_FIELD_NUMBER: _ClassVar[int]
        TAGNUMBER_FIELD_NUMBER: _ClassVar[int]
        serialNumber: str
        tagNumber: str
        def __init__(self, serialNumber: _Optional[str] = ..., tagNumber: _Optional[str] = ...) -> None: ...
    METADATA_FIELD_NUMBER: _ClassVar[int]
    metadata: UserNFCTokenMetadataTrait.Metadata
    def __init__(self, metadata: _Optional[_Union[UserNFCTokenMetadataTrait.Metadata, _Mapping]] = ...) -> None: ...

class BoltLockSettingsTrait(_message.Message):
    __slots__ = ("autoRelockOn", "autoRelockDuration")
    AUTORELOCKON_FIELD_NUMBER: _ClassVar[int]
    AUTORELOCKDURATION_FIELD_NUMBER: _ClassVar[int]
    autoRelockOn: bool
    autoRelockDuration: _duration_pb2.Duration
    def __init__(self, autoRelockOn: bool = ..., autoRelockDuration: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ...) -> None: ...

class BoltLockCapabilitiesTrait(_message.Message):
    __slots__ = ("handedness", "maxAutoRelockDuration")
    class BoltLockCapabilitiesHandedness(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        BOLT_LOCK_CAPABILITIES_HANDEDNESS_UNSPECIFIED: _ClassVar[BoltLockCapabilitiesTrait.BoltLockCapabilitiesHandedness]
        BOLT_LOCK_CAPABILITIES_HANDEDNESS_RIGHT: _ClassVar[BoltLockCapabilitiesTrait.BoltLockCapabilitiesHandedness]
        BOLT_LOCK_CAPABILITIES_HANDEDNESS_LEFT: _ClassVar[BoltLockCapabilitiesTrait.BoltLockCapabilitiesHandedness]
        BOLT_LOCK_CAPABILITIES_HANDEDNESS_FIXED_UNKNOWN: _ClassVar[BoltLockCapabilitiesTrait.BoltLockCapabilitiesHandedness]
    BOLT_LOCK_CAPABILITIES_HANDEDNESS_UNSPECIFIED: BoltLockCapabilitiesTrait.BoltLockCapabilitiesHandedness
    BOLT_LOCK_CAPABILITIES_HANDEDNESS_RIGHT: BoltLockCapabilitiesTrait.BoltLockCapabilitiesHandedness
    BOLT_LOCK_CAPABILITIES_HANDEDNESS_LEFT: BoltLockCapabilitiesTrait.BoltLockCapabilitiesHandedness
    BOLT_LOCK_CAPABILITIES_HANDEDNESS_FIXED_UNKNOWN: BoltLockCapabilitiesTrait.BoltLockCapabilitiesHandedness
    HANDEDNESS_FIELD_NUMBER: _ClassVar[int]
    MAXAUTORELOCKDURATION_FIELD_NUMBER: _ClassVar[int]
    handedness: BoltLockCapabilitiesTrait.BoltLockCapabilitiesHandedness
    maxAutoRelockDuration: _duration_pb2.Duration
    def __init__(self, handedness: _Optional[_Union[BoltLockCapabilitiesTrait.BoltLockCapabilitiesHandedness, str]] = ..., maxAutoRelockDuration: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ...) -> None: ...

class UserNFCTokenSettingsTrait(_message.Message):
    __slots__ = ("userNfcTokens",)
    class UserNfcTokensEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: int
        value: UserNFCTokenSettingsTrait.UserNFCToken
        def __init__(self, key: _Optional[int] = ..., value: _Optional[_Union[UserNFCTokenSettingsTrait.UserNFCToken, _Mapping]] = ...) -> None: ...
    class UserNFCToken(_message.Message):
        __slots__ = ("userId", "tokenDeviceId", "publicKey")
        USERID_FIELD_NUMBER: _ClassVar[int]
        TOKENDEVICEID_FIELD_NUMBER: _ClassVar[int]
        PUBLICKEY_FIELD_NUMBER: _ClassVar[int]
        userId: _common_pb2.ResourceId
        tokenDeviceId: _common_pb2.ResourceId
        publicKey: bytes
        def __init__(self, userId: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ..., tokenDeviceId: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ..., publicKey: _Optional[bytes] = ...) -> None: ...
    USERNFCTOKENS_FIELD_NUMBER: _ClassVar[int]
    userNfcTokens: _containers.MessageMap[int, UserNFCTokenSettingsTrait.UserNFCToken]
    def __init__(self, userNfcTokens: _Optional[_Mapping[int, UserNFCTokenSettingsTrait.UserNFCToken]] = ...) -> None: ...

class DoorCheckSettingsTrait(_message.Message):
    __slots__ = ("doorCheckEnabled", "sensorDeviceId")
    DOORCHECKENABLED_FIELD_NUMBER: _ClassVar[int]
    SENSORDEVICEID_FIELD_NUMBER: _ClassVar[int]
    doorCheckEnabled: _wrappers_pb2.BoolValue
    sensorDeviceId: _common_pb2.ResourceId
    def __init__(self, doorCheckEnabled: _Optional[_Union[_wrappers_pb2.BoolValue, _Mapping]] = ..., sensorDeviceId: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ...) -> None: ...

class PincodeInputSettingsTrait(_message.Message):
    __slots__ = ("wrongEntryCodeLimit", "wrongEntryDisableTime")
    WRONGENTRYCODELIMIT_FIELD_NUMBER: _ClassVar[int]
    WRONGENTRYDISABLETIME_FIELD_NUMBER: _ClassVar[int]
    wrongEntryCodeLimit: int
    wrongEntryDisableTime: _duration_pb2.Duration
    def __init__(self, wrongEntryCodeLimit: _Optional[int] = ..., wrongEntryDisableTime: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ...) -> None: ...

class UserPincodesCapabilitiesTrait(_message.Message):
    __slots__ = ("minPincodeLength", "maxPincodeLength", "maxPincodesSupported")
    MINPINCODELENGTH_FIELD_NUMBER: _ClassVar[int]
    MAXPINCODELENGTH_FIELD_NUMBER: _ClassVar[int]
    MAXPINCODESSUPPORTED_FIELD_NUMBER: _ClassVar[int]
    minPincodeLength: int
    maxPincodeLength: int
    maxPincodesSupported: int
    def __init__(self, minPincodeLength: _Optional[int] = ..., maxPincodeLength: _Optional[int] = ..., maxPincodesSupported: _Optional[int] = ...) -> None: ...
