"""Config flow for MQTT."""

from __future__ import annotations

import asyncio
from collections import OrderedDict
from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass
from enum import IntEnum
import logging
import queue
from ssl import PROTOCOL_TLS_CLIENT, SSLContext, SSLError
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, cast
from uuid import uuid4

from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    load_der_private_key,
    load_pem_private_key,
)
from cryptography.x509 import load_der_x509_certificate, load_pem_x509_certificate
import voluptuous as vol

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.button import ButtonDeviceClass
from homeassistant.components.file_upload import process_uploaded_file
from homeassistant.components.hassio import AddonError, AddonManager, AddonState
from homeassistant.components.light import (
    DEFAULT_MAX_KELVIN,
    DEFAULT_MIN_KELVIN,
    VALID_COLOR_MODES,
    valid_supported_color_modes,
)
from homeassistant.components.sensor import (
    CONF_STATE_CLASS,
    DEVICE_CLASS_UNITS,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.components.switch import SwitchDeviceClass
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
    ATTR_MODEL,
    ATTR_MODEL_ID,
    ATTR_NAME,
    ATTR_SW_VERSION,
    CONF_BRIGHTNESS,
    CONF_CLIENT_ID,
    CONF_DEVICE,
    CONF_DEVICE_CLASS,
    CONF_DISCOVERY,
    CONF_EFFECT,
    CONF_HOST,
    CONF_NAME,
    CONF_OPTIMISTIC,
    CONF_PASSWORD,
    CONF_PAYLOAD,
    CONF_PAYLOAD_OFF,
    CONF_PAYLOAD_ON,
    CONF_PLATFORM,
    CONF_PORT,
    CONF_PROTOCOL,
    CONF_STATE_TEMPLATE,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_USERNAME,
    CONF_VALUE_TEMPLATE,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import AbortFlow, SectionConfig, section
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.hassio import is_hassio
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
from homeassistant.helpers.service_info.hassio import HassioServiceInfo
from homeassistant.util.json import JSON_DECODE_EXCEPTIONS, json_loads

from .addon import get_addon_manager
from .client import MqttClientSetup
from .const import (
    ATTR_PAYLOAD,
    ATTR_QOS,
    ATTR_RETAIN,
    ATTR_TOPIC,
    CONF_AVAILABILITY_TEMPLATE,
    CONF_AVAILABILITY_TOPIC,
    CONF_BIRTH_MESSAGE,
    CONF_BLUE_TEMPLATE,
    CONF_BRIGHTNESS_COMMAND_TEMPLATE,
    CONF_BRIGHTNESS_COMMAND_TOPIC,
    CONF_BRIGHTNESS_SCALE,
    CONF_BRIGHTNESS_STATE_TOPIC,
    CONF_BRIGHTNESS_TEMPLATE,
    CONF_BRIGHTNESS_VALUE_TEMPLATE,
    CONF_BROKER,
    CONF_CERTIFICATE,
    CONF_CLIENT_CERT,
    CONF_CLIENT_KEY,
    CONF_COLOR_MODE_STATE_TOPIC,
    CONF_COLOR_MODE_VALUE_TEMPLATE,
    CONF_COLOR_TEMP_COMMAND_TEMPLATE,
    CONF_COLOR_TEMP_COMMAND_TOPIC,
    CONF_COLOR_TEMP_KELVIN,
    CONF_COLOR_TEMP_STATE_TOPIC,
    CONF_COLOR_TEMP_TEMPLATE,
    CONF_COLOR_TEMP_VALUE_TEMPLATE,
    CONF_COMMAND_OFF_TEMPLATE,
    CONF_COMMAND_ON_TEMPLATE,
    CONF_COMMAND_TEMPLATE,
    CONF_COMMAND_TOPIC,
    CONF_DISCOVERY_PREFIX,
    CONF_EFFECT_COMMAND_TEMPLATE,
    CONF_EFFECT_COMMAND_TOPIC,
    CONF_EFFECT_LIST,
    CONF_EFFECT_STATE_TOPIC,
    CONF_EFFECT_TEMPLATE,
    CONF_EFFECT_VALUE_TEMPLATE,
    CONF_ENTITY_PICTURE,
    CONF_EXPIRE_AFTER,
    CONF_FLASH,
    CONF_FLASH_TIME_LONG,
    CONF_FLASH_TIME_SHORT,
    CONF_GREEN_TEMPLATE,
    CONF_HS_COMMAND_TEMPLATE,
    CONF_HS_COMMAND_TOPIC,
    CONF_HS_STATE_TOPIC,
    CONF_HS_VALUE_TEMPLATE,
    CONF_KEEPALIVE,
    CONF_LAST_RESET_VALUE_TEMPLATE,
    CONF_MAX_KELVIN,
    CONF_MIN_KELVIN,
    CONF_OFF_DELAY,
    CONF_ON_COMMAND_TYPE,
    CONF_OPTIONS,
    CONF_PAYLOAD_AVAILABLE,
    CONF_PAYLOAD_NOT_AVAILABLE,
    CONF_PAYLOAD_PRESS,
    CONF_QOS,
    CONF_RED_TEMPLATE,
    CONF_RETAIN,
    CONF_RGB_COMMAND_TEMPLATE,
    CONF_RGB_COMMAND_TOPIC,
    CONF_RGB_STATE_TOPIC,
    CONF_RGB_VALUE_TEMPLATE,
    CONF_RGBW_COMMAND_TEMPLATE,
    CONF_RGBW_COMMAND_TOPIC,
    CONF_RGBW_STATE_TOPIC,
    CONF_RGBW_VALUE_TEMPLATE,
    CONF_RGBWW_COMMAND_TEMPLATE,
    CONF_RGBWW_COMMAND_TOPIC,
    CONF_RGBWW_STATE_TOPIC,
    CONF_RGBWW_VALUE_TEMPLATE,
    CONF_SCHEMA,
    CONF_STATE_TOPIC,
    CONF_STATE_VALUE_TEMPLATE,
    CONF_SUGGESTED_DISPLAY_PRECISION,
    CONF_SUPPORTED_COLOR_MODES,
    CONF_TLS_INSECURE,
    CONF_TRANSITION,
    CONF_TRANSPORT,
    CONF_WHITE_COMMAND_TOPIC,
    CONF_WHITE_SCALE,
    CONF_WILL_MESSAGE,
    CONF_WS_HEADERS,
    CONF_WS_PATH,
    CONF_XY_COMMAND_TEMPLATE,
    CONF_XY_COMMAND_TOPIC,
    CONF_XY_STATE_TOPIC,
    CONF_XY_VALUE_TEMPLATE,
    CONFIG_ENTRY_MINOR_VERSION,
    CONFIG_ENTRY_VERSION,
    DEFAULT_BIRTH,
    DEFAULT_DISCOVERY,
    DEFAULT_ENCODING,
    DEFAULT_KEEPALIVE,
    DEFAULT_ON_COMMAND_TYPE,
    DEFAULT_PAYLOAD_AVAILABLE,
    DEFAULT_PAYLOAD_NOT_AVAILABLE,
    DEFAULT_PAYLOAD_OFF,
    DEFAULT_PAYLOAD_ON,
    DEFAULT_PAYLOAD_PRESS,
    DEFAULT_PORT,
    DEFAULT_PREFIX,
    DEFAULT_PROTOCOL,
    DEFAULT_QOS,
    DEFAULT_TRANSPORT,
    DEFAULT_WILL,
    DEFAULT_WS_PATH,
    DOMAIN,
    SUPPORTED_PROTOCOLS,
    TRANSPORT_TCP,
    TRANSPORT_WEBSOCKETS,
    VALUES_ON_COMMAND_TYPE,
    Platform,
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

BOOLEAN_SELECTOR = BooleanSelector()
TEXT_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT))
PUBLISH_TOPIC_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT))
PORT_SELECTOR = vol.All(
    NumberSelector(NumberSelectorConfig(mode=NumberSelectorMode.BOX, min=1, max=65535)),
    vol.Coerce(int),
)
PASSWORD_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))
QOS_SELECTOR = NumberSelector(
    NumberSelectorConfig(mode=NumberSelectorMode.BOX, min=0, max=2)
)
KEEPALIVE_SELECTOR = vol.All(
    NumberSelector(
        NumberSelectorConfig(
            mode=NumberSelectorMode.BOX, min=15, step="any", unit_of_measurement="sec"
        )
    ),
    vol.Coerce(int),
)
PROTOCOL_SELECTOR = SelectSelector(
    SelectSelectorConfig(
        options=SUPPORTED_PROTOCOLS,
        mode=SelectSelectorMode.DROPDOWN,
    )
)
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
CA_VERIFICATION_MODES = [
    "off",
    "auto",
    "custom",
]
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
CERT_UPLOAD_SELECTOR = FileSelector(
    FileSelectorConfig(accept=".pem,.crt,.cer,.der,application/x-x509-user-cert")
)
KEY_UPLOAD_SELECTOR = FileSelector(
    FileSelectorConfig(accept=".pem,.key,.der,.pk8,application/pkcs8")
)

# Subentry selectors
SUBENTRY_PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.LIGHT,
    Platform.NOTIFY,
    Platform.SENSOR,
    Platform.SWITCH,
]
SUBENTRY_PLATFORM_SELECTOR = SelectSelector(
    SelectSelectorConfig(
        options=[platform.value for platform in SUBENTRY_PLATFORMS],
        mode=SelectSelectorMode.DROPDOWN,
        translation_key=CONF_PLATFORM,
    )
)
TEMPLATE_SELECTOR = TemplateSelector(TemplateSelectorConfig())

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

# Sensor specific selectors
SENSOR_DEVICE_CLASS_SELECTOR = SelectSelector(
    SelectSelectorConfig(
        options=[device_class.value for device_class in SensorDeviceClass],
        mode=SelectSelectorMode.DROPDOWN,
        translation_key="device_class_sensor",
        sort=True,
    )
)
BINARY_SENSOR_DEVICE_CLASS_SELECTOR = SelectSelector(
    SelectSelectorConfig(
        options=[device_class.value for device_class in BinarySensorDeviceClass],
        mode=SelectSelectorMode.DROPDOWN,
        translation_key="device_class_binary_sensor",
        sort=True,
    )
)
BUTTON_DEVICE_CLASS_SELECTOR = SelectSelector(
    SelectSelectorConfig(
        options=[device_class.value for device_class in ButtonDeviceClass],
        mode=SelectSelectorMode.DROPDOWN,
        translation_key="device_class_button",
        sort=True,
    )
)
SENSOR_STATE_CLASS_SELECTOR = SelectSelector(
    SelectSelectorConfig(
        options=[device_class.value for device_class in SensorStateClass],
        mode=SelectSelectorMode.DROPDOWN,
        translation_key=CONF_STATE_CLASS,
    )
)
OPTIONS_SELECTOR = SelectSelector(
    SelectSelectorConfig(
        options=[],
        custom_value=True,
        multiple=True,
    )
)
SUGGESTED_DISPLAY_PRECISION_SELECTOR = NumberSelector(
    NumberSelectorConfig(mode=NumberSelectorMode.BOX, min=0, max=9)
)
TIMEOUT_SELECTOR = NumberSelector(
    NumberSelectorConfig(mode=NumberSelectorMode.BOX, min=0)
)

# Switch specific selectors
SWITCH_DEVICE_CLASS_SELECTOR = SelectSelector(
    SelectSelectorConfig(
        options=[device_class.value for device_class in SwitchDeviceClass],
        mode=SelectSelectorMode.DROPDOWN,
        translation_key="device_class_switch",
    )
)

# Light specific selectors
LIGHT_SCHEMA_SELECTOR = SelectSelector(
    SelectSelectorConfig(
        options=["basic", "json", "template"],
        translation_key="light_schema",
    )
)
KELVIN_SELECTOR = NumberSelector(
    NumberSelectorConfig(
        mode=NumberSelectorMode.BOX,
        min=1000,
        max=10000,
        step="any",
        unit_of_measurement="K",
    )
)
SCALE_SELECTOR = NumberSelector(
    NumberSelectorConfig(
        mode=NumberSelectorMode.BOX,
        min=1,
        max=255,
        step=1,
    )
)
FLASH_TIME_SELECTOR = NumberSelector(
    NumberSelectorConfig(
        mode=NumberSelectorMode.BOX,
        min=1,
    )
)
ON_COMMAND_TYPE_SELECTOR = SelectSelector(
    SelectSelectorConfig(
        options=VALUES_ON_COMMAND_TYPE,
        mode=SelectSelectorMode.DROPDOWN,
        translation_key=CONF_ON_COMMAND_TYPE,
        sort=True,
    )
)
SUPPORTED_COLOR_MODES_SELECTOR = SelectSelector(
    SelectSelectorConfig(
        options=[platform.value for platform in VALID_COLOR_MODES],
        mode=SelectSelectorMode.DROPDOWN,
        translation_key=CONF_SUPPORTED_COLOR_MODES,
        multiple=True,
        sort=True,
    )
)


@callback
def validate_sensor_platform_config(
    config: dict[str, Any],
) -> dict[str, str]:
    """Validate the sensor options, state and device class config."""
    errors: dict[str, str] = {}
    # Only allow `options` to be set for `enum` sensors
    # to limit the possible sensor values
    if config.get(CONF_OPTIONS) is not None:
        if config.get(CONF_STATE_CLASS) or config.get(CONF_UNIT_OF_MEASUREMENT):
            errors[CONF_OPTIONS] = "options_not_allowed_with_state_class_or_uom"

        if (device_class := config.get(CONF_DEVICE_CLASS)) != SensorDeviceClass.ENUM:
            errors[CONF_DEVICE_CLASS] = "options_device_class_enum"

    if (
        (device_class := config.get(CONF_DEVICE_CLASS)) == SensorDeviceClass.ENUM
        and errors is not None
        and CONF_OPTIONS not in config
    ):
        errors[CONF_OPTIONS] = "options_with_enum_device_class"

    if (
        device_class in DEVICE_CLASS_UNITS
        and (unit_of_measurement := config.get(CONF_UNIT_OF_MEASUREMENT)) is None
        and errors is not None
    ):
        # Do not allow an empty unit of measurement in a subentry data flow
        errors[CONF_UNIT_OF_MEASUREMENT] = "uom_required_for_device_class"
        return errors

    if (
        device_class is not None
        and device_class in DEVICE_CLASS_UNITS
        and unit_of_measurement not in DEVICE_CLASS_UNITS[device_class]
    ):
        errors[CONF_UNIT_OF_MEASUREMENT] = "invalid_uom"

    return errors


@dataclass(frozen=True, kw_only=True)
class PlatformField:
    """Stores a platform config field schema, required flag and validator."""

    selector: Selector[Any] | Callable[..., Selector[Any]]
    required: bool
    validator: Callable[..., Any]
    error: str | None = None
    default: str | int | bool | None | vol.Undefined = vol.UNDEFINED
    is_schema_default: bool = False
    exclude_from_reconfig: bool = False
    conditions: tuple[dict[str, Any], ...] | None = None
    custom_filtering: bool = False
    section: str | None = None


@callback
def unit_of_measurement_selector(user_data: dict[str, Any | None]) -> Selector:
    """Return a context based unit of measurement selector."""
    if (
        user_data is None
        or (device_class := user_data.get(CONF_DEVICE_CLASS)) is None
        or device_class not in DEVICE_CLASS_UNITS
    ):
        return TEXT_SELECTOR
    return SelectSelector(
        SelectSelectorConfig(
            options=[str(uom) for uom in DEVICE_CLASS_UNITS[device_class]],
            sort=True,
            custom_value=True,
        )
    )


@callback
def validate_light_platform_config(user_data: dict[str, Any]) -> dict[str, str]:
    """Validate MQTT light configuration."""
    errors: dict[str, Any] = {}
    if user_data.get(CONF_MIN_KELVIN, DEFAULT_MIN_KELVIN) >= user_data.get(
        CONF_MAX_KELVIN, DEFAULT_MAX_KELVIN
    ):
        errors[CONF_MAX_KELVIN] = "max_below_min_kelvin"
        errors[CONF_MIN_KELVIN] = "max_below_min_kelvin"
    return errors


COMMON_ENTITY_FIELDS = {
    CONF_PLATFORM: PlatformField(
        selector=SUBENTRY_PLATFORM_SELECTOR,
        required=True,
        validator=str,
        exclude_from_reconfig=True,
    ),
    CONF_NAME: PlatformField(
        selector=TEXT_SELECTOR,
        required=False,
        validator=str,
        exclude_from_reconfig=True,
        default=None,
    ),
    CONF_ENTITY_PICTURE: PlatformField(
        selector=TEXT_SELECTOR, required=False, validator=cv.url, error="invalid_url"
    ),
}

PLATFORM_ENTITY_FIELDS = {
    Platform.BINARY_SENSOR.value: {
        CONF_DEVICE_CLASS: PlatformField(
            selector=BINARY_SENSOR_DEVICE_CLASS_SELECTOR,
            required=False,
            validator=str,
        ),
    },
    Platform.BUTTON.value: {
        CONF_DEVICE_CLASS: PlatformField(
            selector=BUTTON_DEVICE_CLASS_SELECTOR,
            required=False,
            validator=str,
        ),
    },
    Platform.NOTIFY.value: {},
    Platform.SENSOR.value: {
        CONF_DEVICE_CLASS: PlatformField(
            selector=SENSOR_DEVICE_CLASS_SELECTOR, required=False, validator=str
        ),
        CONF_STATE_CLASS: PlatformField(
            selector=SENSOR_STATE_CLASS_SELECTOR, required=False, validator=str
        ),
        CONF_UNIT_OF_MEASUREMENT: PlatformField(
            selector=unit_of_measurement_selector,
            required=False,
            validator=str,
            custom_filtering=True,
        ),
        CONF_SUGGESTED_DISPLAY_PRECISION: PlatformField(
            selector=SUGGESTED_DISPLAY_PRECISION_SELECTOR,
            required=False,
            validator=cv.positive_int,
            section="advanced_settings",
        ),
        CONF_OPTIONS: PlatformField(
            selector=OPTIONS_SELECTOR,
            required=False,
            validator=cv.ensure_list,
            conditions=({"device_class": "enum"},),
        ),
    },
    Platform.SWITCH.value: {
        CONF_DEVICE_CLASS: PlatformField(
            selector=SWITCH_DEVICE_CLASS_SELECTOR, required=False, validator=str
        ),
    },
    Platform.LIGHT.value: {
        CONF_SCHEMA: PlatformField(
            selector=LIGHT_SCHEMA_SELECTOR,
            required=True,
            validator=str,
            default="basic",
            exclude_from_reconfig=True,
        ),
        CONF_COLOR_TEMP_KELVIN: PlatformField(
            selector=BOOLEAN_SELECTOR,
            required=True,
            validator=bool,
            default=True,
            is_schema_default=True,
        ),
    },
}
PLATFORM_MQTT_FIELDS = {
    Platform.BINARY_SENSOR.value: {
        CONF_STATE_TOPIC: PlatformField(
            selector=TEXT_SELECTOR,
            required=True,
            validator=valid_subscribe_topic,
            error="invalid_subscribe_topic",
        ),
        CONF_VALUE_TEMPLATE: PlatformField(
            selector=TEMPLATE_SELECTOR,
            required=False,
            validator=cv.template,
            error="invalid_template",
        ),
        CONF_PAYLOAD_OFF: PlatformField(
            selector=TEXT_SELECTOR,
            required=False,
            validator=str,
            default=DEFAULT_PAYLOAD_OFF,
        ),
        CONF_PAYLOAD_ON: PlatformField(
            selector=TEXT_SELECTOR,
            required=False,
            validator=str,
            default=DEFAULT_PAYLOAD_ON,
        ),
        CONF_EXPIRE_AFTER: PlatformField(
            selector=TIMEOUT_SELECTOR,
            required=False,
            validator=cv.positive_int,
            section="advanced_settings",
        ),
        CONF_OFF_DELAY: PlatformField(
            selector=TIMEOUT_SELECTOR,
            required=False,
            validator=cv.positive_int,
            section="advanced_settings",
        ),
    },
    Platform.BUTTON.value: {
        CONF_COMMAND_TOPIC: PlatformField(
            selector=TEXT_SELECTOR,
            required=True,
            validator=valid_publish_topic,
            error="invalid_publish_topic",
        ),
        CONF_COMMAND_TEMPLATE: PlatformField(
            selector=TEMPLATE_SELECTOR,
            required=False,
            validator=cv.template,
            error="invalid_template",
        ),
        CONF_PAYLOAD_PRESS: PlatformField(
            selector=TEXT_SELECTOR,
            required=False,
            validator=str,
            default=DEFAULT_PAYLOAD_PRESS,
        ),
        CONF_RETAIN: PlatformField(
            selector=BOOLEAN_SELECTOR, required=False, validator=bool
        ),
    },
    Platform.NOTIFY.value: {
        CONF_COMMAND_TOPIC: PlatformField(
            selector=TEXT_SELECTOR,
            required=True,
            validator=valid_publish_topic,
            error="invalid_publish_topic",
        ),
        CONF_COMMAND_TEMPLATE: PlatformField(
            selector=TEMPLATE_SELECTOR,
            required=False,
            validator=cv.template,
            error="invalid_template",
        ),
        CONF_RETAIN: PlatformField(
            selector=BOOLEAN_SELECTOR, required=False, validator=bool
        ),
    },
    Platform.SENSOR.value: {
        CONF_STATE_TOPIC: PlatformField(
            selector=TEXT_SELECTOR,
            required=True,
            validator=valid_subscribe_topic,
            error="invalid_subscribe_topic",
        ),
        CONF_VALUE_TEMPLATE: PlatformField(
            selector=TEMPLATE_SELECTOR,
            required=False,
            validator=cv.template,
            error="invalid_template",
        ),
        CONF_LAST_RESET_VALUE_TEMPLATE: PlatformField(
            selector=TEMPLATE_SELECTOR,
            required=False,
            validator=cv.template,
            error="invalid_template",
            conditions=({CONF_STATE_CLASS: "total"},),
        ),
        CONF_EXPIRE_AFTER: PlatformField(
            selector=TIMEOUT_SELECTOR,
            required=False,
            validator=cv.positive_int,
            section="advanced_settings",
        ),
    },
    Platform.SWITCH.value: {
        CONF_COMMAND_TOPIC: PlatformField(
            selector=TEXT_SELECTOR,
            required=True,
            validator=valid_publish_topic,
            error="invalid_publish_topic",
        ),
        CONF_COMMAND_TEMPLATE: PlatformField(
            selector=TEMPLATE_SELECTOR,
            required=False,
            validator=cv.template,
            error="invalid_template",
        ),
        CONF_STATE_TOPIC: PlatformField(
            selector=TEXT_SELECTOR,
            required=False,
            validator=valid_subscribe_topic,
            error="invalid_subscribe_topic",
        ),
        CONF_VALUE_TEMPLATE: PlatformField(
            selector=TEMPLATE_SELECTOR,
            required=False,
            validator=cv.template,
            error="invalid_template",
        ),
        CONF_RETAIN: PlatformField(
            selector=BOOLEAN_SELECTOR, required=False, validator=bool
        ),
        CONF_OPTIMISTIC: PlatformField(
            selector=BOOLEAN_SELECTOR, required=False, validator=bool
        ),
    },
    Platform.LIGHT.value: {
        CONF_COMMAND_TOPIC: PlatformField(
            selector=TEXT_SELECTOR,
            required=True,
            validator=valid_publish_topic,
            error="invalid_publish_topic",
        ),
        CONF_COMMAND_ON_TEMPLATE: PlatformField(
            selector=TEMPLATE_SELECTOR,
            required=True,
            validator=cv.template,
            error="invalid_template",
            conditions=({CONF_SCHEMA: "template"},),
        ),
        CONF_COMMAND_OFF_TEMPLATE: PlatformField(
            selector=TEMPLATE_SELECTOR,
            required=True,
            validator=cv.template,
            error="invalid_template",
            conditions=({CONF_SCHEMA: "template"},),
        ),
        CONF_ON_COMMAND_TYPE: PlatformField(
            selector=ON_COMMAND_TYPE_SELECTOR,
            required=False,
            validator=str,
            default=DEFAULT_ON_COMMAND_TYPE,
            conditions=({CONF_SCHEMA: "basic"},),
        ),
        CONF_STATE_TOPIC: PlatformField(
            selector=TEXT_SELECTOR,
            required=False,
            validator=valid_subscribe_topic,
            error="invalid_subscribe_topic",
        ),
        CONF_STATE_VALUE_TEMPLATE: PlatformField(
            selector=TEMPLATE_SELECTOR,
            required=False,
            validator=cv.template,
            error="invalid_template",
            conditions=({CONF_SCHEMA: "basic"},),
        ),
        CONF_STATE_TEMPLATE: PlatformField(
            selector=TEMPLATE_SELECTOR,
            required=False,
            validator=cv.template,
            error="invalid_template",
            conditions=({CONF_SCHEMA: "template"},),
        ),
        CONF_SUPPORTED_COLOR_MODES: PlatformField(
            selector=SUPPORTED_COLOR_MODES_SELECTOR,
            required=False,
            validator=valid_supported_color_modes,
            error="invalid_supported_color_modes",
            conditions=({CONF_SCHEMA: "json"},),
        ),
        CONF_OPTIMISTIC: PlatformField(
            selector=BOOLEAN_SELECTOR, required=False, validator=bool
        ),
        CONF_RETAIN: PlatformField(
            selector=BOOLEAN_SELECTOR,
            required=False,
            validator=bool,
            conditions=({CONF_SCHEMA: "basic"},),
        ),
        CONF_BRIGHTNESS: PlatformField(
            selector=BOOLEAN_SELECTOR,
            required=False,
            validator=bool,
            conditions=({CONF_SCHEMA: "json"},),
            section="light_brightness_settings",
        ),
        CONF_BRIGHTNESS_COMMAND_TOPIC: PlatformField(
            selector=TEXT_SELECTOR,
            required=False,
            validator=valid_publish_topic,
            error="invalid_publish_topic",
            conditions=({CONF_SCHEMA: "basic"},),
            section="light_brightness_settings",
        ),
        CONF_BRIGHTNESS_COMMAND_TEMPLATE: PlatformField(
            selector=TEMPLATE_SELECTOR,
            required=False,
            validator=cv.template,
            error="invalid_template",
            conditions=({CONF_SCHEMA: "basic"},),
            section="light_brightness_settings",
        ),
        CONF_BRIGHTNESS_STATE_TOPIC: PlatformField(
            selector=TEXT_SELECTOR,
            required=False,
            validator=valid_subscribe_topic,
            error="invalid_subscribe_topic",
            conditions=({CONF_SCHEMA: "basic"},),
            section="light_brightness_settings",
        ),
        CONF_PAYLOAD_OFF: PlatformField(
            selector=TEXT_SELECTOR,
            required=False,
            validator=str,
            default=DEFAULT_PAYLOAD_OFF,
            conditions=({CONF_SCHEMA: "basic"},),
        ),
        CONF_PAYLOAD_ON: PlatformField(
            selector=TEXT_SELECTOR,
            required=False,
            validator=str,
            default=DEFAULT_PAYLOAD_ON,
            conditions=({CONF_SCHEMA: "basic"},),
        ),
        CONF_BRIGHTNESS_VALUE_TEMPLATE: PlatformField(
            selector=TEMPLATE_SELECTOR,
            required=False,
            validator=cv.template,
            error="invalid_template",
            conditions=({CONF_SCHEMA: "basic"},),
            section="light_brightness_settings",
        ),
        CONF_BRIGHTNESS_SCALE: PlatformField(
            selector=SCALE_SELECTOR,
            required=False,
            validator=cv.positive_int,
            default=255,
            conditions=(
                {CONF_SCHEMA: "basic"},
                {CONF_SCHEMA: "json"},
            ),
            section="light_brightness_settings",
        ),
        CONF_COLOR_MODE_STATE_TOPIC: PlatformField(
            selector=TEXT_SELECTOR,
            required=False,
            validator=valid_subscribe_topic,
            error="invalid_subscribe_topic",
            conditions=({CONF_SCHEMA: "basic"},),
            section="light_color_mode_settings",
        ),
        CONF_COLOR_MODE_VALUE_TEMPLATE: PlatformField(
            selector=TEMPLATE_SELECTOR,
            required=False,
            validator=cv.template,
            error="invalid_template",
            conditions=({CONF_SCHEMA: "basic"},),
            section="light_color_mode_settings",
        ),
        CONF_COLOR_TEMP_COMMAND_TOPIC: PlatformField(
            selector=TEXT_SELECTOR,
            required=False,
            validator=valid_publish_topic,
            error="invalid_publish_topic",
            conditions=({CONF_SCHEMA: "basic"},),
            section="light_color_temp_settings",
        ),
        CONF_COLOR_TEMP_COMMAND_TEMPLATE: PlatformField(
            selector=TEMPLATE_SELECTOR,
            required=False,
            validator=cv.template,
            error="invalid_template",
            conditions=({CONF_SCHEMA: "basic"},),
            section="light_color_temp_settings",
        ),
        CONF_COLOR_TEMP_STATE_TOPIC: PlatformField(
            selector=TEXT_SELECTOR,
            required=False,
            validator=valid_subscribe_topic,
            error="invalid_subscribe_topic",
            conditions=({CONF_SCHEMA: "basic"},),
            section="light_color_temp_settings",
        ),
        CONF_COLOR_TEMP_VALUE_TEMPLATE: PlatformField(
            selector=TEMPLATE_SELECTOR,
            required=False,
            validator=cv.template,
            error="invalid_template",
            conditions=({CONF_SCHEMA: "basic"},),
            section="light_color_temp_settings",
        ),
        CONF_BRIGHTNESS_TEMPLATE: PlatformField(
            selector=TEMPLATE_SELECTOR,
            required=False,
            validator=cv.template,
            error="invalid_template",
            conditions=({CONF_SCHEMA: "template"},),
        ),
        CONF_RED_TEMPLATE: PlatformField(
            selector=TEMPLATE_SELECTOR,
            required=False,
            validator=cv.template,
            error="invalid_template",
            conditions=({CONF_SCHEMA: "template"},),
        ),
        CONF_GREEN_TEMPLATE: PlatformField(
            selector=TEMPLATE_SELECTOR,
            required=False,
            validator=cv.template,
            error="invalid_template",
            conditions=({CONF_SCHEMA: "template"},),
        ),
        CONF_BLUE_TEMPLATE: PlatformField(
            selector=TEMPLATE_SELECTOR,
            required=False,
            validator=cv.template,
            error="invalid_template",
            conditions=({CONF_SCHEMA: "template"},),
        ),
        CONF_COLOR_TEMP_TEMPLATE: PlatformField(
            selector=TEMPLATE_SELECTOR,
            required=False,
            validator=cv.template,
            error="invalid_template",
            conditions=({CONF_SCHEMA: "template"},),
        ),
        CONF_HS_COMMAND_TOPIC: PlatformField(
            selector=TEXT_SELECTOR,
            required=False,
            validator=valid_publish_topic,
            error="invalid_publish_topic",
            conditions=({CONF_SCHEMA: "basic"},),
            section="light_hs_settings",
        ),
        CONF_HS_COMMAND_TEMPLATE: PlatformField(
            selector=TEMPLATE_SELECTOR,
            required=False,
            validator=cv.template,
            error="invalid_template",
            conditions=({CONF_SCHEMA: "basic"},),
            section="light_hs_settings",
        ),
        CONF_HS_STATE_TOPIC: PlatformField(
            selector=TEXT_SELECTOR,
            required=False,
            validator=valid_subscribe_topic,
            error="invalid_subscribe_topic",
            conditions=({CONF_SCHEMA: "basic"},),
            section="light_hs_settings",
        ),
        CONF_HS_VALUE_TEMPLATE: PlatformField(
            selector=TEMPLATE_SELECTOR,
            required=False,
            validator=cv.template,
            error="invalid_template",
            conditions=({CONF_SCHEMA: "basic"},),
            section="light_hs_settings",
        ),
        CONF_RGB_COMMAND_TOPIC: PlatformField(
            selector=TEXT_SELECTOR,
            required=False,
            validator=valid_publish_topic,
            error="invalid_publish_topic",
            conditions=({CONF_SCHEMA: "basic"},),
            section="light_rgb_settings",
        ),
        CONF_RGB_COMMAND_TEMPLATE: PlatformField(
            selector=TEMPLATE_SELECTOR,
            required=False,
            validator=cv.template,
            error="invalid_template",
            conditions=({CONF_SCHEMA: "basic"},),
            section="light_rgb_settings",
        ),
        CONF_RGB_STATE_TOPIC: PlatformField(
            selector=TEXT_SELECTOR,
            required=False,
            validator=valid_subscribe_topic,
            error="invalid_subscribe_topic",
            conditions=({CONF_SCHEMA: "basic"},),
            section="light_rgb_settings",
        ),
        CONF_RGB_VALUE_TEMPLATE: PlatformField(
            selector=TEMPLATE_SELECTOR,
            required=False,
            validator=cv.template,
            error="invalid_template",
            conditions=({CONF_SCHEMA: "basic"},),
            section="light_rgb_settings",
        ),
        CONF_RGBW_COMMAND_TOPIC: PlatformField(
            selector=TEXT_SELECTOR,
            required=False,
            validator=valid_publish_topic,
            error="invalid_publish_topic",
            conditions=({CONF_SCHEMA: "basic"},),
            section="light_rgbw_settings",
        ),
        CONF_RGBW_COMMAND_TEMPLATE: PlatformField(
            selector=TEMPLATE_SELECTOR,
            required=False,
            validator=cv.template,
            error="invalid_template",
            conditions=({CONF_SCHEMA: "basic"},),
            section="light_rgbw_settings",
        ),
        CONF_RGBW_STATE_TOPIC: PlatformField(
            selector=TEXT_SELECTOR,
            required=False,
            validator=valid_subscribe_topic,
            error="invalid_subscribe_topic",
            conditions=({CONF_SCHEMA: "basic"},),
            section="light_rgbw_settings",
        ),
        CONF_RGBW_VALUE_TEMPLATE: PlatformField(
            selector=TEMPLATE_SELECTOR,
            required=False,
            validator=cv.template,
            error="invalid_template",
            conditions=({CONF_SCHEMA: "basic"},),
            section="light_rgbw_settings",
        ),
        CONF_RGBWW_COMMAND_TOPIC: PlatformField(
            selector=TEXT_SELECTOR,
            required=False,
            validator=valid_publish_topic,
            error="invalid_publish_topic",
            conditions=({CONF_SCHEMA: "basic"},),
            section="light_rgbww_settings",
        ),
        CONF_RGBWW_COMMAND_TEMPLATE: PlatformField(
            selector=TEMPLATE_SELECTOR,
            required=False,
            validator=cv.template,
            error="invalid_template",
            conditions=({CONF_SCHEMA: "basic"},),
            section="light_rgbww_settings",
        ),
        CONF_RGBWW_STATE_TOPIC: PlatformField(
            selector=TEXT_SELECTOR,
            required=False,
            validator=valid_subscribe_topic,
            error="invalid_subscribe_topic",
            conditions=({CONF_SCHEMA: "basic"},),
            section="light_rgbww_settings",
        ),
        CONF_RGBWW_VALUE_TEMPLATE: PlatformField(
            selector=TEMPLATE_SELECTOR,
            required=False,
            validator=cv.template,
            error="invalid_template",
            conditions=({CONF_SCHEMA: "basic"},),
            section="light_rgbww_settings",
        ),
        CONF_XY_COMMAND_TOPIC: PlatformField(
            selector=TEXT_SELECTOR,
            required=False,
            validator=valid_publish_topic,
            error="invalid_publish_topic",
            conditions=({CONF_SCHEMA: "basic"},),
            section="light_xy_settings",
        ),
        CONF_XY_COMMAND_TEMPLATE: PlatformField(
            selector=TEMPLATE_SELECTOR,
            required=False,
            validator=cv.template,
            error="invalid_template",
            conditions=({CONF_SCHEMA: "basic"},),
            section="light_xy_settings",
        ),
        CONF_XY_STATE_TOPIC: PlatformField(
            selector=TEXT_SELECTOR,
            required=False,
            validator=valid_subscribe_topic,
            error="invalid_subscribe_topic",
            conditions=({CONF_SCHEMA: "basic"},),
            section="light_xy_settings",
        ),
        CONF_XY_VALUE_TEMPLATE: PlatformField(
            selector=TEMPLATE_SELECTOR,
            required=False,
            validator=cv.template,
            error="invalid_template",
            conditions=({CONF_SCHEMA: "basic"},),
            section="light_xy_settings",
        ),
        CONF_WHITE_COMMAND_TOPIC: PlatformField(
            selector=TEXT_SELECTOR,
            required=False,
            validator=valid_publish_topic,
            error="invalid_publish_topic",
            conditions=({CONF_SCHEMA: "basic"},),
            section="light_white_settings",
        ),
        CONF_WHITE_SCALE: PlatformField(
            selector=SCALE_SELECTOR,
            required=False,
            validator=cv.positive_int,
            default=255,
            conditions=(
                {CONF_SCHEMA: "basic"},
                {CONF_SCHEMA: "json"},
            ),
            section="light_white_settings",
        ),
        CONF_EFFECT: PlatformField(
            selector=BOOLEAN_SELECTOR,
            required=False,
            validator=bool,
            conditions=({CONF_SCHEMA: "json"},),
            section="light_effect_settings",
        ),
        CONF_EFFECT_COMMAND_TOPIC: PlatformField(
            selector=TEXT_SELECTOR,
            required=False,
            validator=valid_publish_topic,
            error="invalid_publish_topic",
            conditions=({CONF_SCHEMA: "basic"},),
            section="light_effect_settings",
        ),
        CONF_EFFECT_COMMAND_TEMPLATE: PlatformField(
            selector=TEMPLATE_SELECTOR,
            required=False,
            validator=cv.template,
            error="invalid_template",
            conditions=({CONF_SCHEMA: "basic"},),
            section="light_effect_settings",
        ),
        CONF_EFFECT_STATE_TOPIC: PlatformField(
            selector=TEXT_SELECTOR,
            required=False,
            validator=valid_subscribe_topic,
            error="invalid_subscribe_topic",
            conditions=({CONF_SCHEMA: "basic"},),
            section="light_effect_settings",
        ),
        CONF_EFFECT_TEMPLATE: PlatformField(
            selector=TEMPLATE_SELECTOR,
            required=False,
            validator=cv.template,
            error="invalid_template",
            conditions=({CONF_SCHEMA: "template"},),
            section="light_effect_settings",
        ),
        CONF_EFFECT_VALUE_TEMPLATE: PlatformField(
            selector=TEMPLATE_SELECTOR,
            required=False,
            validator=cv.template,
            error="invalid_template",
            conditions=({CONF_SCHEMA: "basic"},),
            section="light_effect_settings",
        ),
        CONF_EFFECT_LIST: PlatformField(
            selector=OPTIONS_SELECTOR,
            required=False,
            validator=cv.ensure_list,
            section="light_effect_settings",
        ),
        CONF_FLASH: PlatformField(
            selector=BOOLEAN_SELECTOR,
            required=False,
            default=False,
            validator=cv.boolean,
            conditions=({CONF_SCHEMA: "json"},),
            section="advanced_settings",
        ),
        CONF_FLASH_TIME_SHORT: PlatformField(
            selector=FLASH_TIME_SELECTOR,
            required=False,
            validator=cv.positive_int,
            default=2,
            conditions=({CONF_SCHEMA: "json"},),
            section="advanced_settings",
        ),
        CONF_FLASH_TIME_LONG: PlatformField(
            selector=FLASH_TIME_SELECTOR,
            required=False,
            validator=cv.positive_int,
            default=10,
            conditions=({CONF_SCHEMA: "json"},),
            section="advanced_settings",
        ),
        CONF_TRANSITION: PlatformField(
            selector=BOOLEAN_SELECTOR,
            required=False,
            default=False,
            validator=cv.boolean,
            conditions=({CONF_SCHEMA: "json"},),
            section="advanced_settings",
        ),
        CONF_MAX_KELVIN: PlatformField(
            selector=KELVIN_SELECTOR,
            required=False,
            validator=cv.positive_int,
            default=DEFAULT_MAX_KELVIN,
            section="advanced_settings",
        ),
        CONF_MIN_KELVIN: PlatformField(
            selector=KELVIN_SELECTOR,
            required=False,
            validator=cv.positive_int,
            default=DEFAULT_MIN_KELVIN,
            section="advanced_settings",
        ),
    },
}
ENTITY_CONFIG_VALIDATOR: dict[
    str,
    Callable[[dict[str, Any]], dict[str, str]] | None,
] = {
    Platform.BINARY_SENSOR.value: None,
    Platform.BUTTON.value: None,
    Platform.LIGHT.value: validate_light_platform_config,
    Platform.NOTIFY.value: None,
    Platform.SENSOR.value: validate_sensor_platform_config,
    Platform.SWITCH.value: None,
}

MQTT_DEVICE_PLATFORM_FIELDS = {
    ATTR_NAME: PlatformField(selector=TEXT_SELECTOR, required=True, validator=str),
    ATTR_SW_VERSION: PlatformField(
        selector=TEXT_SELECTOR, required=False, validator=str
    ),
    ATTR_HW_VERSION: PlatformField(
        selector=TEXT_SELECTOR, required=False, validator=str
    ),
    ATTR_MODEL: PlatformField(selector=TEXT_SELECTOR, required=False, validator=str),
    ATTR_MODEL_ID: PlatformField(selector=TEXT_SELECTOR, required=False, validator=str),
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

REAUTH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): TEXT_SELECTOR,
        vol.Required(CONF_PASSWORD): PASSWORD_SELECTOR,
    }
)
PWD_NOT_CHANGED = "__**password_not_changed**__"


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


@callback
def validate_field(
    field: str,
    validator: Callable[..., Any],
    user_input: dict[str, Any] | None,
    errors: dict[str, str],
    error: str,
) -> None:
    """Validate a single field."""
    if user_input is None or field not in user_input:
        return
    try:
        validator(user_input[field])
    except (ValueError, vol.Error, vol.Invalid):
        errors[field] = error


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
            validator(value)
        except (ValueError, vol.Error, vol.Invalid):
            errors[field] = data_schema_fields[field].error or "invalid_input"

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
def data_schema_from_fields(
    data_schema_fields: dict[str, PlatformField],
    reconfig: bool,
    component_data: dict[str, Any] | None = None,
    user_input: dict[str, Any] | None = None,
    device_data: MqttDeviceData | None = None,
) -> vol.Schema:
    """Generate custom data schema from platform fields or device data."""
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
    for schema_section in sections:
        data_schema_element = {
            vol.Required(field_name, default=field_details.default)
            if field_details.required
            else vol.Optional(
                field_name,
                default=field_details.default
                if field_details.default is not None
                else vol.UNDEFINED,
            ): field_details.selector(component_data_with_user_input)  # type: ignore[operator]
            if field_details.custom_filtering
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
        if not data_element_options:
            continue
        if schema_section is None:
            data_schema.update(data_schema_element)
            continue
        collapsed = (
            not any(
                (default := data_schema_fields[str(option)].default) is vol.UNDEFINED
                or component_data_with_user_input[str(option)] != default
                for option in data_element_options
                if option in component_data_with_user_input
            )
            if component_data_with_user_input is not None
            else True
        )
        data_schema[vol.Optional(schema_section)] = section(
            vol.Schema(data_schema_element), SectionConfig({"collapsed": collapsed})
        )

    # Reset all fields from the component_data not in the schema
    if component_data:
        filtered_fields = (
            set(data_schema_fields) - all_data_element_options - no_reconfig_options
        )
        for field in filtered_fields:
            if field in component_data:
                del component_data[field]
    return vol.Schema(data_schema)


@callback
def subentry_schema_default_data_from_fields(
    data_schema_fields: dict[str, PlatformField],
    component_data: dict[str, Any],
) -> dict[str, Any]:
    """Generate custom data schema from platform fields or device data."""
    return {
        key: field.default
        for key, field in data_schema_fields.items()
        if field.is_schema_default
        or (field.default is not vol.UNDEFINED and key not in component_data)
    }


class FlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    # Can be bumped to version 2.1 with HA Core 2026.1.0
    VERSION = CONFIG_ENTRY_VERSION  # 1
    MINOR_VERSION = CONFIG_ENTRY_MINOR_VERSION  # 2

    _hassio_discovery: dict[str, Any] | None = None
    _addon_manager: AddonManager

    def __init__(self) -> None:
        """Set up flow instance."""
        self.install_task: asyncio.Task | None = None
        self.start_task: asyncio.Task | None = None

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

    async def _async_install_addon(self) -> None:
        """Install the Mosquitto Mqtt broker add-on."""
        addon_manager: AddonManager = get_addon_manager(self.hass)
        await addon_manager.async_schedule_install_addon()

    async def async_step_install_failed(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add-on installation failed."""
        return self.async_abort(
            reason="addon_install_failed",
            description_placeholders={"addon": self._addon_manager.addon_name},
        )

    async def async_step_install_addon(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Install Mosquitto Broker add-on."""
        if self.install_task is None:
            self.install_task = self.hass.async_create_task(self._async_install_addon())

        if not self.install_task.done():
            return self.async_show_progress(
                step_id="install_addon",
                progress_action="install_addon",
                progress_task=self.install_task,
            )

        try:
            await self.install_task
        except AddonError as err:
            _LOGGER.error(err)
            return self.async_show_progress_done(next_step_id="install_failed")
        finally:
            self.install_task = None

        return self.async_show_progress_done(next_step_id="start_addon")

    async def async_step_start_failed(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add-on start failed."""
        return self.async_abort(
            reason="addon_start_failed",
            description_placeholders={"addon": self._addon_manager.addon_name},
        )

    async def async_step_start_addon(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Start Mosquitto Broker add-on."""
        if not self.start_task:
            self.start_task = self.hass.async_create_task(self._async_start_addon())
        if not self.start_task.done():
            return self.async_show_progress(
                step_id="start_addon",
                progress_action="start_addon",
                progress_task=self.start_task,
            )
        try:
            await self.start_task
        except AddonError as err:
            _LOGGER.error(err)
            return self.async_show_progress_done(next_step_id="start_failed")
        finally:
            self.start_task = None

        return self.async_show_progress_done(next_step_id="setup_entry_from_discovery")

    async def _async_get_config_and_try(self) -> dict[str, Any] | None:
        """Get the MQTT add-on discovery info and try the connection."""
        if self._hassio_discovery is not None:
            return self._hassio_discovery
        addon_manager: AddonManager = get_addon_manager(self.hass)
        try:
            addon_discovery_config = (
                await addon_manager.async_get_addon_discovery_info()
            )
            config: dict[str, Any] = {
                CONF_BROKER: addon_discovery_config[CONF_HOST],
                CONF_PORT: addon_discovery_config[CONF_PORT],
                CONF_USERNAME: addon_discovery_config.get(CONF_USERNAME),
                CONF_PASSWORD: addon_discovery_config.get(CONF_PASSWORD),
                CONF_DISCOVERY: DEFAULT_DISCOVERY,
            }
        except AddonError:
            # We do not have discovery information yet
            return None
        if await self.hass.async_add_executor_job(
            try_connection,
            config,
        ):
            self._hassio_discovery = config
            return config
        return None

    async def _async_start_addon(self) -> None:
        """Start the Mosquitto Broker add-on."""
        addon_manager: AddonManager = get_addon_manager(self.hass)
        await addon_manager.async_schedule_start_addon()

        # Sleep some seconds to let the add-on start properly before connecting.
        for _ in range(ADDON_SETUP_TIMEOUT_ROUNDS):
            await asyncio.sleep(ADDON_SETUP_TIMEOUT)
            # Finish setup using discovery info to test the connection
            if await self._async_get_config_and_try():
                break
        else:
            raise AddonError(
                translation_domain=DOMAIN,
                translation_key="addon_start_failed",
                translation_placeholders={"addon": addon_manager.addon_name},
            )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        if is_hassio(self.hass):
            # Offer to set up broker add-on if supervisor is available
            self._addon_manager = get_addon_manager(self.hass)
            return self.async_show_menu(
                step_id="user",
                menu_options=["addon", "broker"],
                description_placeholders={"addon": self._addon_manager.addon_name},
            )

        # Start up a flow for manual setup
        return await self.async_step_broker()

    async def async_step_setup_entry_from_discovery(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Set up mqtt entry from discovery info."""
        if (config := await self._async_get_config_and_try()) is not None:
            return self.async_create_entry(
                title=self._addon_manager.addon_name,
                data=config,
            )

        raise AbortFlow(
            "addon_connection_failed",
            description_placeholders={"addon": self._addon_manager.addon_name},
        )

    async def async_step_addon(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Install and start MQTT broker add-on."""
        addon_manager = self._addon_manager

        try:
            addon_info = await addon_manager.async_get_addon_info()
        except AddonError as err:
            raise AbortFlow(
                "addon_info_failed",
                description_placeholders={"addon": self._addon_manager.addon_name},
            ) from err

        if addon_info.state == AddonState.RUNNING:
            # Finish setup using discovery info
            return await self.async_step_setup_entry_from_discovery()

        if addon_info.state == AddonState.NOT_RUNNING:
            return await self.async_step_start_addon()

        # Install the add-on and start it
        return await self.async_step_install_addon()

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle re-authentication with MQTT broker."""
        if is_hassio(self.hass):
            # Check if entry setup matches the add-on discovery config
            addon_manager = get_addon_manager(self.hass)
            try:
                addon_discovery_config = (
                    await addon_manager.async_get_addon_discovery_info()
                )
            except AddonError:
                # Follow manual flow if we have an error
                pass
            else:
                # Check if the addon secrets need to be renewed.
                # This will repair the config entry,
                # in case the official Mosquitto Broker addon was re-installed.
                if (
                    entry_data[CONF_BROKER] == addon_discovery_config[CONF_HOST]
                    and entry_data[CONF_PORT] == addon_discovery_config[CONF_PORT]
                    and entry_data.get(CONF_USERNAME)
                    == (username := addon_discovery_config.get(CONF_USERNAME))
                    and entry_data.get(CONF_PASSWORD)
                    != (password := addon_discovery_config.get(CONF_PASSWORD))
                ):
                    _LOGGER.info(
                        "Executing autorecovery %s add-on secrets",
                        addon_manager.addon_name,
                    )
                    return await self.async_step_reauth_confirm(
                        user_input={CONF_USERNAME: username, CONF_PASSWORD: password}
                    )

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
                return self.async_update_reload_and_abort(
                    reauth_entry, data=new_entry_data
                )

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
        if await async_get_broker_settings(
            self,
            fields,
            reconfigure_entry.data if is_reconfigure else None,
            user_input,
            validated_user_input,
            errors,
        ):
            if is_reconfigure:
                validated_user_input = update_password_from_user_input(
                    reconfigure_entry.data.get(CONF_PASSWORD), validated_user_input
                )

            can_connect = await self.hass.async_add_executor_job(
                try_connection,
                validated_user_input,
            )

            if can_connect:
                if is_reconfigure:
                    return self.async_update_reload_and_abort(
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

    async def async_step_hassio(
        self, discovery_info: HassioServiceInfo
    ) -> ConfigFlowResult:
        """Receive a Hass.io discovery or process setup after addon install."""
        await self._async_handle_discovery_without_unique_id()

        self._hassio_discovery = discovery_info.config

        return await self.async_step_hassio_confirm()

    async def async_step_hassio_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm a Hass.io discovery."""
        errors: dict[str, str] = {}
        if TYPE_CHECKING:
            assert self._hassio_discovery

        if user_input is not None:
            data: dict[str, Any] = self._hassio_discovery.copy()
            data[CONF_BROKER] = data.pop(CONF_HOST)
            can_connect = await self.hass.async_add_executor_job(
                try_connection,
                data,
            )

            if can_connect:
                return self.async_create_entry(
                    title=data["addon"],
                    data={
                        CONF_BROKER: data[CONF_BROKER],
                        CONF_PORT: data[CONF_PORT],
                        CONF_USERNAME: data.get(CONF_USERNAME),
                        CONF_PASSWORD: data.get(CONF_PASSWORD),
                        CONF_DISCOVERY: DEFAULT_DISCOVERY,
                    },
                )

            errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="hassio_confirm",
            description_placeholders={"addon": self._hassio_discovery["addon"]},
            errors=errors,
        )


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
            _, errors = validate_user_input(user_input, MQTT_DEVICE_PLATFORM_FIELDS)
            if not errors:
                self._subentry_data[CONF_DEVICE] = cast(MqttDeviceData, user_input)
                if self.source == SOURCE_RECONFIGURE:
                    return await self.async_step_summary_menu()
                return await self.async_step_entity()
        data_schema = self.add_suggested_values_to_schema(
            data_schema, device_data if user_input is None else user_input
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
            description_placeholders={
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
                label=f"{device_name} {component_data.get(CONF_NAME, '-')}"
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
        data_schema_fields = PLATFORM_ENTITY_FIELDS[platform]
        errors: dict[str, str] = {}

        data_schema = data_schema_from_fields(
            data_schema_fields,
            reconfig=bool(
                {field for field in data_schema_fields if field in component_data}
            ),
            component_data=component_data,
            user_input=user_input,
        )
        if not data_schema.schema:
            return await self.async_step_mqtt_platform_config()
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
            description_placeholders={
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
            description_placeholders={
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
            subentry_default_data = subentry_schema_default_data_from_fields(
                COMMON_ENTITY_FIELDS
                | PLATFORM_ENTITY_FIELDS[platform]
                | PLATFORM_MQTT_FIELDS[platform],
                component_data,
            )
            component_data.update(subentry_default_data)

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
            f"{mqtt_device} {component_data.get(CONF_NAME, '-')} ({component_data[CONF_PLATFORM]})"
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
        if self._subentry_data != self._get_reconfigure_subentry().data:
            menu_options.append("save_changes")
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
        current_port = user_input_basic.get(CONF_PORT, DEFAULT_PORT)
        current_user = user_input_basic.get(CONF_USERNAME)
        current_pass = user_input_basic.get(CONF_PASSWORD)
    else:
        # Get default settings from entry (if any)
        current_broker = current_config.get(CONF_BROKER)
        current_port = current_config.get(CONF_PORT, DEFAULT_PORT)
        current_user = current_config.get(CONF_USERNAME)
        # Return the sentinel password to avoid exposure
        current_entry_pass = current_config.get(CONF_PASSWORD)
        current_pass = PWD_NOT_CHANGED if current_entry_pass else None

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
    fields[vol.Required(CONF_PORT, default=current_port)] = PORT_SELECTOR
    fields[
        vol.Optional(
            CONF_USERNAME,
            description={"suggested_value": current_user},
        )
    ] = TEXT_SELECTOR
    fields[
        vol.Optional(
            CONF_PASSWORD,
            description={"suggested_value": current_pass},
        )
    ] = PASSWORD_SELECTOR
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
        ] = KEY_UPLOAD_SELECTOR
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
    import paho.mqtt.client as mqtt  # pylint: disable=import-outside-toplevel

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

    client.connect_async(user_input[CONF_BROKER], user_input[CONF_PORT])
    client.loop_start()

    try:
        return result.get(timeout=MQTT_TIMEOUT)
    except queue.Empty:
        return False
    finally:
        client.disconnect()
        client.loop_stop()


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
