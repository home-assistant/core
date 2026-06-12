from google.protobuf import struct_pb2 as _struct_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Frame(_message.Message):
    __slots__ = ("id", "type", "request", "response")
    ID_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    REQUEST_FIELD_NUMBER: _ClassVar[int]
    RESPONSE_FIELD_NUMBER: _ClassVar[int]
    id: int
    type: str
    request: bytes
    response: Response
    def __init__(self, id: _Optional[int] = ..., type: _Optional[str] = ..., request: _Optional[bytes] = ..., response: _Optional[_Union[Response, _Mapping]] = ...) -> None: ...

class Response(_message.Message):
    __slots__ = ("ok", "result", "error")
    OK_FIELD_NUMBER: _ClassVar[int]
    RESULT_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    ok: bool
    result: bytes
    error: Error
    def __init__(self, ok: bool = ..., result: _Optional[bytes] = ..., error: _Optional[_Union[Error, _Mapping]] = ...) -> None: ...

class Error(_message.Message):
    __slots__ = ("message", "type", "invalid", "multiple")
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    INVALID_FIELD_NUMBER: _ClassVar[int]
    MULTIPLE_FIELD_NUMBER: _ClassVar[int]
    message: str
    type: str
    invalid: _containers.RepeatedCompositeFieldContainer[InvalidError]
    multiple: bool
    def __init__(self, message: _Optional[str] = ..., type: _Optional[str] = ..., invalid: _Optional[_Iterable[_Union[InvalidError, _Mapping]]] = ..., multiple: bool = ...) -> None: ...

class InvalidError(_message.Message):
    __slots__ = ("message", "path")
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    PATH_FIELD_NUMBER: _ClassVar[int]
    message: str
    path: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, message: _Optional[str] = ..., path: _Optional[_Iterable[str]] = ...) -> None: ...

class DevicePair(_message.Message):
    __slots__ = ("key", "value")
    KEY_FIELD_NUMBER: _ClassVar[int]
    VALUE_FIELD_NUMBER: _ClassVar[int]
    key: str
    value: str
    def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...

class DeviceInfo(_message.Message):
    __slots__ = ("identifiers", "connections", "via_device", "entry_type", "name", "manufacturer", "model", "model_id", "sw_version", "hw_version", "serial_number", "suggested_area", "configuration_url", "default_name", "default_manufacturer", "default_model", "translation_key")
    IDENTIFIERS_FIELD_NUMBER: _ClassVar[int]
    CONNECTIONS_FIELD_NUMBER: _ClassVar[int]
    VIA_DEVICE_FIELD_NUMBER: _ClassVar[int]
    ENTRY_TYPE_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    MANUFACTURER_FIELD_NUMBER: _ClassVar[int]
    MODEL_FIELD_NUMBER: _ClassVar[int]
    MODEL_ID_FIELD_NUMBER: _ClassVar[int]
    SW_VERSION_FIELD_NUMBER: _ClassVar[int]
    HW_VERSION_FIELD_NUMBER: _ClassVar[int]
    SERIAL_NUMBER_FIELD_NUMBER: _ClassVar[int]
    SUGGESTED_AREA_FIELD_NUMBER: _ClassVar[int]
    CONFIGURATION_URL_FIELD_NUMBER: _ClassVar[int]
    DEFAULT_NAME_FIELD_NUMBER: _ClassVar[int]
    DEFAULT_MANUFACTURER_FIELD_NUMBER: _ClassVar[int]
    DEFAULT_MODEL_FIELD_NUMBER: _ClassVar[int]
    TRANSLATION_KEY_FIELD_NUMBER: _ClassVar[int]
    identifiers: _containers.RepeatedCompositeFieldContainer[DevicePair]
    connections: _containers.RepeatedCompositeFieldContainer[DevicePair]
    via_device: DevicePair
    entry_type: str
    name: str
    manufacturer: str
    model: str
    model_id: str
    sw_version: str
    hw_version: str
    serial_number: str
    suggested_area: str
    configuration_url: str
    default_name: str
    default_manufacturer: str
    default_model: str
    translation_key: str
    def __init__(self, identifiers: _Optional[_Iterable[_Union[DevicePair, _Mapping]]] = ..., connections: _Optional[_Iterable[_Union[DevicePair, _Mapping]]] = ..., via_device: _Optional[_Union[DevicePair, _Mapping]] = ..., entry_type: _Optional[str] = ..., name: _Optional[str] = ..., manufacturer: _Optional[str] = ..., model: _Optional[str] = ..., model_id: _Optional[str] = ..., sw_version: _Optional[str] = ..., hw_version: _Optional[str] = ..., serial_number: _Optional[str] = ..., suggested_area: _Optional[str] = ..., configuration_url: _Optional[str] = ..., default_name: _Optional[str] = ..., default_manufacturer: _Optional[str] = ..., default_model: _Optional[str] = ..., translation_key: _Optional[str] = ...) -> None: ...

class IntegrationSource(_message.Message):
    __slots__ = ("kind", "url", "ref", "tag", "domain", "subdir")
    KIND_FIELD_NUMBER: _ClassVar[int]
    URL_FIELD_NUMBER: _ClassVar[int]
    REF_FIELD_NUMBER: _ClassVar[int]
    TAG_FIELD_NUMBER: _ClassVar[int]
    DOMAIN_FIELD_NUMBER: _ClassVar[int]
    SUBDIR_FIELD_NUMBER: _ClassVar[int]
    kind: str
    url: str
    ref: str
    tag: str
    domain: str
    subdir: str
    def __init__(self, kind: _Optional[str] = ..., url: _Optional[str] = ..., ref: _Optional[str] = ..., tag: _Optional[str] = ..., domain: _Optional[str] = ..., subdir: _Optional[str] = ...) -> None: ...

class EntrySetup(_message.Message):
    __slots__ = ("entry_id", "domain", "title", "data", "options", "source", "unique_id", "version", "minor_version", "integration_source")
    ENTRY_ID_FIELD_NUMBER: _ClassVar[int]
    DOMAIN_FIELD_NUMBER: _ClassVar[int]
    TITLE_FIELD_NUMBER: _ClassVar[int]
    DATA_FIELD_NUMBER: _ClassVar[int]
    OPTIONS_FIELD_NUMBER: _ClassVar[int]
    SOURCE_FIELD_NUMBER: _ClassVar[int]
    UNIQUE_ID_FIELD_NUMBER: _ClassVar[int]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    MINOR_VERSION_FIELD_NUMBER: _ClassVar[int]
    INTEGRATION_SOURCE_FIELD_NUMBER: _ClassVar[int]
    entry_id: str
    domain: str
    title: str
    data: _struct_pb2.Struct
    options: _struct_pb2.Struct
    source: str
    unique_id: str
    version: int
    minor_version: int
    integration_source: IntegrationSource
    def __init__(self, entry_id: _Optional[str] = ..., domain: _Optional[str] = ..., title: _Optional[str] = ..., data: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ..., options: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ..., source: _Optional[str] = ..., unique_id: _Optional[str] = ..., version: _Optional[int] = ..., minor_version: _Optional[int] = ..., integration_source: _Optional[_Union[IntegrationSource, _Mapping]] = ...) -> None: ...

class EntrySetupResult(_message.Message):
    __slots__ = ("ok", "reason")
    OK_FIELD_NUMBER: _ClassVar[int]
    REASON_FIELD_NUMBER: _ClassVar[int]
    ok: bool
    reason: str
    def __init__(self, ok: bool = ..., reason: _Optional[str] = ...) -> None: ...

class EntryUnload(_message.Message):
    __slots__ = ("entry_id",)
    ENTRY_ID_FIELD_NUMBER: _ClassVar[int]
    entry_id: str
    def __init__(self, entry_id: _Optional[str] = ...) -> None: ...

class EntryUnloadResult(_message.Message):
    __slots__ = ("ok",)
    OK_FIELD_NUMBER: _ClassVar[int]
    ok: bool
    def __init__(self, ok: bool = ...) -> None: ...

class CallService(_message.Message):
    __slots__ = ("domain", "service", "target", "service_data", "context_id", "return_response")
    DOMAIN_FIELD_NUMBER: _ClassVar[int]
    SERVICE_FIELD_NUMBER: _ClassVar[int]
    TARGET_FIELD_NUMBER: _ClassVar[int]
    SERVICE_DATA_FIELD_NUMBER: _ClassVar[int]
    CONTEXT_ID_FIELD_NUMBER: _ClassVar[int]
    RETURN_RESPONSE_FIELD_NUMBER: _ClassVar[int]
    domain: str
    service: str
    target: _struct_pb2.Struct
    service_data: _struct_pb2.Struct
    context_id: str
    return_response: bool
    def __init__(self, domain: _Optional[str] = ..., service: _Optional[str] = ..., target: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ..., service_data: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ..., context_id: _Optional[str] = ..., return_response: bool = ...) -> None: ...

class ServiceResponse(_message.Message):
    __slots__ = ("data",)
    DATA_FIELD_NUMBER: _ClassVar[int]
    data: _struct_pb2.Struct
    def __init__(self, data: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ...) -> None: ...

class CallServiceResult(_message.Message):
    __slots__ = ("response",)
    RESPONSE_FIELD_NUMBER: _ClassVar[int]
    response: ServiceResponse
    def __init__(self, response: _Optional[_Union[ServiceResponse, _Mapping]] = ...) -> None: ...

class EntityQuery(_message.Message):
    __slots__ = ("sandbox_entity_id", "method", "args", "context_id")
    SANDBOX_ENTITY_ID_FIELD_NUMBER: _ClassVar[int]
    METHOD_FIELD_NUMBER: _ClassVar[int]
    ARGS_FIELD_NUMBER: _ClassVar[int]
    CONTEXT_ID_FIELD_NUMBER: _ClassVar[int]
    sandbox_entity_id: str
    method: str
    args: _struct_pb2.Struct
    context_id: str
    def __init__(self, sandbox_entity_id: _Optional[str] = ..., method: _Optional[str] = ..., args: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ..., context_id: _Optional[str] = ...) -> None: ...

class EntityQueryResult(_message.Message):
    __slots__ = ("result",)
    RESULT_FIELD_NUMBER: _ClassVar[int]
    result: _struct_pb2.Struct
    def __init__(self, result: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ...) -> None: ...

class GetTranslations(_message.Message):
    __slots__ = ("language", "domains")
    LANGUAGE_FIELD_NUMBER: _ClassVar[int]
    DOMAINS_FIELD_NUMBER: _ClassVar[int]
    language: str
    domains: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, language: _Optional[str] = ..., domains: _Optional[_Iterable[str]] = ...) -> None: ...

class GetTranslationsResult(_message.Message):
    __slots__ = ("language", "strings")
    LANGUAGE_FIELD_NUMBER: _ClassVar[int]
    STRINGS_FIELD_NUMBER: _ClassVar[int]
    language: str
    strings: _struct_pb2.Struct
    def __init__(self, language: _Optional[str] = ..., strings: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ...) -> None: ...

class Shutdown(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ShutdownResult(_message.Message):
    __slots__ = ("ok", "unloaded", "restore_state")
    OK_FIELD_NUMBER: _ClassVar[int]
    UNLOADED_FIELD_NUMBER: _ClassVar[int]
    RESTORE_STATE_FIELD_NUMBER: _ClassVar[int]
    ok: bool
    unloaded: int
    restore_state: _struct_pb2.Struct
    def __init__(self, ok: bool = ..., unloaded: _Optional[int] = ..., restore_state: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ...) -> None: ...

class Ping(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class PingResult(_message.Message):
    __slots__ = ("pong",)
    PONG_FIELD_NUMBER: _ClassVar[int]
    pong: str
    def __init__(self, pong: _Optional[str] = ...) -> None: ...

class Ready(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class FlowInit(_message.Message):
    __slots__ = ("handler", "context", "data")
    HANDLER_FIELD_NUMBER: _ClassVar[int]
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    DATA_FIELD_NUMBER: _ClassVar[int]
    handler: str
    context: _struct_pb2.Struct
    data: _struct_pb2.Struct
    def __init__(self, handler: _Optional[str] = ..., context: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ..., data: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ...) -> None: ...

class FlowStep(_message.Message):
    __slots__ = ("flow_id", "user_input")
    FLOW_ID_FIELD_NUMBER: _ClassVar[int]
    USER_INPUT_FIELD_NUMBER: _ClassVar[int]
    flow_id: str
    user_input: _struct_pb2.Struct
    def __init__(self, flow_id: _Optional[str] = ..., user_input: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ...) -> None: ...

class FlowAbort(_message.Message):
    __slots__ = ("flow_id",)
    FLOW_ID_FIELD_NUMBER: _ClassVar[int]
    flow_id: str
    def __init__(self, flow_id: _Optional[str] = ...) -> None: ...

class FlowAbortResult(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class FlowResult(_message.Message):
    __slots__ = ("type", "flow_id", "handler", "step_id", "reason", "title", "description", "last_step", "preview", "version", "minor_version", "data", "options", "errors", "description_placeholders", "context", "data_schema", "has_data_schema", "menu_options", "sort")
    TYPE_FIELD_NUMBER: _ClassVar[int]
    FLOW_ID_FIELD_NUMBER: _ClassVar[int]
    HANDLER_FIELD_NUMBER: _ClassVar[int]
    STEP_ID_FIELD_NUMBER: _ClassVar[int]
    REASON_FIELD_NUMBER: _ClassVar[int]
    TITLE_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    LAST_STEP_FIELD_NUMBER: _ClassVar[int]
    PREVIEW_FIELD_NUMBER: _ClassVar[int]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    MINOR_VERSION_FIELD_NUMBER: _ClassVar[int]
    DATA_FIELD_NUMBER: _ClassVar[int]
    OPTIONS_FIELD_NUMBER: _ClassVar[int]
    ERRORS_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_PLACEHOLDERS_FIELD_NUMBER: _ClassVar[int]
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    DATA_SCHEMA_FIELD_NUMBER: _ClassVar[int]
    HAS_DATA_SCHEMA_FIELD_NUMBER: _ClassVar[int]
    MENU_OPTIONS_FIELD_NUMBER: _ClassVar[int]
    SORT_FIELD_NUMBER: _ClassVar[int]
    type: str
    flow_id: str
    handler: str
    step_id: str
    reason: str
    title: str
    description: str
    last_step: bool
    preview: str
    version: int
    minor_version: int
    data: _struct_pb2.Struct
    options: _struct_pb2.Struct
    errors: _struct_pb2.Struct
    description_placeholders: _struct_pb2.Struct
    context: _struct_pb2.Struct
    data_schema: _struct_pb2.ListValue
    has_data_schema: bool
    menu_options: _struct_pb2.ListValue
    sort: bool
    def __init__(self, type: _Optional[str] = ..., flow_id: _Optional[str] = ..., handler: _Optional[str] = ..., step_id: _Optional[str] = ..., reason: _Optional[str] = ..., title: _Optional[str] = ..., description: _Optional[str] = ..., last_step: bool = ..., preview: _Optional[str] = ..., version: _Optional[int] = ..., minor_version: _Optional[int] = ..., data: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ..., options: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ..., errors: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ..., description_placeholders: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ..., context: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ..., data_schema: _Optional[_Union[_struct_pb2.ListValue, _Mapping]] = ..., has_data_schema: bool = ..., menu_options: _Optional[_Union[_struct_pb2.ListValue, _Mapping]] = ..., sort: bool = ...) -> None: ...

class EntityInfo(_message.Message):
    __slots__ = ("description", "device_info")
    class Description(_message.Message):
        __slots__ = ("name", "icon", "entity_category", "device_class", "supported_features", "translation_key")
        NAME_FIELD_NUMBER: _ClassVar[int]
        ICON_FIELD_NUMBER: _ClassVar[int]
        ENTITY_CATEGORY_FIELD_NUMBER: _ClassVar[int]
        DEVICE_CLASS_FIELD_NUMBER: _ClassVar[int]
        SUPPORTED_FEATURES_FIELD_NUMBER: _ClassVar[int]
        TRANSLATION_KEY_FIELD_NUMBER: _ClassVar[int]
        name: str
        icon: str
        entity_category: str
        device_class: str
        supported_features: int
        translation_key: str
        def __init__(self, name: _Optional[str] = ..., icon: _Optional[str] = ..., entity_category: _Optional[str] = ..., device_class: _Optional[str] = ..., supported_features: _Optional[int] = ..., translation_key: _Optional[str] = ...) -> None: ...
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    DEVICE_INFO_FIELD_NUMBER: _ClassVar[int]
    description: EntityInfo.Description
    device_info: DeviceInfo
    def __init__(self, description: _Optional[_Union[EntityInfo.Description, _Mapping]] = ..., device_info: _Optional[_Union[DeviceInfo, _Mapping]] = ...) -> None: ...

class InitialState(_message.Message):
    __slots__ = ("state", "capabilities", "attributes")
    STATE_FIELD_NUMBER: _ClassVar[int]
    CAPABILITIES_FIELD_NUMBER: _ClassVar[int]
    ATTRIBUTES_FIELD_NUMBER: _ClassVar[int]
    state: str
    capabilities: _struct_pb2.Struct
    attributes: _struct_pb2.Struct
    def __init__(self, state: _Optional[str] = ..., capabilities: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ..., attributes: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ...) -> None: ...

class EntityDescription(_message.Message):
    __slots__ = ("entry_id", "domain", "sandbox_entity_id", "unique_id", "has_entity_name", "info", "initial")
    ENTRY_ID_FIELD_NUMBER: _ClassVar[int]
    DOMAIN_FIELD_NUMBER: _ClassVar[int]
    SANDBOX_ENTITY_ID_FIELD_NUMBER: _ClassVar[int]
    UNIQUE_ID_FIELD_NUMBER: _ClassVar[int]
    HAS_ENTITY_NAME_FIELD_NUMBER: _ClassVar[int]
    INFO_FIELD_NUMBER: _ClassVar[int]
    INITIAL_FIELD_NUMBER: _ClassVar[int]
    entry_id: str
    domain: str
    sandbox_entity_id: str
    unique_id: str
    has_entity_name: bool
    info: EntityInfo
    initial: InitialState
    def __init__(self, entry_id: _Optional[str] = ..., domain: _Optional[str] = ..., sandbox_entity_id: _Optional[str] = ..., unique_id: _Optional[str] = ..., has_entity_name: bool = ..., info: _Optional[_Union[EntityInfo, _Mapping]] = ..., initial: _Optional[_Union[InitialState, _Mapping]] = ...) -> None: ...

class RegisterEntityResult(_message.Message):
    __slots__ = ("entity_id",)
    ENTITY_ID_FIELD_NUMBER: _ClassVar[int]
    entity_id: str
    def __init__(self, entity_id: _Optional[str] = ...) -> None: ...

class UnregisterEntity(_message.Message):
    __slots__ = ("sandbox_entity_id",)
    SANDBOX_ENTITY_ID_FIELD_NUMBER: _ClassVar[int]
    sandbox_entity_id: str
    def __init__(self, sandbox_entity_id: _Optional[str] = ...) -> None: ...

class UnregisterEntityResult(_message.Message):
    __slots__ = ("ok",)
    OK_FIELD_NUMBER: _ClassVar[int]
    ok: bool
    def __init__(self, ok: bool = ...) -> None: ...

class StateChanged(_message.Message):
    __slots__ = ("sandbox_entity_id", "state", "attributes", "context_id")
    SANDBOX_ENTITY_ID_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    ATTRIBUTES_FIELD_NUMBER: _ClassVar[int]
    CONTEXT_ID_FIELD_NUMBER: _ClassVar[int]
    sandbox_entity_id: str
    state: str
    attributes: _struct_pb2.Struct
    context_id: str
    def __init__(self, sandbox_entity_id: _Optional[str] = ..., state: _Optional[str] = ..., attributes: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ..., context_id: _Optional[str] = ...) -> None: ...

class RegisterService(_message.Message):
    __slots__ = ("domain", "service", "supports_response", "schema")
    DOMAIN_FIELD_NUMBER: _ClassVar[int]
    SERVICE_FIELD_NUMBER: _ClassVar[int]
    SUPPORTS_RESPONSE_FIELD_NUMBER: _ClassVar[int]
    SCHEMA_FIELD_NUMBER: _ClassVar[int]
    domain: str
    service: str
    supports_response: str
    schema: _struct_pb2.ListValue
    def __init__(self, domain: _Optional[str] = ..., service: _Optional[str] = ..., supports_response: _Optional[str] = ..., schema: _Optional[_Union[_struct_pb2.ListValue, _Mapping]] = ...) -> None: ...

class RegisterServiceResult(_message.Message):
    __slots__ = ("ok", "installed")
    OK_FIELD_NUMBER: _ClassVar[int]
    INSTALLED_FIELD_NUMBER: _ClassVar[int]
    ok: bool
    installed: bool
    def __init__(self, ok: bool = ..., installed: bool = ...) -> None: ...

class UnregisterService(_message.Message):
    __slots__ = ("domain", "service")
    DOMAIN_FIELD_NUMBER: _ClassVar[int]
    SERVICE_FIELD_NUMBER: _ClassVar[int]
    domain: str
    service: str
    def __init__(self, domain: _Optional[str] = ..., service: _Optional[str] = ...) -> None: ...

class UnregisterServiceResult(_message.Message):
    __slots__ = ("ok", "removed")
    OK_FIELD_NUMBER: _ClassVar[int]
    REMOVED_FIELD_NUMBER: _ClassVar[int]
    ok: bool
    removed: bool
    def __init__(self, ok: bool = ..., removed: bool = ...) -> None: ...

class FireEvent(_message.Message):
    __slots__ = ("event_type", "event_data", "context_id")
    EVENT_TYPE_FIELD_NUMBER: _ClassVar[int]
    EVENT_DATA_FIELD_NUMBER: _ClassVar[int]
    CONTEXT_ID_FIELD_NUMBER: _ClassVar[int]
    event_type: str
    event_data: _struct_pb2.Struct
    context_id: str
    def __init__(self, event_type: _Optional[str] = ..., event_data: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ..., context_id: _Optional[str] = ...) -> None: ...

class StoreLoad(_message.Message):
    __slots__ = ("key",)
    KEY_FIELD_NUMBER: _ClassVar[int]
    key: str
    def __init__(self, key: _Optional[str] = ...) -> None: ...

class StoreLoadResult(_message.Message):
    __slots__ = ("data",)
    DATA_FIELD_NUMBER: _ClassVar[int]
    data: _struct_pb2.Struct
    def __init__(self, data: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ...) -> None: ...

class StoreSave(_message.Message):
    __slots__ = ("key", "data")
    KEY_FIELD_NUMBER: _ClassVar[int]
    DATA_FIELD_NUMBER: _ClassVar[int]
    key: str
    data: _struct_pb2.Struct
    def __init__(self, key: _Optional[str] = ..., data: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ...) -> None: ...

class StoreSaveResult(_message.Message):
    __slots__ = ("ok",)
    OK_FIELD_NUMBER: _ClassVar[int]
    ok: bool
    def __init__(self, ok: bool = ...) -> None: ...

class StoreRemove(_message.Message):
    __slots__ = ("key",)
    KEY_FIELD_NUMBER: _ClassVar[int]
    key: str
    def __init__(self, key: _Optional[str] = ...) -> None: ...

class StoreRemoveResult(_message.Message):
    __slots__ = ("ok",)
    OK_FIELD_NUMBER: _ClassVar[int]
    ok: bool
    def __init__(self, ok: bool = ...) -> None: ...
