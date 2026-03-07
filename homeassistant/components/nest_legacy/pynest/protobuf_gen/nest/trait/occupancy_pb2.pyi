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

class StructureModeTrait(_message.Message):
    __slots__ = ("structureMode", "occupancy", "allowance", "structureModeReason", "structureModeSetter", "structureModeEffectiveTime", "activityAgnosticStructureMode", "activityAgnosticStructureModeEffectiveTime", "privateState", "blames", "actorMethod", "primaryBlame")
    class StructureMode(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        STRUCTURE_MODE_UNSPECIFIED: _ClassVar[StructureModeTrait.StructureMode]
        STRUCTURE_MODE_HOME: _ClassVar[StructureModeTrait.StructureMode]
        STRUCTURE_MODE_AWAY: _ClassVar[StructureModeTrait.StructureMode]
        STRUCTURE_MODE_SLEEP: _ClassVar[StructureModeTrait.StructureMode]
        STRUCTURE_MODE_VACATION: _ClassVar[StructureModeTrait.StructureMode]
    STRUCTURE_MODE_UNSPECIFIED: StructureModeTrait.StructureMode
    STRUCTURE_MODE_HOME: StructureModeTrait.StructureMode
    STRUCTURE_MODE_AWAY: StructureModeTrait.StructureMode
    STRUCTURE_MODE_SLEEP: StructureModeTrait.StructureMode
    STRUCTURE_MODE_VACATION: StructureModeTrait.StructureMode
    class Activity(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        ACTIVITY_UNSPECIFIED: _ClassVar[StructureModeTrait.Activity]
        ACTIVITY_ACTIVE: _ClassVar[StructureModeTrait.Activity]
        ACTIVITY_INACTIVE: _ClassVar[StructureModeTrait.Activity]
    ACTIVITY_UNSPECIFIED: StructureModeTrait.Activity
    ACTIVITY_ACTIVE: StructureModeTrait.Activity
    ACTIVITY_INACTIVE: StructureModeTrait.Activity
    class Presence(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        PRESENCE_UNSPECIFIED: _ClassVar[StructureModeTrait.Presence]
        PRESENCE_UNAVAILABLE: _ClassVar[StructureModeTrait.Presence]
        PRESENCE_PRESENT: _ClassVar[StructureModeTrait.Presence]
        PRESENCE_ABSENT: _ClassVar[StructureModeTrait.Presence]
    PRESENCE_UNSPECIFIED: StructureModeTrait.Presence
    PRESENCE_UNAVAILABLE: StructureModeTrait.Presence
    PRESENCE_PRESENT: StructureModeTrait.Presence
    PRESENCE_ABSENT: StructureModeTrait.Presence
    class ModeStickiness(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        MODE_STICKINESS_UNSPECIFIED: _ClassVar[StructureModeTrait.ModeStickiness]
        MODE_STICKINESS_NONE: _ClassVar[StructureModeTrait.ModeStickiness]
        MODE_STICKINESS_TIMED: _ClassVar[StructureModeTrait.ModeStickiness]
        MODE_STICKINESS_CONDITIONAL_TIMED: _ClassVar[StructureModeTrait.ModeStickiness]
    MODE_STICKINESS_UNSPECIFIED: StructureModeTrait.ModeStickiness
    MODE_STICKINESS_NONE: StructureModeTrait.ModeStickiness
    MODE_STICKINESS_TIMED: StructureModeTrait.ModeStickiness
    MODE_STICKINESS_CONDITIONAL_TIMED: StructureModeTrait.ModeStickiness
    class StructureModeReason(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        STRUCTURE_MODE_REASON_UNSPECIFIED: _ClassVar[StructureModeTrait.StructureModeReason]
        STRUCTURE_MODE_REASON_EXPLICIT_INTENT: _ClassVar[StructureModeTrait.StructureModeReason]
        STRUCTURE_MODE_REASON_IMPLICIT_INTENT: _ClassVar[StructureModeTrait.StructureModeReason]
        STRUCTURE_MODE_REASON_ACTIVITY: _ClassVar[StructureModeTrait.StructureModeReason]
        STRUCTURE_MODE_REASON_EXTENDED_INACTIVITY: _ClassVar[StructureModeTrait.StructureModeReason]
        STRUCTURE_MODE_REASON_IDENTIFIED_PRESENCE: _ClassVar[StructureModeTrait.StructureModeReason]
        STRUCTURE_MODE_REASON_IDENTIFIED_ABSENCE: _ClassVar[StructureModeTrait.StructureModeReason]
        STRUCTURE_MODE_REASON_SCHEDULE: _ClassVar[StructureModeTrait.StructureModeReason]
    STRUCTURE_MODE_REASON_UNSPECIFIED: StructureModeTrait.StructureModeReason
    STRUCTURE_MODE_REASON_EXPLICIT_INTENT: StructureModeTrait.StructureModeReason
    STRUCTURE_MODE_REASON_IMPLICIT_INTENT: StructureModeTrait.StructureModeReason
    STRUCTURE_MODE_REASON_ACTIVITY: StructureModeTrait.StructureModeReason
    STRUCTURE_MODE_REASON_EXTENDED_INACTIVITY: StructureModeTrait.StructureModeReason
    STRUCTURE_MODE_REASON_IDENTIFIED_PRESENCE: StructureModeTrait.StructureModeReason
    STRUCTURE_MODE_REASON_IDENTIFIED_ABSENCE: StructureModeTrait.StructureModeReason
    STRUCTURE_MODE_REASON_SCHEDULE: StructureModeTrait.StructureModeReason
    class StructureModeActorMethod(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        STRUCTURE_MODE_ACTOR_METHOD_UNSPECIFIED: _ClassVar[StructureModeTrait.StructureModeActorMethod]
        STRUCTURE_MODE_ACTOR_METHOD_LEGACY_NEST_APP: _ClassVar[StructureModeTrait.StructureModeActorMethod]
        STRUCTURE_MODE_ACTOR_METHOD_GOOGLE_HOME_APP: _ClassVar[StructureModeTrait.StructureModeActorMethod]
        STRUCTURE_MODE_ACTOR_METHOD_GOOGLE_ASSISTANT: _ClassVar[StructureModeTrait.StructureModeActorMethod]
    STRUCTURE_MODE_ACTOR_METHOD_UNSPECIFIED: StructureModeTrait.StructureModeActorMethod
    STRUCTURE_MODE_ACTOR_METHOD_LEGACY_NEST_APP: StructureModeTrait.StructureModeActorMethod
    STRUCTURE_MODE_ACTOR_METHOD_GOOGLE_HOME_APP: StructureModeTrait.StructureModeActorMethod
    STRUCTURE_MODE_ACTOR_METHOD_GOOGLE_ASSISTANT: StructureModeTrait.StructureModeActorMethod
    class UserBlameType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        USER_BLAME_TYPE_UNSPECIFIED: _ClassVar[StructureModeTrait.UserBlameType]
        USER_BLAME_TYPE_PHONE_LOCATION: _ClassVar[StructureModeTrait.UserBlameType]
        USER_BLAME_TYPE_MANUAL_CHANGE: _ClassVar[StructureModeTrait.UserBlameType]
    USER_BLAME_TYPE_UNSPECIFIED: StructureModeTrait.UserBlameType
    USER_BLAME_TYPE_PHONE_LOCATION: StructureModeTrait.UserBlameType
    USER_BLAME_TYPE_MANUAL_CHANGE: StructureModeTrait.UserBlameType
    class DeviceBlameType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        DEVICE_BLAME_TYPE_UNSPECIFIED: _ClassVar[StructureModeTrait.DeviceBlameType]
        DEVICE_BLAME_TYPE_LOCK: _ClassVar[StructureModeTrait.DeviceBlameType]
        DEVICE_BLAME_TYPE_UNLOCK: _ClassVar[StructureModeTrait.DeviceBlameType]
        DEVICE_BLAME_TYPE_MOTION_DETECTION: _ClassVar[StructureModeTrait.DeviceBlameType]
        DEVICE_BLAME_TYPE_TOUCH_INTERACTION: _ClassVar[StructureModeTrait.DeviceBlameType]
        DEVICE_BLAME_TYPE_VOICE_INTERACTION: _ClassVar[StructureModeTrait.DeviceBlameType]
    DEVICE_BLAME_TYPE_UNSPECIFIED: StructureModeTrait.DeviceBlameType
    DEVICE_BLAME_TYPE_LOCK: StructureModeTrait.DeviceBlameType
    DEVICE_BLAME_TYPE_UNLOCK: StructureModeTrait.DeviceBlameType
    DEVICE_BLAME_TYPE_MOTION_DETECTION: StructureModeTrait.DeviceBlameType
    DEVICE_BLAME_TYPE_TOUCH_INTERACTION: StructureModeTrait.DeviceBlameType
    DEVICE_BLAME_TYPE_VOICE_INTERACTION: StructureModeTrait.DeviceBlameType
    class NonPropagatingChangeSourceType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        NON_PROPAGATING_CHANGE_SOURCE_TYPE_UNSPECIFIED: _ClassVar[StructureModeTrait.NonPropagatingChangeSourceType]
        NON_PROPAGATING_CHANGE_SOURCE_TYPE_CZ: _ClassVar[StructureModeTrait.NonPropagatingChangeSourceType]
    NON_PROPAGATING_CHANGE_SOURCE_TYPE_UNSPECIFIED: StructureModeTrait.NonPropagatingChangeSourceType
    NON_PROPAGATING_CHANGE_SOURCE_TYPE_CZ: StructureModeTrait.NonPropagatingChangeSourceType
    class StructureModeChangeResponseType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        STRUCTURE_MODE_CHANGE_RESPONSE_TYPE_UNSPECIFIED: _ClassVar[StructureModeTrait.StructureModeChangeResponseType]
        STRUCTURE_MODE_CHANGE_RESPONSE_TYPE_SUCCESS: _ClassVar[StructureModeTrait.StructureModeChangeResponseType]
        STRUCTURE_MODE_CHANGE_RESPONSE_TYPE_FAIL_ALREADY: _ClassVar[StructureModeTrait.StructureModeChangeResponseType]
    STRUCTURE_MODE_CHANGE_RESPONSE_TYPE_UNSPECIFIED: StructureModeTrait.StructureModeChangeResponseType
    STRUCTURE_MODE_CHANGE_RESPONSE_TYPE_SUCCESS: StructureModeTrait.StructureModeChangeResponseType
    STRUCTURE_MODE_CHANGE_RESPONSE_TYPE_FAIL_ALREADY: StructureModeTrait.StructureModeChangeResponseType
    class StructureModeCompleteUpdateResponseType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        STRUCTURE_MODE_COMPLETE_UPDATE_RESPONSE_TYPE_UNSPECIFIED: _ClassVar[StructureModeTrait.StructureModeCompleteUpdateResponseType]
        STRUCTURE_MODE_COMPLETE_UPDATE_RESPONSE_TYPE_SUCCESS: _ClassVar[StructureModeTrait.StructureModeCompleteUpdateResponseType]
        STRUCTURE_MODE_COMPLETE_UPDATE_RESPONSE_TYPE_FAIL_ALREADY: _ClassVar[StructureModeTrait.StructureModeCompleteUpdateResponseType]
        STRUCTURE_MODE_COMPLETE_UPDATE_RESPONSE_TYPE_FAIL_VERSION: _ClassVar[StructureModeTrait.StructureModeCompleteUpdateResponseType]
        STRUCTURE_MODE_COMPLETE_UPDATE_RESPONSE_TYPE_FAIL_OTHER: _ClassVar[StructureModeTrait.StructureModeCompleteUpdateResponseType]
    STRUCTURE_MODE_COMPLETE_UPDATE_RESPONSE_TYPE_UNSPECIFIED: StructureModeTrait.StructureModeCompleteUpdateResponseType
    STRUCTURE_MODE_COMPLETE_UPDATE_RESPONSE_TYPE_SUCCESS: StructureModeTrait.StructureModeCompleteUpdateResponseType
    STRUCTURE_MODE_COMPLETE_UPDATE_RESPONSE_TYPE_FAIL_ALREADY: StructureModeTrait.StructureModeCompleteUpdateResponseType
    STRUCTURE_MODE_COMPLETE_UPDATE_RESPONSE_TYPE_FAIL_VERSION: StructureModeTrait.StructureModeCompleteUpdateResponseType
    STRUCTURE_MODE_COMPLETE_UPDATE_RESPONSE_TYPE_FAIL_OTHER: StructureModeTrait.StructureModeCompleteUpdateResponseType
    class LegacyAwayState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        LEGACY_AWAY_STATE_UNSPECIFIED: _ClassVar[StructureModeTrait.LegacyAwayState]
        LEGACY_AWAY_STATE_TRUE: _ClassVar[StructureModeTrait.LegacyAwayState]
        LEGACY_AWAY_STATE_FALSE: _ClassVar[StructureModeTrait.LegacyAwayState]
    LEGACY_AWAY_STATE_UNSPECIFIED: StructureModeTrait.LegacyAwayState
    LEGACY_AWAY_STATE_TRUE: StructureModeTrait.LegacyAwayState
    LEGACY_AWAY_STATE_FALSE: StructureModeTrait.LegacyAwayState
    class LegacyAwaySetter(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        LEGACY_AWAY_SETTER_UNSPECIFIED: _ClassVar[StructureModeTrait.LegacyAwaySetter]
        LEGACY_AWAY_SETTER_CLIENT: _ClassVar[StructureModeTrait.LegacyAwaySetter]
        LEGACY_AWAY_SETTER_CONTROL: _ClassVar[StructureModeTrait.LegacyAwaySetter]
        LEGACY_AWAY_SETTER_CLOUD: _ClassVar[StructureModeTrait.LegacyAwaySetter]
    LEGACY_AWAY_SETTER_UNSPECIFIED: StructureModeTrait.LegacyAwaySetter
    LEGACY_AWAY_SETTER_CLIENT: StructureModeTrait.LegacyAwaySetter
    LEGACY_AWAY_SETTER_CONTROL: StructureModeTrait.LegacyAwaySetter
    LEGACY_AWAY_SETTER_CLOUD: StructureModeTrait.LegacyAwaySetter
    class LegacyTouchedBy(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        LEGACY_TOUCHED_BY_UNSPECIFIED: _ClassVar[StructureModeTrait.LegacyTouchedBy]
        LEGACY_TOUCHED_BY_NOBODY: _ClassVar[StructureModeTrait.LegacyTouchedBy]
        LEGACY_TOUCHED_BY_LEARNING: _ClassVar[StructureModeTrait.LegacyTouchedBy]
        LEGACY_TOUCHED_BY_LOCAL: _ClassVar[StructureModeTrait.LegacyTouchedBy]
        LEGACY_TOUCHED_BY_REMOTE: _ClassVar[StructureModeTrait.LegacyTouchedBy]
        LEGACY_TOUCHED_BY_WEB: _ClassVar[StructureModeTrait.LegacyTouchedBy]
        LEGACY_TOUCHED_BY_ANDROID: _ClassVar[StructureModeTrait.LegacyTouchedBy]
        LEGACY_TOUCHED_BY_IOS: _ClassVar[StructureModeTrait.LegacyTouchedBy]
        LEGACY_TOUCHED_BY_WIN_MOBILE: _ClassVar[StructureModeTrait.LegacyTouchedBy]
        LEGACY_TOUCHED_BY_TUNE_UP: _ClassVar[StructureModeTrait.LegacyTouchedBy]
        LEGACY_TOUCHED_BY_DR: _ClassVar[StructureModeTrait.LegacyTouchedBy]
        LEGACY_TOUCHED_BY_TOU: _ClassVar[StructureModeTrait.LegacyTouchedBy]
        LEGACY_TOUCHED_BY_TOPAZ_CO: _ClassVar[StructureModeTrait.LegacyTouchedBy]
        LEGACY_TOUCHED_BY_PROGRAMMER: _ClassVar[StructureModeTrait.LegacyTouchedBy]
        LEGACY_TOUCHED_BY_TOPAZ_SMOKE: _ClassVar[StructureModeTrait.LegacyTouchedBy]
        LEGACY_TOUCHED_BY_DEMAND_CHARGE: _ClassVar[StructureModeTrait.LegacyTouchedBy]
    LEGACY_TOUCHED_BY_UNSPECIFIED: StructureModeTrait.LegacyTouchedBy
    LEGACY_TOUCHED_BY_NOBODY: StructureModeTrait.LegacyTouchedBy
    LEGACY_TOUCHED_BY_LEARNING: StructureModeTrait.LegacyTouchedBy
    LEGACY_TOUCHED_BY_LOCAL: StructureModeTrait.LegacyTouchedBy
    LEGACY_TOUCHED_BY_REMOTE: StructureModeTrait.LegacyTouchedBy
    LEGACY_TOUCHED_BY_WEB: StructureModeTrait.LegacyTouchedBy
    LEGACY_TOUCHED_BY_ANDROID: StructureModeTrait.LegacyTouchedBy
    LEGACY_TOUCHED_BY_IOS: StructureModeTrait.LegacyTouchedBy
    LEGACY_TOUCHED_BY_WIN_MOBILE: StructureModeTrait.LegacyTouchedBy
    LEGACY_TOUCHED_BY_TUNE_UP: StructureModeTrait.LegacyTouchedBy
    LEGACY_TOUCHED_BY_DR: StructureModeTrait.LegacyTouchedBy
    LEGACY_TOUCHED_BY_TOU: StructureModeTrait.LegacyTouchedBy
    LEGACY_TOUCHED_BY_TOPAZ_CO: StructureModeTrait.LegacyTouchedBy
    LEGACY_TOUCHED_BY_PROGRAMMER: StructureModeTrait.LegacyTouchedBy
    LEGACY_TOUCHED_BY_TOPAZ_SMOKE: StructureModeTrait.LegacyTouchedBy
    LEGACY_TOUCHED_BY_DEMAND_CHARGE: StructureModeTrait.LegacyTouchedBy
    class AutoAskType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        AUTO_ASK_TYPE_UNSPECIFIED: _ClassVar[StructureModeTrait.AutoAskType]
        AUTO_ASK_TYPE_AWAY_AND_ARM: _ClassVar[StructureModeTrait.AutoAskType]
        AUTO_ASK_TYPE_HOME_AND_DISARM: _ClassVar[StructureModeTrait.AutoAskType]
        AUTO_ASK_TYPE_ARM: _ClassVar[StructureModeTrait.AutoAskType]
        AUTO_ASK_TYPE_DISARM: _ClassVar[StructureModeTrait.AutoAskType]
    AUTO_ASK_TYPE_UNSPECIFIED: StructureModeTrait.AutoAskType
    AUTO_ASK_TYPE_AWAY_AND_ARM: StructureModeTrait.AutoAskType
    AUTO_ASK_TYPE_HOME_AND_DISARM: StructureModeTrait.AutoAskType
    AUTO_ASK_TYPE_ARM: StructureModeTrait.AutoAskType
    AUTO_ASK_TYPE_DISARM: StructureModeTrait.AutoAskType
    class AutoAskArm(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        AUTO_ASK_ARM_UNSPECIFIED: _ClassVar[StructureModeTrait.AutoAskArm]
        AUTO_ASK_ARM_TYPE_ARM: _ClassVar[StructureModeTrait.AutoAskArm]
        AUTO_ASK_ARM_TYPE_DISARM: _ClassVar[StructureModeTrait.AutoAskArm]
    AUTO_ASK_ARM_UNSPECIFIED: StructureModeTrait.AutoAskArm
    AUTO_ASK_ARM_TYPE_ARM: StructureModeTrait.AutoAskArm
    AUTO_ASK_ARM_TYPE_DISARM: StructureModeTrait.AutoAskArm
    class AutoAskLock(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        AUTO_ASK_LOCK_UNSPECIFIED: _ClassVar[StructureModeTrait.AutoAskLock]
        AUTO_ASK_LOCK_TYPE_LOCK: _ClassVar[StructureModeTrait.AutoAskLock]
        AUTO_ASK_LOCK_TYPE_UNLOCK: _ClassVar[StructureModeTrait.AutoAskLock]
    AUTO_ASK_LOCK_UNSPECIFIED: StructureModeTrait.AutoAskLock
    AUTO_ASK_LOCK_TYPE_LOCK: StructureModeTrait.AutoAskLock
    AUTO_ASK_LOCK_TYPE_UNLOCK: StructureModeTrait.AutoAskLock
    class AutoAskStructureMode(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        AUTO_ASK_STRUCTURE_MODE_UNSPECIFIED: _ClassVar[StructureModeTrait.AutoAskStructureMode]
        AUTO_ASK_STRUCTURE_MODE_TYPE_HOME: _ClassVar[StructureModeTrait.AutoAskStructureMode]
        AUTO_ASK_STRUCTURE_MODE_TYPE_AWAY: _ClassVar[StructureModeTrait.AutoAskStructureMode]
    AUTO_ASK_STRUCTURE_MODE_UNSPECIFIED: StructureModeTrait.AutoAskStructureMode
    AUTO_ASK_STRUCTURE_MODE_TYPE_HOME: StructureModeTrait.AutoAskStructureMode
    AUTO_ASK_STRUCTURE_MODE_TYPE_AWAY: StructureModeTrait.AutoAskStructureMode
    class BlamesEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: int
        value: StructureModeTrait.StructureModeBlame
        def __init__(self, key: _Optional[int] = ..., value: _Optional[_Union[StructureModeTrait.StructureModeBlame, _Mapping]] = ...) -> None: ...
    class Occupancy(_message.Message):
        __slots__ = ("activity", "presence", "lastActivityTime", "activityHoldOff")
        ACTIVITY_FIELD_NUMBER: _ClassVar[int]
        PRESENCE_FIELD_NUMBER: _ClassVar[int]
        LASTACTIVITYTIME_FIELD_NUMBER: _ClassVar[int]
        ACTIVITYHOLDOFF_FIELD_NUMBER: _ClassVar[int]
        activity: StructureModeTrait.Activity
        presence: StructureModeTrait.Presence
        lastActivityTime: _timestamp_pb2.Timestamp
        activityHoldOff: _timestamp_pb2.Timestamp
        def __init__(self, activity: _Optional[_Union[StructureModeTrait.Activity, str]] = ..., presence: _Optional[_Union[StructureModeTrait.Presence, str]] = ..., lastActivityTime: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., activityHoldOff: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...
    class Allowance(_message.Message):
        __slots__ = ("modeStickiness", "modeStickinessExpiration")
        MODESTICKINESS_FIELD_NUMBER: _ClassVar[int]
        MODESTICKINESSEXPIRATION_FIELD_NUMBER: _ClassVar[int]
        modeStickiness: StructureModeTrait.ModeStickiness
        modeStickinessExpiration: _timestamp_pb2.Timestamp
        def __init__(self, modeStickiness: _Optional[_Union[StructureModeTrait.ModeStickiness, str]] = ..., modeStickinessExpiration: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...
    class UserBlame(_message.Message):
        __slots__ = ("gaiaId", "blameType")
        GAIAID_FIELD_NUMBER: _ClassVar[int]
        BLAMETYPE_FIELD_NUMBER: _ClassVar[int]
        gaiaId: int
        blameType: StructureModeTrait.UserBlameType
        def __init__(self, gaiaId: _Optional[int] = ..., blameType: _Optional[_Union[StructureModeTrait.UserBlameType, str]] = ...) -> None: ...
    class DeviceBlame(_message.Message):
        __slots__ = ("hgsDeviceId", "blameType")
        HGSDEVICEID_FIELD_NUMBER: _ClassVar[int]
        BLAMETYPE_FIELD_NUMBER: _ClassVar[int]
        hgsDeviceId: str
        blameType: StructureModeTrait.DeviceBlameType
        def __init__(self, hgsDeviceId: _Optional[str] = ..., blameType: _Optional[_Union[StructureModeTrait.DeviceBlameType, str]] = ...) -> None: ...
    class StructureModeBlame(_message.Message):
        __slots__ = ("observedTimestamp", "payloadTypeUrl", "leafEventUrl", "payload", "userBlame", "deviceBlame")
        OBSERVEDTIMESTAMP_FIELD_NUMBER: _ClassVar[int]
        PAYLOADTYPEURL_FIELD_NUMBER: _ClassVar[int]
        LEAFEVENTURL_FIELD_NUMBER: _ClassVar[int]
        PAYLOAD_FIELD_NUMBER: _ClassVar[int]
        USERBLAME_FIELD_NUMBER: _ClassVar[int]
        DEVICEBLAME_FIELD_NUMBER: _ClassVar[int]
        observedTimestamp: _timestamp_pb2.Timestamp
        payloadTypeUrl: str
        leafEventUrl: str
        payload: bytes
        userBlame: StructureModeTrait.UserBlame
        deviceBlame: StructureModeTrait.DeviceBlame
        def __init__(self, observedTimestamp: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., payloadTypeUrl: _Optional[str] = ..., leafEventUrl: _Optional[str] = ..., payload: _Optional[bytes] = ..., userBlame: _Optional[_Union[StructureModeTrait.UserBlame, _Mapping]] = ..., deviceBlame: _Optional[_Union[StructureModeTrait.DeviceBlame, _Mapping]] = ...) -> None: ...
    class PrivateTraitHandlerState(_message.Message):
        __slots__ = ("isCzUpdateStateOk",)
        ISCZUPDATESTATEOK_FIELD_NUMBER: _ClassVar[int]
        isCzUpdateStateOk: bool
        def __init__(self, isCzUpdateStateOk: bool = ...) -> None: ...
    class UserInfo(_message.Message):
        __slots__ = ("rtsUserId", "phoenixUserId")
        RTSUSERID_FIELD_NUMBER: _ClassVar[int]
        PHOENIXUSERID_FIELD_NUMBER: _ClassVar[int]
        rtsUserId: _wrappers_pb2.StringValue
        phoenixUserId: _wrappers_pb2.StringValue
        def __init__(self, rtsUserId: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., phoenixUserId: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ...) -> None: ...
    class StructureModeChangeRequest(_message.Message):
        __slots__ = ("structureMode", "reason", "userId", "nonPropagatingChangeDetails", "actorMethod")
        STRUCTUREMODE_FIELD_NUMBER: _ClassVar[int]
        REASON_FIELD_NUMBER: _ClassVar[int]
        USERID_FIELD_NUMBER: _ClassVar[int]
        NONPROPAGATINGCHANGEDETAILS_FIELD_NUMBER: _ClassVar[int]
        ACTORMETHOD_FIELD_NUMBER: _ClassVar[int]
        structureMode: StructureModeTrait.StructureMode
        reason: StructureModeTrait.StructureModeReason
        userId: _common_pb2.ResourceId
        nonPropagatingChangeDetails: StructureModeTrait.NonPropagatingChangeDetails
        actorMethod: StructureModeTrait.StructureModeActorMethod
        def __init__(self, structureMode: _Optional[_Union[StructureModeTrait.StructureMode, str]] = ..., reason: _Optional[_Union[StructureModeTrait.StructureModeReason, str]] = ..., userId: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ..., nonPropagatingChangeDetails: _Optional[_Union[StructureModeTrait.NonPropagatingChangeDetails, _Mapping]] = ..., actorMethod: _Optional[_Union[StructureModeTrait.StructureModeActorMethod, str]] = ...) -> None: ...
    class NonPropagatingChangeDetails(_message.Message):
        __slots__ = ("sourceType", "changeTime")
        SOURCETYPE_FIELD_NUMBER: _ClassVar[int]
        CHANGETIME_FIELD_NUMBER: _ClassVar[int]
        sourceType: StructureModeTrait.NonPropagatingChangeSourceType
        changeTime: _timestamp_pb2.Timestamp
        def __init__(self, sourceType: _Optional[_Union[StructureModeTrait.NonPropagatingChangeSourceType, str]] = ..., changeTime: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...
    class StructureModeChangeResponse(_message.Message):
        __slots__ = ("responseType",)
        RESPONSETYPE_FIELD_NUMBER: _ClassVar[int]
        responseType: StructureModeTrait.StructureModeChangeResponseType
        def __init__(self, responseType: _Optional[_Union[StructureModeTrait.StructureModeChangeResponseType, str]] = ...) -> None: ...
    class StructureModeCompleteUpdateRequest(_message.Message):
        __slots__ = ("structureMode", "occupancy", "allowance", "structureModeReason", "structureModeSetter", "structureModeEffectiveTime", "activityAgnosticStructureMode", "activityAgnosticStructureModeEffectiveTime", "revisionId", "identifiedPresenceChangeRtsUserId", "identifiedPresenceChangeTime", "recentUserArrivals", "recentUserDepartures", "mlpSessionId", "blames", "primaryBlame")
        class BlamesEntry(_message.Message):
            __slots__ = ("key", "value")
            KEY_FIELD_NUMBER: _ClassVar[int]
            VALUE_FIELD_NUMBER: _ClassVar[int]
            key: int
            value: StructureModeTrait.StructureModeBlame
            def __init__(self, key: _Optional[int] = ..., value: _Optional[_Union[StructureModeTrait.StructureModeBlame, _Mapping]] = ...) -> None: ...
        STRUCTUREMODE_FIELD_NUMBER: _ClassVar[int]
        OCCUPANCY_FIELD_NUMBER: _ClassVar[int]
        ALLOWANCE_FIELD_NUMBER: _ClassVar[int]
        STRUCTUREMODEREASON_FIELD_NUMBER: _ClassVar[int]
        STRUCTUREMODESETTER_FIELD_NUMBER: _ClassVar[int]
        STRUCTUREMODEEFFECTIVETIME_FIELD_NUMBER: _ClassVar[int]
        ACTIVITYAGNOSTICSTRUCTUREMODE_FIELD_NUMBER: _ClassVar[int]
        ACTIVITYAGNOSTICSTRUCTUREMODEEFFECTIVETIME_FIELD_NUMBER: _ClassVar[int]
        REVISIONID_FIELD_NUMBER: _ClassVar[int]
        IDENTIFIEDPRESENCECHANGERTSUSERID_FIELD_NUMBER: _ClassVar[int]
        IDENTIFIEDPRESENCECHANGETIME_FIELD_NUMBER: _ClassVar[int]
        RECENTUSERARRIVALS_FIELD_NUMBER: _ClassVar[int]
        RECENTUSERDEPARTURES_FIELD_NUMBER: _ClassVar[int]
        MLPSESSIONID_FIELD_NUMBER: _ClassVar[int]
        BLAMES_FIELD_NUMBER: _ClassVar[int]
        PRIMARYBLAME_FIELD_NUMBER: _ClassVar[int]
        structureMode: StructureModeTrait.StructureMode
        occupancy: StructureModeTrait.Occupancy
        allowance: StructureModeTrait.Allowance
        structureModeReason: StructureModeTrait.StructureModeReason
        structureModeSetter: _common_pb2.ResourceId
        structureModeEffectiveTime: _timestamp_pb2.Timestamp
        activityAgnosticStructureMode: StructureModeTrait.StructureMode
        activityAgnosticStructureModeEffectiveTime: _timestamp_pb2.Timestamp
        revisionId: _wrappers_pb2.UInt64Value
        identifiedPresenceChangeRtsUserId: StructureModeTrait.UserInfo
        identifiedPresenceChangeTime: _timestamp_pb2.Timestamp
        recentUserArrivals: _containers.RepeatedCompositeFieldContainer[StructureModeTrait.UserInfo]
        recentUserDepartures: _containers.RepeatedCompositeFieldContainer[StructureModeTrait.UserInfo]
        mlpSessionId: str
        blames: _containers.MessageMap[int, StructureModeTrait.StructureModeBlame]
        primaryBlame: StructureModeTrait.StructureModeBlame
        def __init__(self, structureMode: _Optional[_Union[StructureModeTrait.StructureMode, str]] = ..., occupancy: _Optional[_Union[StructureModeTrait.Occupancy, _Mapping]] = ..., allowance: _Optional[_Union[StructureModeTrait.Allowance, _Mapping]] = ..., structureModeReason: _Optional[_Union[StructureModeTrait.StructureModeReason, str]] = ..., structureModeSetter: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ..., structureModeEffectiveTime: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., activityAgnosticStructureMode: _Optional[_Union[StructureModeTrait.StructureMode, str]] = ..., activityAgnosticStructureModeEffectiveTime: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., revisionId: _Optional[_Union[_wrappers_pb2.UInt64Value, _Mapping]] = ..., identifiedPresenceChangeRtsUserId: _Optional[_Union[StructureModeTrait.UserInfo, _Mapping]] = ..., identifiedPresenceChangeTime: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., recentUserArrivals: _Optional[_Iterable[_Union[StructureModeTrait.UserInfo, _Mapping]]] = ..., recentUserDepartures: _Optional[_Iterable[_Union[StructureModeTrait.UserInfo, _Mapping]]] = ..., mlpSessionId: _Optional[str] = ..., blames: _Optional[_Mapping[int, StructureModeTrait.StructureModeBlame]] = ..., primaryBlame: _Optional[_Union[StructureModeTrait.StructureModeBlame, _Mapping]] = ...) -> None: ...
    class StructureModeCompleteUpdateResponse(_message.Message):
        __slots__ = ("responseType", "completeResponseType")
        RESPONSETYPE_FIELD_NUMBER: _ClassVar[int]
        COMPLETERESPONSETYPE_FIELD_NUMBER: _ClassVar[int]
        responseType: StructureModeTrait.StructureModeChangeResponseType
        completeResponseType: StructureModeTrait.StructureModeCompleteUpdateResponseType
        def __init__(self, responseType: _Optional[_Union[StructureModeTrait.StructureModeChangeResponseType, str]] = ..., completeResponseType: _Optional[_Union[StructureModeTrait.StructureModeCompleteUpdateResponseType, str]] = ...) -> None: ...
    class LegacyStructureModeChangeRequest(_message.Message):
        __slots__ = ("structureMode", "reason", "userId", "wwnId")
        STRUCTUREMODE_FIELD_NUMBER: _ClassVar[int]
        REASON_FIELD_NUMBER: _ClassVar[int]
        USERID_FIELD_NUMBER: _ClassVar[int]
        WWNID_FIELD_NUMBER: _ClassVar[int]
        structureMode: StructureModeTrait.StructureMode
        reason: StructureModeTrait.StructureModeReason
        userId: _common_pb2.ResourceId
        wwnId: _wrappers_pb2.StringValue
        def __init__(self, structureMode: _Optional[_Union[StructureModeTrait.StructureMode, str]] = ..., reason: _Optional[_Union[StructureModeTrait.StructureModeReason, str]] = ..., userId: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ..., wwnId: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ...) -> None: ...
    class ConsumeOccupancyStateBeliefRequest(_message.Message):
        __slots__ = ("activeProbability", "sleepProbability", "vacantProbability", "identifiedPresenceProbability", "lastMotionEventTimestamp", "unknownProbability", "evaluationTimestamp", "transitionEvaluationTimestamp", "identifiedPresenceChangeUserId", "identifiedPresenceChangeTime", "recentUserArrivals", "recentUserDepartures")
        ACTIVEPROBABILITY_FIELD_NUMBER: _ClassVar[int]
        SLEEPPROBABILITY_FIELD_NUMBER: _ClassVar[int]
        VACANTPROBABILITY_FIELD_NUMBER: _ClassVar[int]
        IDENTIFIEDPRESENCEPROBABILITY_FIELD_NUMBER: _ClassVar[int]
        LASTMOTIONEVENTTIMESTAMP_FIELD_NUMBER: _ClassVar[int]
        UNKNOWNPROBABILITY_FIELD_NUMBER: _ClassVar[int]
        EVALUATIONTIMESTAMP_FIELD_NUMBER: _ClassVar[int]
        TRANSITIONEVALUATIONTIMESTAMP_FIELD_NUMBER: _ClassVar[int]
        IDENTIFIEDPRESENCECHANGEUSERID_FIELD_NUMBER: _ClassVar[int]
        IDENTIFIEDPRESENCECHANGETIME_FIELD_NUMBER: _ClassVar[int]
        RECENTUSERARRIVALS_FIELD_NUMBER: _ClassVar[int]
        RECENTUSERDEPARTURES_FIELD_NUMBER: _ClassVar[int]
        activeProbability: float
        sleepProbability: float
        vacantProbability: float
        identifiedPresenceProbability: float
        lastMotionEventTimestamp: _timestamp_pb2.Timestamp
        unknownProbability: float
        evaluationTimestamp: _timestamp_pb2.Timestamp
        transitionEvaluationTimestamp: _timestamp_pb2.Timestamp
        identifiedPresenceChangeUserId: StructureModeTrait.UserInfo
        identifiedPresenceChangeTime: _timestamp_pb2.Timestamp
        recentUserArrivals: _containers.RepeatedCompositeFieldContainer[StructureModeTrait.UserInfo]
        recentUserDepartures: _containers.RepeatedCompositeFieldContainer[StructureModeTrait.UserInfo]
        def __init__(self, activeProbability: _Optional[float] = ..., sleepProbability: _Optional[float] = ..., vacantProbability: _Optional[float] = ..., identifiedPresenceProbability: _Optional[float] = ..., lastMotionEventTimestamp: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., unknownProbability: _Optional[float] = ..., evaluationTimestamp: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., transitionEvaluationTimestamp: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., identifiedPresenceChangeUserId: _Optional[_Union[StructureModeTrait.UserInfo, _Mapping]] = ..., identifiedPresenceChangeTime: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., recentUserArrivals: _Optional[_Iterable[_Union[StructureModeTrait.UserInfo, _Mapping]]] = ..., recentUserDepartures: _Optional[_Iterable[_Union[StructureModeTrait.UserInfo, _Mapping]]] = ...) -> None: ...
    class ConsumeOccupancyStateBeliefResponse(_message.Message):
        __slots__ = ("responseType",)
        RESPONSETYPE_FIELD_NUMBER: _ClassVar[int]
        responseType: StructureModeTrait.StructureModeChangeResponseType
        def __init__(self, responseType: _Optional[_Union[StructureModeTrait.StructureModeChangeResponseType, str]] = ...) -> None: ...
    class ConsumeSecurityArmStateChangeRequest(_message.Message):
        __slots__ = ()
        def __init__(self) -> None: ...
    class ConsumeBoltActuatorStateChangeRequest(_message.Message):
        __slots__ = ()
        def __init__(self) -> None: ...
    class ConsumeLegacyStructureModeChangeRequest(_message.Message):
        __slots__ = ("away", "awaySetter", "manualAwayTimestamp", "touchedBy", "touchedId")
        AWAY_FIELD_NUMBER: _ClassVar[int]
        AWAYSETTER_FIELD_NUMBER: _ClassVar[int]
        MANUALAWAYTIMESTAMP_FIELD_NUMBER: _ClassVar[int]
        TOUCHEDBY_FIELD_NUMBER: _ClassVar[int]
        TOUCHEDID_FIELD_NUMBER: _ClassVar[int]
        away: StructureModeTrait.LegacyAwayState
        awaySetter: StructureModeTrait.LegacyAwaySetter
        manualAwayTimestamp: _timestamp_pb2.Timestamp
        touchedBy: StructureModeTrait.LegacyTouchedBy
        touchedId: _common_pb2.ResourceId
        def __init__(self, away: _Optional[_Union[StructureModeTrait.LegacyAwayState, str]] = ..., awaySetter: _Optional[_Union[StructureModeTrait.LegacyAwaySetter, str]] = ..., manualAwayTimestamp: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., touchedBy: _Optional[_Union[StructureModeTrait.LegacyTouchedBy, str]] = ..., touchedId: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ...) -> None: ...
    class StructureModeChangeEvent(_message.Message):
        __slots__ = ("structureMode", "priorStructureMode", "reason", "userId", "deviceId", "rtsDeviceId", "controlEventTypeUrl", "wwnId", "blames", "actorMethod", "primaryBlame")
        class BlamesEntry(_message.Message):
            __slots__ = ("key", "value")
            KEY_FIELD_NUMBER: _ClassVar[int]
            VALUE_FIELD_NUMBER: _ClassVar[int]
            key: int
            value: StructureModeTrait.StructureModeBlame
            def __init__(self, key: _Optional[int] = ..., value: _Optional[_Union[StructureModeTrait.StructureModeBlame, _Mapping]] = ...) -> None: ...
        STRUCTUREMODE_FIELD_NUMBER: _ClassVar[int]
        PRIORSTRUCTUREMODE_FIELD_NUMBER: _ClassVar[int]
        REASON_FIELD_NUMBER: _ClassVar[int]
        USERID_FIELD_NUMBER: _ClassVar[int]
        DEVICEID_FIELD_NUMBER: _ClassVar[int]
        RTSDEVICEID_FIELD_NUMBER: _ClassVar[int]
        CONTROLEVENTTYPEURL_FIELD_NUMBER: _ClassVar[int]
        WWNID_FIELD_NUMBER: _ClassVar[int]
        BLAMES_FIELD_NUMBER: _ClassVar[int]
        ACTORMETHOD_FIELD_NUMBER: _ClassVar[int]
        PRIMARYBLAME_FIELD_NUMBER: _ClassVar[int]
        structureMode: StructureModeTrait.StructureMode
        priorStructureMode: StructureModeTrait.StructureMode
        reason: StructureModeTrait.StructureModeReason
        userId: _common_pb2.ResourceId
        deviceId: _common_pb2.ResourceId
        rtsDeviceId: _wrappers_pb2.StringValue
        controlEventTypeUrl: _wrappers_pb2.StringValue
        wwnId: _wrappers_pb2.StringValue
        blames: _containers.MessageMap[int, StructureModeTrait.StructureModeBlame]
        actorMethod: StructureModeTrait.StructureModeActorMethod
        primaryBlame: StructureModeTrait.StructureModeBlame
        def __init__(self, structureMode: _Optional[_Union[StructureModeTrait.StructureMode, str]] = ..., priorStructureMode: _Optional[_Union[StructureModeTrait.StructureMode, str]] = ..., reason: _Optional[_Union[StructureModeTrait.StructureModeReason, str]] = ..., userId: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ..., deviceId: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ..., rtsDeviceId: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., controlEventTypeUrl: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., wwnId: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., blames: _Optional[_Mapping[int, StructureModeTrait.StructureModeBlame]] = ..., actorMethod: _Optional[_Union[StructureModeTrait.StructureModeActorMethod, str]] = ..., primaryBlame: _Optional[_Union[StructureModeTrait.StructureModeBlame, _Mapping]] = ...) -> None: ...
    class OccupancyChangeEvent(_message.Message):
        __slots__ = ("occupancy", "priorOccupancy")
        OCCUPANCY_FIELD_NUMBER: _ClassVar[int]
        PRIOROCCUPANCY_FIELD_NUMBER: _ClassVar[int]
        occupancy: StructureModeTrait.Occupancy
        priorOccupancy: StructureModeTrait.Occupancy
        def __init__(self, occupancy: _Optional[_Union[StructureModeTrait.Occupancy, _Mapping]] = ..., priorOccupancy: _Optional[_Union[StructureModeTrait.Occupancy, _Mapping]] = ...) -> None: ...
    class AllowanceChangeEvent(_message.Message):
        __slots__ = ("allowance", "priorAllowance")
        ALLOWANCE_FIELD_NUMBER: _ClassVar[int]
        PRIORALLOWANCE_FIELD_NUMBER: _ClassVar[int]
        allowance: StructureModeTrait.Allowance
        priorAllowance: StructureModeTrait.Allowance
        def __init__(self, allowance: _Optional[_Union[StructureModeTrait.Allowance, _Mapping]] = ..., priorAllowance: _Optional[_Union[StructureModeTrait.Allowance, _Mapping]] = ...) -> None: ...
    class AutoAsk(_message.Message):
        __slots__ = ("autoAskArm", "autoAskLock", "autoAskStructureMode")
        AUTOASKARM_FIELD_NUMBER: _ClassVar[int]
        AUTOASKLOCK_FIELD_NUMBER: _ClassVar[int]
        AUTOASKSTRUCTUREMODE_FIELD_NUMBER: _ClassVar[int]
        autoAskArm: StructureModeTrait.AutoAskArm
        autoAskLock: StructureModeTrait.AutoAskLock
        autoAskStructureMode: StructureModeTrait.AutoAskStructureMode
        def __init__(self, autoAskArm: _Optional[_Union[StructureModeTrait.AutoAskArm, str]] = ..., autoAskLock: _Optional[_Union[StructureModeTrait.AutoAskLock, str]] = ..., autoAskStructureMode: _Optional[_Union[StructureModeTrait.AutoAskStructureMode, str]] = ...) -> None: ...
    class AutoAskEvent(_message.Message):
        __slots__ = ("askType", "userId", "deviceId", "dryRun", "autoAsk")
        ASKTYPE_FIELD_NUMBER: _ClassVar[int]
        USERID_FIELD_NUMBER: _ClassVar[int]
        DEVICEID_FIELD_NUMBER: _ClassVar[int]
        DRYRUN_FIELD_NUMBER: _ClassVar[int]
        AUTOASK_FIELD_NUMBER: _ClassVar[int]
        askType: StructureModeTrait.AutoAskType
        userId: _containers.RepeatedCompositeFieldContainer[_common_pb2.ResourceId]
        deviceId: _common_pb2.ResourceId
        dryRun: bool
        autoAsk: StructureModeTrait.AutoAsk
        def __init__(self, askType: _Optional[_Union[StructureModeTrait.AutoAskType, str]] = ..., userId: _Optional[_Iterable[_Union[_common_pb2.ResourceId, _Mapping]]] = ..., deviceId: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ..., dryRun: bool = ..., autoAsk: _Optional[_Union[StructureModeTrait.AutoAsk, _Mapping]] = ...) -> None: ...
    class ActivityAgnosticStructureModeChangeEvent(_message.Message):
        __slots__ = ("activityAgnosticStructureMode", "priorActivityAgnosticStructureMode", "reason")
        ACTIVITYAGNOSTICSTRUCTUREMODE_FIELD_NUMBER: _ClassVar[int]
        PRIORACTIVITYAGNOSTICSTRUCTUREMODE_FIELD_NUMBER: _ClassVar[int]
        REASON_FIELD_NUMBER: _ClassVar[int]
        activityAgnosticStructureMode: StructureModeTrait.StructureMode
        priorActivityAgnosticStructureMode: StructureModeTrait.StructureMode
        reason: StructureModeTrait.StructureModeReason
        def __init__(self, activityAgnosticStructureMode: _Optional[_Union[StructureModeTrait.StructureMode, str]] = ..., priorActivityAgnosticStructureMode: _Optional[_Union[StructureModeTrait.StructureMode, str]] = ..., reason: _Optional[_Union[StructureModeTrait.StructureModeReason, str]] = ...) -> None: ...
    class StructureModeTraceEventState(_message.Message):
        __slots__ = ("structureMode", "occupancy", "allowance", "structureModeReason", "structureModeSetter", "structureModeEffectiveTime", "activityAgnosticStructureMode", "activityAgnosticStructureModeEffectiveTime")
        STRUCTUREMODE_FIELD_NUMBER: _ClassVar[int]
        OCCUPANCY_FIELD_NUMBER: _ClassVar[int]
        ALLOWANCE_FIELD_NUMBER: _ClassVar[int]
        STRUCTUREMODEREASON_FIELD_NUMBER: _ClassVar[int]
        STRUCTUREMODESETTER_FIELD_NUMBER: _ClassVar[int]
        STRUCTUREMODEEFFECTIVETIME_FIELD_NUMBER: _ClassVar[int]
        ACTIVITYAGNOSTICSTRUCTUREMODE_FIELD_NUMBER: _ClassVar[int]
        ACTIVITYAGNOSTICSTRUCTUREMODEEFFECTIVETIME_FIELD_NUMBER: _ClassVar[int]
        structureMode: StructureModeTrait.StructureMode
        occupancy: StructureModeTrait.Occupancy
        allowance: StructureModeTrait.Allowance
        structureModeReason: StructureModeTrait.StructureModeReason
        structureModeSetter: _common_pb2.ResourceId
        structureModeEffectiveTime: _timestamp_pb2.Timestamp
        activityAgnosticStructureMode: StructureModeTrait.StructureMode
        activityAgnosticStructureModeEffectiveTime: _timestamp_pb2.Timestamp
        def __init__(self, structureMode: _Optional[_Union[StructureModeTrait.StructureMode, str]] = ..., occupancy: _Optional[_Union[StructureModeTrait.Occupancy, _Mapping]] = ..., allowance: _Optional[_Union[StructureModeTrait.Allowance, _Mapping]] = ..., structureModeReason: _Optional[_Union[StructureModeTrait.StructureModeReason, str]] = ..., structureModeSetter: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ..., structureModeEffectiveTime: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., activityAgnosticStructureMode: _Optional[_Union[StructureModeTrait.StructureMode, str]] = ..., activityAgnosticStructureModeEffectiveTime: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...
    class StructureModeTraceEventStateChange(_message.Message):
        __slots__ = ("to",)
        FROM_FIELD_NUMBER: _ClassVar[int]
        TO_FIELD_NUMBER: _ClassVar[int]
        to: StructureModeTrait.StructureModeTraceEventState
        def __init__(self, to: _Optional[_Union[StructureModeTrait.StructureModeTraceEventState, _Mapping]] = ..., **kwargs) -> None: ...
    class StructureModeTraceEventStep(_message.Message):
        __slots__ = ("time", "labels")
        class LabelsEntry(_message.Message):
            __slots__ = ("key", "value")
            KEY_FIELD_NUMBER: _ClassVar[int]
            VALUE_FIELD_NUMBER: _ClassVar[int]
            key: str
            value: str
            def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...
        TIME_FIELD_NUMBER: _ClassVar[int]
        LABELS_FIELD_NUMBER: _ClassVar[int]
        time: _timestamp_pb2.Timestamp
        labels: _containers.ScalarMap[str, str]
        def __init__(self, time: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., labels: _Optional[_Mapping[str, str]] = ...) -> None: ...
    class StructureModeTraceEvent(_message.Message):
        __slots__ = ("trigger", "triggerAgent", "triggerEventKey", "triggerTime", "startTime", "stateChange", "steps", "scenarioId", "error", "rtsStructureId")
        TRIGGER_FIELD_NUMBER: _ClassVar[int]
        TRIGGERAGENT_FIELD_NUMBER: _ClassVar[int]
        TRIGGEREVENTKEY_FIELD_NUMBER: _ClassVar[int]
        TRIGGERTIME_FIELD_NUMBER: _ClassVar[int]
        STARTTIME_FIELD_NUMBER: _ClassVar[int]
        STATECHANGE_FIELD_NUMBER: _ClassVar[int]
        STEPS_FIELD_NUMBER: _ClassVar[int]
        SCENARIOID_FIELD_NUMBER: _ClassVar[int]
        ERROR_FIELD_NUMBER: _ClassVar[int]
        RTSSTRUCTUREID_FIELD_NUMBER: _ClassVar[int]
        trigger: str
        triggerAgent: str
        triggerEventKey: str
        triggerTime: _timestamp_pb2.Timestamp
        startTime: _timestamp_pb2.Timestamp
        stateChange: StructureModeTrait.StructureModeTraceEventStateChange
        steps: _containers.RepeatedCompositeFieldContainer[StructureModeTrait.StructureModeTraceEventStep]
        scenarioId: _containers.RepeatedScalarFieldContainer[str]
        error: str
        rtsStructureId: str
        def __init__(self, trigger: _Optional[str] = ..., triggerAgent: _Optional[str] = ..., triggerEventKey: _Optional[str] = ..., triggerTime: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., startTime: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., stateChange: _Optional[_Union[StructureModeTrait.StructureModeTraceEventStateChange, _Mapping]] = ..., steps: _Optional[_Iterable[_Union[StructureModeTrait.StructureModeTraceEventStep, _Mapping]]] = ..., scenarioId: _Optional[_Iterable[str]] = ..., error: _Optional[str] = ..., rtsStructureId: _Optional[str] = ...) -> None: ...
    STRUCTUREMODE_FIELD_NUMBER: _ClassVar[int]
    OCCUPANCY_FIELD_NUMBER: _ClassVar[int]
    ALLOWANCE_FIELD_NUMBER: _ClassVar[int]
    STRUCTUREMODEREASON_FIELD_NUMBER: _ClassVar[int]
    STRUCTUREMODESETTER_FIELD_NUMBER: _ClassVar[int]
    STRUCTUREMODEEFFECTIVETIME_FIELD_NUMBER: _ClassVar[int]
    ACTIVITYAGNOSTICSTRUCTUREMODE_FIELD_NUMBER: _ClassVar[int]
    ACTIVITYAGNOSTICSTRUCTUREMODEEFFECTIVETIME_FIELD_NUMBER: _ClassVar[int]
    PRIVATESTATE_FIELD_NUMBER: _ClassVar[int]
    BLAMES_FIELD_NUMBER: _ClassVar[int]
    ACTORMETHOD_FIELD_NUMBER: _ClassVar[int]
    PRIMARYBLAME_FIELD_NUMBER: _ClassVar[int]
    structureMode: StructureModeTrait.StructureMode
    occupancy: StructureModeTrait.Occupancy
    allowance: StructureModeTrait.Allowance
    structureModeReason: StructureModeTrait.StructureModeReason
    structureModeSetter: _common_pb2.ResourceId
    structureModeEffectiveTime: _timestamp_pb2.Timestamp
    activityAgnosticStructureMode: StructureModeTrait.StructureMode
    activityAgnosticStructureModeEffectiveTime: _timestamp_pb2.Timestamp
    privateState: StructureModeTrait.PrivateTraitHandlerState
    blames: _containers.MessageMap[int, StructureModeTrait.StructureModeBlame]
    actorMethod: StructureModeTrait.StructureModeActorMethod
    primaryBlame: StructureModeTrait.StructureModeBlame
    def __init__(self, structureMode: _Optional[_Union[StructureModeTrait.StructureMode, str]] = ..., occupancy: _Optional[_Union[StructureModeTrait.Occupancy, _Mapping]] = ..., allowance: _Optional[_Union[StructureModeTrait.Allowance, _Mapping]] = ..., structureModeReason: _Optional[_Union[StructureModeTrait.StructureModeReason, str]] = ..., structureModeSetter: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ..., structureModeEffectiveTime: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., activityAgnosticStructureMode: _Optional[_Union[StructureModeTrait.StructureMode, str]] = ..., activityAgnosticStructureModeEffectiveTime: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., privateState: _Optional[_Union[StructureModeTrait.PrivateTraitHandlerState, _Mapping]] = ..., blames: _Optional[_Mapping[int, StructureModeTrait.StructureModeBlame]] = ..., actorMethod: _Optional[_Union[StructureModeTrait.StructureModeActorMethod, str]] = ..., primaryBlame: _Optional[_Union[StructureModeTrait.StructureModeBlame, _Mapping]] = ...) -> None: ...

class StructureGeofencingTrait(_message.Message):
    __slots__ = ("geofenceEnhancedAutoawayStatus", "geofenceEnrolledUsers")
    class GeofenceEnhancedAutoAwayStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        GEOFENCE_ENHANCED_AUTO_AWAY_STATUS_UNSPECIFIED: _ClassVar[StructureGeofencingTrait.GeofenceEnhancedAutoAwayStatus]
        GEOFENCE_ENHANCED_AUTO_AWAY_STATUS_NOT_SET: _ClassVar[StructureGeofencingTrait.GeofenceEnhancedAutoAwayStatus]
        GEOFENCE_ENHANCED_AUTO_AWAY_STATUS_ENABLED: _ClassVar[StructureGeofencingTrait.GeofenceEnhancedAutoAwayStatus]
        GEOFENCE_ENHANCED_AUTO_AWAY_STATUS_DISABLED: _ClassVar[StructureGeofencingTrait.GeofenceEnhancedAutoAwayStatus]
    GEOFENCE_ENHANCED_AUTO_AWAY_STATUS_UNSPECIFIED: StructureGeofencingTrait.GeofenceEnhancedAutoAwayStatus
    GEOFENCE_ENHANCED_AUTO_AWAY_STATUS_NOT_SET: StructureGeofencingTrait.GeofenceEnhancedAutoAwayStatus
    GEOFENCE_ENHANCED_AUTO_AWAY_STATUS_ENABLED: StructureGeofencingTrait.GeofenceEnhancedAutoAwayStatus
    GEOFENCE_ENHANCED_AUTO_AWAY_STATUS_DISABLED: StructureGeofencingTrait.GeofenceEnhancedAutoAwayStatus
    class GeofenceSourceType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        GEOFENCE_SOURCE_TYPE_UNSPECIFIED: _ClassVar[StructureGeofencingTrait.GeofenceSourceType]
        GEOFENCE_SOURCE_TYPE_LEGACY_NEST_APP: _ClassVar[StructureGeofencingTrait.GeofenceSourceType]
        GEOFENCE_SOURCE_TYPE_GOOGLE_HOME_APP: _ClassVar[StructureGeofencingTrait.GeofenceSourceType]
    GEOFENCE_SOURCE_TYPE_UNSPECIFIED: StructureGeofencingTrait.GeofenceSourceType
    GEOFENCE_SOURCE_TYPE_LEGACY_NEST_APP: StructureGeofencingTrait.GeofenceSourceType
    GEOFENCE_SOURCE_TYPE_GOOGLE_HOME_APP: StructureGeofencingTrait.GeofenceSourceType
    class UserGeofenceEnrollmentCause(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        USER_GEOFENCE_ENROLLMENT_CAUSE_UNSPECIFIED: _ClassVar[StructureGeofencingTrait.UserGeofenceEnrollmentCause]
        USER_GEOFENCE_ENROLLMENT_CAUSE_USER_OPTED_IN: _ClassVar[StructureGeofencingTrait.UserGeofenceEnrollmentCause]
        USER_GEOFENCE_ENROLLMENT_CAUSE_USER_ADDED_TO_STRUCTURE: _ClassVar[StructureGeofencingTrait.UserGeofenceEnrollmentCause]
    USER_GEOFENCE_ENROLLMENT_CAUSE_UNSPECIFIED: StructureGeofencingTrait.UserGeofenceEnrollmentCause
    USER_GEOFENCE_ENROLLMENT_CAUSE_USER_OPTED_IN: StructureGeofencingTrait.UserGeofenceEnrollmentCause
    USER_GEOFENCE_ENROLLMENT_CAUSE_USER_ADDED_TO_STRUCTURE: StructureGeofencingTrait.UserGeofenceEnrollmentCause
    class UserGeofenceDisenrollmentCause(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        USER_GEOFENCE_DISENROLLMENT_CAUSE_UNSPECIFIED: _ClassVar[StructureGeofencingTrait.UserGeofenceDisenrollmentCause]
        USER_GEOFENCE_DISENROLLMENT_CAUSE_USER_OPTED_OUT: _ClassVar[StructureGeofencingTrait.UserGeofenceDisenrollmentCause]
        USER_GEOFENCE_DISENROLLMENT_CAUSE_USER_REMOVED_FROM_STRUCTURE: _ClassVar[StructureGeofencingTrait.UserGeofenceDisenrollmentCause]
    USER_GEOFENCE_DISENROLLMENT_CAUSE_UNSPECIFIED: StructureGeofencingTrait.UserGeofenceDisenrollmentCause
    USER_GEOFENCE_DISENROLLMENT_CAUSE_USER_OPTED_OUT: StructureGeofencingTrait.UserGeofenceDisenrollmentCause
    USER_GEOFENCE_DISENROLLMENT_CAUSE_USER_REMOVED_FROM_STRUCTURE: StructureGeofencingTrait.UserGeofenceDisenrollmentCause
    class GeofenceEnrolledUsersEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: int
        value: StructureGeofencingTrait.GeofenceEnrolledUser
        def __init__(self, key: _Optional[int] = ..., value: _Optional[_Union[StructureGeofencingTrait.GeofenceEnrolledUser, _Mapping]] = ...) -> None: ...
    class GeofenceEnrolledUser(_message.Message):
        __slots__ = ("userId", "geofenceSourceType", "mobileDeviceId")
        USERID_FIELD_NUMBER: _ClassVar[int]
        GEOFENCESOURCETYPE_FIELD_NUMBER: _ClassVar[int]
        MOBILEDEVICEID_FIELD_NUMBER: _ClassVar[int]
        userId: _common_pb2.ResourceId
        geofenceSourceType: StructureGeofencingTrait.GeofenceSourceType
        mobileDeviceId: str
        def __init__(self, userId: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ..., geofenceSourceType: _Optional[_Union[StructureGeofencingTrait.GeofenceSourceType, str]] = ..., mobileDeviceId: _Optional[str] = ...) -> None: ...
    class StructureGeofenceStateAssertionEvent(_message.Message):
        __slots__ = ("state", "userId", "rtsFenceId", "rtsMobileDeviceId")
        STATE_FIELD_NUMBER: _ClassVar[int]
        USERID_FIELD_NUMBER: _ClassVar[int]
        RTSFENCEID_FIELD_NUMBER: _ClassVar[int]
        RTSMOBILEDEVICEID_FIELD_NUMBER: _ClassVar[int]
        state: Geofencing.GeofenceState
        userId: _common_pb2.ResourceId
        rtsFenceId: _wrappers_pb2.StringValue
        rtsMobileDeviceId: _wrappers_pb2.StringValue
        def __init__(self, state: _Optional[_Union[Geofencing.GeofenceState, str]] = ..., userId: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ..., rtsFenceId: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ..., rtsMobileDeviceId: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ...) -> None: ...
    class UserGeofenceEnrollmentEvent(_message.Message):
        __slots__ = ("geofenceSourceType", "userId", "mobileDeviceId", "enrollmentCause")
        GEOFENCESOURCETYPE_FIELD_NUMBER: _ClassVar[int]
        USERID_FIELD_NUMBER: _ClassVar[int]
        MOBILEDEVICEID_FIELD_NUMBER: _ClassVar[int]
        ENROLLMENTCAUSE_FIELD_NUMBER: _ClassVar[int]
        geofenceSourceType: StructureGeofencingTrait.GeofenceSourceType
        userId: _common_pb2.ResourceId
        mobileDeviceId: str
        enrollmentCause: StructureGeofencingTrait.UserGeofenceEnrollmentCause
        def __init__(self, geofenceSourceType: _Optional[_Union[StructureGeofencingTrait.GeofenceSourceType, str]] = ..., userId: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ..., mobileDeviceId: _Optional[str] = ..., enrollmentCause: _Optional[_Union[StructureGeofencingTrait.UserGeofenceEnrollmentCause, str]] = ...) -> None: ...
    class UserGeofenceDisenrollmentEvent(_message.Message):
        __slots__ = ("geofenceSourceType", "userId", "mobileDeviceId", "disenrollmentCause")
        GEOFENCESOURCETYPE_FIELD_NUMBER: _ClassVar[int]
        USERID_FIELD_NUMBER: _ClassVar[int]
        MOBILEDEVICEID_FIELD_NUMBER: _ClassVar[int]
        DISENROLLMENTCAUSE_FIELD_NUMBER: _ClassVar[int]
        geofenceSourceType: StructureGeofencingTrait.GeofenceSourceType
        userId: _common_pb2.ResourceId
        mobileDeviceId: str
        disenrollmentCause: StructureGeofencingTrait.UserGeofenceDisenrollmentCause
        def __init__(self, geofenceSourceType: _Optional[_Union[StructureGeofencingTrait.GeofenceSourceType, str]] = ..., userId: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ..., mobileDeviceId: _Optional[str] = ..., disenrollmentCause: _Optional[_Union[StructureGeofencingTrait.UserGeofenceDisenrollmentCause, str]] = ...) -> None: ...
    class UserGeofenceDeviceChangeEvent(_message.Message):
        __slots__ = ("geofenceSourceType", "userId", "previousMobileDeviceId", "currentMobileDeviceId")
        GEOFENCESOURCETYPE_FIELD_NUMBER: _ClassVar[int]
        USERID_FIELD_NUMBER: _ClassVar[int]
        PREVIOUSMOBILEDEVICEID_FIELD_NUMBER: _ClassVar[int]
        CURRENTMOBILEDEVICEID_FIELD_NUMBER: _ClassVar[int]
        geofenceSourceType: StructureGeofencingTrait.GeofenceSourceType
        userId: _common_pb2.ResourceId
        previousMobileDeviceId: str
        currentMobileDeviceId: str
        def __init__(self, geofenceSourceType: _Optional[_Union[StructureGeofencingTrait.GeofenceSourceType, str]] = ..., userId: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ..., previousMobileDeviceId: _Optional[str] = ..., currentMobileDeviceId: _Optional[str] = ...) -> None: ...
    class StructureGeofenceEnrollmentEvent(_message.Message):
        __slots__ = ()
        def __init__(self) -> None: ...
    class StructureGeofenceDisenrollmentEvent(_message.Message):
        __slots__ = ()
        def __init__(self) -> None: ...
    class NestAppGeofenceHealthCheckEvent(_message.Message):
        __slots__ = ("rtsStructureId", "rtsUserId")
        RTSSTRUCTUREID_FIELD_NUMBER: _ClassVar[int]
        RTSUSERID_FIELD_NUMBER: _ClassVar[int]
        rtsStructureId: str
        rtsUserId: str
        def __init__(self, rtsStructureId: _Optional[str] = ..., rtsUserId: _Optional[str] = ...) -> None: ...
    GEOFENCEENHANCEDAUTOAWAYSTATUS_FIELD_NUMBER: _ClassVar[int]
    GEOFENCEENROLLEDUSERS_FIELD_NUMBER: _ClassVar[int]
    geofenceEnhancedAutoawayStatus: StructureGeofencingTrait.GeofenceEnhancedAutoAwayStatus
    geofenceEnrolledUsers: _containers.MessageMap[int, StructureGeofencingTrait.GeofenceEnrolledUser]
    def __init__(self, geofenceEnhancedAutoawayStatus: _Optional[_Union[StructureGeofencingTrait.GeofenceEnhancedAutoAwayStatus, str]] = ..., geofenceEnrolledUsers: _Optional[_Mapping[int, StructureGeofencingTrait.GeofenceEnrolledUser]] = ...) -> None: ...

class StructureModeSettingsTrait(_message.Message):
    __slots__ = ("enableAutoSleep", "sleepSchedule", "derivedDailySleepSchedule", "occupancySensorArmTimestamp")
    class BuildUniformDailySleepScheduleResponseType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        BUILD_UNIFORM_DAILY_SLEEP_SCHEDULE_RESPONSE_TYPE_UNSPECIFIED: _ClassVar[StructureModeSettingsTrait.BuildUniformDailySleepScheduleResponseType]
        BUILD_UNIFORM_DAILY_SLEEP_SCHEDULE_RESPONSE_TYPE_SUCCESS: _ClassVar[StructureModeSettingsTrait.BuildUniformDailySleepScheduleResponseType]
        BUILD_UNIFORM_DAILY_SLEEP_SCHEDULE_RESPONSE_TYPE_FAIL_ALREADY: _ClassVar[StructureModeSettingsTrait.BuildUniformDailySleepScheduleResponseType]
    BUILD_UNIFORM_DAILY_SLEEP_SCHEDULE_RESPONSE_TYPE_UNSPECIFIED: StructureModeSettingsTrait.BuildUniformDailySleepScheduleResponseType
    BUILD_UNIFORM_DAILY_SLEEP_SCHEDULE_RESPONSE_TYPE_SUCCESS: StructureModeSettingsTrait.BuildUniformDailySleepScheduleResponseType
    BUILD_UNIFORM_DAILY_SLEEP_SCHEDULE_RESPONSE_TYPE_FAIL_ALREADY: StructureModeSettingsTrait.BuildUniformDailySleepScheduleResponseType
    class TimeSpan(_message.Message):
        __slots__ = ("startTime", "endTime")
        STARTTIME_FIELD_NUMBER: _ClassVar[int]
        ENDTIME_FIELD_NUMBER: _ClassVar[int]
        startTime: _common_pb2.TimeOfDay
        endTime: _common_pb2.TimeOfDay
        def __init__(self, startTime: _Optional[_Union[_common_pb2.TimeOfDay, _Mapping]] = ..., endTime: _Optional[_Union[_common_pb2.TimeOfDay, _Mapping]] = ...) -> None: ...
    class DayTimeSpan(_message.Message):
        __slots__ = ("startDay", "startTime", "endDay", "endTime")
        STARTDAY_FIELD_NUMBER: _ClassVar[int]
        STARTTIME_FIELD_NUMBER: _ClassVar[int]
        ENDDAY_FIELD_NUMBER: _ClassVar[int]
        ENDTIME_FIELD_NUMBER: _ClassVar[int]
        startDay: _common_pb2.DayOfWeek
        startTime: _common_pb2.TimeOfDay
        endDay: _common_pb2.DayOfWeek
        endTime: _common_pb2.TimeOfDay
        def __init__(self, startDay: _Optional[_Union[_common_pb2.DayOfWeek, str]] = ..., startTime: _Optional[_Union[_common_pb2.TimeOfDay, _Mapping]] = ..., endDay: _Optional[_Union[_common_pb2.DayOfWeek, str]] = ..., endTime: _Optional[_Union[_common_pb2.TimeOfDay, _Mapping]] = ...) -> None: ...
    class BuildUniformDailySleepScheduleRequest(_message.Message):
        __slots__ = ("timeSpan", "userId")
        TIMESPAN_FIELD_NUMBER: _ClassVar[int]
        USERID_FIELD_NUMBER: _ClassVar[int]
        timeSpan: StructureModeSettingsTrait.TimeSpan
        userId: _common_pb2.ResourceId
        def __init__(self, timeSpan: _Optional[_Union[StructureModeSettingsTrait.TimeSpan, _Mapping]] = ..., userId: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ...) -> None: ...
    class BuildUniformDailySleepScheduleResponse(_message.Message):
        __slots__ = ("responseType",)
        RESPONSETYPE_FIELD_NUMBER: _ClassVar[int]
        responseType: StructureModeSettingsTrait.BuildUniformDailySleepScheduleResponseType
        def __init__(self, responseType: _Optional[_Union[StructureModeSettingsTrait.BuildUniformDailySleepScheduleResponseType, str]] = ...) -> None: ...
    class SleepScheduleChangeEvent(_message.Message):
        __slots__ = ("enableAutoSleep", "priorEnableAutoSleep", "sleepSchedule", "priorSleepSchedule", "userId")
        ENABLEAUTOSLEEP_FIELD_NUMBER: _ClassVar[int]
        PRIORENABLEAUTOSLEEP_FIELD_NUMBER: _ClassVar[int]
        SLEEPSCHEDULE_FIELD_NUMBER: _ClassVar[int]
        PRIORSLEEPSCHEDULE_FIELD_NUMBER: _ClassVar[int]
        USERID_FIELD_NUMBER: _ClassVar[int]
        enableAutoSleep: bool
        priorEnableAutoSleep: bool
        sleepSchedule: _containers.RepeatedCompositeFieldContainer[StructureModeSettingsTrait.DayTimeSpan]
        priorSleepSchedule: _containers.RepeatedCompositeFieldContainer[StructureModeSettingsTrait.DayTimeSpan]
        userId: _common_pb2.ResourceId
        def __init__(self, enableAutoSleep: bool = ..., priorEnableAutoSleep: bool = ..., sleepSchedule: _Optional[_Iterable[_Union[StructureModeSettingsTrait.DayTimeSpan, _Mapping]]] = ..., priorSleepSchedule: _Optional[_Iterable[_Union[StructureModeSettingsTrait.DayTimeSpan, _Mapping]]] = ..., userId: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ...) -> None: ...
    ENABLEAUTOSLEEP_FIELD_NUMBER: _ClassVar[int]
    SLEEPSCHEDULE_FIELD_NUMBER: _ClassVar[int]
    DERIVEDDAILYSLEEPSCHEDULE_FIELD_NUMBER: _ClassVar[int]
    OCCUPANCYSENSORARMTIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    enableAutoSleep: bool
    sleepSchedule: _containers.RepeatedCompositeFieldContainer[StructureModeSettingsTrait.DayTimeSpan]
    derivedDailySleepSchedule: StructureModeSettingsTrait.TimeSpan
    occupancySensorArmTimestamp: _timestamp_pb2.Timestamp
    def __init__(self, enableAutoSleep: bool = ..., sleepSchedule: _Optional[_Iterable[_Union[StructureModeSettingsTrait.DayTimeSpan, _Mapping]]] = ..., derivedDailySleepSchedule: _Optional[_Union[StructureModeSettingsTrait.TimeSpan, _Mapping]] = ..., occupancySensorArmTimestamp: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class Geofencing(_message.Message):
    __slots__ = ()
    class GeofenceState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        GEOFENCE_STATE_UNSPECIFIED: _ClassVar[Geofencing.GeofenceState]
        GEOFENCE_STATE_INSIDE: _ClassVar[Geofencing.GeofenceState]
        GEOFENCE_STATE_OUTSIDE: _ClassVar[Geofencing.GeofenceState]
        GEOFENCE_STATE_UNKNOWN: _ClassVar[Geofencing.GeofenceState]
    GEOFENCE_STATE_UNSPECIFIED: Geofencing.GeofenceState
    GEOFENCE_STATE_INSIDE: Geofencing.GeofenceState
    GEOFENCE_STATE_OUTSIDE: Geofencing.GeofenceState
    GEOFENCE_STATE_UNKNOWN: Geofencing.GeofenceState
    def __init__(self) -> None: ...

class OccupancyInputSettingsTrait(_message.Message):
    __slots__ = ("deviceActivityConsidered",)
    class OccupancyInputEnrollmentEvent(_message.Message):
        __slots__ = ("structureId",)
        STRUCTUREID_FIELD_NUMBER: _ClassVar[int]
        structureId: _common_pb2.ResourceId
        def __init__(self, structureId: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ...) -> None: ...
    class OccupancyInputDisenrollmentEvent(_message.Message):
        __slots__ = ("structureId",)
        STRUCTUREID_FIELD_NUMBER: _ClassVar[int]
        structureId: _common_pb2.ResourceId
        def __init__(self, structureId: _Optional[_Union[_common_pb2.ResourceId, _Mapping]] = ...) -> None: ...
    DEVICEACTIVITYCONSIDERED_FIELD_NUMBER: _ClassVar[int]
    deviceActivityConsidered: bool
    def __init__(self, deviceActivityConsidered: bool = ...) -> None: ...

class StructureModeCapabilitiesTrait(_message.Message):
    __slots__ = ("sleepStructureModeEnabled",)
    SLEEPSTRUCTUREMODEENABLED_FIELD_NUMBER: _ClassVar[int]
    sleepStructureModeEnabled: bool
    def __init__(self, sleepStructureModeEnabled: bool = ...) -> None: ...
