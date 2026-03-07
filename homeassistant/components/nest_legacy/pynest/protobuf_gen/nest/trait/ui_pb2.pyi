import datetime

from google.protobuf import duration_pb2 as _duration_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class SoyMessage(_message.Message):
    __slots__ = ()
    class SoyTemplateMessage(_message.Message):
        __slots__ = ("messageNamespace", "parameters")
        class ParametersEntry(_message.Message):
            __slots__ = ("key", "value")
            KEY_FIELD_NUMBER: _ClassVar[int]
            VALUE_FIELD_NUMBER: _ClassVar[int]
            key: int
            value: SoyMessage.SoyParameter
            def __init__(self, key: _Optional[int] = ..., value: _Optional[_Union[SoyMessage.SoyParameter, _Mapping]] = ...) -> None: ...
        MESSAGENAMESPACE_FIELD_NUMBER: _ClassVar[int]
        PARAMETERS_FIELD_NUMBER: _ClassVar[int]
        messageNamespace: str
        parameters: _containers.MessageMap[int, SoyMessage.SoyParameter]
        def __init__(self, messageNamespace: _Optional[str] = ..., parameters: _Optional[_Mapping[int, SoyMessage.SoyParameter]] = ...) -> None: ...
    class Any(_message.Message):
        __slots__ = ("typeUrl", "value")
        TYPEURL_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        typeUrl: str
        value: bytes
        def __init__(self, typeUrl: _Optional[str] = ..., value: _Optional[bytes] = ...) -> None: ...
    class SoyParameter(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: SoyMessage.SoyParameterValue
        def __init__(self, key: _Optional[str] = ..., value: _Optional[_Union[SoyMessage.SoyParameterValue, _Mapping]] = ...) -> None: ...
    class SoyParameterValue(_message.Message):
        __slots__ = ("singleValue", "boolValue", "intValue", "protoValue", "stringListValue")
        SINGLEVALUE_FIELD_NUMBER: _ClassVar[int]
        BOOLVALUE_FIELD_NUMBER: _ClassVar[int]
        INTVALUE_FIELD_NUMBER: _ClassVar[int]
        PROTOVALUE_FIELD_NUMBER: _ClassVar[int]
        STRINGLISTVALUE_FIELD_NUMBER: _ClassVar[int]
        singleValue: str
        boolValue: bool
        intValue: int
        protoValue: SoyMessage.Any
        stringListValue: SoyMessage.StringList
        def __init__(self, singleValue: _Optional[str] = ..., boolValue: bool = ..., intValue: _Optional[int] = ..., protoValue: _Optional[_Union[SoyMessage.Any, _Mapping]] = ..., stringListValue: _Optional[_Union[SoyMessage.StringList, _Mapping]] = ...) -> None: ...
    class StringList(_message.Message):
        __slots__ = ("values",)
        VALUES_FIELD_NUMBER: _ClassVar[int]
        values: _containers.RepeatedScalarFieldContainer[str]
        def __init__(self, values: _Optional[_Iterable[str]] = ...) -> None: ...
    class SoyTemplateImage(_message.Message):
        __slots__ = ("url", "accessibilityText", "width", "height")
        URL_FIELD_NUMBER: _ClassVar[int]
        ACCESSIBILITYTEXT_FIELD_NUMBER: _ClassVar[int]
        WIDTH_FIELD_NUMBER: _ClassVar[int]
        HEIGHT_FIELD_NUMBER: _ClassVar[int]
        url: str
        accessibilityText: SoyMessage.SoyTemplateMessage
        width: int
        height: int
        def __init__(self, url: _Optional[str] = ..., accessibilityText: _Optional[_Union[SoyMessage.SoyTemplateMessage, _Mapping]] = ..., width: _Optional[int] = ..., height: _Optional[int] = ...) -> None: ...
    class SoyTemplateInfo(_message.Message):
        __slots__ = ("msgIdString",)
        MSGIDSTRING_FIELD_NUMBER: _ClassVar[int]
        msgIdString: str
        def __init__(self, msgIdString: _Optional[str] = ...) -> None: ...
    def __init__(self) -> None: ...

class EnhancedPathlightSettingsTrait(_message.Message):
    __slots__ = ("triggers", "brightnessDiscrete")
    class PathlightBrightnessDiscrete(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        PATHLIGHT_BRIGHTNESS_DISCRETE_UNSPECIFIED: _ClassVar[EnhancedPathlightSettingsTrait.PathlightBrightnessDiscrete]
        PATHLIGHT_BRIGHTNESS_DISCRETE_LOW: _ClassVar[EnhancedPathlightSettingsTrait.PathlightBrightnessDiscrete]
        PATHLIGHT_BRIGHTNESS_DISCRETE_MEDIUM: _ClassVar[EnhancedPathlightSettingsTrait.PathlightBrightnessDiscrete]
        PATHLIGHT_BRIGHTNESS_DISCRETE_HIGH: _ClassVar[EnhancedPathlightSettingsTrait.PathlightBrightnessDiscrete]
    PATHLIGHT_BRIGHTNESS_DISCRETE_UNSPECIFIED: EnhancedPathlightSettingsTrait.PathlightBrightnessDiscrete
    PATHLIGHT_BRIGHTNESS_DISCRETE_LOW: EnhancedPathlightSettingsTrait.PathlightBrightnessDiscrete
    PATHLIGHT_BRIGHTNESS_DISCRETE_MEDIUM: EnhancedPathlightSettingsTrait.PathlightBrightnessDiscrete
    PATHLIGHT_BRIGHTNESS_DISCRETE_HIGH: EnhancedPathlightSettingsTrait.PathlightBrightnessDiscrete
    class PathlightCondition(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        PATHLIGHT_CONDITION_UNSPECIFIED: _ClassVar[EnhancedPathlightSettingsTrait.PathlightCondition]
        PATHLIGHT_CONDITION_LINE_POWER: _ClassVar[EnhancedPathlightSettingsTrait.PathlightCondition]
        PATHLIGHT_CONDITION_DARKNESS: _ClassVar[EnhancedPathlightSettingsTrait.PathlightCondition]
        PATHLIGHT_CONDITION_MOTION: _ClassVar[EnhancedPathlightSettingsTrait.PathlightCondition]
    PATHLIGHT_CONDITION_UNSPECIFIED: EnhancedPathlightSettingsTrait.PathlightCondition
    PATHLIGHT_CONDITION_LINE_POWER: EnhancedPathlightSettingsTrait.PathlightCondition
    PATHLIGHT_CONDITION_DARKNESS: EnhancedPathlightSettingsTrait.PathlightCondition
    PATHLIGHT_CONDITION_MOTION: EnhancedPathlightSettingsTrait.PathlightCondition
    class TriggersEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: int
        value: EnhancedPathlightSettingsTrait.PathlightTrigger
        def __init__(self, key: _Optional[int] = ..., value: _Optional[_Union[EnhancedPathlightSettingsTrait.PathlightTrigger, _Mapping]] = ...) -> None: ...
    class PathlightTrigger(_message.Message):
        __slots__ = ("timeout", "brightnessDiscrete", "activationConditions")
        TIMEOUT_FIELD_NUMBER: _ClassVar[int]
        BRIGHTNESSDISCRETE_FIELD_NUMBER: _ClassVar[int]
        ACTIVATIONCONDITIONS_FIELD_NUMBER: _ClassVar[int]
        timeout: _duration_pb2.Duration
        brightnessDiscrete: EnhancedPathlightSettingsTrait.PathlightBrightnessDiscrete
        activationConditions: _containers.RepeatedScalarFieldContainer[EnhancedPathlightSettingsTrait.PathlightCondition]
        def __init__(self, timeout: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ..., brightnessDiscrete: _Optional[_Union[EnhancedPathlightSettingsTrait.PathlightBrightnessDiscrete, str]] = ..., activationConditions: _Optional[_Iterable[_Union[EnhancedPathlightSettingsTrait.PathlightCondition, str]]] = ...) -> None: ...
    TRIGGERS_FIELD_NUMBER: _ClassVar[int]
    BRIGHTNESSDISCRETE_FIELD_NUMBER: _ClassVar[int]
    triggers: _containers.MessageMap[int, EnhancedPathlightSettingsTrait.PathlightTrigger]
    brightnessDiscrete: EnhancedPathlightSettingsTrait.PathlightBrightnessDiscrete
    def __init__(self, triggers: _Optional[_Mapping[int, EnhancedPathlightSettingsTrait.PathlightTrigger]] = ..., brightnessDiscrete: _Optional[_Union[EnhancedPathlightSettingsTrait.PathlightBrightnessDiscrete, str]] = ...) -> None: ...

class UserInteractionTrait(_message.Message):
    __slots__ = ()
    class UserInteractionDetectedEvent(_message.Message):
        __slots__ = ("unused",)
        UNUSED_FIELD_NUMBER: _ClassVar[int]
        unused: int
        def __init__(self, unused: _Optional[int] = ...) -> None: ...
    def __init__(self) -> None: ...

class EnhancedPathlightStateTrait(_message.Message):
    __slots__ = ()
    class ActivationState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        ACTIVATION_STATE_UNSPECIFIED: _ClassVar[EnhancedPathlightStateTrait.ActivationState]
        ACTIVATION_STATE_OFF: _ClassVar[EnhancedPathlightStateTrait.ActivationState]
        ACTIVATION_STATE_TIMED_OUT: _ClassVar[EnhancedPathlightStateTrait.ActivationState]
        ACTIVATION_STATE_ACTIVE: _ClassVar[EnhancedPathlightStateTrait.ActivationState]
    ACTIVATION_STATE_UNSPECIFIED: EnhancedPathlightStateTrait.ActivationState
    ACTIVATION_STATE_OFF: EnhancedPathlightStateTrait.ActivationState
    ACTIVATION_STATE_TIMED_OUT: EnhancedPathlightStateTrait.ActivationState
    ACTIVATION_STATE_ACTIVE: EnhancedPathlightStateTrait.ActivationState
    class PathlightStateChangeEvent(_message.Message):
        __slots__ = ("state", "conditions", "activatedConditions", "previousState", "activeDuration")
        STATE_FIELD_NUMBER: _ClassVar[int]
        CONDITIONS_FIELD_NUMBER: _ClassVar[int]
        ACTIVATEDCONDITIONS_FIELD_NUMBER: _ClassVar[int]
        PREVIOUSSTATE_FIELD_NUMBER: _ClassVar[int]
        ACTIVEDURATION_FIELD_NUMBER: _ClassVar[int]
        state: EnhancedPathlightStateTrait.ActivationState
        conditions: _containers.RepeatedScalarFieldContainer[EnhancedPathlightSettingsTrait.PathlightCondition]
        activatedConditions: _containers.RepeatedScalarFieldContainer[EnhancedPathlightSettingsTrait.PathlightCondition]
        previousState: EnhancedPathlightStateTrait.ActivationState
        activeDuration: _duration_pb2.Duration
        def __init__(self, state: _Optional[_Union[EnhancedPathlightStateTrait.ActivationState, str]] = ..., conditions: _Optional[_Iterable[_Union[EnhancedPathlightSettingsTrait.PathlightCondition, str]]] = ..., activatedConditions: _Optional[_Iterable[_Union[EnhancedPathlightSettingsTrait.PathlightCondition, str]]] = ..., previousState: _Optional[_Union[EnhancedPathlightStateTrait.ActivationState, str]] = ..., activeDuration: _Optional[_Union[datetime.timedelta, _duration_pb2.Duration, _Mapping]] = ...) -> None: ...
    def __init__(self) -> None: ...

class PathlightSettingsTrait(_message.Message):
    __slots__ = ("pathlightBrightness",)
    class PathlightBrightness(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        PATHLIGHT_BRIGHTNESS_UNSPECIFIED: _ClassVar[PathlightSettingsTrait.PathlightBrightness]
        PATHLIGHT_BRIGHTNESS_OFF: _ClassVar[PathlightSettingsTrait.PathlightBrightness]
        PATHLIGHT_BRIGHTNESS_LOW: _ClassVar[PathlightSettingsTrait.PathlightBrightness]
        PATHLIGHT_BRIGHTNESS_MEDIUM: _ClassVar[PathlightSettingsTrait.PathlightBrightness]
        PATHLIGHT_BRIGHTNESS_HIGH: _ClassVar[PathlightSettingsTrait.PathlightBrightness]
    PATHLIGHT_BRIGHTNESS_UNSPECIFIED: PathlightSettingsTrait.PathlightBrightness
    PATHLIGHT_BRIGHTNESS_OFF: PathlightSettingsTrait.PathlightBrightness
    PATHLIGHT_BRIGHTNESS_LOW: PathlightSettingsTrait.PathlightBrightness
    PATHLIGHT_BRIGHTNESS_MEDIUM: PathlightSettingsTrait.PathlightBrightness
    PATHLIGHT_BRIGHTNESS_HIGH: PathlightSettingsTrait.PathlightBrightness
    PATHLIGHTBRIGHTNESS_FIELD_NUMBER: _ClassVar[int]
    pathlightBrightness: PathlightSettingsTrait.PathlightBrightness
    def __init__(self, pathlightBrightness: _Optional[_Union[PathlightSettingsTrait.PathlightBrightness, str]] = ...) -> None: ...
