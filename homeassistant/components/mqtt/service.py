"""Support for MQTT services."""

from collections import OrderedDict
from collections.abc import Callable, Sequence
from copy import copy, deepcopy
import functools
import logging
from typing import Any, TypedDict, cast

import voluptuous as vol

from homeassistant.backports.enum import StrEnum
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_MODE, CONF_DESCRIPTION, CONF_NAME, CONF_TYPE
from homeassistant.core import HomeAssistant, ServiceCall, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.selector import SelectOptionDict, SelectSelectorMode
from homeassistant.helpers.service import async_set_service_schema
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType, TemplateVarsType
from homeassistant.util import slugify

from . import async_publish
from .config import MQTT_BASE_SCHEMA
from .const import (
    ATTR_DISCOVERY_HASH,
    CONF_COMMAND_TEMPLATE,
    CONF_COMMAND_TOPIC,
    CONF_ENCODING,
    CONF_OPTIONS,
    CONF_QOS,
    CONF_RETAIN,
    CONF_SCHEMA,
    DEFAULT_RETAIN,
    DOMAIN,
)
from .discovery import MQTTDiscoveryPayload
from .mixins import (
    MqttDiscoveryDeviceUpdate,
    async_setup_entry_helper,
    send_discovery_done,
)
from .models import MqttCommandTemplate, PublishPayloadType
from .util import get_mqtt_data, valid_publish_topic

_LOGGER = logging.getLogger(__name__)

LOG_NAME = "Service"

SERVICE = "service"

CONF_EXAMPLE = "example"
CONF_REQUIRED = "required"
CONF_EXCLUSIVE = "exclusive"
CONF_INCLUSIVE = "inclusive"
CONF_MULTIPLE = "multiple"
CONF_CUSTOM_VALUE = "custom_value"


class UserServiceArgType(StrEnum):
    """Selectors to be used for the user service schema."""

    BOOL = "bool"
    DROPDOWN = "dropdown"
    INT = "int"
    FLOAT = "float"
    STRING = "string"
    MULTILINE = "multiline"
    PASSWORD = "password"
    SELECT = "select"


class SelectSelectorArgs(TypedDict, total=False):
    """Arguments for select selector."""

    options: Sequence[str] | Sequence[SelectOptionDict]
    custom_value: bool
    multiple: bool
    mode: str


class ServiceArgMetadata(TypedDict, total=False):
    """Metadata for services."""

    name: str
    type: str
    description: str
    required: bool
    multiple: bool
    custom_value: bool
    example: str
    selector: dict[str, SelectSelectorArgs | dict[str, Any] | None]
    validator: Any


ARG_TYPE_METADATA = {
    UserServiceArgType.BOOL: ServiceArgMetadata(
        validator=cv.boolean,
        example="False",
        selector={"boolean": None},
    ),
    UserServiceArgType.DROPDOWN: ServiceArgMetadata(
        validator=cv.ensure_list,
        example="",
        selector={"select": SelectSelectorArgs(mode=SelectSelectorMode.DROPDOWN.value)},
    ),
    UserServiceArgType.INT: ServiceArgMetadata(
        validator=vol.Coerce(int),
        example="42",
        selector={"number": {ATTR_MODE: "box"}},
    ),
    UserServiceArgType.FLOAT: ServiceArgMetadata(
        validator=vol.Coerce(float),
        example="12.3",
        selector={"number": {ATTR_MODE: "box", "step": 1e-3}},
    ),
    UserServiceArgType.MULTILINE: ServiceArgMetadata(
        validator=cv.string,
        example="Abc",
        selector={"text": {"multiline": True}},
    ),
    UserServiceArgType.PASSWORD: ServiceArgMetadata(
        validator=cv.string,
        example="s3cretp@assw0rd",
        selector={"text": {"type": "password"}},
    ),
    UserServiceArgType.STRING: ServiceArgMetadata(
        validator=cv.string,
        example="Abc",
        selector={"text": None},
    ),
    UserServiceArgType.SELECT: ServiceArgMetadata(
        validator=cv.ensure_list,
        example="",
        selector={"select": SelectSelectorArgs()},
    ),
}

SELECT_SELECTORS = [UserServiceArgType.DROPDOWN, UserServiceArgType.SELECT]


def validate_options(
    options: list[Any],
) -> Sequence[str] | Sequence[SelectOptionDict]:
    """Validate selector select options."""
    if not options:
        raise vol.Invalid("Required options are missing")
    if isinstance(options[0], str):
        return options

    schema = vol.Schema(
        {vol.Required("value"): cv.string, vol.Required("label"): cv.string}
    )
    return [
        SelectOptionDict(value=option["value"], label=option["label"])
        for option in options
        if schema(option)
    ]


SERVICE_ARG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): vol.All(
            cv.string, vol.NotIn(["dump", "publish", "reload"])
        ),
        vol.Required(CONF_TYPE): vol.In(
            [arg_type.value for arg_type in UserServiceArgType]
        ),
        vol.Optional(CONF_DESCRIPTION): cv.string,
        vol.Optional(CONF_EXAMPLE): cv.string,
        vol.Optional(CONF_OPTIONS): vol.All(cv.ensure_list, validate_options),
        vol.Optional(CONF_MULTIPLE): cv.boolean,
        vol.Optional(CONF_CUSTOM_VALUE): cv.boolean,
        vol.Optional(CONF_REQUIRED): cv.boolean,
        vol.Optional(CONF_EXCLUSIVE): cv.string,
        vol.Optional(CONF_INCLUSIVE): cv.string,
    }
)
PLATFORM_SCHEMA = MQTT_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_COMMAND_TOPIC): valid_publish_topic,
        vol.Required(CONF_COMMAND_TEMPLATE): cv.template,
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_DESCRIPTION): cv.string,
        vol.Optional(CONF_SCHEMA): vol.All(
            [SERVICE_ARG_SCHEMA],
            cv.ensure_list,
        ),
        vol.Optional(CONF_RETAIN, default=DEFAULT_RETAIN): cv.boolean,
    },
    extra=vol.REMOVE_EXTRA,
)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Set up MQTT service dynamically through MQTT discovery."""

    setup = functools.partial(_async_setup_service, hass, config_entry=config_entry)
    await async_setup_entry_helper(hass, SERVICE, setup, PLATFORM_SCHEMA)


async def _async_setup_service(
    hass: HomeAssistant,
    config: ConfigType,
    config_entry: ConfigEntry,
    discovery_data: dict,
) -> None:
    """Set up the MQTT service."""
    mqtt_data = get_mqtt_data(hass, True)
    discovery_hash = discovery_data[ATTR_DISCOVERY_HASH]
    discovery_id = discovery_hash[1]

    mqtt_data.services[discovery_id] = MQTTService(
        hass,
        config,
        discovery_data,
        config_entry,
    )

    send_discovery_done(hass, discovery_data)


class MQTTService(MqttDiscoveryDeviceUpdate):
    """MQTT Service."""

    _command_template: Callable[
        [PublishPayloadType, TemplateVarsType], PublishPayloadType
    ]
    data_schema: OrderedDict[str, ServiceArgMetadata]
    service_name: str | None

    def __init__(
        self,
        hass: HomeAssistant,
        config: ConfigType,
        discovery_data: DiscoveryInfoType,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize."""
        self._config = config
        self._config_entry = config_entry
        self.discovery_data = discovery_data
        self.hass = hass
        self._command_template = MqttCommandTemplate(
            config.get(CONF_COMMAND_TEMPLATE),
            hass=self.hass,
        ).async_render

        self._async_register_service()

        MqttDiscoveryDeviceUpdate.__init__(
            self, hass, discovery_data, None, config_entry, LOG_NAME
        )

    @callback
    def _async_register_service(self) -> None:
        """Register the MQTT service."""
        discovery_hash: tuple[str, str] = self.discovery_data[ATTR_DISCOVERY_HASH]
        discovery_id = discovery_hash[1]
        service_name = slugify(self._config.get(CONF_NAME, f"service_{discovery_id}"))
        services = self.hass.services.async_services().get(DOMAIN)
        if services and services.get(service_name):
            _LOGGER.error("Service '%s' is already registered", service_name)
            self.service_name = None
            return
        self.service_name = service_name

        self.build_data_schema()

        data_schema = {}
        fields = {}
        for arg in self._config.get(CONF_SCHEMA, []):
            key = arg[CONF_NAME]
            validator = self.data_schema[key]["validator"]
            if CONF_EXCLUSIVE in arg:
                data_schema[vol.Exclusive(key, arg[CONF_EXCLUSIVE])] = validator
            elif CONF_INCLUSIVE in arg:
                data_schema[vol.Inclusive(key, arg[CONF_INCLUSIVE])] = validator
            elif CONF_REQUIRED in arg:
                data_schema[vol.Required(key)] = validator
            else:
                data_schema[vol.Optional(key)] = validator
            fields[key] = self.data_schema[key].copy()
            del fields[key]["validator"]

        async def _async_execute_service(call: ServiceCall) -> None:
            """Handle service call."""
            _LOGGER.debug(
                "Service call received for service '%s', data: %s",
                self.service_name,
                call.data,
            )
            payload = self._command_template(
                None, {key: call.data.get(key) for key in self.data_schema}
            )
            await async_publish(
                self.hass,
                self._config[CONF_COMMAND_TOPIC],
                payload,
                self._config[CONF_QOS],
                self._config[CONF_RETAIN],
                self._config[CONF_ENCODING],
            )

        self.hass.services.async_register(
            DOMAIN, service_name, _async_execute_service, vol.Schema(data_schema)
        )

        service_desc = {}
        if description := self._config.get(CONF_DESCRIPTION, ""):
            service_desc["description"] = description
        if fields:
            service_desc["fields"] = fields

        async_set_service_schema(self.hass, DOMAIN, service_name, service_desc)

    def build_data_schema(self) -> None:
        """Build a service schema based on the config supplied."""
        schema: list[dict[str, Any]] | None
        if not (schema := self._config.get(CONF_SCHEMA)):
            self.data_schema = OrderedDict()
            return None

        data_schema = OrderedDict[str, ServiceArgMetadata]({})
        schema_arg: dict[str, Any]
        for schema_arg in schema:
            arg = copy(schema_arg)
            metadata = deepcopy(ARG_TYPE_METADATA[arg[CONF_TYPE]])
            metadata[CONF_NAME] = arg[CONF_NAME]
            if CONF_DESCRIPTION in arg:
                metadata[CONF_DESCRIPTION] = arg[CONF_DESCRIPTION]
            if CONF_EXAMPLE in arg:
                metadata["example"] = arg[CONF_EXAMPLE]
            if arg[CONF_TYPE] in SELECT_SELECTORS and CONF_OPTIONS in arg:
                assert isinstance(arg, dict)
                selector_args = cast(SelectSelectorArgs, metadata["selector"]["select"])
                selector_args["options"] = arg.pop(CONF_OPTIONS)
                if CONF_MULTIPLE in arg:
                    selector_args["multiple"] = arg.pop(CONF_MULTIPLE)
                if CONF_CUSTOM_VALUE in arg:
                    selector_args["custom_value"] = arg.pop(CONF_CUSTOM_VALUE)
                metadata["selector"]["select"] = selector_args
            data_schema[arg[CONF_NAME]] = metadata

        self.data_schema = data_schema

    async def async_update(self, discovery_data: MQTTDiscoveryPayload) -> None:
        """Handle MQTT service discovery updates."""
        # Update service
        config: DiscoveryInfoType = PLATFORM_SCHEMA(discovery_data)
        self._config = config
        self._command_template = MqttCommandTemplate(
            config.get(CONF_COMMAND_TEMPLATE),
            hass=self.hass,
        ).async_render
        if self.service_name is not None:
            self.hass.services.async_remove(DOMAIN, self.service_name)
        self._async_register_service()

    async def async_tear_down(self) -> None:
        """Cleanup service."""
        if self.service_name is not None:
            self.hass.services.async_remove(DOMAIN, self.service_name)
        discovery_hash = self.discovery_data[ATTR_DISCOVERY_HASH]
        discovery_id = discovery_hash[1]
        del get_mqtt_data(self.hass).services[discovery_id]
