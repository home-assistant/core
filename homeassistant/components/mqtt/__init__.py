"""Support for MQTT message handling."""
import asyncio
from functools import lru_cache, partial, wraps
import inspect
from itertools import groupby
import logging
from operator import attrgetter
import os
import ssl
import time
from typing import Any, Callable, List, Optional, Union
import uuid

import attr
import certifi
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import websocket_api
from homeassistant.const import (
    CONF_CLIENT_ID,
    CONF_PASSWORD,
    CONF_PAYLOAD,
    CONF_PORT,
    CONF_PROTOCOL,
    CONF_USERNAME,
    CONF_VALUE_TEMPLATE,
    EVENT_HOMEASSISTANT_STARTED,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.const import CONF_UNIQUE_ID  # noqa: F401
from homeassistant.core import CoreState, Event, HassJob, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, Unauthorized
from homeassistant.helpers import config_validation as cv, event, template
from homeassistant.helpers.dispatcher import async_dispatcher_connect, dispatcher_send
from homeassistant.helpers.typing import ConfigType, HomeAssistantType, ServiceDataType
from homeassistant.loader import bind_hass
from homeassistant.util import dt as dt_util
from homeassistant.util.async_ import run_callback_threadsafe
from homeassistant.util.logging import catch_log_exception

# Loading the config flow file will register the flow
from . import config_flow  # noqa: F401 pylint: disable=unused-import
from . import debug_info, discovery
from .const import (
    ATTR_PAYLOAD,
    ATTR_QOS,
    ATTR_RETAIN,
    ATTR_TOPIC,
    CONF_BIRTH_MESSAGE,
    CONF_BROKER,
    CONF_DISCOVERY,
    CONF_QOS,
    CONF_RETAIN,
    CONF_STATE_TOPIC,
    CONF_WILL_MESSAGE,
    DATA_MQTT_CONFIG,
    DEFAULT_BIRTH,
    DEFAULT_DISCOVERY,
    DEFAULT_PREFIX,
    DEFAULT_QOS,
    DEFAULT_RETAIN,
    DEFAULT_WILL,
    DOMAIN,
    MQTT_CONNECTED,
    MQTT_DISCONNECTED,
    PROTOCOL_311,
)
from .discovery import LAST_DISCOVERY
from .models import Message, MessageCallbackType, PublishPayloadType
from .util import _VALID_QOS_SCHEMA, valid_publish_topic, valid_subscribe_topic

_LOGGER = logging.getLogger(__name__)

DATA_MQTT = "mqtt"

SERVICE_PUBLISH = "publish"
SERVICE_DUMP = "dump"

CONF_DISCOVERY_PREFIX = "discovery_prefix"
CONF_KEEPALIVE = "keepalive"
CONF_CERTIFICATE = "certificate"
CONF_CLIENT_KEY = "client_key"
CONF_CLIENT_CERT = "client_cert"
CONF_TLS_INSECURE = "tls_insecure"
CONF_TLS_VERSION = "tls_version"

CONF_COMMAND_TOPIC = "command_topic"
CONF_TOPIC = "topic"

PROTOCOL_31 = "3.1"

DEFAULT_PORT = 1883
DEFAULT_KEEPALIVE = 60
DEFAULT_PROTOCOL = PROTOCOL_311
DEFAULT_TLS_PROTOCOL = "auto"

ATTR_PAYLOAD_TEMPLATE = "payload_template"

MAX_RECONNECT_WAIT = 300  # seconds

CONNECTION_SUCCESS = "connection_success"
CONNECTION_FAILED = "connection_failed"
CONNECTION_FAILED_RECOVERABLE = "connection_failed_recoverable"

DISCOVERY_COOLDOWN = 2
TIMEOUT_ACK = 10

PLATFORMS = [
    "alarm_control_panel",
    "binary_sensor",
    "camera",
    "climate",
    "cover",
    "fan",
    "light",
    "lock",
    "number",
    "scene",
    "sensor",
    "switch",
    "vacuum",
]


CLIENT_KEY_AUTH_MSG = (
    "client_key and client_cert must both be present in "
    "the MQTT broker configuration"
)

MQTT_WILL_BIRTH_SCHEMA = vol.Schema(
    {
        vol.Inclusive(ATTR_TOPIC, "topic_payload"): valid_publish_topic,
        vol.Inclusive(ATTR_PAYLOAD, "topic_payload"): cv.string,
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
        DOMAIN: vol.All(
            cv.deprecated(CONF_TLS_VERSION),
            vol.Schema(
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
                    vol.Optional(
                        CONF_TLS_VERSION, default=DEFAULT_TLS_PROTOCOL
                    ): vol.Any("auto", "1.0", "1.1", "1.2"),
                    vol.Optional(CONF_PROTOCOL, default=DEFAULT_PROTOCOL): vol.All(
                        cv.string, vol.In([PROTOCOL_31, PROTOCOL_311])
                    ),
                    vol.Optional(
                        CONF_WILL_MESSAGE, default=DEFAULT_WILL
                    ): MQTT_WILL_BIRTH_SCHEMA,
                    vol.Optional(
                        CONF_BIRTH_MESSAGE, default=DEFAULT_BIRTH
                    ): MQTT_WILL_BIRTH_SCHEMA,
                    vol.Optional(CONF_DISCOVERY, default=DEFAULT_DISCOVERY): cv.boolean,
                    # discovery_prefix must be a valid publish topic because if no
                    # state topic is specified, it will be created with the given prefix.
                    vol.Optional(
                        CONF_DISCOVERY_PREFIX, default=DEFAULT_PREFIX
                    ): valid_publish_topic,
                }
            ),
        )
    },
    extra=vol.ALLOW_EXTRA,
)

SCHEMA_BASE = {vol.Optional(CONF_QOS, default=DEFAULT_QOS): _VALID_QOS_SCHEMA}

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
        vol.Exclusive(ATTR_PAYLOAD, CONF_PAYLOAD): cv.string,
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
    """Publish message to an MQTT topic."""
    hass.add_job(async_publish_template, hass, topic, payload_template, qos, retain)


@bind_hass
def async_publish_template(
    hass: HomeAssistantType, topic, payload_template, qos=None, retain=None
) -> None:
    """Publish message to an MQTT topic using a template payload."""
    data = _build_publish_data(topic, qos, retain)
    data[ATTR_PAYLOAD_TEMPLATE] = payload_template
    hass.async_create_task(hass.services.async_call(DOMAIN, SERVICE_PUBLISH, data))


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
            """Call with deprecated signature."""
            await msg_callback(msg.topic, msg.payload, msg.qos)

        wrapper_func = async_wrapper
    else:

        @wraps(msg_callback)
        def wrapper(msg: Any) -> None:
            """Call with deprecated signature."""
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


async def _async_setup_discovery(
    hass: HomeAssistantType, conf: ConfigType, config_entry
) -> bool:
    """Try to start the discovery of MQTT devices.

    This method is a coroutine.
    """
    success: bool = await discovery.async_start(
        hass, conf[CONF_DISCOVERY_PREFIX], config_entry
    )

    return success


async def async_setup(hass: HomeAssistantType, config: ConfigType) -> bool:
    """Start the MQTT protocol service."""
    conf: Optional[ConfigType] = config.get(DOMAIN)

    websocket_api.async_register_command(hass, websocket_subscribe)
    websocket_api.async_register_command(hass, websocket_remove_device)
    websocket_api.async_register_command(hass, websocket_mqtt_info)

    if conf is None:
        # If we have a config entry, setup is done by that config entry.
        # If there is no config entry, this should fail.
        return bool(hass.config_entries.async_entries(DOMAIN))

    conf = dict(conf)

    hass.data[DATA_MQTT_CONFIG] = conf

    # Only import if we haven't before.
    if not hass.config_entries.async_entries(DOMAIN):
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data={}
            )
        )

    return True


def _merge_config(entry, conf):
    """Merge configuration.yaml config with config entry."""
    return {**conf, **entry.data}


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
        shared_keys = conf.keys() & entry.data.keys()
        override = {k: entry.data[k] for k in shared_keys}
        if CONF_PASSWORD in override:
            override[CONF_PASSWORD] = "********"
        _LOGGER.info(
            "Data in your configuration entry is going to override your "
            "configuration.yaml: %s",
            override,
        )

    conf = _merge_config(entry, conf)

    hass.data[DATA_MQTT] = MQTT(
        hass,
        entry,
        conf,
    )

    await hass.data[DATA_MQTT].async_connect()

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
                payload = template.Template(payload_template, hass).async_render(
                    parse_result=False
                )
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
        await _async_setup_discovery(hass, conf, entry)

    return True


@attr.s(slots=True, frozen=True)
class Subscription:
    """Class to hold data about an active subscription."""

    topic: str = attr.ib()
    matcher: Any = attr.ib()
    job: HassJob = attr.ib()
    qos: int = attr.ib(default=0)
    encoding: str = attr.ib(default="utf-8")


class MQTT:
    """Home Assistant MQTT client."""

    def __init__(
        self,
        hass: HomeAssistantType,
        config_entry,
        conf,
    ) -> None:
        """Initialize Home Assistant MQTT client."""
        # We don't import on the top because some integrations
        # should be able to optionally rely on MQTT.
        import paho.mqtt.client as mqtt  # pylint: disable=import-outside-toplevel

        self.hass = hass
        self.config_entry = config_entry
        self.conf = conf
        self.subscriptions: List[Subscription] = []
        self.connected = False
        self._ha_started = asyncio.Event()
        self._last_subscribe = time.time()
        self._mqttc: mqtt.Client = None
        self._paho_lock = asyncio.Lock()

        self._pending_operations = {}

        if self.hass.state == CoreState.running:
            self._ha_started.set()
        else:

            @callback
            def ha_started(_):
                self._ha_started.set()

            self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, ha_started)

        self.init_client()
        self.config_entry.add_update_listener(self.async_config_entry_updated)

    @staticmethod
    async def async_config_entry_updated(hass, entry) -> None:
        """Handle signals of config entry being updated.

        This is a static method because a class method (bound method), can not be used with weak references.
        Causes for this is config entry options changing.
        """
        self = hass.data[DATA_MQTT]

        conf = hass.data.get(DATA_MQTT_CONFIG)
        if conf is None:
            conf = CONFIG_SCHEMA({DOMAIN: dict(entry.data)})[DOMAIN]

        self.conf = _merge_config(entry, conf)
        await self.async_disconnect()
        self.init_client()
        await self.async_connect()

        await discovery.async_stop(hass)
        if self.conf.get(CONF_DISCOVERY):
            await _async_setup_discovery(hass, self.conf, entry)

    def init_client(self):
        """Initialize paho client."""
        # We don't import on the top because some integrations
        # should be able to optionally rely on MQTT.
        import paho.mqtt.client as mqtt  # pylint: disable=import-outside-toplevel

        if self.conf[CONF_PROTOCOL] == PROTOCOL_31:
            proto: int = mqtt.MQTTv31
        else:
            proto = mqtt.MQTTv311

        client_id = self.conf.get(CONF_CLIENT_ID)
        if client_id is None:
            # PAHO MQTT relies on the MQTT server to generate random client IDs.
            # However, that feature is not mandatory so we generate our own.
            client_id = mqtt.base62(uuid.uuid4().int, padding=22)
        self._mqttc = mqtt.Client(client_id, protocol=proto)

        # Enable logging
        self._mqttc.enable_logger()

        username = self.conf.get(CONF_USERNAME)
        password = self.conf.get(CONF_PASSWORD)
        if username is not None:
            self._mqttc.username_pw_set(username, password)

        certificate = self.conf.get(CONF_CERTIFICATE)

        # For cloudmqtt.com, secured connection, auto fill in certificate
        if (
            certificate is None
            and 19999 < self.conf[CONF_PORT] < 30000
            and self.conf[CONF_BROKER].endswith(".cloudmqtt.com")
        ):
            certificate = os.path.join(
                os.path.dirname(__file__), "addtrustexternalcaroot.crt"
            )

        # When the certificate is set to auto, use bundled certs from certifi
        elif certificate == "auto":
            certificate = certifi.where()

        client_key = self.conf.get(CONF_CLIENT_KEY)
        client_cert = self.conf.get(CONF_CLIENT_CERT)
        tls_insecure = self.conf.get(CONF_TLS_INSECURE)
        if certificate is not None:
            self._mqttc.tls_set(
                certificate,
                certfile=client_cert,
                keyfile=client_key,
                tls_version=ssl.PROTOCOL_TLS,
            )

            if tls_insecure is not None:
                self._mqttc.tls_insecure_set(tls_insecure)

        self._mqttc.on_connect = self._mqtt_on_connect
        self._mqttc.on_disconnect = self._mqtt_on_disconnect
        self._mqttc.on_message = self._mqtt_on_message
        self._mqttc.on_publish = self._mqtt_on_callback
        self._mqttc.on_subscribe = self._mqtt_on_callback
        self._mqttc.on_unsubscribe = self._mqtt_on_callback

        if (
            CONF_WILL_MESSAGE in self.conf
            and ATTR_TOPIC in self.conf[CONF_WILL_MESSAGE]
        ):
            will_message = Message(**self.conf[CONF_WILL_MESSAGE])
        else:
            will_message = None

        if will_message is not None:
            self._mqttc.will_set(  # pylint: disable=no-value-for-parameter
                topic=will_message.topic,
                payload=will_message.payload,
                qos=will_message.qos,
                retain=will_message.retain,
            )

    async def async_publish(
        self, topic: str, payload: PublishPayloadType, qos: int, retain: bool
    ) -> None:
        """Publish a MQTT message."""
        async with self._paho_lock:
            msg_info = await self.hass.async_add_executor_job(
                self._mqttc.publish, topic, payload, qos, retain
            )
            _LOGGER.debug(
                "Transmitting message on %s: '%s', mid: %s",
                topic,
                payload,
                msg_info.mid,
            )
            _raise_on_error(msg_info.rc)
        await self._wait_for_mid(msg_info.mid)

    async def async_connect(self) -> str:
        """Connect to the host. Does not process messages yet."""
        # pylint: disable=import-outside-toplevel
        import paho.mqtt.client as mqtt

        result: int = None
        try:
            result = await self.hass.async_add_executor_job(
                self._mqttc.connect,
                self.conf[CONF_BROKER],
                self.conf[CONF_PORT],
                self.conf[CONF_KEEPALIVE],
            )
        except OSError as err:
            _LOGGER.error("Failed to connect to MQTT server due to exception: %s", err)

        if result is not None and result != 0:
            _LOGGER.error(
                "Failed to connect to MQTT server: %s", mqtt.error_string(result)
            )

        self._mqttc.loop_start()

    async def async_disconnect(self):
        """Stop the MQTT client."""

        def stop():
            """Stop the MQTT client."""
            # Do not disconnect, we want the broker to always publish will
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

        subscription = Subscription(
            topic, _matcher_for_topic(topic), HassJob(msg_callback), qos, encoding
        )
        self.subscriptions.append(subscription)
        self._matching_subscriptions.cache_clear()

        # Only subscribe if currently connected.
        if self.connected:
            self._last_subscribe = time.time()
            await self._async_perform_subscription(topic, qos)

        @callback
        def async_remove() -> None:
            """Remove subscription."""
            if subscription not in self.subscriptions:
                raise HomeAssistantError("Can't remove subscription twice")
            self.subscriptions.remove(subscription)
            self._matching_subscriptions.cache_clear()

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
            result, mid = await self.hass.async_add_executor_job(
                self._mqttc.unsubscribe, topic
            )
            _LOGGER.debug("Unsubscribing from %s, mid: %s", topic, mid)
            _raise_on_error(result)
        await self._wait_for_mid(mid)

    async def _async_perform_subscription(self, topic: str, qos: int) -> None:
        """Perform a paho-mqtt subscription."""
        async with self._paho_lock:
            result: int = None
            result, mid = await self.hass.async_add_executor_job(
                self._mqttc.subscribe, topic, qos
            )
            _LOGGER.debug("Subscribing to %s, mid: %s", topic, mid)
            _raise_on_error(result)
        await self._wait_for_mid(mid)

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
            return

        self.connected = True
        dispatcher_send(self.hass, MQTT_CONNECTED)
        _LOGGER.info(
            "Connected to MQTT server %s:%s (%s)",
            self.conf[CONF_BROKER],
            self.conf[CONF_PORT],
            result_code,
        )

        # Group subscriptions to only re-subscribe once for each topic.
        keyfunc = attrgetter("topic")
        for topic, subs in groupby(sorted(self.subscriptions, key=keyfunc), keyfunc):
            # Re-subscribe with the highest requested qos
            max_qos = max(subscription.qos for subscription in subs)
            self.hass.add_job(self._async_perform_subscription, topic, max_qos)

        if (
            CONF_BIRTH_MESSAGE in self.conf
            and ATTR_TOPIC in self.conf[CONF_BIRTH_MESSAGE]
        ):

            async def publish_birth_message(birth_message):
                await self._ha_started.wait()  # Wait for Home Assistant to start
                await self._discovery_cooldown()  # Wait for MQTT discovery to cool down
                await self.async_publish(  # pylint: disable=no-value-for-parameter
                    topic=birth_message.topic,
                    payload=birth_message.payload,
                    qos=birth_message.qos,
                    retain=birth_message.retain,
                )

            birth_message = Message(**self.conf[CONF_BIRTH_MESSAGE])
            asyncio.run_coroutine_threadsafe(
                publish_birth_message(birth_message), self.hass.loop
            )

    def _mqtt_on_message(self, _mqttc, _userdata, msg) -> None:
        """Message received callback."""
        self.hass.add_job(self._mqtt_handle_message, msg)

    @lru_cache(2048)
    def _matching_subscriptions(self, topic):
        subscriptions = []
        for subscription in self.subscriptions:
            if subscription.matcher(topic):
                subscriptions.append(subscription)
        return subscriptions

    @callback
    def _mqtt_handle_message(self, msg) -> None:
        _LOGGER.debug(
            "Received message on %s%s: %s",
            msg.topic,
            " (retained)" if msg.retain else "",
            msg.payload[0:8192],
        )
        timestamp = dt_util.utcnow()

        subscriptions = self._matching_subscriptions(msg.topic)

        for subscription in subscriptions:

            payload: SubscribePayloadType = msg.payload
            if subscription.encoding is not None:
                try:
                    payload = msg.payload.decode(subscription.encoding)
                except (AttributeError, UnicodeDecodeError):
                    _LOGGER.warning(
                        "Can't decode payload %s on %s with encoding %s (for %s)",
                        msg.payload[0:8192],
                        msg.topic,
                        subscription.encoding,
                        subscription.job,
                    )
                    continue

            self.hass.async_run_hass_job(
                subscription.job,
                Message(
                    msg.topic,
                    payload,
                    msg.qos,
                    msg.retain,
                    subscription.topic,
                    timestamp,
                ),
            )

    def _mqtt_on_callback(self, _mqttc, _userdata, mid, _granted_qos=None) -> None:
        """Publish / Subscribe / Unsubscribe callback."""
        self.hass.add_job(self._mqtt_handle_mid, mid)

    @callback
    def _mqtt_handle_mid(self, mid) -> None:
        # Create the mid event if not created, either _mqtt_handle_mid or _wait_for_mid
        # may be executed first.
        if mid not in self._pending_operations:
            self._pending_operations[mid] = asyncio.Event()
        self._pending_operations[mid].set()

    def _mqtt_on_disconnect(self, _mqttc, _userdata, result_code: int) -> None:
        """Disconnected callback."""
        self.connected = False
        dispatcher_send(self.hass, MQTT_DISCONNECTED)
        _LOGGER.warning(
            "Disconnected from MQTT server %s:%s (%s)",
            self.conf[CONF_BROKER],
            self.conf[CONF_PORT],
            result_code,
        )

    async def _wait_for_mid(self, mid):
        """Wait for ACK from broker."""
        # Create the mid event if not created, either _mqtt_handle_mid or _wait_for_mid
        # may be executed first.
        if mid not in self._pending_operations:
            self._pending_operations[mid] = asyncio.Event()
        try:
            await asyncio.wait_for(self._pending_operations[mid].wait(), TIMEOUT_ACK)
        except asyncio.TimeoutError:
            _LOGGER.error("Timed out waiting for mid %s", mid)
        finally:
            del self._pending_operations[mid]

    async def _discovery_cooldown(self):
        now = time.time()
        # Reset discovery and subscribe cooldowns
        self.hass.data[LAST_DISCOVERY] = now
        self._last_subscribe = now

        last_discovery = self.hass.data[LAST_DISCOVERY]
        last_subscribe = self._last_subscribe
        wait_until = max(
            last_discovery + DISCOVERY_COOLDOWN, last_subscribe + DISCOVERY_COOLDOWN
        )
        while now < wait_until:
            await asyncio.sleep(wait_until - now)
            now = time.time()
            last_discovery = self.hass.data[LAST_DISCOVERY]
            last_subscribe = self._last_subscribe
            wait_until = max(
                last_discovery + DISCOVERY_COOLDOWN, last_subscribe + DISCOVERY_COOLDOWN
            )


def _raise_on_error(result_code: int) -> None:
    """Raise error if error result."""
    # pylint: disable=import-outside-toplevel
    import paho.mqtt.client as mqtt

    if result_code != 0:
        raise HomeAssistantError(
            f"Error talking to MQTT: {mqtt.error_string(result_code)}"
        )


def _matcher_for_topic(subscription: str) -> Any:
    # pylint: disable=import-outside-toplevel
    from paho.mqtt.matcher import MQTTMatcher

    matcher = MQTTMatcher()
    matcher[subscription] = True

    return lambda topic: next(matcher.iter_match(topic), False)


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


@callback
def async_subscribe_connection_status(hass, connection_status_callback):
    """Subscribe to MQTT connection changes."""

    connection_status_callback_job = HassJob(connection_status_callback)

    async def connected():
        task = hass.async_run_hass_job(connection_status_callback_job, True)
        if task:
            await task

    async def disconnected():
        task = hass.async_run_hass_job(connection_status_callback_job, False)
        if task:
            await task

    subscriptions = {
        "connect": async_dispatcher_connect(hass, MQTT_CONNECTED, connected),
        "disconnect": async_dispatcher_connect(hass, MQTT_DISCONNECTED, disconnected),
    }

    @callback
    def unsubscribe():
        subscriptions["connect"]()
        subscriptions["disconnect"]()

    return unsubscribe


def is_connected(hass):
    """Return if MQTT client is connected."""
    return hass.data[DATA_MQTT].connected
