"""Config flow for MQTT."""

from collections import OrderedDict
from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass
from enum import IntEnum
import json
import logging
import queue
from ssl import PROTOCOL_TLS_CLIENT, SSLContext, SSLError
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, cast
from uuid import uuid4

from aiohttp import ClientSession, TCPConnector
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    load_der_private_key,
    load_pem_private_key,
)
from cryptography.x509 import load_der_x509_certificate, load_pem_x509_certificate
import voluptuous as vol
import yaml

from homeassistant.components.file_upload import process_uploaded_file
from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    OptionsFlow,
    SubentryFlowResult,
)
from homeassistant.const import (
    ATTR_CONFIGURATION_URL,
    ATTR_HW_VERSION,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_MODEL_ID,
    ATTR_NAME,
    ATTR_SW_VERSION,
    CONF_CLIENT_ID,
    CONF_CODE,
    CONF_DEVICE,
    CONF_DISCOVERY,
    CONF_ENTITY_CATEGORY,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PAYLOAD,
    CONF_PLATFORM,
    CONF_PORT,
    CONF_PROTOCOL,
    CONF_UNIQUE_ID,
    CONF_USERNAME,
    CONF_VALUE_TEMPLATE,
    EntityCategory,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import SectionConfig, section
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.json import json_dumps
from homeassistant.helpers.selector import (
    BooleanSelector,
    FileSelector,
    FileSelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    Selector,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TemplateSelector,
    TemplateSelectorConfig,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
from homeassistant.util.json import JSON_DECODE_EXCEPTIONS, json_loads

from aiolocknalert import (
    LocknAlertBridgeApi,
    LocknAlertCannotConnect,
    LocknAlertInvalidResponse,
)
from .client import MqttClientSetup
from .const import (
    ALARM_CONTROL_PANEL_SUPPORTED_FEATURES,
    ATTR_PAYLOAD,
    ATTR_QOS,
    ATTR_RETAIN,
    ATTR_TOPIC,
    CONF_AVAILABILITY_TEMPLATE,
    CONF_AVAILABILITY_TOPIC,
    CONF_BIRTH_MESSAGE,
    CONF_BRIDGE_SERIAL,
    CONF_BROKER,
    CONF_CERTIFICATE,
    CONF_CLIENT_CERT,
    CONF_CLIENT_KEY,
    CONF_CODE_ARM_REQUIRED,
    CONF_CODE_DISARM_REQUIRED,
    CONF_CODE_TRIGGER_REQUIRED,
    CONF_COMMAND_TEMPLATE,
    CONF_COMMAND_TOPIC,
    CONF_DISCOVERY_PREFIX,
    CONF_ENTITY_PICTURE,
    CONF_KEEPALIVE,
    CONF_PAYLOAD_ARM_AWAY,
    CONF_PAYLOAD_ARM_CUSTOM_BYPASS,
    CONF_PAYLOAD_ARM_HOME,
    CONF_PAYLOAD_ARM_NIGHT,
    CONF_PAYLOAD_ARM_VACATION,
    CONF_PAYLOAD_AVAILABLE,
    CONF_PAYLOAD_NOT_AVAILABLE,
    CONF_PAYLOAD_TRIGGER,
    CONF_QOS,
    CONF_RETAIN,
    CONF_STATE_TOPIC,
    CONF_SUPPORTED_FEATURES,
    CONF_TLS_INSECURE,
    CONF_TRANSPORT,
    CONF_WILL_MESSAGE,
    CONF_WS_HEADERS,
    CONF_WS_PATH,
    CONFIG_ENTRY_MINOR_VERSION,
    CONFIG_ENTRY_VERSION,
    DEFAULT_ALARM_CONTROL_PANEL_COMMAND_TEMPLATE,
    DEFAULT_API_PORT,
    DEFAULT_BIRTH,
    DEFAULT_DISCOVERY,
    DEFAULT_ENCODING,
    DEFAULT_KEEPALIVE,
    DEFAULT_PAYLOAD_ARM_AWAY,
    DEFAULT_PAYLOAD_ARM_CUSTOM_BYPASS,
    DEFAULT_PAYLOAD_ARM_HOME,
    DEFAULT_PAYLOAD_ARM_NIGHT,
    DEFAULT_PAYLOAD_ARM_VACATION,
    DEFAULT_PAYLOAD_AVAILABLE,
    DEFAULT_PAYLOAD_NOT_AVAILABLE,
    DEFAULT_PAYLOAD_TRIGGER,
    DEFAULT_PORT,
    DEFAULT_PREFIX,
    DEFAULT_PROTOCOL,
    DEFAULT_QOS,
    DEFAULT_TRANSPORT,
    DEFAULT_WILL,
    DEFAULT_WS_PATH,
    DISCOVERY_ATTR_API_PORT,
    DISCOVERY_ATTR_SERIAL,
    DOMAIN,
    REMOTE_CODE,
    REMOTE_CODE_TEXT,
    SUPPORTED_PROTOCOLS,
    TRANSPORT_TCP,
    TRANSPORT_WEBSOCKETS,
)
from .models import MqttAvailabilityData, MqttDeviceData, MqttSubentryData
from .util import (
    async_create_certificate_temp_files,
    get_file_path,
    learn_more_url,
    valid_birth_will,
    valid_publish_topic,
    valid_subscribe_topic,
    valid_subscribe_topic_template,
)

_LOGGER = logging.getLogger(__name__)

ADDON_SETUP_TIMEOUT = 5
ADDON_SETUP_TIMEOUT_ROUNDS = 5

CONF_CLIENT_KEY_PASSWORD = "client_key_password"

MQTT_TIMEOUT = 5

ADVANCED_OPTIONS = "advanced_options"
SET_CA_CERT = "set_ca_cert"
SET_CLIENT_CERT = "set_client_cert"

CA_VERIFICATION_MODES = [
    "off",
    "auto",
    "custom",
]

SUBENTRY_PLATFORMS = [
    Platform.ALARM_CONTROL_PANEL,
]

_CODE_VALIDATION_MODE = {
    "remote_code": REMOTE_CODE,
    "remote_code_text": REMOTE_CODE_TEXT,
}
EXCLUDE_FROM_CONFIG_IF_NONE = {CONF_ENTITY_CATEGORY}
PWD_NOT_CHANGED = "__**password_not_changed**__"

DEVELOPER_DOCUMENTATION_URL = "https://developers.home-assistant.io/"
USER_DOCUMENTATION_URL = "https://www.home-assistant.io/"

INTEGRATION_URL = f"{USER_DOCUMENTATION_URL}integrations/{DOMAIN}/"
TEMPLATING_URL = f"{USER_DOCUMENTATION_URL}docs/configuration/templating/"
COMMAND_TEMPLATING_URL = f"{TEMPLATING_URL}#using-command-templates-with-mqtt"
VALUE_TEMPLATING_URL = f"{TEMPLATING_URL}#using-value-templates-with-mqtt"
AVAILABLE_STATE_CLASSES_URL = (
    f"{DEVELOPER_DOCUMENTATION_URL}docs/core/entity/sensor/#available-state-classes"
)
NAMING_ENTITIES_URL = f"{INTEGRATION_URL}#naming-of-mqtt-entities"
REGISTRY_PROPERTIES_URL = (
    f"{DEVELOPER_DOCUMENTATION_URL}docs/core/entity/#registry-properties"
)

TRANSLATION_DESCRIPTION_PLACEHOLDERS = {
    "command_templating_url": COMMAND_TEMPLATING_URL,
    "value_templating_url": VALUE_TEMPLATING_URL,
    "available_state_classes_url": AVAILABLE_STATE_CLASSES_URL,
    "naming_entities_url": NAMING_ENTITIES_URL,
    "registry_properties_url": REGISTRY_PROPERTIES_URL,
}

# Common selectors
BOOLEAN_SELECTOR = BooleanSelector()
TEMPLATE_SELECTOR = TemplateSelector(TemplateSelectorConfig())
TEMPLATE_SELECTOR_READ_ONLY = TemplateSelector(TemplateSelectorConfig(read_only=True))
TEXT_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT))
TEXT_SELECTOR_READ_ONLY = TextSelector(
    TextSelectorConfig(type=TextSelectorType.TEXT, read_only=True)
)
PASSWORD_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))
QOS_SELECTOR = NumberSelector(
    NumberSelectorConfig(mode=NumberSelectorMode.BOX, min=0, max=2)
)
URL_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.URL))

# Config flow specific selectors
BROKER_VERIFICATION_SELECTOR = SelectSelector(
    SelectSelectorConfig(
        options=CA_VERIFICATION_MODES,
        mode=SelectSelectorMode.DROPDOWN,
        translation_key=SET_CA_CERT,
    )
)
# mime configuration from https://pki-tutorial.readthedocs.io/en/latest/mime.html
CA_CERT_UPLOAD_SELECTOR = FileSelector(
    FileSelectorConfig(accept=".pem,.crt,.cer,.der,application/x-x509-ca-cert")
)
CERT_KEY_UPLOAD_SELECTOR = FileSelector(
    FileSelectorConfig(accept=".pem,.key,.der,.pk8,application/pkcs8")
)
CERT_UPLOAD_SELECTOR = FileSelector(
    FileSelectorConfig(accept=".pem,.crt,.cer,.der,application/x-x509-user-cert")
)
KEEPALIVE_SELECTOR = vol.All(
    NumberSelector(
        NumberSelectorConfig(
            mode=NumberSelectorMode.BOX, min=15, step="any", unit_of_measurement="sec"
        )
    ),
    vol.Coerce(int),
)
PORT_SELECTOR = vol.All(
    NumberSelector(NumberSelectorConfig(mode=NumberSelectorMode.BOX, min=1, max=65535)),
    vol.Coerce(int),
)
PROTOCOL_SELECTOR = SelectSelector(
    SelectSelectorConfig(
        options=SUPPORTED_PROTOCOLS,
        mode=SelectSelectorMode.DROPDOWN,
    )
)
PUBLISH_TOPIC_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT))
SUPPORTED_TRANSPORTS = [
    SelectOptionDict(value=TRANSPORT_TCP, label="TCP"),
    SelectOptionDict(value=TRANSPORT_WEBSOCKETS, label="WebSocket"),
]
TRANSPORT_SELECTOR = SelectSelector(
    SelectSelectorConfig(
        options=SUPPORTED_TRANSPORTS,
        mode=SelectSelectorMode.DROPDOWN,
    )
)
WS_HEADERS_SELECTOR = TextSelector(
    TextSelectorConfig(type=TextSelectorType.TEXT, multiline=True)
)

# MQTT device subentry selectors
ENTITY_CATEGORY_SELECTOR = SelectSelector(
    SelectSelectorConfig(
        options=[category.value for category in EntityCategory],
        mode=SelectSelectorMode.DROPDOWN,
        translation_key=CONF_ENTITY_CATEGORY,
        sort=True,
    )
)
SUBENTRY_AVAILABILITY_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_AVAILABILITY_TOPIC): TEXT_SELECTOR,
        vol.Optional(CONF_AVAILABILITY_TEMPLATE): TEMPLATE_SELECTOR,
        vol.Optional(
            CONF_PAYLOAD_AVAILABLE, default=DEFAULT_PAYLOAD_AVAILABLE
        ): TEXT_SELECTOR,
        vol.Optional(
            CONF_PAYLOAD_NOT_AVAILABLE, default=DEFAULT_PAYLOAD_NOT_AVAILABLE
        ): TEXT_SELECTOR,
    }
)
SUBENTRY_PLATFORM_SELECTOR = SelectSelector(
    SelectSelectorConfig(
        options=[platform.value for platform in SUBENTRY_PLATFORMS],
        mode=SelectSelectorMode.DROPDOWN,
        translation_key=CONF_PLATFORM,
    )
)

# Entity platform specific selectors
ALARM_CONTROL_PANEL_FEATURES_SELECTOR = SelectSelector(
    SelectSelectorConfig(
        options=list(ALARM_CONTROL_PANEL_SUPPORTED_FEATURES),
        multiple=True,
        translation_key="alarm_control_panel_features",
    )
)
ALARM_CONTROL_PANEL_CODE_MODE = SelectSelector(
    SelectSelectorConfig(
        options=["local_code", "remote_code", "remote_code_text"],
        translation_key="alarm_control_panel_code_mode",
    )
)


@callback
def default_alarm_control_panel_code(config: dict[str, Any]) -> str:
    """Return alarm control panel code based on the stored code and code mode."""
    code: str
    if config["alarm_control_panel_code_mode"] in _CODE_VALIDATION_MODE:
        # Return magic value for remote code validation
        return _CODE_VALIDATION_MODE[config["alarm_control_panel_code_mode"]]
    if (code := config.get(CONF_CODE, "")) in _CODE_VALIDATION_MODE.values():
        # Remove magic value for remote code validation
        return ""

    return code


@callback
def no_empty_list(value: list[Any]) -> list[Any]:
    """Validate a selector returns at least one item."""
    if not value:
        raise vol.Invalid("empty_list_not_allowed")
    return value


@callback
def validate(validator: Callable[[Any], Any]) -> Callable[[Any], Any]:
    """Run validator, then return the unmodified input."""

    def _validate(value: Any) -> Any:
        validator(value)
        return value

    return _validate


@callback
def validate_field(
    field: str,
    validator: Callable[..., Any],
    user_input: dict[str, Any] | None,
    errors: dict[str, str],
    error: str,
) -> None:
    """Validate a single field."""
    if user_input is None or field not in user_input or validator is None:
        return
    try:
        user_input[field] = validator(user_input[field])
    except (ValueError, vol.Error, vol.Invalid):
        errors[field] = error


ENTITY_CONFIG_VALIDATOR: dict[
    str,
    Callable[[dict[str, Any]], dict[str, str]] | None,
] = {
    Platform.ALARM_CONTROL_PANEL: None,
}


@dataclass(frozen=True, kw_only=True)
class PlatformField:
    """Stores a platform config field schema, required flag and validator."""

    selector: Selector[Any] | Callable[[dict[str, Any]], Selector[Any]]
    required: bool
    validator: Callable[[Any], Any] | None = None
    error: str | None = None
    default: Any | None | Callable[[dict[str, Any]], Any] | vol.Undefined = (
        vol.UNDEFINED
    )
    is_schema_default: bool = False
    include_in_config: bool = False
    exclude_from_reconfig: bool = False
    exclude_from_config: bool = False
    conditions: tuple[dict[str, Any], ...] | None = None
    custom_filtering: bool = False
    section: str | None = None


COMMON_ENTITY_FIELDS: dict[str, PlatformField] = {
    CONF_PLATFORM: PlatformField(
        selector=SUBENTRY_PLATFORM_SELECTOR,
        required=True,
        exclude_from_reconfig=True,
    ),
    CONF_NAME: PlatformField(
        selector=TEXT_SELECTOR,
        required=False,
        exclude_from_reconfig=True,
        default=None,
    ),
    CONF_ENTITY_PICTURE: PlatformField(
        selector=TEXT_SELECTOR, required=False, validator=cv.url, error="invalid_url"
    ),
}
SHARED_PLATFORM_ENTITY_FIELDS: dict[str, PlatformField] = {
    CONF_ENTITY_CATEGORY: PlatformField(
        selector=ENTITY_CATEGORY_SELECTOR,
        required=False,
        default=None,
    ),
}
PLATFORM_ENTITY_FIELDS: dict[Platform, dict[str, PlatformField]] = {
    Platform.ALARM_CONTROL_PANEL: {
        CONF_SUPPORTED_FEATURES: PlatformField(
            selector=ALARM_CONTROL_PANEL_FEATURES_SELECTOR,
            required=True,
            default=lambda config: config.get(
                CONF_SUPPORTED_FEATURES, list(ALARM_CONTROL_PANEL_SUPPORTED_FEATURES)
            ),
        ),
        "alarm_control_panel_code_mode": PlatformField(
            selector=ALARM_CONTROL_PANEL_CODE_MODE,
            required=True,
            exclude_from_config=True,
            default=lambda config: (
                config[CONF_CODE].lower()
                if config.get(CONF_CODE) in (REMOTE_CODE, REMOTE_CODE_TEXT)
                else "local_code"
            ),
        ),
    },
}
PLATFORM_MQTT_FIELDS: dict[Platform, dict[str, PlatformField]] = {
    Platform.ALARM_CONTROL_PANEL: {
        CONF_COMMAND_TOPIC: PlatformField(
            selector=TEXT_SELECTOR,
            required=True,
            validator=valid_publish_topic,
            error="invalid_publish_topic",
        ),
        CONF_COMMAND_TEMPLATE: PlatformField(
            selector=TEMPLATE_SELECTOR,
            required=False,
            default=DEFAULT_ALARM_CONTROL_PANEL_COMMAND_TEMPLATE,
            validator=validate(cv.template),
            error="invalid_template",
        ),
        CONF_STATE_TOPIC: PlatformField(
            selector=TEXT_SELECTOR,
            required=True,
            validator=valid_subscribe_topic,
            error="invalid_subscribe_topic",
        ),
        CONF_VALUE_TEMPLATE: PlatformField(
            selector=TEMPLATE_SELECTOR,
            required=False,
            validator=validate(cv.template),
            error="invalid_template",
        ),
        CONF_CODE: PlatformField(
            selector=PASSWORD_SELECTOR,
            required=True,
            include_in_config=True,
            default=default_alarm_control_panel_code,
            conditions=({"alarm_control_panel_code_mode": "local_code"},),
        ),
        CONF_CODE_ARM_REQUIRED: PlatformField(
            selector=BOOLEAN_SELECTOR,
            required=True,
            default=True,
        ),
        CONF_CODE_DISARM_REQUIRED: PlatformField(
            selector=BOOLEAN_SELECTOR,
            required=True,
            default=True,
        ),
        CONF_CODE_TRIGGER_REQUIRED: PlatformField(
            selector=BOOLEAN_SELECTOR,
            required=True,
            default=True,
        ),
        CONF_RETAIN: PlatformField(selector=BOOLEAN_SELECTOR, required=False),
        CONF_PAYLOAD_ARM_HOME: PlatformField(
            selector=TEXT_SELECTOR,
            required=False,
            default=DEFAULT_PAYLOAD_ARM_HOME,
            section="alarm_control_panel_payload_settings",
        ),
        CONF_PAYLOAD_ARM_AWAY: PlatformField(
            selector=TEXT_SELECTOR,
            required=False,
            default=DEFAULT_PAYLOAD_ARM_AWAY,
            section="alarm_control_panel_payload_settings",
        ),
        CONF_PAYLOAD_ARM_NIGHT: PlatformField(
            selector=TEXT_SELECTOR,
            required=False,
            default=DEFAULT_PAYLOAD_ARM_NIGHT,
            section="alarm_control_panel_payload_settings",
        ),
        CONF_PAYLOAD_ARM_VACATION: PlatformField(
            selector=TEXT_SELECTOR,
            required=False,
            default=DEFAULT_PAYLOAD_ARM_VACATION,
            section="alarm_control_panel_payload_settings",
        ),
        CONF_PAYLOAD_ARM_CUSTOM_BYPASS: PlatformField(
            selector=TEXT_SELECTOR,
            required=False,
            default=DEFAULT_PAYLOAD_ARM_CUSTOM_BYPASS,
            section="alarm_control_panel_payload_settings",
        ),
        CONF_PAYLOAD_TRIGGER: PlatformField(
            selector=TEXT_SELECTOR,
            required=False,
            default=DEFAULT_PAYLOAD_TRIGGER,
            section="alarm_control_panel_payload_settings",
        ),
    },
}
MQTT_DEVICE_PLATFORM_FIELDS = {
    ATTR_NAME: PlatformField(selector=TEXT_SELECTOR, required=True),
    ATTR_SW_VERSION: PlatformField(
        selector=TEXT_SELECTOR, required=False, section="advanced_settings"
    ),
    ATTR_HW_VERSION: PlatformField(
        selector=TEXT_SELECTOR, required=False, section="advanced_settings"
    ),
    ATTR_MODEL: PlatformField(selector=TEXT_SELECTOR, required=False),
    ATTR_MODEL_ID: PlatformField(selector=TEXT_SELECTOR, required=False),
    ATTR_MANUFACTURER: PlatformField(selector=TEXT_SELECTOR, required=False),
    ATTR_CONFIGURATION_URL: PlatformField(
        selector=TEXT_SELECTOR, required=False, validator=cv.url, error="invalid_url"
    ),
    CONF_QOS: PlatformField(
        selector=QOS_SELECTOR,
        required=False,
        validator=int,
        default=DEFAULT_QOS,
        section="mqtt_settings",
    ),
}


@callback
def _check_conditions(
    platform_field: PlatformField, component_data: dict[str, Any] | None = None
) -> bool:
    """Only include field if one of conditions match, or no conditions are set."""
    if platform_field.conditions is None or component_data is None:
        return True
    return any(
        all(component_data.get(key) == value for key, value in condition.items())
        for condition in platform_field.conditions
    )


@callback
def calculate_merged_config(
    merged_user_input: dict[str, Any],
    data_schema_fields: dict[str, PlatformField],
    component_data: dict[str, Any],
) -> dict[str, Any]:
    """Calculate merged config."""
    base_schema_fields = {
        key
        for key, platform_field in data_schema_fields.items()
        if _check_conditions(platform_field, component_data)
    } - set(merged_user_input)
    return {
        key: value
        for key, value in component_data.items()
        if key not in base_schema_fields
    } | merged_user_input


@callback
def data_schema_from_fields(
    data_schema_fields: dict[str, PlatformField],
    reconfig: bool,
    component_data: dict[str, Any] | None = None,
    user_input: dict[str, Any] | None = None,
    device_data: MqttDeviceData | None = None,
) -> vol.Schema:
    """Generate custom data schema from platform fields or device data."""

    def get_default(field_details: PlatformField) -> Any:
        if callable(field_details.default):
            if TYPE_CHECKING:
                assert component_data is not None
            return field_details.default(component_data)
        return field_details.default

    if device_data is not None:
        component_data_with_user_input: dict[str, Any] | None = dict(device_data)
        if TYPE_CHECKING:
            assert component_data_with_user_input is not None
        component_data_with_user_input.update(
            component_data_with_user_input.pop("mqtt_settings", {})
        )
    else:
        component_data_with_user_input = deepcopy(component_data)
    if component_data_with_user_input is not None and user_input is not None:
        component_data_with_user_input |= user_input

    sections: dict[str | None, None] = {
        field_details.section: None
        for field_details in data_schema_fields.values()
        if not field_details.is_schema_default
    }
    data_schema: dict[Any, Any] = {}
    all_data_element_options: set[Any] = set()
    no_reconfig_options: set[Any] = set()

    defaults: dict[str, Any] = {}
    for field_name, field_details in data_schema_fields.items():
        default = defaults[field_name] = get_default(field_details)
        if not field_details.include_in_config or component_data is None:
            continue
        component_data[field_name] = default

    for schema_section in sections:
        # Always calculate the default values
        # Getting the default value may update the subentry data,
        # even when and option is filtered out
        data_schema_element = {
            vol.Required(field_name, default=defaults[field_name])
            if field_details.required
            else vol.Optional(
                field_name,
                default=defaults[field_name]
                if field_details.default is not None
                else vol.UNDEFINED,
            ): field_details.selector(component_data_with_user_input or {})
            if callable(field_details.selector) and field_details.custom_filtering
            else field_details.selector
            for field_name, field_details in data_schema_fields.items()
            if not field_details.is_schema_default
            and field_details.section == schema_section
            and (not field_details.exclude_from_reconfig or not reconfig)
            and _check_conditions(field_details, component_data_with_user_input)
        }
        data_element_options = set(data_schema_element)
        all_data_element_options |= data_element_options
        no_reconfig_options |= {
            field_name
            for field_name, field_details in data_schema_fields.items()
            if field_details.section == schema_section
            and field_details.exclude_from_reconfig
        }
        if schema_section is None:
            data_schema.update(data_schema_element)
            continue
        if not data_schema_element:
            # Do not show empty sections
            continue
        # Collapse if values are changed or required fields need to be set
        collapsed = (
            not any(
                (default := data_schema_fields[str(option)].default) is vol.UNDEFINED
                or (
                    str(option) in component_data_with_user_input
                    and component_data_with_user_input[str(option)] != default
                )
                for option in data_element_options
                if option in component_data_with_user_input
                or (
                    str(option) in data_schema_fields
                    and data_schema_fields[str(option)].required
                )
            )
            if component_data_with_user_input is not None
            else True
        )
        data_schema[vol.Optional(schema_section)] = section(
            vol.Schema(data_schema_element), SectionConfig({"collapsed": collapsed})
        )

    # Reset all fields from the component_data not in the schema
    # except for options that should stay included
    if component_data:
        filtered_fields = (
            set(data_schema_fields) - all_data_element_options - no_reconfig_options
        )
        for field in filtered_fields:
            if (
                field in component_data
                and not data_schema_fields[field].include_in_config
            ):
                del component_data[field]
    return vol.Schema(data_schema)


@callback
def validate_user_input(
    user_input: dict[str, Any],
    data_schema_fields: dict[str, PlatformField],
    *,
    component_data: dict[str, Any] | None = None,
    config_validator: Callable[[dict[str, Any]], dict[str, str]] | None = None,
) -> tuple[dict[str, Any], dict[str, str]]:
    """Validate user input."""
    errors: dict[str, str] = {}
    # Merge sections
    merged_user_input: dict[str, Any] = {}
    for key, value in user_input.items():
        if isinstance(value, dict):
            merged_user_input.update(value)
        else:
            merged_user_input[key] = value

    for field, value in merged_user_input.items():
        validator = data_schema_fields[field].validator
        try:
            merged_user_input[field] = (
                validator(value) if validator is not None else value
            )
        except (ValueError, vol.Error, vol.Invalid):
            data_schema_field = data_schema_fields[field]
            errors[data_schema_field.section or field] = (
                data_schema_field.error or "invalid_input"
            )

    if config_validator is not None:
        if TYPE_CHECKING:
            assert component_data is not None

        errors |= config_validator(
            calculate_merged_config(
                merged_user_input, data_schema_fields, component_data
            ),
        )

    return merged_user_input, errors


@callback
def subentry_schema_default_data_from_fields(
    data_schema_fields: dict[str, PlatformField],
    component_data: dict[str, Any],
) -> dict[str, Any]:
    """Generate custom data schema from platform fields or device data."""
    return {
        key: field.default
        for key, field in data_schema_fields.items()
        if _check_conditions(field, component_data)
        and (
            field.is_schema_default
            or (field.default is not vol.UNDEFINED and key not in component_data)
        )
    }


@callback
def update_password_from_user_input(
    entry_password: str | None, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Update the password if the entry has been updated.

    As we want to avoid reflecting the stored password in the UI,
    we replace the suggested value in the UI with a sentitel,
    and we change it back here if it was changed.
    """
    substituted_used_data = dict(user_input)
    # Take out the password submitted
    user_password: str | None = substituted_used_data.pop(CONF_PASSWORD, None)
    # Only add the password if it has changed.
    # If the sentinel password is submitted, we replace that with our current
    # password from the config entry data.
    password_changed = user_password is not None and user_password != PWD_NOT_CHANGED
    password = user_password if password_changed else entry_password
    if password is not None:
        substituted_used_data[CONF_PASSWORD] = password
    return substituted_used_data


REAUTH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): TEXT_SELECTOR,
        vol.Required(CONF_PASSWORD): PASSWORD_SELECTOR,
    }
)


def extract_serial_from_discovery(discovery_info: ZeroconfServiceInfo) -> str | None:
    """Extract bridge serial from zeroconf discovery info.

    Discovery format: "BRIDGE_SERIAL._locknalert._tcp.local."
    Example: "ABC123456._locknalert._tcp.local."
    """
    # Extract from discovery.name before the service type
    if discovery_info.name:
        # Remove service type suffix: "_locknalert._tcp.local."
        parts = discovery_info.name.split(".")
        if parts:
            return parts[0]  # Return serial/hostname part

    # Fallback to TXT property
    return discovery_info.properties.get(DISCOVERY_ATTR_SERIAL)


class FlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = CONFIG_ENTRY_VERSION  # 2
    MINOR_VERSION = CONFIG_ENTRY_MINOR_VERSION  # 1

    _selected_bridge: ZeroconfServiceInfo | None = None
    _bridge_api: LocknAlertBridgeApi | None = None
    _bridge_serial: str | None = None

    def __init__(self) -> None:
        """Set up flow instance."""
        self._selected_bridge = None
        self._bridge_api = None
        self._bridge_serial = None

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this handler."""
        return {CONF_DEVICE: MQTTSubentryFlowHandler}

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> MQTTOptionsFlowHandler:
        """Get the options flow for this handler."""
        return MQTTOptionsFlowHandler()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        # Always use manual broker setup flow (LocknAlert bridges discovered via zeroconf)
        return await self.async_step_broker()

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery of LocknAlert bridge."""
        serial = extract_serial_from_discovery(discovery_info)

        if not serial:
            return self.async_abort(reason="cannot_determine_serial")

        await self.async_set_unique_id(serial)
        self._abort_if_unique_id_configured()

        try:
            api_port = int(
                discovery_info.properties.get(DISCOVERY_ATTR_API_PORT, DEFAULT_API_PORT)
            )
        except (ValueError, TypeError):
            api_port = DEFAULT_API_PORT

        # Store discovery info — connectivity is validated on confirm submit.
        self._selected_bridge = discovery_info
        self._bridge_api = LocknAlertBridgeApi(
            host=discovery_info.host,
            port=api_port,
            verify_ssl=False,
        )
        self._bridge_serial = serial

        self.context.update(
            {
                "title_placeholders": {"serial": serial},
                "configuration_url": f"https://{discovery_info.host}:{api_port}/api",
            }
        )

        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle user confirmation of discovered bridge."""
        if user_input is not None:
            self._bridge_serial = user_input[CONF_BRIDGE_SERIAL]
            return await self._async_bootstrap_from_bridge()

        data_schema = self.add_suggested_values_to_schema(
            vol.Schema({vol.Required(CONF_BRIDGE_SERIAL): TEXT_SELECTOR}),
            {CONF_BRIDGE_SERIAL: self._bridge_serial or ""},
        )
        return self.async_show_form(
            step_id="zeroconf_confirm",
            data_schema=data_schema,
            last_step=True,
        )

    async def _async_bootstrap_from_bridge(self) -> ConfigFlowResult:
        """Bootstrap MQTT credentials from discovered bridge."""
        if not self._bridge_api or not self._selected_bridge or not self._bridge_serial:
            return self.async_abort(reason="bridge_not_configured")

        try:
            async with ClientSession(connector=TCPConnector(ssl=False)) as session:
                await self._bridge_api.async_get_info(session)
                mqtt_config = await self._bridge_api.async_bootstrap(session)
        except LocknAlertCannotConnect:
            return self.async_abort(reason="cannot_connect")
        except LocknAlertInvalidResponse:
            return self.async_abort(reason="invalid_response")

        # Build config from bootstrap response.
        # Prefer the bridge's discovered IP over the bootstrap hostname, since
        # .local mDNS names are not reliably resolvable from HA's environment.
        mqtt_host = self._selected_bridge.host or mqtt_config.get("host", "")
        config_data = {
            CONF_BROKER: mqtt_host,
            CONF_PORT: mqtt_config.get("port", DEFAULT_PORT),
            CONF_USERNAME: mqtt_config["username"],
            CONF_PASSWORD: mqtt_config["password"],
            CONF_DISCOVERY: DEFAULT_DISCOVERY,
            CONF_BRIDGE_SERIAL: self._bridge_serial,
        }

        # Test MQTT connection before creating entry
        if not await self.hass.async_add_executor_job(try_connection, config_data):
            return self.async_abort(reason="cannot_connect_mqtt")

        return self.async_create_entry(
            title=f"LocknAlert Bridge {self._bridge_serial}",
            data=config_data,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle re-authentication with MQTT broker."""

        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm re-authentication with MQTT broker."""
        errors: dict[str, str] = {}

        reauth_entry = self._get_reauth_entry()
        if user_input:
            substituted_used_data = update_password_from_user_input(
                reauth_entry.data.get(CONF_PASSWORD), user_input
            )
            new_entry_data = {**reauth_entry.data, **substituted_used_data}
            if await self.hass.async_add_executor_job(
                try_connection,
                new_entry_data,
            ):
                return self.async_update_and_abort(reauth_entry, data=new_entry_data)

            errors["base"] = "invalid_auth"

        schema = self.add_suggested_values_to_schema(
            REAUTH_SCHEMA,
            {
                CONF_USERNAME: reauth_entry.data.get(CONF_USERNAME),
                CONF_PASSWORD: PWD_NOT_CHANGED,
            },
        )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_broker(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm the setup."""
        errors: dict[str, str] = {}
        fields: OrderedDict[Any, Any] = OrderedDict()
        validated_user_input: dict[str, Any] = {}
        if is_reconfigure := (self.source == SOURCE_RECONFIGURE):
            reconfigure_entry = self._get_reconfigure_entry()
        # If the user opened the broker form, always show a simple form
        # that asks for broker and bridge serial so the UI will prompt
        # for the serial explicitly instead of sometimes showing an empty popup.
        if user_input is None:
            schema = vol.Schema(
                {
                    vol.Required(CONF_BROKER): TEXT_SELECTOR,
                    vol.Optional(CONF_BRIDGE_SERIAL): TEXT_SELECTOR,
                }
            )
            return self.async_show_form(step_id="broker", data_schema=schema, errors=errors)
        if await async_get_broker_settings(
            self,
            fields,
            reconfigure_entry.data if is_reconfigure else None,
            user_input,
            validated_user_input,
            errors,
        ):
            # Fetch MQTT credentials from bridgeapi

            try:
                bridge_api = LocknAlertBridgeApi(validated_user_input[CONF_BROKER])
                async with ClientSession(connector=TCPConnector(ssl=False)) as session:
                    # First try to obtain bridge identity (serial) where possible
                    try:
                        info = await bridge_api.async_get_info(session)
                        serial_found = info.get(DISCOVERY_ATTR_SERIAL) if isinstance(info, dict) else None
                        # common keys fallback
                        if not serial_found:
                            serial_found = info.get("serial") if isinstance(info, dict) else None
                        if serial_found:
                            validated_user_input[CONF_BRIDGE_SERIAL] = serial_found
                            _LOGGER.debug("LocknAlert bridge serial discovered via API: %s", serial_found)
                    except Exception as _err:  # noqa: BLE001  # still attempt bootstrap even if identity fetch fails
                        _LOGGER.debug("Could not fetch bridge identity from %s: %s", validated_user_input[CONF_BROKER], _err)

                    # Then bootstrap MQTT credentials
                    mqtt_config = await bridge_api.async_bootstrap(session)

                # Update validated_user_input with fetched credentials
                validated_user_input.update(
                    {
                        CONF_PORT: mqtt_config.get("port", DEFAULT_PORT),
                        CONF_USERNAME: mqtt_config.get("username"),
                        CONF_PASSWORD: mqtt_config.get("password"),
                    }
                )
            except (LocknAlertCannotConnect, LocknAlertInvalidResponse) as err:
                _LOGGER.error(
                    "Error contacting LocknAlert bridge at %s: %s",
                    validated_user_input.get(CONF_BROKER),
                    err,
                )
                errors["base"] = "cannot_connect"
                # Rebuild the broker settings form so fields are present for the user
                await async_get_broker_settings(
                    self,
                    fields,
                    reconfigure_entry.data if is_reconfigure else None,
                    None,
                    validated_user_input,
                    errors,
                )
                return self.async_show_form(
                    step_id="broker", data_schema=vol.Schema(fields), errors=errors
                )

            can_connect = await self.hass.async_add_executor_job(
                try_connection, validated_user_input
            )

            if can_connect:
                if is_reconfigure:
                    return self.async_update_and_abort(
                        reconfigure_entry,
                        data=validated_user_input,
                    )
                return self.async_create_entry(
                    title=validated_user_input[CONF_BROKER],
                    data=validated_user_input,
                )

            errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="broker", data_schema=vol.Schema(fields), errors=errors
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a reconfiguration flow initialized by the user."""
        return await self.async_step_broker()


class MQTTOptionsFlowHandler(OptionsFlow):
    """Handle MQTT options."""

    async def async_step_init(self, user_input: None = None) -> ConfigFlowResult:
        """Manage the MQTT options."""
        return await self.async_step_options()

    async def async_step_options(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the MQTT options."""
        errors = {}

        options_config: dict[str, Any] = dict(self.config_entry.options)
        bad_input: bool = False

        def _birth_will(birt_or_will: str) -> dict[str, Any]:
            """Return the user input for birth or will."""
            if TYPE_CHECKING:
                assert user_input
            return {
                ATTR_TOPIC: user_input[f"{birt_or_will}_topic"],
                ATTR_PAYLOAD: user_input.get(f"{birt_or_will}_payload", ""),
                ATTR_QOS: user_input[f"{birt_or_will}_qos"],
                ATTR_RETAIN: user_input[f"{birt_or_will}_retain"],
            }

        def _validate(
            field: str,
            values: dict[str, Any],
            error_code: str,
            schema: Callable[[Any], Any],
        ) -> None:
            """Validate the user input."""
            nonlocal bad_input
            try:
                option_values = schema(values)
                options_config[field] = option_values
            except vol.Invalid:
                errors["base"] = error_code
                bad_input = True

        if user_input is not None:
            # validate input
            options_config[CONF_DISCOVERY] = user_input[CONF_DISCOVERY]
            _validate(
                CONF_DISCOVERY_PREFIX,
                user_input[CONF_DISCOVERY_PREFIX],
                "bad_discovery_prefix",
                valid_publish_topic,
            )
            if "birth_topic" in user_input:
                _validate(
                    CONF_BIRTH_MESSAGE,
                    _birth_will("birth"),
                    "bad_birth",
                    valid_birth_will,
                )
            if not user_input["birth_enable"]:
                options_config[CONF_BIRTH_MESSAGE] = {}

            if "will_topic" in user_input:
                _validate(
                    CONF_WILL_MESSAGE,
                    _birth_will("will"),
                    "bad_will",
                    valid_birth_will,
                )
            if not user_input["will_enable"]:
                options_config[CONF_WILL_MESSAGE] = {}

            if not bad_input:
                return self.async_create_entry(data=options_config)

        birth = {
            **DEFAULT_BIRTH,
            **options_config.get(CONF_BIRTH_MESSAGE, {}),
        }
        will = {
            **DEFAULT_WILL,
            **options_config.get(CONF_WILL_MESSAGE, {}),
        }
        discovery = options_config.get(CONF_DISCOVERY, DEFAULT_DISCOVERY)
        discovery_prefix = options_config.get(CONF_DISCOVERY_PREFIX, DEFAULT_PREFIX)

        # build form
        fields: OrderedDict[vol.Marker, Any] = OrderedDict()
        fields[vol.Optional(CONF_DISCOVERY, default=discovery)] = BOOLEAN_SELECTOR
        fields[vol.Optional(CONF_DISCOVERY_PREFIX, default=discovery_prefix)] = (
            PUBLISH_TOPIC_SELECTOR
        )

        # Birth message is disabled if CONF_BIRTH_MESSAGE = {}
        fields[
            vol.Optional(
                "birth_enable",
                default=CONF_BIRTH_MESSAGE not in options_config
                or options_config[CONF_BIRTH_MESSAGE] != {},
            )
        ] = BOOLEAN_SELECTOR
        fields[
            vol.Optional(
                "birth_topic", description={"suggested_value": birth[ATTR_TOPIC]}
            )
        ] = PUBLISH_TOPIC_SELECTOR
        fields[
            vol.Optional(
                "birth_payload", description={"suggested_value": birth[CONF_PAYLOAD]}
            )
        ] = TEXT_SELECTOR
        fields[vol.Optional("birth_qos", default=birth[ATTR_QOS])] = QOS_SELECTOR
        fields[vol.Optional("birth_retain", default=birth[ATTR_RETAIN])] = (
            BOOLEAN_SELECTOR
        )

        # Will message is disabled if CONF_WILL_MESSAGE = {}
        fields[
            vol.Optional(
                "will_enable",
                default=CONF_WILL_MESSAGE not in options_config
                or options_config[CONF_WILL_MESSAGE] != {},
            )
        ] = BOOLEAN_SELECTOR
        fields[
            vol.Optional(
                "will_topic", description={"suggested_value": will[ATTR_TOPIC]}
            )
        ] = PUBLISH_TOPIC_SELECTOR
        fields[
            vol.Optional(
                "will_payload", description={"suggested_value": will[CONF_PAYLOAD]}
            )
        ] = TEXT_SELECTOR
        fields[vol.Optional("will_qos", default=will[ATTR_QOS])] = QOS_SELECTOR
        fields[vol.Optional("will_retain", default=will[ATTR_RETAIN])] = (
            BOOLEAN_SELECTOR
        )

        return self.async_show_form(
            step_id="options",
            data_schema=vol.Schema(fields),
            errors=errors,
            last_step=True,
        )


class MQTTSubentryFlowHandler(ConfigSubentryFlow):
    """Handle MQTT subentry flow."""

    _subentry_data: MqttSubentryData
    _component_id: str | None = None

    @callback
    def update_component_fields(
        self,
        data_schema_fields: dict[str, PlatformField],
        merged_user_input: dict[str, Any],
    ) -> None:
        """Update the componment fields."""
        if TYPE_CHECKING:
            assert self._component_id is not None
        component_data = self._subentry_data["components"][self._component_id]
        # Remove the fields from the component data
        # if they are not in the schema and not in the user input
        config = calculate_merged_config(
            merged_user_input, data_schema_fields, component_data
        )
        for field in (
            field
            for field, platform_field in data_schema_fields.items()
            if field in (set(component_data) - set(config))
            and not platform_field.exclude_from_reconfig
            and not platform_field.include_in_config
        ):
            component_data.pop(field)
        component_data.update(merged_user_input)

    @callback
    def generate_names(self) -> tuple[str, str]:
        """Generate the device and full entity name."""
        if TYPE_CHECKING:
            assert self._component_id is not None
        device_name = self._subentry_data[CONF_DEVICE][CONF_NAME]
        if entity_name := self._subentry_data["components"][self._component_id].get(
            CONF_NAME
        ):
            full_entity_name: str = f"{device_name} {entity_name}"
        else:
            full_entity_name = device_name
        return device_name, full_entity_name

    @callback
    def get_suggested_values_from_component(
        self, data_schema: vol.Schema
    ) -> dict[str, Any]:
        """Get suggestions from component data based on the data schema."""
        if TYPE_CHECKING:
            assert self._component_id is not None
        component_data = self._subentry_data["components"][self._component_id]
        return {
            field_key: self.get_suggested_values_from_component(value.schema)
            if isinstance(value, section)
            else component_data.get(field_key)
            for field_key, value in data_schema.schema.items()
        }

    @callback
    def get_suggested_values_from_device_data(
        self, data_schema: vol.Schema
    ) -> dict[str, Any]:
        """Get suggestions from device data based on the data schema."""
        device_data = self._subentry_data["device"]
        return {
            field_key: self.get_suggested_values_from_device_data(value.schema)
            if isinstance(value, section)
            else device_data.get(field_key)
            for field_key, value in data_schema.schema.items()
        }

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Add a subentry."""
        self._subentry_data = MqttSubentryData(device=MqttDeviceData(), components={})
        return await self.async_step_device()

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Reconfigure a subentry."""
        reconfigure_subentry = self._get_reconfigure_subentry()
        self._subentry_data = cast(
            MqttSubentryData, deepcopy(dict(reconfigure_subentry.data))
        )
        return await self.async_step_summary_menu()

    async def async_step_device(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Add a new MQTT device."""
        errors: dict[str, Any] = {}
        device_data = self._subentry_data[CONF_DEVICE]
        data_schema = data_schema_from_fields(
            MQTT_DEVICE_PLATFORM_FIELDS,
            device_data=device_data,
            reconfig=True,
        )
        if user_input is not None:
            new_device_data: dict[str, Any] = user_input.copy()
            _, errors = validate_user_input(user_input, MQTT_DEVICE_PLATFORM_FIELDS)
            if "advanced_settings" in new_device_data:
                new_device_data |= new_device_data.pop("advanced_settings")
            if not errors:
                self._subentry_data[CONF_DEVICE] = cast(MqttDeviceData, new_device_data)
                if self.source == SOURCE_RECONFIGURE:
                    return await self.async_step_summary_menu()
                return await self.async_step_entity()
            data_schema = self.add_suggested_values_to_schema(
                data_schema, device_data if user_input is None else user_input
            )
        elif self.source == SOURCE_RECONFIGURE:
            data_schema = self.add_suggested_values_to_schema(
                data_schema,
                self.get_suggested_values_from_device_data(data_schema),
            )

        return self.async_show_form(
            step_id=CONF_DEVICE,
            data_schema=data_schema,
            errors=errors,
            last_step=False,
        )

    async def async_step_entity(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Add or edit an mqtt entity."""
        errors: dict[str, str] = {}
        data_schema_fields = COMMON_ENTITY_FIELDS
        entity_name_label: str = ""
        platform_label: str = ""
        component_data: dict[str, Any] | None = None
        if reconfig := (self._component_id is not None):
            component_data = self._subentry_data["components"][self._component_id]
            name: str | None = component_data.get(CONF_NAME)
            platform_label = f"{self._subentry_data['components'][self._component_id][CONF_PLATFORM]} "
            entity_name_label = f" ({name})" if name is not None else ""
        data_schema = data_schema_from_fields(data_schema_fields, reconfig=reconfig)
        if user_input is not None:
            merged_user_input, errors = validate_user_input(
                user_input, data_schema_fields, component_data=component_data
            )
            if not errors:
                if self._component_id is None:
                    self._component_id = uuid4().hex
                self._subentry_data["components"].setdefault(self._component_id, {})
                self.update_component_fields(data_schema_fields, merged_user_input)
                return await self.async_step_entity_platform_config()
            data_schema = self.add_suggested_values_to_schema(data_schema, user_input)
        elif self.source == SOURCE_RECONFIGURE and self._component_id is not None:
            data_schema = self.add_suggested_values_to_schema(
                data_schema,
                self.get_suggested_values_from_component(data_schema),
            )
        device_name = self._subentry_data[CONF_DEVICE][CONF_NAME]
        return self.async_show_form(
            step_id="entity",
            data_schema=data_schema,
            description_placeholders=TRANSLATION_DESCRIPTION_PLACEHOLDERS
            | {
                "mqtt_device": device_name,
                "entity_name_label": entity_name_label,
                "platform_label": platform_label,
            },
            errors=errors,
            last_step=False,
        )

    def _show_update_or_delete_form(self, step_id: str) -> SubentryFlowResult:
        """Help selecting an entity to update or delete."""
        device_name = self._subentry_data[CONF_DEVICE][CONF_NAME]
        entities = [
            SelectOptionDict(
                value=key,
                label=f"{device_name} {component_data.get(CONF_NAME, '-') or '-'}"
                f" ({component_data[CONF_PLATFORM]})",
            )
            for key, component_data in self._subentry_data["components"].items()
        ]
        data_schema = vol.Schema(
            {
                vol.Required("component"): SelectSelector(
                    SelectSelectorConfig(
                        options=entities,
                        mode=SelectSelectorMode.LIST,
                    )
                )
            }
        )
        return self.async_show_form(
            step_id=step_id, data_schema=data_schema, last_step=False
        )

    async def async_step_update_entity(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Select the entity to update."""
        if user_input:
            self._component_id = user_input["component"]
            return await self.async_step_entity()
        if len(self._subentry_data["components"]) == 1:
            # Return first key
            self._component_id = next(iter(self._subentry_data["components"]))
            return await self.async_step_entity()
        return self._show_update_or_delete_form("update_entity")

    async def async_step_delete_entity(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Select the entity to delete."""
        if user_input:
            del self._subentry_data["components"][user_input["component"]]
            return await self.async_step_summary_menu()
        return self._show_update_or_delete_form("delete_entity")

    async def async_step_entity_platform_config(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Configure platform entity details."""
        if TYPE_CHECKING:
            assert self._component_id is not None
        component_data = self._subentry_data["components"][self._component_id]
        platform = component_data[CONF_PLATFORM]
        data_schema_fields = (
            SHARED_PLATFORM_ENTITY_FIELDS | PLATFORM_ENTITY_FIELDS[platform]
        )
        errors: dict[str, str] = {}

        data_schema = data_schema_from_fields(
            data_schema_fields,
            reconfig=bool(
                {field for field in data_schema_fields if field in component_data}
            ),
            component_data=component_data,
            user_input=user_input,
        )
        if user_input is not None:
            # Test entity fields against the validator
            merged_user_input, errors = validate_user_input(
                user_input,
                data_schema_fields,
                component_data=component_data,
                config_validator=ENTITY_CONFIG_VALIDATOR[platform],
            )
            if not errors:
                self.update_component_fields(data_schema_fields, merged_user_input)
                return await self.async_step_mqtt_platform_config()

            data_schema = self.add_suggested_values_to_schema(data_schema, user_input)
        else:
            data_schema = self.add_suggested_values_to_schema(
                data_schema,
                self.get_suggested_values_from_component(data_schema),
            )

        device_name, full_entity_name = self.generate_names()
        return self.async_show_form(
            step_id="entity_platform_config",
            data_schema=data_schema,
            description_placeholders=TRANSLATION_DESCRIPTION_PLACEHOLDERS
            | {
                "mqtt_device": device_name,
                CONF_PLATFORM: platform,
                "entity": full_entity_name,
                "url": learn_more_url(platform),
            }
            | (user_input or {}),
            errors=errors,
            last_step=False,
        )

    async def async_step_mqtt_platform_config(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Configure entity platform MQTT details."""
        errors: dict[str, str] = {}
        if TYPE_CHECKING:
            assert self._component_id is not None
        component_data = self._subentry_data["components"][self._component_id]
        platform = component_data[CONF_PLATFORM]
        data_schema_fields = PLATFORM_MQTT_FIELDS[platform]
        data_schema = data_schema_from_fields(
            data_schema_fields,
            reconfig=bool(
                {field for field in data_schema_fields if field in component_data}
            ),
            component_data=component_data,
        )
        if user_input is not None:
            # Test entity fields against the validator
            merged_user_input, errors = validate_user_input(
                user_input,
                data_schema_fields,
                component_data=component_data,
                config_validator=ENTITY_CONFIG_VALIDATOR[platform],
            )
            if not errors:
                self.update_component_fields(data_schema_fields, merged_user_input)
                self._component_id = None
                if self.source == SOURCE_RECONFIGURE:
                    return await self.async_step_summary_menu()
                return self._async_create_subentry()

            data_schema = self.add_suggested_values_to_schema(data_schema, user_input)
        else:
            data_schema = self.add_suggested_values_to_schema(
                data_schema,
                self.get_suggested_values_from_component(data_schema),
            )
        device_name, full_entity_name = self.generate_names()
        return self.async_show_form(
            step_id="mqtt_platform_config",
            data_schema=data_schema,
            description_placeholders=TRANSLATION_DESCRIPTION_PLACEHOLDERS
            | {
                "mqtt_device": device_name,
                CONF_PLATFORM: platform,
                "entity": full_entity_name,
                "url": learn_more_url(platform),
            },
            errors=errors,
            last_step=False,
        )

    @callback
    def _async_update_component_data_defaults(self) -> None:
        """Update component data defaults."""
        for component_data in self._subentry_data["components"].values():
            platform = component_data[CONF_PLATFORM]
            platform_fields: dict[str, PlatformField] = (
                COMMON_ENTITY_FIELDS
                | SHARED_PLATFORM_ENTITY_FIELDS
                | PLATFORM_ENTITY_FIELDS[platform]
                | PLATFORM_MQTT_FIELDS[platform]
            )
            subentry_default_data = subentry_schema_default_data_from_fields(
                platform_fields,
                component_data,
            )
            component_data.update(subentry_default_data)
            for key, platform_field in platform_fields.items():
                if (
                    not platform_field.exclude_from_config
                    or platform_field.include_in_config
                ):
                    continue
                if key in component_data:
                    component_data.pop(key)

    @callback
    def _async_create_subentry(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Create a subentry for a new MQTT device."""
        device_name = self._subentry_data[CONF_DEVICE][CONF_NAME]
        component_data: dict[str, Any] = next(
            iter(self._subentry_data["components"].values())
        )
        platform = component_data[CONF_PLATFORM]
        entity_name: str | None
        if entity_name := component_data.get(CONF_NAME):
            full_entity_name: str = f"{device_name} {entity_name}"
        else:
            full_entity_name = device_name

        self._async_update_component_data_defaults()
        return self.async_create_entry(
            data=self._subentry_data,
            title=self._subentry_data[CONF_DEVICE][CONF_NAME],
            description_placeholders={
                "entity": full_entity_name,
                CONF_PLATFORM: platform,
            },
        )

    async def async_step_availability(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Configure availability options."""
        errors: dict[str, str] = {}
        validate_field(
            "availability_topic",
            valid_subscribe_topic,
            user_input,
            errors,
            "invalid_subscribe_topic",
        )
        validate_field(
            "availability_template",
            valid_subscribe_topic_template,
            user_input,
            errors,
            "invalid_template",
        )
        if not errors and user_input is not None:
            self._subentry_data.setdefault("availability", MqttAvailabilityData())
            self._subentry_data["availability"] = cast(MqttAvailabilityData, user_input)
            return await self.async_step_summary_menu()

        data_schema = SUBENTRY_AVAILABILITY_SCHEMA
        data_schema = self.add_suggested_values_to_schema(
            data_schema,
            dict(self._subentry_data.setdefault("availability", {}))
            if self.source == SOURCE_RECONFIGURE
            else user_input,
        )
        return self.async_show_form(
            step_id="availability",
            data_schema=data_schema,
            errors=errors,
            last_step=False,
        )

    async def async_step_summary_menu(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Show summary menu and decide to add more entities or to finish the flow."""
        self._component_id = None
        mqtt_device = self._subentry_data[CONF_DEVICE][CONF_NAME]
        mqtt_items = ", ".join(
            f"{mqtt_device} {component_data.get(CONF_NAME, '-') or '-'} "
            f"({component_data[CONF_PLATFORM]})"
            for component_data in self._subentry_data["components"].values()
        )
        menu_options = [
            "entity",
            "update_entity",
        ]
        if len(self._subentry_data["components"]) > 1:
            menu_options.append("delete_entity")
        menu_options.extend(["device", "availability"])
        self._async_update_component_data_defaults()
        menu_options.append(
            "save_changes"
            if self._subentry_data != self._get_reconfigure_subentry().data
            else "export"
        )
        return self.async_show_menu(
            step_id="summary_menu",
            menu_options=menu_options,
            description_placeholders={
                "mqtt_device": mqtt_device,
                "mqtt_items": mqtt_items,
            },
        )

    async def async_step_save_changes(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Save the changes made to the subentry."""
        entry = self._get_entry()
        subentry = self._get_reconfigure_subentry()
        entity_registry = er.async_get(self.hass)

        # When a component is removed from the MQTT device,
        # And we save the changes to the subentry,
        # we need to clean up stale entity registry entries.
        # The component id is used as a part of the unique id of the entity.
        for unique_id, platform in [
            (
                f"{subentry.subentry_id}_{component_id}",
                subentry.data["components"][component_id][CONF_PLATFORM],
            )
            for component_id in subentry.data["components"]
            if component_id not in self._subentry_data["components"]
        ]:
            if entity_id := entity_registry.async_get_entity_id(
                platform, DOMAIN, unique_id
            ):
                entity_registry.async_remove(entity_id)

        return self.async_update_and_abort(
            entry,
            subentry,
            data=self._subentry_data,
            title=self._subentry_data[CONF_DEVICE][CONF_NAME],
        )

    async def async_step_export(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Export the MQTT device config as YAML or discovery payload."""
        return self.async_show_menu(
            step_id="export",
            menu_options=["export_yaml", "export_discovery"],
        )

    async def async_step_export_yaml(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Export the MQTT device config as YAML."""
        if user_input is not None:
            return await self.async_step_summary_menu()

        subentry = self._get_reconfigure_subentry()
        mqtt_yaml_config_base: dict[str, list[dict[str, dict[str, Any]]]] = {DOMAIN: []}
        mqtt_yaml_config = mqtt_yaml_config_base[DOMAIN]

        for component_id, component_data in self._subentry_data["components"].items():
            component_config: dict[str, Any] = component_data.copy()
            component_config[CONF_UNIQUE_ID] = f"{subentry.subentry_id}_{component_id}"
            component_config[CONF_DEVICE] = {
                key: value
                for key, value in self._subentry_data["device"].items()
                if key != "mqtt_settings"
            } | {"identifiers": [subentry.subentry_id]}
            platform = component_config.pop(CONF_PLATFORM)
            component_config.update(self._subentry_data.get("availability", {}))
            component_config.update(
                self._subentry_data["device"].get("mqtt_settings", {}).copy()
            )
            for field in EXCLUDE_FROM_CONFIG_IF_NONE:
                if field in component_config and (
                    component_config[field] is None or component_config[field] == "None"
                ):
                    component_config.pop(field)
            mqtt_yaml_config.append({platform: component_config})

        yaml_config = yaml.dump(mqtt_yaml_config_base)
        data_schema = vol.Schema(
            {
                vol.Optional("yaml"): TEMPLATE_SELECTOR_READ_ONLY,
            }
        )
        data_schema = self.add_suggested_values_to_schema(
            data_schema=data_schema,
            suggested_values={"yaml": yaml_config},
        )
        return self.async_show_form(
            step_id="export_yaml",
            last_step=False,
            data_schema=data_schema,
            description_placeholders={"url": INTEGRATION_URL},
        )

    async def async_step_export_discovery(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Export the MQTT device config dor MQTT discovery."""

        if user_input is not None:
            return await self.async_step_summary_menu()

        subentry = self._get_reconfigure_subentry()
        discovery_topic = f"homeassistant/device/{subentry.subentry_id}/config"
        discovery_payload: dict[str, Any] = {}
        discovery_payload.update(self._subentry_data.get("availability", {}))
        discovery_payload["dev"] = {
            key: value
            for key, value in self._subentry_data["device"].items()
            if key != "mqtt_settings"
        } | {"identifiers": [subentry.subentry_id]}
        discovery_payload["o"] = {"name": "MQTT subentry export"}
        discovery_payload["cmps"] = {}

        for component_id, component_data in self._subentry_data["components"].items():
            component_config: dict[str, Any] = component_data.copy()
            component_config[CONF_UNIQUE_ID] = f"{subentry.subentry_id}_{component_id}"
            component_config.update(self._subentry_data.get("availability", {}))
            component_config.update(
                self._subentry_data["device"].get("mqtt_settings", {}).copy()
            )
            for field in EXCLUDE_FROM_CONFIG_IF_NONE:
                if field in component_config and (
                    component_config[field] is None or component_config[field] == "None"
                ):
                    component_config.pop(field)
            discovery_payload["cmps"][component_id] = component_config

        data_schema = vol.Schema(
            {
                vol.Optional("discovery_topic"): TEXT_SELECTOR_READ_ONLY,
                vol.Optional("discovery_payload"): TEMPLATE_SELECTOR_READ_ONLY,
            }
        )
        data_schema = self.add_suggested_values_to_schema(
            data_schema=data_schema,
            suggested_values={
                "discovery_topic": discovery_topic,
                "discovery_payload": json.dumps(discovery_payload, indent=2),
            },
        )
        return self.async_show_form(
            step_id="export_discovery",
            last_step=False,
            data_schema=data_schema,
            description_placeholders={"url": INTEGRATION_URL},
        )


@callback
def async_is_pem_data(data: bytes) -> bool:
    """Return True if data is in PEM format."""
    return (
        b"-----BEGIN CERTIFICATE-----" in data
        or b"-----BEGIN PRIVATE KEY-----" in data
        or b"-----BEGIN EC PRIVATE KEY-----" in data
        or b"-----BEGIN RSA PRIVATE KEY-----" in data
        or b"-----BEGIN ENCRYPTED PRIVATE KEY-----" in data
    )


class PEMType(IntEnum):
    """Type of PEM data."""

    CERTIFICATE = 1
    PRIVATE_KEY = 2


@callback
def async_convert_to_pem(
    data: bytes, pem_type: PEMType, password: str | None = None
) -> str | None:
    """Convert data to PEM format."""
    try:
        if async_is_pem_data(data):
            if not password:
                # Assume unencrypted PEM encoded private key
                return data.decode(DEFAULT_ENCODING)
            # Return decrypted PEM encoded private key
            return (
                load_pem_private_key(data, password=password.encode(DEFAULT_ENCODING))
                .private_bytes(
                    encoding=Encoding.PEM,
                    format=PrivateFormat.TraditionalOpenSSL,
                    encryption_algorithm=NoEncryption(),
                )
                .decode(DEFAULT_ENCODING)
            )
        # Convert from DER encoding to PEM
        if pem_type == PEMType.CERTIFICATE:
            return (
                load_der_x509_certificate(data)
                .public_bytes(
                    encoding=Encoding.PEM,
                )
                .decode(DEFAULT_ENCODING)
            )
        # Assume DER encoded private key
        pem_key_data: bytes = load_der_private_key(
            data, password.encode(DEFAULT_ENCODING) if password else None
        ).private_bytes(
            encoding=Encoding.PEM,
            format=PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=NoEncryption(),
        )
        return pem_key_data.decode("utf-8")
    except (TypeError, ValueError, SSLError):
        _LOGGER.exception("Error converting %s file data to PEM format", pem_type.name)
        return None


async def _get_uploaded_file(hass: HomeAssistant, id: str) -> bytes:
    """Get file content from uploaded certificate or key file."""

    def _proces_uploaded_file() -> bytes:
        with process_uploaded_file(hass, id) as file_path:
            return file_path.read_bytes()

    return await hass.async_add_executor_job(_proces_uploaded_file)


def _validate_pki_file(
    file_id: str | None, pem_data: str | None, errors: dict[str, str], error: str
) -> bool:
    """Return False if uploaded file could not be converted to PEM format."""
    if file_id and not pem_data:
        errors["base"] = error
        return False
    return True


async def async_get_broker_settings(  # noqa: C901
    flow: ConfigFlow | OptionsFlow,
    fields: OrderedDict[Any, Any],
    entry_config: MappingProxyType[str, Any] | None,
    user_input: dict[str, Any] | None,
    validated_user_input: dict[str, Any],
    errors: dict[str, str],
) -> bool:
    """Build the config flow schema to collect the broker settings.

    Shows advanced options if one or more are configured
    or when the advanced_broker_options checkbox was selected.
    Returns True when settings are collected successfully.
    """
    hass = flow.hass
    advanced_broker_options: bool = False
    user_input_basic: dict[str, Any] = {}
    current_config: dict[str, Any] = (
        entry_config.copy() if entry_config is not None else {}
    )

    async def _async_validate_broker_settings(
        config: dict[str, Any],
        user_input: dict[str, Any],
        validated_user_input: dict[str, Any],
        errors: dict[str, str],
    ) -> bool:
        """Additional validation on broker settings for better error messages."""

        # Get current certificate settings from config entry
        certificate: str | None = (
            "auto"
            if user_input.get(SET_CA_CERT, "off") == "auto"
            else config.get(CONF_CERTIFICATE)
            if user_input.get(SET_CA_CERT, "off") == "custom"
            else None
        )
        client_certificate: str | None = (
            config.get(CONF_CLIENT_CERT) if user_input.get(SET_CLIENT_CERT) else None
        )
        client_key: str | None = (
            config.get(CONF_CLIENT_KEY) if user_input.get(SET_CLIENT_CERT) else None
        )

        # Prepare entry update with uploaded files
        validated_user_input.update(user_input)
        client_certificate_id: str | None = user_input.get(CONF_CLIENT_CERT)
        client_key_id: str | None = user_input.get(CONF_CLIENT_KEY)
        # We do not store the private key password in the entry data
        client_key_password: str | None = validated_user_input.pop(
            CONF_CLIENT_KEY_PASSWORD, None
        )
        if (client_certificate_id and not client_key_id) or (
            not client_certificate_id and client_key_id
        ):
            errors["base"] = "invalid_inclusion"
            return False
        certificate_id: str | None = user_input.get(CONF_CERTIFICATE)
        if certificate_id:
            certificate_data_raw = await _get_uploaded_file(hass, certificate_id)
            certificate = async_convert_to_pem(
                certificate_data_raw, PEMType.CERTIFICATE
            )
        if not _validate_pki_file(
            certificate_id, certificate, errors, "bad_certificate"
        ):
            return False

        # Return to form for file upload CA cert or client cert and key
        if (
            (
                not client_certificate
                and user_input.get(SET_CLIENT_CERT)
                and not client_certificate_id
            )
            or (
                not certificate
                and user_input.get(SET_CA_CERT, "off") == "custom"
                and not certificate_id
            )
            or (
                user_input.get(CONF_TRANSPORT) == TRANSPORT_WEBSOCKETS
                and CONF_WS_PATH not in user_input
            )
        ):
            return False

        if client_certificate_id:
            client_certificate_data = await _get_uploaded_file(
                hass, client_certificate_id
            )
            client_certificate = async_convert_to_pem(
                client_certificate_data, PEMType.CERTIFICATE
            )
        if not _validate_pki_file(
            client_certificate_id, client_certificate, errors, "bad_client_cert"
        ):
            return False

        if client_key_id:
            client_key_data = await _get_uploaded_file(hass, client_key_id)
            client_key = async_convert_to_pem(
                client_key_data, PEMType.PRIVATE_KEY, password=client_key_password
            )
        if not _validate_pki_file(
            client_key_id, client_key, errors, "client_key_error"
        ):
            return False

        certificate_data: dict[str, Any] = {}
        if certificate:
            certificate_data[CONF_CERTIFICATE] = certificate
        if client_certificate:
            certificate_data[CONF_CLIENT_CERT] = client_certificate
            certificate_data[CONF_CLIENT_KEY] = client_key

        validated_user_input.update(certificate_data)
        await async_create_certificate_temp_files(hass, certificate_data)
        if error := await hass.async_add_executor_job(
            check_certicate_chain,
        ):
            errors["base"] = error
            return False

        if SET_CA_CERT in validated_user_input:
            del validated_user_input[SET_CA_CERT]
        if SET_CLIENT_CERT in validated_user_input:
            del validated_user_input[SET_CLIENT_CERT]
        if validated_user_input.get(CONF_TRANSPORT, TRANSPORT_TCP) == TRANSPORT_TCP:
            if CONF_WS_PATH in validated_user_input:
                del validated_user_input[CONF_WS_PATH]
            if CONF_WS_HEADERS in validated_user_input:
                del validated_user_input[CONF_WS_HEADERS]
            return True
        try:
            validated_user_input[CONF_WS_HEADERS] = json_loads(
                validated_user_input.get(CONF_WS_HEADERS, "{}")
            )
            schema = vol.Schema({cv.string: cv.template})
            schema(validated_user_input[CONF_WS_HEADERS])
        except (*JSON_DECODE_EXCEPTIONS, vol.MultipleInvalid):
            errors["base"] = "bad_ws_headers"
            return False
        return True

    if user_input:
        user_input_basic = user_input.copy()
        advanced_broker_options = user_input_basic.get(ADVANCED_OPTIONS, False)
        if ADVANCED_OPTIONS not in user_input or advanced_broker_options is False:
            if await _async_validate_broker_settings(
                current_config,
                user_input_basic,
                validated_user_input,
                errors,
            ):
                return True
        # Get defaults settings from previous post
        current_broker = user_input_basic.get(CONF_BROKER)
    else:
        # Get default settings from entry (if any)
        current_broker = current_config.get(CONF_BROKER)

    # Treat the previous post as an update of the current settings
    # (if there was a basic broker setup step)
    current_config.update(user_input_basic)

    # Get default settings for advanced broker options
    current_client_id = current_config.get(CONF_CLIENT_ID)
    current_keepalive = current_config.get(CONF_KEEPALIVE, DEFAULT_KEEPALIVE)
    current_ca_certificate = current_config.get(CONF_CERTIFICATE)
    current_client_certificate = current_config.get(CONF_CLIENT_CERT)
    current_client_key = current_config.get(CONF_CLIENT_KEY)
    current_tls_insecure = current_config.get(CONF_TLS_INSECURE, False)
    current_protocol = current_config.get(CONF_PROTOCOL, DEFAULT_PROTOCOL)
    current_transport = current_config.get(CONF_TRANSPORT, DEFAULT_TRANSPORT)
    current_ws_path = current_config.get(CONF_WS_PATH, DEFAULT_WS_PATH)
    current_ws_headers = (
        json_dumps(current_config.get(CONF_WS_HEADERS))
        if CONF_WS_HEADERS in current_config
        else None
    )
    advanced_broker_options |= bool(
        current_client_id
        or current_keepalive != DEFAULT_KEEPALIVE
        or current_ca_certificate
        or current_client_certificate
        or current_client_key
        or current_tls_insecure
        or current_protocol != DEFAULT_PROTOCOL
        or current_config.get(SET_CA_CERT, "off") != "off"
        or current_config.get(SET_CLIENT_CERT)
        or current_transport == TRANSPORT_WEBSOCKETS
    )

    # Build form
    fields[vol.Required(CONF_BROKER, default=current_broker)] = TEXT_SELECTOR
    # Allow the user to optionally provide the bridge serial when manual setup is used
    fields[
        vol.Optional(
            CONF_BRIDGE_SERIAL,
            description={"suggested_value": current_config.get(CONF_BRIDGE_SERIAL)},
        )
    ] = TEXT_SELECTOR
    # show advanced options checkbox if requested and
    # advanced options are enabled
    # or when the defaults of advanced options are overridden
    if not advanced_broker_options:
        if not flow.show_advanced_options:
            return False
        fields[
            vol.Optional(
                ADVANCED_OPTIONS,
            )
        ] = BOOLEAN_SELECTOR
        return False
    fields[
        vol.Optional(
            CONF_CLIENT_ID,
            description={"suggested_value": current_client_id},
        )
    ] = TEXT_SELECTOR
    fields[
        vol.Optional(
            CONF_KEEPALIVE,
            description={"suggested_value": current_keepalive},
        )
    ] = KEEPALIVE_SELECTOR
    fields[
        vol.Optional(
            SET_CLIENT_CERT,
            default=current_client_certificate is not None
            or current_config.get(SET_CLIENT_CERT) is True,
        )
    ] = BOOLEAN_SELECTOR
    if (
        current_client_certificate is not None
        or current_config.get(SET_CLIENT_CERT) is True
    ):
        fields[
            vol.Optional(
                CONF_CLIENT_CERT,
                description={"suggested_value": user_input_basic.get(CONF_CLIENT_CERT)},
            )
        ] = CERT_UPLOAD_SELECTOR
        fields[
            vol.Optional(
                CONF_CLIENT_KEY,
                description={"suggested_value": user_input_basic.get(CONF_CLIENT_KEY)},
            )
        ] = CERT_KEY_UPLOAD_SELECTOR
        fields[
            vol.Optional(
                CONF_CLIENT_KEY_PASSWORD,
                description={
                    "suggested_value": user_input_basic.get(CONF_CLIENT_KEY_PASSWORD)
                },
            )
        ] = PASSWORD_SELECTOR
    verification_mode = current_config.get(SET_CA_CERT) or (
        "off"
        if current_ca_certificate is None
        else "auto"
        if current_ca_certificate == "auto"
        else "custom"
    )
    fields[
        vol.Optional(
            SET_CA_CERT,
            default=verification_mode,
        )
    ] = BROKER_VERIFICATION_SELECTOR
    if current_ca_certificate is not None or verification_mode == "custom":
        fields[
            vol.Optional(
                CONF_CERTIFICATE,
                user_input_basic.get(CONF_CERTIFICATE),
            )
        ] = CA_CERT_UPLOAD_SELECTOR
    fields[
        vol.Optional(
            CONF_TLS_INSECURE,
            description={"suggested_value": current_tls_insecure},
        )
    ] = BOOLEAN_SELECTOR
    fields[
        vol.Optional(
            CONF_PROTOCOL,
            description={"suggested_value": current_protocol},
        )
    ] = PROTOCOL_SELECTOR
    fields[
        vol.Optional(
            CONF_TRANSPORT,
            description={"suggested_value": current_transport},
        )
    ] = TRANSPORT_SELECTOR
    if current_transport == TRANSPORT_WEBSOCKETS:
        fields[
            vol.Optional(CONF_WS_PATH, description={"suggested_value": current_ws_path})
        ] = TEXT_SELECTOR
        fields[
            vol.Optional(
                CONF_WS_HEADERS, description={"suggested_value": current_ws_headers}
            )
        ] = WS_HEADERS_SELECTOR

    # Show form
    return False


def try_connection(
    user_input: dict[str, Any],
) -> bool:
    """Test if we can connect to an MQTT broker."""
    # We don't import on the top because some integrations
    # should be able to optionally rely on MQTT.
    import paho.mqtt.client as mqtt  # noqa: PLC0415

    mqtt_client_setup = MqttClientSetup(user_input)
    mqtt_client_setup.setup()
    client = mqtt_client_setup.client

    result: queue.Queue[bool] = queue.Queue(maxsize=1)

    def on_connect(
        _mqttc: mqtt.Client,
        _userdata: None,
        _connect_flags: mqtt.ConnectFlags,
        reason_code: mqtt.ReasonCode,
        _properties: mqtt.Properties | None = None,
    ) -> None:
        """Handle connection result."""
        result.put(not reason_code.is_failure)

    client.on_connect = on_connect

    # Log the connection attempt (mask password)
    try:
        user = user_input.get(CONF_USERNAME)
        port = user_input.get(CONF_PORT)
        _LOGGER.debug(
            "Attempting MQTT connection to %s:%s as user=%s", user_input[CONF_BROKER], port, user
        )
    except Exception:  # noqa: BLE001
        _LOGGER.debug("Attempting MQTT connection (failed to extract details)")

    client.connect_async(user_input[CONF_BROKER], user_input[CONF_PORT])
    client.loop_start()

    try:
        success = result.get(timeout=MQTT_TIMEOUT)
        _LOGGER.debug("MQTT connect result for %s: %s", user_input[CONF_BROKER], success)
    except queue.Empty:
        _LOGGER.debug("MQTT connection attempt to %s timed out after %s seconds", user_input[CONF_BROKER], MQTT_TIMEOUT)
        return False
    else:
        return success
    finally:
        try:
            client.disconnect()
        except Exception:  # noqa: BLE001
            _LOGGER.debug("Error while disconnecting MQTT client", exc_info=True)
        try:
            client.loop_stop()
        except Exception:  # noqa: BLE001
            _LOGGER.debug("Error while stopping MQTT loop", exc_info=True)


def check_certicate_chain() -> str | None:
    """Check the MQTT certificates."""
    if client_certificate := get_file_path(CONF_CLIENT_CERT):
        try:
            with open(client_certificate, "rb") as client_certificate_file:
                load_pem_x509_certificate(client_certificate_file.read())
        except ValueError:
            return "bad_client_cert"
    # Check we can serialize the private key file
    if private_key := get_file_path(CONF_CLIENT_KEY):
        try:
            with open(private_key, "rb") as client_key_file:
                load_pem_private_key(client_key_file.read(), password=None)
        except (TypeError, ValueError):
            return "client_key_error"
    # Check the certificate chain
    context = SSLContext(PROTOCOL_TLS_CLIENT)
    if client_certificate and private_key:
        try:
            context.load_cert_chain(client_certificate, private_key)
        except SSLError:
            return "bad_client_cert_key"
    # try to load the custom CA file
    if (ca_cert := get_file_path(CONF_CERTIFICATE)) is None:
        return None

    try:
        context.load_verify_locations(ca_cert)
    except SSLError:
        return "bad_certificate"
    return None
