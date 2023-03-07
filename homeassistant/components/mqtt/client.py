"""Support for MQTT message handling."""
from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine, Iterable
from functools import lru_cache
import inspect
from itertools import chain, groupby
import logging
from operator import attrgetter
import ssl
import time
from typing import TYPE_CHECKING, Any
import uuid

import async_timeout
import attr
import certifi

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_CLIENT_ID,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_PROTOCOL,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STARTED,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import (
    CALLBACK_TYPE,
    CoreState,
    Event,
    HassJob,
    HomeAssistant,
    callback,
)
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
    CONF_TRANSPORT,
    CONF_WILL_MESSAGE,
    CONF_WS_HEADERS,
    CONF_WS_PATH,
    DEFAULT_ENCODING,
    DEFAULT_PROTOCOL,
    DEFAULT_QOS,
    DEFAULT_TRANSPORT,
    MQTT_CONNECTED,
    MQTT_DISCONNECTED,
    PROTOCOL_5,
    PROTOCOL_31,
    TRANSPORT_WEBSOCKETS,
)
from .models import (
    AsyncMessageCallbackType,
    MessageCallbackType,
    PublishMessage,
    PublishPayloadType,
    ReceiveMessage,
)
from .util import get_file_path, get_mqtt_data, mqtt_config_entry_enabled

if TYPE_CHECKING:
    # Only import for paho-mqtt type checking here, imports are done locally
    # because integrations should be able to optionally rely on MQTT.
    import paho.mqtt.client as mqtt

_LOGGER = logging.getLogger(__name__)

DISCOVERY_COOLDOWN = 2
TIMEOUT_ACK = 10

SubscribePayloadType = str | bytes  # Only bytes if encoding is None


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
    mqtt_data = get_mqtt_data(hass, True)
    if mqtt_data.client is None or not mqtt_config_entry_enabled(hass):
        raise HomeAssistantError(
            f"Cannot publish to topic '{topic}', MQTT is not enabled"
        )
    outgoing_payload = payload
    if not isinstance(payload, bytes):
        if not encoding:
            _LOGGER.error(
                (
                    "Can't pass-through payload for publishing %s on %s with no"
                    " encoding set, need 'bytes' got %s"
                ),
                payload,
                topic,
                type(payload),
            )
            return
        outgoing_payload = str(payload)
        if encoding != DEFAULT_ENCODING:
            # A string is encoded as utf-8 by default, other encoding
            # requires bytes as payload
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

    await mqtt_data.client.async_publish(
        topic, outgoing_payload, qos or 0, retain or False
    )


@bind_hass
async def async_subscribe(
    hass: HomeAssistant,
    topic: str,
    msg_callback: AsyncMessageCallbackType | MessageCallbackType,
    qos: int = DEFAULT_QOS,
    encoding: str | None = DEFAULT_ENCODING,
) -> CALLBACK_TYPE:
    """Subscribe to an MQTT topic.

    Call the return value to unsubscribe.
    """
    mqtt_data = get_mqtt_data(hass, True)
    if mqtt_data.client is None or not mqtt_config_entry_enabled(hass):
        raise HomeAssistantError(
            f"Cannot subscribe to topic '{topic}', MQTT is not enabled"
        )
    # Support for a deprecated callback type was removed with HA core 2023.3.0
    # The signature validation code can be removed from HA core 2023.5.0
    non_default = 0
    if msg_callback:
        non_default = sum(
            p.default == inspect.Parameter.empty
            for _, p in inspect.signature(msg_callback).parameters.items()
        )

    # Check for not supported callback signatures
    # Can be removed from HA core 2023.5.0
    if non_default != 1:
        module = inspect.getmodule(msg_callback)
        raise HomeAssistantError(
            "Signature for MQTT msg_callback '{}.{}' is not supported".format(
                module.__name__ if module else "<unknown>", msg_callback.__name__
            )
        )

    async_remove = await mqtt_data.client.async_subscribe(
        topic,
        catch_log_exception(
            msg_callback,
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

    def remove() -> None:
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

        if (protocol := config.get(CONF_PROTOCOL, DEFAULT_PROTOCOL)) == PROTOCOL_31:
            proto = mqtt.MQTTv31
        elif protocol == PROTOCOL_5:
            proto = mqtt.MQTTv5
        else:
            proto = mqtt.MQTTv311

        if (client_id := config.get(CONF_CLIENT_ID)) is None:
            # PAHO MQTT relies on the MQTT server to generate random client IDs.
            # However, that feature is not mandatory so we generate our own.
            client_id = mqtt.base62(uuid.uuid4().int, padding=22)
        transport = config.get(CONF_TRANSPORT, DEFAULT_TRANSPORT)
        self._client = mqtt.Client(client_id, protocol=proto, transport=transport)

        # Enable logging
        self._client.enable_logger()

        username: str | None = config.get(CONF_USERNAME)
        password: str | None = config.get(CONF_PASSWORD)
        if username is not None:
            self._client.username_pw_set(username, password)

        if (
            certificate := get_file_path(CONF_CERTIFICATE, config.get(CONF_CERTIFICATE))
        ) == "auto":
            certificate = certifi.where()

        client_key = get_file_path(CONF_CLIENT_KEY, config.get(CONF_CLIENT_KEY))
        client_cert = get_file_path(CONF_CLIENT_CERT, config.get(CONF_CLIENT_CERT))
        tls_insecure = config.get(CONF_TLS_INSECURE)
        if transport == TRANSPORT_WEBSOCKETS:
            ws_path: str = config[CONF_WS_PATH]
            ws_headers: dict[str, str] = config[CONF_WS_HEADERS]
            self._client.ws_set_options(ws_path, ws_headers)
        if certificate is not None:
            self._client.tls_set(
                certificate,
                certfile=client_cert,
                keyfile=client_key,
                tls_version=ssl.PROTOCOL_TLS_CLIENT,
            )

            if tls_insecure is not None:
                self._client.tls_insecure_set(tls_insecure)

    @property
    def client(self) -> mqtt.Client:
        """Return the paho MQTT client."""
        return self._client


def _is_simple_match(topic: str) -> bool:
    """Return if a topic is a simple match."""
    return not ("+" in topic or "#" in topic)


class MQTT:
    """Home Assistant MQTT client."""

    _mqttc: mqtt.Client

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        conf: ConfigType,
    ) -> None:
        """Initialize Home Assistant MQTT client."""
        self._mqtt_data = get_mqtt_data(hass)

        self.hass = hass
        self.config_entry = config_entry
        self.conf = conf
        self._simple_subscriptions: dict[str, list[Subscription]] = {}
        self._wildcard_subscriptions: list[Subscription] = []
        self.connected = False
        self._ha_started = asyncio.Event()
        self._last_subscribe = time.time()
        self._cleanup_on_unload: list[Callable[[], None]] = []

        self._paho_lock = asyncio.Lock()  # Prevents parallel calls to the MQTT client
        self._pending_operations: dict[int, asyncio.Event] = {}
        self._pending_operations_condition = asyncio.Condition()

        if self.hass.state == CoreState.running:
            self._ha_started.set()
        else:

            @callback
            def ha_started(_: Event) -> None:
                self._ha_started.set()

            self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, ha_started)

        self.init_client()

        async def async_stop_mqtt(_event: Event) -> None:
            """Stop MQTT component."""
            await self.async_disconnect()

        self._cleanup_on_unload.append(
            hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_stop_mqtt)
        )

    @property
    def subscriptions(self) -> list[Subscription]:
        """Return the tracked subscriptions."""
        return [
            *chain.from_iterable(self._simple_subscriptions.values()),
            *self._wildcard_subscriptions,
        ]

    def cleanup(self) -> None:
        """Clean up listeners."""
        while self._cleanup_on_unload:
            self._cleanup_on_unload.pop()()

    def init_client(self) -> None:
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

    def _is_active_subscription(self, topic: str) -> bool:
        """Check if a topic has an active subscription."""
        return topic in self._simple_subscriptions or any(
            other.topic == topic for other in self._wildcard_subscriptions
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
                "Transmitting%s message on %s: '%s', mid: %s, qos: %s",
                " retained" if retain else "",
                topic,
                payload,
                msg_info.mid,
                qos,
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

    async def async_disconnect(self) -> None:
        """Stop the MQTT client."""

        def stop() -> None:
            """Stop the MQTT client."""
            # Do not disconnect, we want the broker to always publish will
            self._mqttc.loop_stop()

        def no_more_acks() -> bool:
            """Return False if there are unprocessed ACKs."""
            return not any(not op.is_set() for op in self._pending_operations.values())

        # wait for ACKs to be processed
        async with self._pending_operations_condition:
            await self._pending_operations_condition.wait_for(no_more_acks)

        # stop the MQTT loop
        async with self._paho_lock:
            await self.hass.async_add_executor_job(stop)

    @callback
    def async_restore_tracked_subscriptions(
        self, subscriptions: list[Subscription]
    ) -> None:
        """Restore tracked subscriptions after reload."""
        for subscription in subscriptions:
            self._async_track_subscription(subscription)
        self._matching_subscriptions.cache_clear()

    @callback
    def _async_track_subscription(self, subscription: Subscription) -> None:
        """Track a subscription.

        This method does not send a SUBSCRIBE message to the broker.

        The caller is responsible clearing the cache of _matching_subscriptions.
        """
        if _is_simple_match(subscription.topic):
            self._simple_subscriptions.setdefault(subscription.topic, []).append(
                subscription
            )
        else:
            self._wildcard_subscriptions.append(subscription)

    @callback
    def _async_untrack_subscription(self, subscription: Subscription) -> None:
        """Untrack a subscription.

        This method does not send an UNSUBSCRIBE message to the broker.

        The caller is responsible clearing the cache of _matching_subscriptions.
        """
        topic = subscription.topic
        try:
            if _is_simple_match(topic):
                simple_subscriptions = self._simple_subscriptions
                simple_subscriptions[topic].remove(subscription)
                if not simple_subscriptions[topic]:
                    del simple_subscriptions[topic]
            else:
                self._wildcard_subscriptions.remove(subscription)
        except (KeyError, ValueError) as ex:
            raise HomeAssistantError("Can't remove subscription twice") from ex

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
        self._async_track_subscription(subscription)
        self._matching_subscriptions.cache_clear()

        # Only subscribe if currently connected.
        if self.connected:
            self._last_subscribe = time.time()
            await self._async_perform_subscriptions(((topic, qos),))

        @callback
        def async_remove() -> None:
            """Remove subscription."""
            self._async_untrack_subscription(subscription)
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
            result, mid = self._mqttc.unsubscribe(topic)
            _LOGGER.debug("Unsubscribing from %s, mid: %s", topic, mid)
            _raise_on_error(result)
            return mid

        async with self._paho_lock:
            if self._is_active_subscription(topic):
                # Other subscriptions on topic remaining - don't unsubscribe.
                return

            mid = await self.hass.async_add_executor_job(_client_unsubscribe, topic)
            await self._register_mid(mid)

        self.hass.async_create_task(self._wait_for_mid(mid))

    async def _async_perform_subscriptions(
        self, subscriptions: Iterable[tuple[str, int]]
    ) -> None:
        """Perform MQTT client subscriptions."""

        # Section 3.3.1.3 in the specification:
        # http://docs.oasis-open.org/mqtt/mqtt/v3.1.1/os/mqtt-v3.1.1-os.html
        # When sending a PUBLISH Packet to a Client the Server MUST
        # set the RETAIN flag to 1 if a message is sent as a result of a
        # new subscription being made by a Client [MQTT-3.3.1-8].
        # It MUST set the RETAIN flag to 0 when a PUBLISH Packet is sent to
        # a Client because it matches an established subscription regardless
        # of how the flag was set in the message it received [MQTT-3.3.1-9].
        #
        # Since we do not know if a published value is retained we need to
        # (re)subscribe, to ensure retained messages are replayed

        def _process_client_subscriptions() -> list[tuple[int, int]]:
            """Initiate all subscriptions on the MQTT client and return the results."""
            subscribe_result_list = []
            for topic, qos in subscriptions:
                result, mid = self._mqttc.subscribe(topic, qos)
                subscribe_result_list.append((result, mid))
                _LOGGER.debug("Subscribing to %s, mid: %s, qos: %s", topic, mid, qos)
            return subscribe_result_list

        async with self._paho_lock:
            results = await self.hass.async_add_executor_job(
                _process_client_subscriptions
            )

        tasks: list[Coroutine[Any, Any, None]] = []
        errors: list[int] = []
        for result, mid in results:
            if result == 0:
                tasks.append(self._wait_for_mid(mid))
            else:
                errors.append(result)

        if tasks:
            await asyncio.gather(*tasks)
        if errors:
            _raise_on_errors(errors)

    def _mqtt_on_connect(
        self,
        _mqttc: mqtt.Client,
        _userdata: None,
        _flags: dict[str, int],
        result_code: int,
        properties: mqtt.Properties | None = None,
    ) -> None:
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

        self.hass.create_task(self._async_resubscribe())

        if (
            CONF_BIRTH_MESSAGE in self.conf
            and ATTR_TOPIC in self.conf[CONF_BIRTH_MESSAGE]
        ):

            async def publish_birth_message(birth_message: PublishMessage) -> None:
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

    async def _async_resubscribe(self) -> None:
        """Resubscribe on reconnect."""
        # Group subscriptions to only re-subscribe once for each topic.
        keyfunc = attrgetter("topic")
        await self._async_perform_subscriptions(
            [
                # Re-subscribe with the highest requested qos
                (topic, max(subscription.qos for subscription in subs))
                for topic, subs in groupby(
                    sorted(self.subscriptions, key=keyfunc), keyfunc
                )
            ]
        )

    def _mqtt_on_message(
        self, _mqttc: mqtt.Client, _userdata: None, msg: mqtt.MQTTMessage
    ) -> None:
        """Message received callback."""
        self.hass.add_job(self._mqtt_handle_message, msg)

    @lru_cache(None)  # pylint: disable=method-cache-max-size-none
    def _matching_subscriptions(self, topic: str) -> list[Subscription]:
        subscriptions: list[Subscription] = []
        if topic in self._simple_subscriptions:
            subscriptions.extend(self._simple_subscriptions[topic])
        for subscription in self._wildcard_subscriptions:
            if subscription.matcher(topic):
                subscriptions.append(subscription)
        return subscriptions

    @callback
    def _mqtt_handle_message(self, msg: mqtt.MQTTMessage) -> None:
        _LOGGER.debug(
            "Received%s message on %s (qos=%s): %s",
            " retained" if msg.retain else "",
            msg.topic,
            msg.qos,
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
        self._mqtt_data.state_write_requests.process_write_state_requests(msg)

    def _mqtt_on_callback(
        self,
        _mqttc: mqtt.Client,
        _userdata: None,
        mid: int,
        _granted_qos_reason: tuple[int, ...] | mqtt.ReasonCodes | None = None,
        _properties_reason: mqtt.ReasonCodes | None = None,
    ) -> None:
        """Publish / Subscribe / Unsubscribe callback."""
        # The callback signature for on_unsubscribe is different from on_subscribe
        # see https://github.com/eclipse/paho.mqtt.python/issues/687
        # properties and reasoncodes are not used in Home Assistant
        self.hass.create_task(self._mqtt_handle_mid(mid))

    async def _mqtt_handle_mid(self, mid: int) -> None:
        # Create the mid event if not created, either _mqtt_handle_mid or _wait_for_mid
        # may be executed first.
        async with self._pending_operations_condition:
            if mid not in self._pending_operations:
                self._pending_operations[mid] = asyncio.Event()
            self._pending_operations[mid].set()

    async def _register_mid(self, mid: int) -> None:
        """Create Event for an expected ACK."""
        async with self._pending_operations_condition:
            if mid not in self._pending_operations:
                self._pending_operations[mid] = asyncio.Event()

    def _mqtt_on_disconnect(
        self,
        _mqttc: mqtt.Client,
        _userdata: None,
        result_code: int,
        properties: mqtt.Properties | None = None,
    ) -> None:
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
            async with async_timeout.timeout(TIMEOUT_ACK):
                await self._pending_operations[mid].wait()
        except asyncio.TimeoutError:
            _LOGGER.warning(
                "No ACK from MQTT server in %s seconds (mid: %s)", TIMEOUT_ACK, mid
            )
        finally:
            async with self._pending_operations_condition:
                # Cleanup ACK sync buffer
                del self._pending_operations[mid]
                self._pending_operations_condition.notify_all()

    async def _discovery_cooldown(self) -> None:
        now = time.time()
        # Reset discovery and subscribe cooldowns
        self._mqtt_data.last_discovery = now
        self._last_subscribe = now

        last_discovery = self._mqtt_data.last_discovery
        last_subscribe = self._last_subscribe
        wait_until = max(
            last_discovery + DISCOVERY_COOLDOWN, last_subscribe + DISCOVERY_COOLDOWN
        )
        while now < wait_until:
            await asyncio.sleep(wait_until - now)
            now = time.time()
            last_discovery = self._mqtt_data.last_discovery
            last_subscribe = self._last_subscribe
            wait_until = max(
                last_discovery + DISCOVERY_COOLDOWN, last_subscribe + DISCOVERY_COOLDOWN
            )


def _raise_on_errors(result_codes: Iterable[int]) -> None:
    """Raise error if error result."""
    # pylint: disable-next=import-outside-toplevel
    import paho.mqtt.client as mqtt

    if messages := [
        mqtt.error_string(result_code)
        for result_code in result_codes
        if result_code != 0
    ]:
        raise HomeAssistantError(f"Error talking to MQTT: {', '.join(messages)}")


def _raise_on_error(result_code: int) -> None:
    """Raise error if error result."""
    _raise_on_errors((result_code,))


def _matcher_for_topic(subscription: str) -> Any:
    # pylint: disable-next=import-outside-toplevel
    from paho.mqtt.matcher import MQTTMatcher

    matcher = MQTTMatcher()
    matcher[subscription] = True

    return lambda topic: next(matcher.iter_match(topic), False)
