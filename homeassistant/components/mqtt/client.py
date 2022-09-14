"""Support for MQTT message handling."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Coroutine, Iterable
from functools import lru_cache, partial, wraps
import inspect
from itertools import groupby
import logging
from operator import attrgetter
import ssl
import time
from typing import TYPE_CHECKING, Any, Union, cast
import uuid

import attr
import certifi
from paho.mqtt.client import MQTTMessage

from homeassistant.const import (
    CONF_CLIENT_ID,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_PROTOCOL,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STARTED,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import CoreState, Event, HassJob, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import dispatcher_send
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import bind_hass
from homeassistant.util import dt as dt_util
from homeassistant.util.async_ import run_callback_threadsafe
from homeassistant.util.logging import catch_log_exception

from .const import (
    ATTR_TOPIC,
    CONF_BIRTH_MESSAGE,
    CONF_BROKER,
    CONF_CERTIFICATE,
    CONF_CLIENT_CERT,
    CONF_CLIENT_KEY,
    CONF_KEEPALIVE,
    CONF_TLS_INSECURE,
    CONF_WILL_MESSAGE,
    DATA_MQTT,
    DEFAULT_ENCODING,
    DEFAULT_QOS,
    MQTT_CONNECTED,
    MQTT_DISCONNECTED,
    PROTOCOL_31,
)
from .discovery import LAST_DISCOVERY
from .models import (
    AsyncMessageCallbackType,
    MessageCallbackType,
    PublishMessage,
    PublishPayloadType,
    ReceiveMessage,
    ReceivePayloadType,
)
from .util import mqtt_config_entry_enabled

if TYPE_CHECKING:
    # Only import for paho-mqtt type checking here, imports are done locally
    # because integrations should be able to optionally rely on MQTT.
    import paho.mqtt.client as mqtt

_LOGGER = logging.getLogger(__name__)

DISCOVERY_COOLDOWN = 2
TIMEOUT_ACK = 10

SubscribePayloadType = Union[str, bytes]  # Only bytes if encoding is None


def publish(
    hass: HomeAssistant,
    topic: str,
    payload: PublishPayloadType,
    qos: int | None = 0,
    retain: bool | None = False,
    encoding: str | None = DEFAULT_ENCODING,
) -> None:
    """Publish message to a MQTT topic."""
    hass.add_job(async_publish, hass, topic, payload, qos, retain, encoding)


async def async_publish(
    hass: HomeAssistant,
    topic: str,
    payload: PublishPayloadType,
    qos: int | None = 0,
    retain: bool | None = False,
    encoding: str | None = DEFAULT_ENCODING,
) -> None:
    """Publish message to a MQTT topic."""

    if DATA_MQTT not in hass.data or not mqtt_config_entry_enabled(hass):
        raise HomeAssistantError(
            f"Cannot publish to topic '{topic}', MQTT is not enabled"
        )
    outgoing_payload = payload
    if not isinstance(payload, bytes):
        if not encoding:
            _LOGGER.error(
                "Can't pass-through payload for publishing %s on %s with no encoding set, need 'bytes' got %s",
                payload,
                topic,
                type(payload),
            )
            return
        outgoing_payload = str(payload)
        if encoding != DEFAULT_ENCODING:
            # a string is encoded as utf-8 by default, other encoding requires bytes as payload
            try:
                outgoing_payload = outgoing_payload.encode(encoding)
            except (AttributeError, LookupError, UnicodeEncodeError):
                _LOGGER.error(
                    "Can't encode payload for publishing %s on %s with encoding %s",
                    payload,
                    topic,
                    encoding,
                )
                return

    await hass.data[DATA_MQTT].async_publish(topic, outgoing_payload, qos, retain)


AsyncDeprecatedMessageCallbackType = Callable[
    [str, ReceivePayloadType, int], Awaitable[None]
]
DeprecatedMessageCallbackType = Callable[[str, ReceivePayloadType, int], None]


def wrap_msg_callback(
    msg_callback: AsyncDeprecatedMessageCallbackType | DeprecatedMessageCallbackType,
) -> AsyncMessageCallbackType | MessageCallbackType:
    """Wrap an MQTT message callback to support deprecated signature."""
    # Check for partials to properly determine if coroutine function
    check_func = msg_callback
    while isinstance(check_func, partial):
        check_func = check_func.func

    wrapper_func: AsyncMessageCallbackType | MessageCallbackType
    if asyncio.iscoroutinefunction(check_func):

        @wraps(msg_callback)
        async def async_wrapper(msg: ReceiveMessage) -> None:
            """Call with deprecated signature."""
            await cast(AsyncDeprecatedMessageCallbackType, msg_callback)(
                msg.topic, msg.payload, msg.qos
            )

        wrapper_func = async_wrapper
    else:

        @wraps(msg_callback)
        def wrapper(msg: ReceiveMessage) -> None:
            """Call with deprecated signature."""
            msg_callback(msg.topic, msg.payload, msg.qos)

        wrapper_func = wrapper
    return wrapper_func


@bind_hass
async def async_subscribe(
    hass: HomeAssistant,
    topic: str,
    msg_callback: AsyncMessageCallbackType
    | MessageCallbackType
    | DeprecatedMessageCallbackType
    | AsyncDeprecatedMessageCallbackType,
    qos: int = DEFAULT_QOS,
    encoding: str | None = "utf-8",
):
    """Subscribe to an MQTT topic.

    Call the return value to unsubscribe.
    """
    if DATA_MQTT not in hass.data or not mqtt_config_entry_enabled(hass):
        raise HomeAssistantError(
            f"Cannot subscribe to topic '{topic}', MQTT is not enabled"
        )
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
        module = inspect.getmodule(msg_callback)
        _LOGGER.warning(
            "Signature of MQTT msg_callback '%s.%s' is deprecated",
            module.__name__ if module else "<unknown>",
            msg_callback.__name__,
        )
        wrapped_msg_callback = wrap_msg_callback(
            cast(DeprecatedMessageCallbackType, msg_callback)
        )

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
    hass: HomeAssistant,
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


@attr.s(slots=True, frozen=True)
class Subscription:
    """Class to hold data about an active subscription."""

    topic: str = attr.ib()
    matcher: Any = attr.ib()
    job: HassJob[[ReceiveMessage], Coroutine[Any, Any, None] | None] = attr.ib()
    qos: int = attr.ib(default=0)
    encoding: str | None = attr.ib(default="utf-8")


class MqttClientSetup:
    """Helper class to setup the paho mqtt client from config."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the MQTT client setup helper."""

        # We don't import on the top because some integrations
        # should be able to optionally rely on MQTT.
        import paho.mqtt.client as mqtt  # pylint: disable=import-outside-toplevel

        if config[CONF_PROTOCOL] == PROTOCOL_31:
            proto = mqtt.MQTTv31
        else:
            proto = mqtt.MQTTv311

        if (client_id := config.get(CONF_CLIENT_ID)) is None:
            # PAHO MQTT relies on the MQTT server to generate random client IDs.
            # However, that feature is not mandatory so we generate our own.
            client_id = mqtt.base62(uuid.uuid4().int, padding=22)
        self._client = mqtt.Client(client_id, protocol=proto)

        # Enable logging
        self._client.enable_logger()

        username = config.get(CONF_USERNAME)
        password = config.get(CONF_PASSWORD)
        if username is not None:
            self._client.username_pw_set(username, password)

        if (certificate := config.get(CONF_CERTIFICATE)) == "auto":
            certificate = certifi.where()

        client_key = config.get(CONF_CLIENT_KEY)
        client_cert = config.get(CONF_CLIENT_CERT)
        tls_insecure = config.get(CONF_TLS_INSECURE)
        if certificate is not None:
            self._client.tls_set(
                certificate,
                certfile=client_cert,
                keyfile=client_key,
                tls_version=ssl.PROTOCOL_TLS,
            )

            if tls_insecure is not None:
                self._client.tls_insecure_set(tls_insecure)

    @property
    def client(self) -> mqtt.Client:
        """Return the paho MQTT client."""
        return self._client


class MQTT:
    """Home Assistant MQTT client."""

    def __init__(
        self,
        hass,
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
        self.subscriptions: list[Subscription] = []
        self.connected = False
        self._ha_started = asyncio.Event()
        self._last_subscribe = time.time()
        self._mqttc: mqtt.Client = None
        self._cleanup_on_unload: list[Callable] = []

        self._paho_lock = asyncio.Lock()  # Prevents parallel calls to the MQTT client
        self._pending_operations: dict[int, asyncio.Event] = {}
        self._pending_operations_condition = asyncio.Condition()

        if self.hass.state == CoreState.running:
            self._ha_started.set()
        else:

            @callback
            def ha_started(_):
                self._ha_started.set()

            self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, ha_started)

        self.init_client()

        async def async_stop_mqtt(_event: Event):
            """Stop MQTT component."""
            await self.async_disconnect()

        self._cleanup_on_unload.append(
            hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_stop_mqtt)
        )

    def cleanup(self):
        """Clean up listeners."""
        while self._cleanup_on_unload:
            self._cleanup_on_unload.pop()()

    def init_client(self):
        """Initialize paho client."""
        self._mqttc = MqttClientSetup(self.conf).client
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
            will_message = PublishMessage(**self.conf[CONF_WILL_MESSAGE])
        else:
            will_message = None

        if will_message is not None:
            self._mqttc.will_set(
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

    async def async_connect(self) -> None:
        """Connect to the host. Does not process messages yet."""
        # pylint: disable-next=import-outside-toplevel
        import paho.mqtt.client as mqtt

        result: int | None = None
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

        def no_more_acks() -> bool:
            """Return False if there are unprocessed ACKs."""
            return not bool(self._pending_operations)

        # wait for ACKs to be processed
        async with self._pending_operations_condition:
            await self._pending_operations_condition.wait_for(no_more_acks)

        # stop the MQTT loop
        async with self._paho_lock:
            await self.hass.async_add_executor_job(stop)

    async def async_subscribe(
        self,
        topic: str,
        msg_callback: AsyncMessageCallbackType | MessageCallbackType,
        qos: int,
        encoding: str | None = None,
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
            await self._async_perform_subscriptions(((topic, qos),))

        @callback
        def async_remove() -> None:
            """Remove subscription."""
            if subscription not in self.subscriptions:
                raise HomeAssistantError("Can't remove subscription twice")
            self.subscriptions.remove(subscription)
            self._matching_subscriptions.cache_clear()

            # Only unsubscribe if currently connected
            if self.connected:
                self.hass.async_create_task(self._async_unsubscribe(topic))

        return async_remove

    async def _async_unsubscribe(self, topic: str) -> None:
        """Unsubscribe from a topic.

        This method is a coroutine.
        """

        def _client_unsubscribe(topic: str) -> int:
            result: int | None = None
            result, mid = self._mqttc.unsubscribe(topic)
            _LOGGER.debug("Unsubscribing from %s, mid: %s", topic, mid)
            _raise_on_error(result)
            return mid

        if any(other.topic == topic for other in self.subscriptions):
            # Other subscriptions on topic remaining - don't unsubscribe.
            return

        async with self._paho_lock:
            mid = await self.hass.async_add_executor_job(_client_unsubscribe, topic)
            await self._register_mid(mid)

        self.hass.async_create_task(self._wait_for_mid(mid))

    async def _async_perform_subscriptions(
        self, subscriptions: Iterable[tuple[str, int]]
    ) -> None:
        """Perform MQTT client subscriptions."""

        def _process_client_subscriptions() -> list[tuple[int, int]]:
            """Initiate all subscriptions on the MQTT client and return the results."""
            subscribe_result_list = []
            for topic, qos in subscriptions:
                result, mid = self._mqttc.subscribe(topic, qos)
                subscribe_result_list.append((result, mid))
                _LOGGER.debug("Subscribing to %s, mid: %s", topic, mid)
            return subscribe_result_list

        async with self._paho_lock:
            results = await self.hass.async_add_executor_job(
                _process_client_subscriptions
            )

        tasks = []
        errors = []
        for result, mid in results:
            if result == 0:
                tasks.append(self._wait_for_mid(mid))
            else:
                errors.append(result)

        if tasks:
            await asyncio.gather(*tasks)
        if errors:
            _raise_on_errors(errors)

    def _mqtt_on_connect(self, _mqttc, _userdata, _flags, result_code: int) -> None:
        """On connect callback.

        Resubscribe to all topics we were subscribed to and publish birth
        message.
        """
        # pylint: disable-next=import-outside-toplevel
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
        self.hass.add_job(
            self._async_perform_subscriptions,
            [
                # Re-subscribe with the highest requested qos
                (topic, max(subscription.qos for subscription in subs))
                for topic, subs in groupby(
                    sorted(self.subscriptions, key=keyfunc), keyfunc
                )
            ],
        )

        if (
            CONF_BIRTH_MESSAGE in self.conf
            and ATTR_TOPIC in self.conf[CONF_BIRTH_MESSAGE]
        ):

            async def publish_birth_message(birth_message):
                await self._ha_started.wait()  # Wait for Home Assistant to start
                await self._discovery_cooldown()  # Wait for MQTT discovery to cool down
                await self.async_publish(
                    topic=birth_message.topic,
                    payload=birth_message.payload,
                    qos=birth_message.qos,
                    retain=birth_message.retain,
                )

            birth_message = PublishMessage(**self.conf[CONF_BIRTH_MESSAGE])
            asyncio.run_coroutine_threadsafe(
                publish_birth_message(birth_message), self.hass.loop
            )

    def _mqtt_on_message(self, _mqttc, _userdata, msg) -> None:
        """Message received callback."""
        self.hass.add_job(self._mqtt_handle_message, msg)

    @lru_cache(2048)
    def _matching_subscriptions(self, topic: str) -> list[Subscription]:
        subscriptions: list[Subscription] = []
        for subscription in self.subscriptions:
            if subscription.matcher(topic):
                subscriptions.append(subscription)
        return subscriptions

    @callback
    def _mqtt_handle_message(self, msg: MQTTMessage) -> None:
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
                ReceiveMessage(
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

    async def _mqtt_handle_mid(self, mid: int) -> None:
        # Create the mid event if not created, either _mqtt_handle_mid or _wait_for_mid
        # may be executed first.
        await self._register_mid(mid)
        self._pending_operations[mid].set()

    async def _register_mid(self, mid: int) -> None:
        """Create Event for an expected ACK."""
        async with self._pending_operations_condition:
            if mid not in self._pending_operations:
                self._pending_operations[mid] = asyncio.Event()

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

    async def _wait_for_mid(self, mid: int) -> None:
        """Wait for ACK from broker."""
        # Create the mid event if not created, either _mqtt_handle_mid or _wait_for_mid
        # may be executed first.
        await self._register_mid(mid)
        try:
            await asyncio.wait_for(self._pending_operations[mid].wait(), TIMEOUT_ACK)
        except asyncio.TimeoutError:
            _LOGGER.warning(
                "No ACK from MQTT server in %s seconds (mid: %s)", TIMEOUT_ACK, mid
            )
        finally:
            async with self._pending_operations_condition:
                # Cleanup ACK sync buffer
                del self._pending_operations[mid]
                self._pending_operations_condition.notify_all()

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


def _raise_on_errors(result_codes: Iterable[int | None]) -> None:
    """Raise error if error result."""
    # pylint: disable-next=import-outside-toplevel
    import paho.mqtt.client as mqtt

    if messages := [
        mqtt.error_string(result_code)
        for result_code in result_codes
        if result_code != 0
    ]:
        raise HomeAssistantError(f"Error talking to MQTT: {', '.join(messages)}")


def _raise_on_error(result_code: int | None) -> None:
    """Raise error if error result."""
    _raise_on_errors((result_code,))


def _matcher_for_topic(subscription: str) -> Any:
    # pylint: disable-next=import-outside-toplevel
    from paho.mqtt.matcher import MQTTMatcher

    matcher = MQTTMatcher()
    matcher[subscription] = True

    return lambda topic: next(matcher.iter_match(topic), False)
