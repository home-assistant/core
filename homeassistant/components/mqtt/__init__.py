"""Support for MQTT message handling."""
import asyncio
from functools import partial, wraps
import inspect
from itertools import groupby
import json
import logging
from operator import attrgetter
import os
import socket
import ssl
import sys
import time
from typing import Any, Callable, List, Optional, Union

import attr
import requests.certs
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import websocket_api
from homeassistant.const import (
    CONF_DEVICE,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PAYLOAD,
    CONF_PORT,
    CONF_PROTOCOL,
    CONF_USERNAME,
    CONF_VALUE_TEMPLATE,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import Event, ServiceCall, callback
from homeassistant.exceptions import (
    ConfigEntryNotReady,
    HomeAssistantError,
    Unauthorized,
)
from homeassistant.helpers import config_validation as cv, event, template
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import ConfigType, HomeAssistantType, ServiceDataType
from homeassistant.loader import bind_hass
from homeassistant.util.async_ import run_callback_threadsafe
from homeassistant.util.logging import catch_log_exception

# Loading the config flow file will register the flow
from . import config_flow  # noqa: F401 pylint: disable=unused-import
from . import debug_info, discovery, server
from .const import (
    ATTR_DISCOVERY_HASH,
    ATTR_DISCOVERY_TOPIC,
    CONF_BROKER,
    CONF_DISCOVERY,
    CONF_STATE_TOPIC,
    DEFAULT_DISCOVERY,
    DEFAULT_QOS,
    PROTOCOL_311,
)
from .debug_info import log_messages
from .discovery import MQTT_DISCOVERY_UPDATED, clear_discovery_hash, set_discovery_hash
from .models import Message, MessageCallbackType, PublishPayloadType
from .subscription import async_subscribe_topics, async_unsubscribe_topics

_LOGGER = logging.getLogger(__name__)

DOMAIN = "mqtt"

DATA_MQTT = "mqtt"
DATA_MQTT_CONFIG = "mqtt_config"
DATA_MQTT_HASS_CONFIG = "mqtt_hass_config"

SERVICE_PUBLISH = "publish"
SERVICE_DUMP = "dump"

CONF_EMBEDDED = "embedded"

CONF_CLIENT_ID = "client_id"
CONF_DISCOVERY_PREFIX = "discovery_prefix"
CONF_KEEPALIVE = "keepalive"
CONF_CERTIFICATE = "certificate"
CONF_CLIENT_KEY = "client_key"
CONF_CLIENT_CERT = "client_cert"
CONF_TLS_INSECURE = "tls_insecure"
CONF_TLS_VERSION = "tls_version"

CONF_BIRTH_MESSAGE = "birth_message"
CONF_WILL_MESSAGE = "will_message"

CONF_COMMAND_TOPIC = "command_topic"
CONF_AVAILABILITY_TOPIC = "availability_topic"
CONF_PAYLOAD_AVAILABLE = "payload_available"
CONF_PAYLOAD_NOT_AVAILABLE = "payload_not_available"
CONF_JSON_ATTRS_TOPIC = "json_attributes_topic"
CONF_JSON_ATTRS_TEMPLATE = "json_attributes_template"
CONF_QOS = "qos"
CONF_RETAIN = "retain"

CONF_UNIQUE_ID = "unique_id"
CONF_IDENTIFIERS = "identifiers"
CONF_CONNECTIONS = "connections"
CONF_MANUFACTURER = "manufacturer"
CONF_MODEL = "model"
CONF_SW_VERSION = "sw_version"
CONF_VIA_DEVICE = "via_device"
CONF_DEPRECATED_VIA_HUB = "via_hub"

PROTOCOL_31 = "3.1"

DEFAULT_PORT = 1883
DEFAULT_KEEPALIVE = 60
DEFAULT_RETAIN = False
DEFAULT_PROTOCOL = PROTOCOL_311
DEFAULT_DISCOVERY_PREFIX = "homeassistant"
DEFAULT_TLS_PROTOCOL = "auto"
DEFAULT_PAYLOAD_AVAILABLE = "online"
DEFAULT_PAYLOAD_NOT_AVAILABLE = "offline"

ATTR_TOPIC = "topic"
ATTR_PAYLOAD = "payload"
ATTR_PAYLOAD_TEMPLATE = "payload_template"
ATTR_QOS = CONF_QOS
ATTR_RETAIN = CONF_RETAIN

MAX_RECONNECT_WAIT = 300  # seconds

CONNECTION_SUCCESS = "connection_success"
CONNECTION_FAILED = "connection_failed"
CONNECTION_FAILED_RECOVERABLE = "connection_failed_recoverable"


def valid_topic(value: Any) -> str:
    """Validate that this is a valid topic name/filter."""
    value = cv.string(value)
    try:
        raw_value = value.encode("utf-8")
    except UnicodeError:
        raise vol.Invalid("MQTT topic name/filter must be valid UTF-8 string.")
    if not raw_value:
        raise vol.Invalid("MQTT topic name/filter must not be empty.")
    if len(raw_value) > 65535:
        raise vol.Invalid(
            "MQTT topic name/filter must not be longer than 65535 encoded bytes."
        )
    if "\0" in value:
        raise vol.Invalid("MQTT topic name/filter must not contain null character.")
    return value


def valid_subscribe_topic(value: Any) -> str:
    """Validate that we can subscribe using this MQTT topic."""
    value = valid_topic(value)
    for i in (i for i, c in enumerate(value) if c == "+"):
        if (i > 0 and value[i - 1] != "/") or (
            i < len(value) - 1 and value[i + 1] != "/"
        ):
            raise vol.Invalid(
                "Single-level wildcard must occupy an entire level of the filter"
            )

    index = value.find("#")
    if index != -1:
        if index != len(value) - 1:
            # If there are multiple wildcards, this will also trigger
            raise vol.Invalid(
                "Multi-level wildcard must be the last "
                "character in the topic filter."
            )
        if len(value) > 1 and value[index - 1] != "/":
            raise vol.Invalid(
                "Multi-level wildcard must be after a topic level separator."
            )

    return value


def valid_publish_topic(value: Any) -> str:
    """Validate that we can publish using this MQTT topic."""
    value = valid_topic(value)
    if "+" in value or "#" in value:
        raise vol.Invalid("Wildcards can not be used in topic names")
    return value


def validate_device_has_at_least_one_identifier(value: ConfigType) -> ConfigType:
    """Validate that a device info entry has at least one identifying value."""
    if not value.get(CONF_IDENTIFIERS) and not value.get(CONF_CONNECTIONS):
        raise vol.Invalid(
            "Device must have at least one identifying value in "
            "'identifiers' and/or 'connections'"
        )
    return value


_VALID_QOS_SCHEMA = vol.All(vol.Coerce(int), vol.In([0, 1, 2]))

CLIENT_KEY_AUTH_MSG = (
    "client_key and client_cert must both be present in "
    "the MQTT broker configuration"
)

MQTT_WILL_BIRTH_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_TOPIC): valid_publish_topic,
        vol.Required(ATTR_PAYLOAD, CONF_PAYLOAD): cv.string,
        vol.Optional(ATTR_QOS, default=DEFAULT_QOS): _VALID_QOS_SCHEMA,
        vol.Optional(ATTR_RETAIN, default=DEFAULT_RETAIN): cv.boolean,
    },
    required=True,
)


def embedded_broker_deprecated(value):
    """Warn user that embedded MQTT broker is deprecated."""
    _LOGGER.warning(
        "The embedded MQTT broker has been deprecated and will stop working"
        "after June 5th, 2019. Use an external broker instead. For"
        "instructions, see https://www.home-assistant.io/docs/mqtt/broker"
    )
    return value


CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_CLIENT_ID): cv.string,
                vol.Optional(CONF_KEEPALIVE, default=DEFAULT_KEEPALIVE): vol.All(
                    vol.Coerce(int), vol.Range(min=15)
                ),
                vol.Optional(CONF_BROKER): cv.string,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
                vol.Optional(CONF_USERNAME): cv.string,
                vol.Optional(CONF_PASSWORD): cv.string,
                vol.Optional(CONF_CERTIFICATE): vol.Any("auto", cv.isfile),
                vol.Inclusive(
                    CONF_CLIENT_KEY, "client_key_auth", msg=CLIENT_KEY_AUTH_MSG
                ): cv.isfile,
                vol.Inclusive(
                    CONF_CLIENT_CERT, "client_key_auth", msg=CLIENT_KEY_AUTH_MSG
                ): cv.isfile,
                vol.Optional(CONF_TLS_INSECURE): cv.boolean,
                vol.Optional(CONF_TLS_VERSION, default=DEFAULT_TLS_PROTOCOL): vol.Any(
                    "auto", "1.0", "1.1", "1.2"
                ),
                vol.Optional(CONF_PROTOCOL, default=DEFAULT_PROTOCOL): vol.All(
                    cv.string, vol.In([PROTOCOL_31, PROTOCOL_311])
                ),
                vol.Optional(CONF_EMBEDDED): vol.All(
                    server.HBMQTT_CONFIG_SCHEMA, embedded_broker_deprecated
                ),
                vol.Optional(CONF_WILL_MESSAGE): MQTT_WILL_BIRTH_SCHEMA,
                vol.Optional(CONF_BIRTH_MESSAGE): MQTT_WILL_BIRTH_SCHEMA,
                vol.Optional(CONF_DISCOVERY, default=DEFAULT_DISCOVERY): cv.boolean,
                # discovery_prefix must be a valid publish topic because if no
                # state topic is specified, it will be created with the given prefix.
                vol.Optional(
                    CONF_DISCOVERY_PREFIX, default=DEFAULT_DISCOVERY_PREFIX
                ): valid_publish_topic,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

SCHEMA_BASE = {vol.Optional(CONF_QOS, default=DEFAULT_QOS): _VALID_QOS_SCHEMA}

MQTT_AVAILABILITY_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_AVAILABILITY_TOPIC): valid_subscribe_topic,
        vol.Optional(
            CONF_PAYLOAD_AVAILABLE, default=DEFAULT_PAYLOAD_AVAILABLE
        ): cv.string,
        vol.Optional(
            CONF_PAYLOAD_NOT_AVAILABLE, default=DEFAULT_PAYLOAD_NOT_AVAILABLE
        ): cv.string,
    }
)

MQTT_ENTITY_DEVICE_INFO_SCHEMA = vol.All(
    cv.deprecated(CONF_DEPRECATED_VIA_HUB, CONF_VIA_DEVICE),
    vol.Schema(
        {
            vol.Optional(CONF_IDENTIFIERS, default=list): vol.All(
                cv.ensure_list, [cv.string]
            ),
            vol.Optional(CONF_CONNECTIONS, default=list): vol.All(
                cv.ensure_list, [vol.All(vol.Length(2), [cv.string])]
            ),
            vol.Optional(CONF_MANUFACTURER): cv.string,
            vol.Optional(CONF_MODEL): cv.string,
            vol.Optional(CONF_NAME): cv.string,
            vol.Optional(CONF_SW_VERSION): cv.string,
            vol.Optional(CONF_VIA_DEVICE): cv.string,
        }
    ),
    validate_device_has_at_least_one_identifier,
)

MQTT_JSON_ATTRS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_JSON_ATTRS_TOPIC): valid_subscribe_topic,
        vol.Optional(CONF_JSON_ATTRS_TEMPLATE): cv.template,
    }
)

MQTT_BASE_PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA.extend(SCHEMA_BASE)

# Sensor type platforms subscribe to MQTT events
MQTT_RO_PLATFORM_SCHEMA = MQTT_BASE_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_STATE_TOPIC): valid_subscribe_topic,
        vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
    }
)

# Switch type platforms publish to MQTT and may subscribe
MQTT_RW_PLATFORM_SCHEMA = MQTT_BASE_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_COMMAND_TOPIC): valid_publish_topic,
        vol.Optional(CONF_RETAIN, default=DEFAULT_RETAIN): cv.boolean,
        vol.Optional(CONF_STATE_TOPIC): valid_subscribe_topic,
        vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
    }
)

# Service call validation schema
MQTT_PUBLISH_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_TOPIC): valid_publish_topic,
        vol.Exclusive(ATTR_PAYLOAD, CONF_PAYLOAD): object,
        vol.Exclusive(ATTR_PAYLOAD_TEMPLATE, CONF_PAYLOAD): cv.string,
        vol.Optional(ATTR_QOS, default=DEFAULT_QOS): _VALID_QOS_SCHEMA,
        vol.Optional(ATTR_RETAIN, default=DEFAULT_RETAIN): cv.boolean,
    },
    required=True,
)


SubscribePayloadType = Union[str, bytes]  # Only bytes if encoding is None


def _build_publish_data(topic: Any, qos: int, retain: bool) -> ServiceDataType:
    """Build the arguments for the publish service without the payload."""
    data = {ATTR_TOPIC: topic}
    if qos is not None:
        data[ATTR_QOS] = qos
    if retain is not None:
        data[ATTR_RETAIN] = retain
    return data


@bind_hass
def publish(hass: HomeAssistantType, topic, payload, qos=None, retain=None) -> None:
    """Publish message to an MQTT topic."""
    hass.add_job(async_publish, hass, topic, payload, qos, retain)


@callback
@bind_hass
def async_publish(
    hass: HomeAssistantType, topic: Any, payload, qos=None, retain=None
) -> None:
    """Publish message to an MQTT topic."""
    data = _build_publish_data(topic, qos, retain)
    data[ATTR_PAYLOAD] = payload
    hass.async_create_task(hass.services.async_call(DOMAIN, SERVICE_PUBLISH, data))


@bind_hass
def publish_template(
    hass: HomeAssistantType, topic, payload_template, qos=None, retain=None
) -> None:
    """Publish message to an MQTT topic using a template payload."""
    data = _build_publish_data(topic, qos, retain)
    data[ATTR_PAYLOAD_TEMPLATE] = payload_template
    hass.services.call(DOMAIN, SERVICE_PUBLISH, data)


def wrap_msg_callback(msg_callback: MessageCallbackType) -> MessageCallbackType:
    """Wrap an MQTT message callback to support deprecated signature."""
    # Check for partials to properly determine if coroutine function
    check_func = msg_callback
    while isinstance(check_func, partial):
        check_func = check_func.func

    wrapper_func = None
    if asyncio.iscoroutinefunction(check_func):

        @wraps(msg_callback)
        async def async_wrapper(msg: Any) -> None:
            """Catch and log exception."""
            await msg_callback(msg.topic, msg.payload, msg.qos)

        wrapper_func = async_wrapper
    else:

        @wraps(msg_callback)
        def wrapper(msg: Any) -> None:
            """Catch and log exception."""
            msg_callback(msg.topic, msg.payload, msg.qos)

        wrapper_func = wrapper
    return wrapper_func


@bind_hass
async def async_subscribe(
    hass: HomeAssistantType,
    topic: str,
    msg_callback: MessageCallbackType,
    qos: int = DEFAULT_QOS,
    encoding: Optional[str] = "utf-8",
):
    """Subscribe to an MQTT topic.

    Call the return value to unsubscribe.
    """
    # Count callback parameters which don't have a default value
    non_default = 0
    if msg_callback:
        non_default = sum(
            p.default == inspect.Parameter.empty
            for _, p in inspect.signature(msg_callback).parameters.items()
        )

    wrapped_msg_callback = msg_callback
    # If we have 3 parameters with no default value, wrap the callback
    if non_default == 3:
        _LOGGER.warning(
            "Signature of MQTT msg_callback '%s.%s' is deprecated",
            inspect.getmodule(msg_callback).__name__,
            msg_callback.__name__,
        )
        wrapped_msg_callback = wrap_msg_callback(msg_callback)

    async_remove = await hass.data[DATA_MQTT].async_subscribe(
        topic,
        catch_log_exception(
            wrapped_msg_callback,
            lambda msg: (
                f"Exception in {msg_callback.__name__} when handling msg on "
                f"'{msg.topic}': '{msg.payload}'"
            ),
        ),
        qos,
        encoding,
    )
    return async_remove


@bind_hass
def subscribe(
    hass: HomeAssistantType,
    topic: str,
    msg_callback: MessageCallbackType,
    qos: int = DEFAULT_QOS,
    encoding: str = "utf-8",
) -> Callable[[], None]:
    """Subscribe to an MQTT topic."""
    async_remove = asyncio.run_coroutine_threadsafe(
        async_subscribe(hass, topic, msg_callback, qos, encoding), hass.loop
    ).result()

    def remove():
        """Remove listener convert."""
        run_callback_threadsafe(hass.loop, async_remove).result()

    return remove


async def _async_setup_server(hass: HomeAssistantType, config: ConfigType):
    """Try to start embedded MQTT broker.

    This method is a coroutine.
    """
    conf: ConfigType = config.get(DOMAIN, {})

    success, broker_config = await server.async_start(
        hass, conf.get(CONF_PASSWORD), conf.get(CONF_EMBEDDED)
    )

    if not success:
        return None

    return broker_config


async def _async_setup_discovery(
    hass: HomeAssistantType, conf: ConfigType, hass_config: ConfigType, config_entry
) -> bool:
    """Try to start the discovery of MQTT devices.

    This method is a coroutine.
    """
    if discovery is None:
        _LOGGER.error("Unable to load MQTT discovery")
        return False

    success: bool = await discovery.async_start(
        hass, conf[CONF_DISCOVERY_PREFIX], hass_config, config_entry
    )

    return success


async def async_setup(hass: HomeAssistantType, config: ConfigType) -> bool:
    """Start the MQTT protocol service."""
    conf: Optional[ConfigType] = config.get(DOMAIN)

    # We need this because discovery can cause components to be set up and
    # otherwise it will not load the users config.
    # This needs a better solution.
    hass.data[DATA_MQTT_HASS_CONFIG] = config

    websocket_api.async_register_command(hass, websocket_subscribe)
    websocket_api.async_register_command(hass, websocket_remove_device)
    websocket_api.async_register_command(hass, websocket_mqtt_info)

    if conf is None:
        # If we have a config entry, setup is done by that config entry.
        # If there is no config entry, this should fail.
        return bool(hass.config_entries.async_entries(DOMAIN))

    conf = dict(conf)

    if CONF_EMBEDDED in conf or CONF_BROKER not in conf:

        broker_config = await _async_setup_server(hass, config)

        if broker_config is None:
            _LOGGER.error("Unable to start embedded MQTT broker")
            return False

        conf.update(
            {
                CONF_BROKER: broker_config[0],
                CONF_PORT: broker_config[1],
                CONF_USERNAME: broker_config[2],
                CONF_PASSWORD: broker_config[3],
                CONF_CERTIFICATE: broker_config[4],
                CONF_PROTOCOL: broker_config[5],
                CONF_CLIENT_KEY: None,
                CONF_CLIENT_CERT: None,
                CONF_TLS_INSECURE: None,
            }
        )

    hass.data[DATA_MQTT_CONFIG] = conf

    # Only import if we haven't before.
    if not hass.config_entries.async_entries(DOMAIN):
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data={}
            )
        )

    return True


async def async_setup_entry(hass, entry):
    """Load a config entry."""
    conf = hass.data.get(DATA_MQTT_CONFIG)

    # Config entry was created because user had configuration.yaml entry
    # They removed that, so remove entry.
    if conf is None and entry.source == config_entries.SOURCE_IMPORT:
        hass.async_create_task(hass.config_entries.async_remove(entry.entry_id))
        return False

    # If user didn't have configuration.yaml config, generate defaults
    if conf is None:
        conf = CONFIG_SCHEMA({DOMAIN: dict(entry.data)})[DOMAIN]
    elif any(key in conf for key in entry.data):
        _LOGGER.warning(
            "Data in your configuration entry is going to override your "
            "configuration.yaml: %s",
            entry.data,
        )

    conf.update(entry.data)

    broker = conf[CONF_BROKER]
    port = conf[CONF_PORT]
    client_id = conf.get(CONF_CLIENT_ID)
    keepalive = conf[CONF_KEEPALIVE]
    username = conf.get(CONF_USERNAME)
    password = conf.get(CONF_PASSWORD)
    certificate = conf.get(CONF_CERTIFICATE)
    client_key = conf.get(CONF_CLIENT_KEY)
    client_cert = conf.get(CONF_CLIENT_CERT)
    tls_insecure = conf.get(CONF_TLS_INSECURE)
    protocol = conf[CONF_PROTOCOL]

    # For cloudmqtt.com, secured connection, auto fill in certificate
    if (
        certificate is None
        and 19999 < conf[CONF_PORT] < 30000
        and broker.endswith(".cloudmqtt.com")
    ):
        certificate = os.path.join(
            os.path.dirname(__file__), "addtrustexternalcaroot.crt"
        )

    # When the certificate is set to auto, use bundled certs from requests
    elif certificate == "auto":
        certificate = requests.certs.where()

    if CONF_WILL_MESSAGE in conf:
        will_message = Message(**conf[CONF_WILL_MESSAGE])
    else:
        will_message = None

    if CONF_BIRTH_MESSAGE in conf:
        birth_message = Message(**conf[CONF_BIRTH_MESSAGE])
    else:
        birth_message = None

    # Be able to override versions other than TLSv1.0 under Python3.6
    conf_tls_version: str = conf.get(CONF_TLS_VERSION)
    if conf_tls_version == "1.2":
        tls_version = ssl.PROTOCOL_TLSv1_2
    elif conf_tls_version == "1.1":
        tls_version = ssl.PROTOCOL_TLSv1_1
    elif conf_tls_version == "1.0":
        tls_version = ssl.PROTOCOL_TLSv1
    else:
        # Python3.6 supports automatic negotiation of highest TLS version
        if sys.hexversion >= 0x03060000:
            tls_version = ssl.PROTOCOL_TLS  # pylint: disable=no-member
        else:
            tls_version = ssl.PROTOCOL_TLSv1

    hass.data[DATA_MQTT] = MQTT(
        hass,
        broker=broker,
        port=port,
        client_id=client_id,
        keepalive=keepalive,
        username=username,
        password=password,
        certificate=certificate,
        client_key=client_key,
        client_cert=client_cert,
        tls_insecure=tls_insecure,
        protocol=protocol,
        will_message=will_message,
        birth_message=birth_message,
        tls_version=tls_version,
    )

    result: str = await hass.data[DATA_MQTT].async_connect()

    if result == CONNECTION_FAILED:
        return False

    if result == CONNECTION_FAILED_RECOVERABLE:
        raise ConfigEntryNotReady

    async def async_stop_mqtt(_event: Event):
        """Stop MQTT component."""
        await hass.data[DATA_MQTT].async_disconnect()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_stop_mqtt)

    async def async_publish_service(call: ServiceCall):
        """Handle MQTT publish service calls."""
        msg_topic: str = call.data[ATTR_TOPIC]
        payload = call.data.get(ATTR_PAYLOAD)
        payload_template = call.data.get(ATTR_PAYLOAD_TEMPLATE)
        qos: int = call.data[ATTR_QOS]
        retain: bool = call.data[ATTR_RETAIN]
        if payload_template is not None:
            try:
                payload = template.Template(payload_template, hass).async_render()
            except template.jinja2.TemplateError as exc:
                _LOGGER.error(
                    "Unable to publish to %s: rendering payload template of "
                    "%s failed because %s",
                    msg_topic,
                    payload_template,
                    exc,
                )
                return

        await hass.data[DATA_MQTT].async_publish(msg_topic, payload, qos, retain)

    hass.services.async_register(
        DOMAIN, SERVICE_PUBLISH, async_publish_service, schema=MQTT_PUBLISH_SCHEMA
    )

    async def async_dump_service(call: ServiceCall):
        """Handle MQTT dump service calls."""
        messages = []

        @callback
        def collect_msg(msg):
            messages.append((msg.topic, msg.payload.replace("\n", "")))

        unsub = await async_subscribe(hass, call.data["topic"], collect_msg)

        def write_dump():
            with open(hass.config.path("mqtt_dump.txt"), "wt") as fp:
                for msg in messages:
                    fp.write(",".join(msg) + "\n")

        async def finish_dump(_):
            """Write dump to file."""
            unsub()
            await hass.async_add_executor_job(write_dump)

        event.async_call_later(hass, call.data["duration"], finish_dump)

    hass.services.async_register(
        DOMAIN,
        SERVICE_DUMP,
        async_dump_service,
        schema=vol.Schema(
            {
                vol.Required("topic"): valid_subscribe_topic,
                vol.Optional("duration", default=5): int,
            }
        ),
    )

    if conf.get(CONF_DISCOVERY):
        await _async_setup_discovery(
            hass, conf, hass.data[DATA_MQTT_HASS_CONFIG], entry
        )

    return True


@attr.s(slots=True, frozen=True)
class Subscription:
    """Class to hold data about an active subscription."""

    topic = attr.ib(type=str)
    callback = attr.ib(type=MessageCallbackType)
    qos = attr.ib(type=int, default=0)
    encoding = attr.ib(type=str, default="utf-8")


class MQTT:
    """Home Assistant MQTT client."""

    def __init__(
        self,
        hass: HomeAssistantType,
        broker: str,
        port: int,
        client_id: Optional[str],
        keepalive: Optional[int],
        username: Optional[str],
        password: Optional[str],
        certificate: Optional[str],
        client_key: Optional[str],
        client_cert: Optional[str],
        tls_insecure: Optional[bool],
        protocol: Optional[str],
        will_message: Optional[Message],
        birth_message: Optional[Message],
        tls_version: Optional[int],
    ) -> None:
        """Initialize Home Assistant MQTT client."""
        # We don't import them on the top because some integrations
        # should be able to optionally rely on MQTT.
        # pylint: disable=import-outside-toplevel
        import paho.mqtt.client as mqtt

        self.hass = hass
        self.broker = broker
        self.port = port
        self.keepalive = keepalive
        self.subscriptions: List[Subscription] = []
        self.birth_message = birth_message
        self.connected = False
        self._mqttc: mqtt.Client = None
        self._paho_lock = asyncio.Lock()

        if protocol == PROTOCOL_31:
            proto: int = mqtt.MQTTv31
        else:
            proto = mqtt.MQTTv311

        if client_id is None:
            self._mqttc = mqtt.Client(protocol=proto)
        else:
            self._mqttc = mqtt.Client(client_id, protocol=proto)

        if username is not None:
            self._mqttc.username_pw_set(username, password)

        if certificate is not None:
            self._mqttc.tls_set(
                certificate,
                certfile=client_cert,
                keyfile=client_key,
                tls_version=tls_version,
            )

            if tls_insecure is not None:
                self._mqttc.tls_insecure_set(tls_insecure)

        self._mqttc.on_connect = self._mqtt_on_connect
        self._mqttc.on_disconnect = self._mqtt_on_disconnect
        self._mqttc.on_message = self._mqtt_on_message

        if will_message is not None:
            self._mqttc.will_set(  # pylint: disable=no-value-for-parameter
                *attr.astuple(will_message)
            )

    async def async_publish(
        self, topic: str, payload: PublishPayloadType, qos: int, retain: bool
    ) -> None:
        """Publish a MQTT message."""
        async with self._paho_lock:
            _LOGGER.debug("Transmitting message on %s: %s", topic, payload)
            await self.hass.async_add_executor_job(
                self._mqttc.publish, topic, payload, qos, retain
            )

    async def async_connect(self) -> str:
        """Connect to the host. Does process messages yet."""
        # pylint: disable=import-outside-toplevel
        import paho.mqtt.client as mqtt

        result: int = None
        try:
            result = await self.hass.async_add_executor_job(
                self._mqttc.connect, self.broker, self.port, self.keepalive
            )
        except OSError as err:
            _LOGGER.error("Failed to connect due to exception: %s", err)
            return CONNECTION_FAILED_RECOVERABLE

        if result != 0:
            _LOGGER.error("Failed to connect: %s", mqtt.error_string(result))
            return CONNECTION_FAILED

        self._mqttc.loop_start()
        return CONNECTION_SUCCESS

    async def async_disconnect(self):
        """Stop the MQTT client."""

        def stop():
            """Stop the MQTT client."""
            self._mqttc.disconnect()
            self._mqttc.loop_stop()

        await self.hass.async_add_executor_job(stop)

    async def async_subscribe(
        self,
        topic: str,
        msg_callback: MessageCallbackType,
        qos: int,
        encoding: Optional[str] = None,
    ) -> Callable[[], None]:
        """Set up a subscription to a topic with the provided qos.

        This method is a coroutine.
        """
        if not isinstance(topic, str):
            raise HomeAssistantError("Topic needs to be a string!")

        subscription = Subscription(topic, msg_callback, qos, encoding)
        self.subscriptions.append(subscription)

        await self._async_perform_subscription(topic, qos)

        @callback
        def async_remove() -> None:
            """Remove subscription."""
            if subscription not in self.subscriptions:
                raise HomeAssistantError("Can't remove subscription twice")
            self.subscriptions.remove(subscription)

            if any(other.topic == topic for other in self.subscriptions):
                # Other subscriptions on topic remaining - don't unsubscribe.
                return

            # Only unsubscribe if currently connected.
            if self.connected:
                self.hass.async_create_task(self._async_unsubscribe(topic))

        return async_remove

    async def _async_unsubscribe(self, topic: str) -> None:
        """Unsubscribe from a topic.

        This method is a coroutine.
        """
        async with self._paho_lock:
            result: int = None
            result, _ = await self.hass.async_add_executor_job(
                self._mqttc.unsubscribe, topic
            )
            _raise_on_error(result)

    async def _async_perform_subscription(self, topic: str, qos: int) -> None:
        """Perform a paho-mqtt subscription."""
        _LOGGER.debug("Subscribing to %s", topic)

        async with self._paho_lock:
            result: int = None
            result, _ = await self.hass.async_add_executor_job(
                self._mqttc.subscribe, topic, qos
            )
            _raise_on_error(result)

    def _mqtt_on_connect(self, _mqttc, _userdata, _flags, result_code: int) -> None:
        """On connect callback.

        Resubscribe to all topics we were subscribed to and publish birth
        message.
        """
        # pylint: disable=import-outside-toplevel
        import paho.mqtt.client as mqtt

        if result_code != mqtt.CONNACK_ACCEPTED:
            _LOGGER.error(
                "Unable to connect to the MQTT broker: %s",
                mqtt.connack_string(result_code),
            )
            self._mqttc.disconnect()
            return

        self.connected = True

        # Group subscriptions to only re-subscribe once for each topic.
        keyfunc = attrgetter("topic")
        for topic, subs in groupby(sorted(self.subscriptions, key=keyfunc), keyfunc):
            # Re-subscribe with the highest requested qos
            max_qos = max(subscription.qos for subscription in subs)
            self.hass.add_job(self._async_perform_subscription, topic, max_qos)

        if self.birth_message:
            self.hass.add_job(
                self.async_publish(  # pylint: disable=no-value-for-parameter
                    *attr.astuple(self.birth_message)
                )
            )

    def _mqtt_on_message(self, _mqttc, _userdata, msg) -> None:
        """Message received callback."""
        self.hass.add_job(self._mqtt_handle_message, msg)

    @callback
    def _mqtt_handle_message(self, msg) -> None:
        _LOGGER.debug(
            "Received message on %s%s: %s",
            msg.topic,
            " (retained)" if msg.retain else "",
            msg.payload,
        )

        for subscription in self.subscriptions:
            if not _match_topic(subscription.topic, msg.topic):
                continue

            payload: SubscribePayloadType = msg.payload
            if subscription.encoding is not None:
                try:
                    payload = msg.payload.decode(subscription.encoding)
                except (AttributeError, UnicodeDecodeError):
                    _LOGGER.warning(
                        "Can't decode payload %s on %s with encoding %s (for %s)",
                        msg.payload,
                        msg.topic,
                        subscription.encoding,
                        subscription.callback,
                    )
                    continue

            self.hass.async_run_job(
                subscription.callback, Message(msg.topic, payload, msg.qos, msg.retain)
            )

    def _mqtt_on_disconnect(self, _mqttc, _userdata, result_code: int) -> None:
        """Disconnected callback."""
        self.connected = False

        # When disconnected because of calling disconnect()
        if result_code == 0:
            return

        tries = 0

        while True:
            try:
                if self._mqttc.reconnect() == 0:
                    self.connected = True
                    _LOGGER.info("Successfully reconnected to the MQTT server")
                    break
            except socket.error:
                pass

            wait_time = min(2 ** tries, MAX_RECONNECT_WAIT)
            _LOGGER.warning(
                "Disconnected from MQTT (%s). Trying to reconnect in %s s",
                result_code,
                wait_time,
            )
            # It is ok to sleep here as we are in the MQTT thread.
            time.sleep(wait_time)
            tries += 1


def _raise_on_error(result_code: int) -> None:
    """Raise error if error result."""
    # pylint: disable=import-outside-toplevel
    import paho.mqtt.client as mqtt

    if result_code != 0:
        raise HomeAssistantError(
            f"Error talking to MQTT: {mqtt.error_string(result_code)}"
        )


def _match_topic(subscription: str, topic: str) -> bool:
    """Test if topic matches subscription."""
    # pylint: disable=import-outside-toplevel
    from paho.mqtt.matcher import MQTTMatcher

    matcher = MQTTMatcher()
    matcher[subscription] = True
    try:
        next(matcher.iter_match(topic))
        return True
    except StopIteration:
        return False


class MqttAttributes(Entity):
    """Mixin used for platforms that support JSON attributes."""

    def __init__(self, config: dict) -> None:
        """Initialize the JSON attributes mixin."""
        self._attributes = None
        self._attributes_sub_state = None
        self._attributes_config = config

    async def async_added_to_hass(self) -> None:
        """Subscribe MQTT events."""
        await super().async_added_to_hass()
        await self._attributes_subscribe_topics()

    async def attributes_discovery_update(self, config: dict):
        """Handle updated discovery message."""
        self._attributes_config = config
        await self._attributes_subscribe_topics()

    async def _attributes_subscribe_topics(self):
        """(Re)Subscribe to topics."""
        attr_tpl = self._attributes_config.get(CONF_JSON_ATTRS_TEMPLATE)
        if attr_tpl is not None:
            attr_tpl.hass = self.hass

        @callback
        @log_messages(self.hass, self.entity_id)
        def attributes_message_received(msg: Message) -> None:
            try:
                payload = msg.payload
                if attr_tpl is not None:
                    payload = attr_tpl.async_render_with_possible_json_value(payload)
                json_dict = json.loads(payload)
                if isinstance(json_dict, dict):
                    self._attributes = json_dict
                    self.async_write_ha_state()
                else:
                    _LOGGER.warning("JSON result was not a dictionary")
                    self._attributes = None
            except ValueError:
                _LOGGER.warning("Erroneous JSON: %s", payload)
                self._attributes = None

        self._attributes_sub_state = await async_subscribe_topics(
            self.hass,
            self._attributes_sub_state,
            {
                CONF_JSON_ATTRS_TOPIC: {
                    "topic": self._attributes_config.get(CONF_JSON_ATTRS_TOPIC),
                    "msg_callback": attributes_message_received,
                    "qos": self._attributes_config.get(CONF_QOS),
                }
            },
        )

    async def async_will_remove_from_hass(self):
        """Unsubscribe when removed."""
        self._attributes_sub_state = await async_unsubscribe_topics(
            self.hass, self._attributes_sub_state
        )

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attributes


class MqttAvailability(Entity):
    """Mixin used for platforms that report availability."""

    def __init__(self, config: dict) -> None:
        """Initialize the availability mixin."""
        self._availability_sub_state = None
        self._available = False

        self._avail_config = config

    async def async_added_to_hass(self) -> None:
        """Subscribe MQTT events."""
        await super().async_added_to_hass()
        await self._availability_subscribe_topics()

    async def availability_discovery_update(self, config: dict):
        """Handle updated discovery message."""
        self._avail_config = config
        await self._availability_subscribe_topics()

    async def _availability_subscribe_topics(self):
        """(Re)Subscribe to topics."""

        @callback
        @log_messages(self.hass, self.entity_id)
        def availability_message_received(msg: Message) -> None:
            """Handle a new received MQTT availability message."""
            if msg.payload == self._avail_config[CONF_PAYLOAD_AVAILABLE]:
                self._available = True
            elif msg.payload == self._avail_config[CONF_PAYLOAD_NOT_AVAILABLE]:
                self._available = False

            self.async_write_ha_state()

        self._availability_sub_state = await async_subscribe_topics(
            self.hass,
            self._availability_sub_state,
            {
                "availability_topic": {
                    "topic": self._avail_config.get(CONF_AVAILABILITY_TOPIC),
                    "msg_callback": availability_message_received,
                    "qos": self._avail_config[CONF_QOS],
                }
            },
        )

    async def async_will_remove_from_hass(self):
        """Unsubscribe when removed."""
        self._availability_sub_state = await async_unsubscribe_topics(
            self.hass, self._availability_sub_state
        )

    @property
    def available(self) -> bool:
        """Return if the device is available."""
        availability_topic = self._avail_config.get(CONF_AVAILABILITY_TOPIC)
        return availability_topic is None or self._available


async def cleanup_device_registry(hass, device_id):
    """Remove device registry entry if there are no remaining entities or triggers."""
    # Local import to avoid circular dependencies
    # pylint: disable=import-outside-toplevel
    from . import device_trigger

    device_registry = await hass.helpers.device_registry.async_get_registry()
    entity_registry = await hass.helpers.entity_registry.async_get_registry()
    if (
        device_id
        and not hass.helpers.entity_registry.async_entries_for_device(
            entity_registry, device_id
        )
        and not await device_trigger.async_get_triggers(hass, device_id)
    ):
        device_registry.async_remove_device(device_id)


class MqttDiscoveryUpdate(Entity):
    """Mixin used to handle updated discovery message."""

    def __init__(self, discovery_data, discovery_update=None) -> None:
        """Initialize the discovery update mixin."""
        self._discovery_data = discovery_data
        self._discovery_update = discovery_update
        self._remove_signal = None
        self._removed_from_hass = False

    async def async_added_to_hass(self) -> None:
        """Subscribe to discovery updates."""
        await super().async_added_to_hass()
        self._removed_from_hass = False
        discovery_hash = (
            self._discovery_data[ATTR_DISCOVERY_HASH] if self._discovery_data else None
        )

        async def _async_remove_state_and_registry_entry(self) -> None:
            """Remove entity's state and entity registry entry.

            Remove entity from entity registry if it is registered, this also removes the state.
            If the entity is not in the entity registry, just remove the state.
            """
            entity_registry = (
                await self.hass.helpers.entity_registry.async_get_registry()
            )
            if entity_registry.async_is_registered(self.entity_id):
                entity_entry = entity_registry.async_get(self.entity_id)
                entity_registry.async_remove(self.entity_id)
                await cleanup_device_registry(self.hass, entity_entry.device_id)
            else:
                await self.async_remove()

        @callback
        async def discovery_callback(payload):
            """Handle discovery update."""
            _LOGGER.info(
                "Got update for entity with hash: %s '%s'", discovery_hash, payload,
            )
            debug_info.update_entity_discovery_data(self.hass, payload, self.entity_id)
            if not payload:
                # Empty payload: Remove component
                _LOGGER.info("Removing component: %s", self.entity_id)
                self._cleanup_discovery_on_remove()
                await _async_remove_state_and_registry_entry(self)
            elif self._discovery_update:
                # Non-empty payload: Notify component
                _LOGGER.info("Updating component: %s", self.entity_id)
                await self._discovery_update(payload)

        if discovery_hash:
            debug_info.add_entity_discovery_data(
                self.hass, self._discovery_data, self.entity_id
            )
            # Set in case the entity has been removed and is re-added
            set_discovery_hash(self.hass, discovery_hash)
            self._remove_signal = async_dispatcher_connect(
                self.hass,
                MQTT_DISCOVERY_UPDATED.format(discovery_hash),
                discovery_callback,
            )

    async def async_removed_from_registry(self) -> None:
        """Clear retained discovery topic in broker."""
        if not self._removed_from_hass:
            discovery_topic = self._discovery_data[ATTR_DISCOVERY_TOPIC]
            publish(
                self.hass, discovery_topic, "", retain=True,
            )

    async def async_will_remove_from_hass(self) -> None:
        """Stop listening to signal and cleanup discovery data.."""
        self._cleanup_discovery_on_remove()

    def _cleanup_discovery_on_remove(self) -> None:
        """Stop listening to signal and cleanup discovery data."""
        if self._discovery_data and not self._removed_from_hass:
            debug_info.remove_entity_data(self.hass, self.entity_id)
            clear_discovery_hash(self.hass, self._discovery_data[ATTR_DISCOVERY_HASH])
            self._removed_from_hass = True

        if self._remove_signal:
            self._remove_signal()
            self._remove_signal = None


def device_info_from_config(config):
    """Return a device description for device registry."""
    if not config:
        return None

    info = {
        "identifiers": {(DOMAIN, id_) for id_ in config[CONF_IDENTIFIERS]},
        "connections": {tuple(x) for x in config[CONF_CONNECTIONS]},
    }

    if CONF_MANUFACTURER in config:
        info["manufacturer"] = config[CONF_MANUFACTURER]

    if CONF_MODEL in config:
        info["model"] = config[CONF_MODEL]

    if CONF_NAME in config:
        info["name"] = config[CONF_NAME]

    if CONF_SW_VERSION in config:
        info["sw_version"] = config[CONF_SW_VERSION]

    if CONF_VIA_DEVICE in config:
        info["via_device"] = (DOMAIN, config[CONF_VIA_DEVICE])

    return info


class MqttEntityDeviceInfo(Entity):
    """Mixin used for mqtt platforms that support the device registry."""

    def __init__(self, device_config: Optional[ConfigType], config_entry=None) -> None:
        """Initialize the device mixin."""
        self._device_config = device_config
        self._config_entry = config_entry

    async def device_info_discovery_update(self, config: dict):
        """Handle updated discovery message."""
        self._device_config = config.get(CONF_DEVICE)
        device_registry = await self.hass.helpers.device_registry.async_get_registry()
        config_entry_id = self._config_entry.entry_id
        device_info = self.device_info

        if config_entry_id is not None and device_info is not None:
            device_info["config_entry_id"] = config_entry_id
            device_registry.async_get_or_create(**device_info)

    @property
    def device_info(self):
        """Return a device description for device registry."""
        return device_info_from_config(self._device_config)


@websocket_api.websocket_command(
    {vol.Required("type"): "mqtt/device/debug_info", vol.Required("device_id"): str}
)
@websocket_api.async_response
async def websocket_mqtt_info(hass, connection, msg):
    """Get MQTT debug info for device."""
    device_id = msg["device_id"]
    mqtt_info = await debug_info.info_for_device(hass, device_id)

    connection.send_result(msg["id"], mqtt_info)


@websocket_api.websocket_command(
    {vol.Required("type"): "mqtt/device/remove", vol.Required("device_id"): str}
)
@websocket_api.async_response
async def websocket_remove_device(hass, connection, msg):
    """Delete device."""
    device_id = msg["device_id"]
    dev_registry = await hass.helpers.device_registry.async_get_registry()

    device = dev_registry.async_get(device_id)
    if not device:
        connection.send_error(
            msg["id"], websocket_api.const.ERR_NOT_FOUND, "Device not found"
        )
        return

    for config_entry in device.config_entries:
        config_entry = hass.config_entries.async_get_entry(config_entry)
        # Only delete the device if it belongs to an MQTT device entry
        if config_entry.domain == DOMAIN:
            dev_registry.async_remove_device(device_id)
            connection.send_message(websocket_api.result_message(msg["id"]))
            return

    connection.send_error(
        msg["id"], websocket_api.const.ERR_NOT_FOUND, "Non MQTT device"
    )


@websocket_api.async_response
@websocket_api.websocket_command(
    {
        vol.Required("type"): "mqtt/subscribe",
        vol.Required("topic"): valid_subscribe_topic,
    }
)
async def websocket_subscribe(hass, connection, msg):
    """Subscribe to a MQTT topic."""
    if not connection.user.is_admin:
        raise Unauthorized

    async def forward_messages(mqttmsg: Message):
        """Forward events to websocket."""
        connection.send_message(
            websocket_api.event_message(
                msg["id"],
                {
                    "topic": mqttmsg.topic,
                    "payload": mqttmsg.payload,
                    "qos": mqttmsg.qos,
                    "retain": mqttmsg.retain,
                },
            )
        )

    connection.subscriptions[msg["id"]] = await async_subscribe(
        hass, msg["topic"], forward_messages
    )

    connection.send_message(websocket_api.result_message(msg["id"]))
