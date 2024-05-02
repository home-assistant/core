"""Support for MQTT message handling."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Callable, Coroutine, Iterable
import contextlib
from dataclasses import dataclass
from functools import lru_cache, partial
from itertools import chain, groupby
import logging
from operator import attrgetter
import socket
import ssl
import time
from typing import TYPE_CHECKING, Any
import uuid

import certifi

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_CLIENT_ID,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_PROTOCOL,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import CALLBACK_TYPE, Event, HassJob, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.start import async_at_started
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import bind_hass
from homeassistant.util.async_ import create_eager_task
from homeassistant.util.logging import catch_log_exception

from .const import (
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
    DEFAULT_BIRTH,
    DEFAULT_ENCODING,
    DEFAULT_KEEPALIVE,
    DEFAULT_PORT,
    DEFAULT_PROTOCOL,
    DEFAULT_QOS,
    DEFAULT_TRANSPORT,
    DEFAULT_WILL,
    DEFAULT_WS_HEADERS,
    DEFAULT_WS_PATH,
    DOMAIN,
    MQTT_CONNECTED,
    MQTT_DISCONNECTED,
    PROTOCOL_5,
    PROTOCOL_31,
    TRANSPORT_WEBSOCKETS,
)
from .models import (
    AsyncMessageCallbackType,
    MessageCallbackType,
    MqttData,
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

DISCOVERY_COOLDOWN = 5
INITIAL_SUBSCRIBE_COOLDOWN = 1.0
SUBSCRIBE_COOLDOWN = 0.1
UNSUBSCRIBE_COOLDOWN = 0.1
TIMEOUT_ACK = 10
RECONNECT_INTERVAL_SECONDS = 10

SocketType = socket.socket | ssl.SSLSocket | Any

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
    hass.create_task(async_publish(hass, topic, payload, qos, retain, encoding))


async def async_publish(
    hass: HomeAssistant,
    topic: str,
    payload: PublishPayloadType,
    qos: int | None = 0,
    retain: bool | None = False,
    encoding: str | None = DEFAULT_ENCODING,
) -> None:
    """Publish message to a MQTT topic."""
    if not mqtt_config_entry_enabled(hass):
        raise HomeAssistantError(
            f"Cannot publish to topic '{topic}', MQTT is not enabled",
            translation_key="mqtt_not_setup_cannot_publish",
            translation_domain=DOMAIN,
            translation_placeholders={"topic": topic},
        )
    mqtt_data = get_mqtt_data(hass)
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
    if not mqtt_config_entry_enabled(hass):
        raise HomeAssistantError(
            f"Cannot subscribe to topic '{topic}', MQTT is not enabled",
            translation_key="mqtt_not_setup_cannot_subscribe",
            translation_domain=DOMAIN,
            translation_placeholders={"topic": topic},
        )
    try:
        mqtt_data = get_mqtt_data(hass)
    except KeyError as exc:
        raise HomeAssistantError(
            f"Cannot subscribe to topic '{topic}', "
            "make sure MQTT is set up correctly",
            translation_key="mqtt_not_setup_cannot_subscribe",
            translation_domain=DOMAIN,
            translation_placeholders={"topic": topic},
        ) from exc
    return await mqtt_data.client.async_subscribe(
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
        # MQTT messages tend to be high volume,
        # and since they come in via a thread and need to be processed in the event loop,
        # we want to avoid hass.add_job since most of the time is spent calling
        # inspect to figure out how to run the callback.
        hass.loop.call_soon_threadsafe(async_remove)

    return remove


@dataclass(frozen=True)
class Subscription:
    """Class to hold data about an active subscription."""

    topic: str
    matcher: Any
    job: HassJob[[ReceiveMessage], Coroutine[Any, Any, None] | None]
    qos: int = 0
    encoding: str | None = "utf-8"


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
        self._client = mqtt.Client(
            client_id, protocol=proto, transport=transport, reconnect_on_failure=False
        )

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
            ws_path: str = config.get(CONF_WS_PATH, DEFAULT_WS_PATH)
            ws_headers: dict[str, str] = config.get(CONF_WS_HEADERS, DEFAULT_WS_HEADERS)
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


class EnsureJobAfterCooldown:
    """Ensure a cool down period before executing a job.

    When a new execute request arrives we cancel the current request
    and start a new one.
    """

    def __init__(
        self, timeout: float, callback_job: Callable[[], Coroutine[Any, None, None]]
    ) -> None:
        """Initialize the timer."""
        self._loop = asyncio.get_running_loop()
        self._timeout = timeout
        self._callback = callback_job
        self._task: asyncio.Future | None = None
        self._timer: asyncio.TimerHandle | None = None

    def set_timeout(self, timeout: float) -> None:
        """Set a new timeout period."""
        self._timeout = timeout

    async def _async_job(self) -> None:
        """Execute after a cooldown period."""
        try:
            await self._callback()
        except HomeAssistantError as ha_error:
            _LOGGER.error("%s", ha_error)

    @callback
    def _async_task_done(self, task: asyncio.Future) -> None:
        """Handle task done."""
        self._task = None

    @callback
    def _async_execute(self) -> None:
        """Execute the job."""
        if self._task:
            # Task already running,
            # so we schedule another run
            self.async_schedule()
            return

        self._async_cancel_timer()
        self._task = create_eager_task(self._async_job())
        self._task.add_done_callback(self._async_task_done)

    async def async_fire(self) -> None:
        """Execute the job immediately."""
        if self._task:
            await self._task
        self._async_execute()

    @callback
    def _async_cancel_timer(self) -> None:
        """Cancel any pending task."""
        if self._timer:
            self._timer.cancel()
            self._timer = None

    @callback
    def async_schedule(self) -> None:
        """Ensure we execute after a cooldown period."""
        # We want to reschedule the timer in the future
        # every time this is called.
        self._async_cancel_timer()
        self._timer = self._loop.call_later(self._timeout, self._async_execute)

    async def async_cleanup(self) -> None:
        """Cleanup any pending task."""
        self._async_cancel_timer()
        if not self._task:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Error cleaning up task")


class MQTT:
    """Home Assistant MQTT client."""

    _mqttc: mqtt.Client
    _last_subscribe: float
    _mqtt_data: MqttData

    def __init__(
        self, hass: HomeAssistant, config_entry: ConfigEntry, conf: ConfigType
    ) -> None:
        """Initialize Home Assistant MQTT client."""
        self.hass = hass
        self.loop = hass.loop
        self.config_entry = config_entry
        self.conf = conf

        self._simple_subscriptions: dict[str, list[Subscription]] = {}
        self._wildcard_subscriptions: list[Subscription] = []
        # _retained_topics prevents a Subscription from receiving a
        # retained message more than once per topic. This prevents flooding
        # already active subscribers when new subscribers subscribe to a topic
        # which has subscribed messages.
        self._retained_topics: dict[Subscription, set[str]] = {}
        self.connected = False
        self._ha_started = asyncio.Event()
        self._cleanup_on_unload: list[Callable[[], None]] = []

        self._connection_lock = asyncio.Lock()
        self._pending_operations: dict[int, asyncio.Future[None]] = {}
        self._subscribe_debouncer = EnsureJobAfterCooldown(
            INITIAL_SUBSCRIBE_COOLDOWN, self._async_perform_subscriptions
        )
        self._misc_task: asyncio.Task | None = None
        self._reconnect_task: asyncio.Task | None = None
        self._should_reconnect: bool = True
        self._available_future: asyncio.Future[bool] | None = None

        self._max_qos: dict[str, int] = {}  # topic, max qos
        self._pending_subscriptions: dict[str, int] = {}  # topic, qos
        self._unsubscribe_debouncer = EnsureJobAfterCooldown(
            UNSUBSCRIBE_COOLDOWN, self._async_perform_unsubscribes
        )
        self._pending_unsubscribes: set[str] = set()  # topic
        self._cleanup_on_unload.extend(
            (
                async_at_started(hass, self._async_ha_started),
                hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, self._async_ha_stop),
            )
        )

    @callback
    def _async_ha_started(self, _hass: HomeAssistant) -> None:
        """Handle HA started."""
        self._ha_started.set()

    async def _async_ha_stop(self, _event: Event) -> None:
        """Handle HA stop."""
        await self.async_disconnect()

    def start(
        self,
        mqtt_data: MqttData,
    ) -> None:
        """Start Home Assistant MQTT client."""
        self._mqtt_data = mqtt_data
        self.init_client()

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

    @contextlib.asynccontextmanager
    async def _async_connect_in_executor(self) -> AsyncGenerator[None, None]:
        # While we are connecting in the executor we need to
        # handle on_socket_open and on_socket_register_write
        # in the executor as well.
        mqttc = self._mqttc
        try:
            mqttc.on_socket_open = self._on_socket_open
            mqttc.on_socket_register_write = self._on_socket_register_write
            yield
        finally:
            # Once the executor job is done, we can switch back to
            # handling these in the event loop.
            mqttc.on_socket_open = self._async_on_socket_open
            mqttc.on_socket_register_write = self._async_on_socket_register_write

    def init_client(self) -> None:
        """Initialize paho client."""
        mqttc = MqttClientSetup(self.conf).client
        # on_socket_unregister_write and _async_on_socket_close
        # are only ever called in the event loop
        mqttc.on_socket_close = self._async_on_socket_close
        mqttc.on_socket_unregister_write = self._async_on_socket_unregister_write

        # These will be called in the event loop
        mqttc.on_connect = self._async_mqtt_on_connect
        mqttc.on_disconnect = self._async_mqtt_on_disconnect
        mqttc.on_message = self._async_mqtt_on_message
        mqttc.on_publish = self._async_mqtt_on_callback
        mqttc.on_subscribe = self._async_mqtt_on_callback
        mqttc.on_unsubscribe = self._async_mqtt_on_callback

        if will := self.conf.get(CONF_WILL_MESSAGE, DEFAULT_WILL):
            will_message = PublishMessage(**will)
            mqttc.will_set(
                topic=will_message.topic,
                payload=will_message.payload,
                qos=will_message.qos,
                retain=will_message.retain,
            )

        self._mqttc = mqttc

    async def _misc_loop(self) -> None:
        """Start the MQTT client misc loop."""
        # pylint: disable=import-outside-toplevel
        import paho.mqtt.client as mqtt

        while self._mqttc.loop_misc() == mqtt.MQTT_ERR_SUCCESS:
            await asyncio.sleep(1)

    @callback
    def _async_reader_callback(self, client: mqtt.Client) -> None:
        """Handle reading data from the socket."""
        if (status := client.loop_read()) != 0:
            self._async_on_disconnect(status)

    @callback
    def _async_start_misc_loop(self) -> None:
        """Start the misc loop."""
        if self._misc_task is None or self._misc_task.done():
            _LOGGER.debug("%s: Starting client misc loop", self.config_entry.title)
            self._misc_task = self.config_entry.async_create_background_task(
                self.hass, self._misc_loop(), name="mqtt misc loop"
            )

    def _on_socket_open(
        self, client: mqtt.Client, userdata: Any, sock: SocketType
    ) -> None:
        """Handle socket open."""
        self.loop.call_soon_threadsafe(
            self._async_on_socket_open, client, userdata, sock
        )

    @callback
    def _async_on_socket_open(
        self, client: mqtt.Client, userdata: Any, sock: SocketType
    ) -> None:
        """Handle socket open."""
        fileno = sock.fileno()
        _LOGGER.debug("%s: connection opened %s", self.config_entry.title, fileno)
        if fileno > -1:
            self.loop.add_reader(sock, partial(self._async_reader_callback, client))
        self._async_start_misc_loop()

    @callback
    def _async_on_socket_close(
        self, client: mqtt.Client, userdata: Any, sock: SocketType
    ) -> None:
        """Handle socket close."""
        fileno = sock.fileno()
        _LOGGER.debug("%s: connection closed %s", self.config_entry.title, fileno)
        # If socket close is called before the connect
        # result is set make sure the first connection result is set
        self._async_connection_result(False)
        if fileno > -1:
            self.loop.remove_reader(sock)
        if self._misc_task is not None and not self._misc_task.done():
            self._misc_task.cancel()

    @callback
    def _async_writer_callback(self, client: mqtt.Client) -> None:
        """Handle writing data to the socket."""
        if (status := client.loop_write()) != 0:
            self._async_on_disconnect(status)

    def _on_socket_register_write(
        self, client: mqtt.Client, userdata: Any, sock: SocketType
    ) -> None:
        """Register the socket for writing."""
        self.loop.call_soon_threadsafe(
            self._async_on_socket_register_write, client, None, sock
        )

    @callback
    def _async_on_socket_register_write(
        self, client: mqtt.Client, userdata: Any, sock: SocketType
    ) -> None:
        """Register the socket for writing."""
        fileno = sock.fileno()
        _LOGGER.debug("%s: register write %s", self.config_entry.title, fileno)
        if fileno > -1:
            self.loop.add_writer(sock, partial(self._async_writer_callback, client))

    @callback
    def _async_on_socket_unregister_write(
        self, client: mqtt.Client, userdata: Any, sock: SocketType
    ) -> None:
        """Unregister the socket for writing."""
        fileno = sock.fileno()
        _LOGGER.debug("%s: unregister write %s", self.config_entry.title, fileno)
        if fileno > -1:
            self.loop.remove_writer(sock)

    def _is_active_subscription(self, topic: str) -> bool:
        """Check if a topic has an active subscription."""
        return topic in self._simple_subscriptions or any(
            other.topic == topic for other in self._wildcard_subscriptions
        )

    async def async_publish(
        self, topic: str, payload: PublishPayloadType, qos: int, retain: bool
    ) -> None:
        """Publish a MQTT message."""
        msg_info = self._mqttc.publish(topic, payload, qos, retain)
        _LOGGER.debug(
            "Transmitting%s message on %s: '%s', mid: %s, qos: %s",
            " retained" if retain else "",
            topic,
            payload,
            msg_info.mid,
            qos,
        )
        _raise_on_error(msg_info.rc)
        await self._async_wait_for_mid(msg_info.mid)

    async def async_connect(self, client_available: asyncio.Future[bool]) -> None:
        """Connect to the host. Does not process messages yet."""
        # pylint: disable-next=import-outside-toplevel
        import paho.mqtt.client as mqtt

        result: int | None = None
        self._available_future = client_available
        self._should_reconnect = True
        try:
            async with self._connection_lock, self._async_connect_in_executor():
                result = await self.hass.async_add_executor_job(
                    self._mqttc.connect,
                    self.conf[CONF_BROKER],
                    self.conf.get(CONF_PORT, DEFAULT_PORT),
                    self.conf.get(CONF_KEEPALIVE, DEFAULT_KEEPALIVE),
                )
        except OSError as err:
            _LOGGER.error("Failed to connect to MQTT server due to exception: %s", err)
            self._async_connection_result(False)
        finally:
            if result is not None and result != 0:
                if result is not None:
                    _LOGGER.error(
                        "Failed to connect to MQTT server: %s",
                        mqtt.error_string(result),
                    )
                self._async_connection_result(False)

    @callback
    def _async_connection_result(self, connected: bool) -> None:
        """Handle a connection result."""
        if self._available_future and not self._available_future.done():
            self._available_future.set_result(connected)

        if connected:
            self._async_cancel_reconnect()
        elif self._should_reconnect and not self._reconnect_task:
            self._reconnect_task = self.config_entry.async_create_background_task(
                self.hass, self._reconnect_loop(), "mqtt reconnect loop"
            )

    @callback
    def _async_cancel_reconnect(self) -> None:
        """Cancel the reconnect task."""
        if self._reconnect_task:
            self._reconnect_task.cancel()
            self._reconnect_task = None

    async def _reconnect_loop(self) -> None:
        """Reconnect to the MQTT server."""
        while True:
            if not self.connected:
                try:
                    async with self._connection_lock, self._async_connect_in_executor():
                        await self.hass.async_add_executor_job(self._mqttc.reconnect)
                except OSError as err:
                    _LOGGER.debug(
                        "Error re-connecting to MQTT server due to exception: %s", err
                    )

            await asyncio.sleep(RECONNECT_INTERVAL_SECONDS)

    async def async_disconnect(self) -> None:
        """Stop the MQTT client."""

        # stop waiting for any pending subscriptions
        await self._subscribe_debouncer.async_cleanup()
        # reset timeout to initial subscribe cooldown
        self._subscribe_debouncer.set_timeout(INITIAL_SUBSCRIBE_COOLDOWN)
        # stop the unsubscribe debouncer
        await self._unsubscribe_debouncer.async_cleanup()
        # make sure the unsubscribes are processed
        await self._async_perform_unsubscribes()

        # wait for ACKs to be processed
        if pending := self._pending_operations.values():
            await asyncio.wait(pending)

        # stop the MQTT loop
        async with self._connection_lock:
            self._should_reconnect = False
            self._async_cancel_reconnect()
            # We do not gracefully disconnect to ensure
            # the broker publishes the will message

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
        except (KeyError, ValueError) as exc:
            raise HomeAssistantError("Can't remove subscription twice") from exc

    @callback
    def _async_queue_subscriptions(
        self, subscriptions: Iterable[tuple[str, int]], queue_only: bool = False
    ) -> None:
        """Queue requested subscriptions."""
        for subscription in subscriptions:
            topic, qos = subscription
            max_qos = max(qos, self._max_qos.setdefault(topic, qos))
            self._max_qos[topic] = max_qos
            self._pending_subscriptions[topic] = max_qos
            # Cancel any pending unsubscribe since we are subscribing now
            if topic in self._pending_unsubscribes:
                self._pending_unsubscribes.remove(topic)
        if queue_only:
            return
        self._subscribe_debouncer.async_schedule()

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
            self._async_queue_subscriptions(((topic, qos),))

        @callback
        def async_remove() -> None:
            """Remove subscription."""
            self._async_untrack_subscription(subscription)
            self._matching_subscriptions.cache_clear()
            if subscription in self._retained_topics:
                del self._retained_topics[subscription]
            # Only unsubscribe if currently connected
            if self.connected:
                self._async_unsubscribe(topic)

        return async_remove

    @callback
    def _async_unsubscribe(self, topic: str) -> None:
        """Unsubscribe from a topic."""
        if self._is_active_subscription(topic):
            if self._max_qos[topic] == 0:
                return
            subs = self._matching_subscriptions(topic)
            self._max_qos[topic] = max(sub.qos for sub in subs)
            # Other subscriptions on topic remaining - don't unsubscribe.
            return
        if topic in self._max_qos:
            del self._max_qos[topic]
        if topic in self._pending_subscriptions:
            # Avoid any pending subscription to be executed
            del self._pending_subscriptions[topic]

        self._pending_unsubscribes.add(topic)
        self._unsubscribe_debouncer.async_schedule()

    async def _async_perform_subscriptions(self) -> None:
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

        if not self._pending_subscriptions:
            return

        subscriptions: dict[str, int] = self._pending_subscriptions
        self._pending_subscriptions = {}

        subscription_list = list(subscriptions.items())
        result, mid = self._mqttc.subscribe(subscription_list)

        for topic, qos in subscriptions.items():
            _LOGGER.debug("Subscribing to %s, mid: %s, qos: %s", topic, mid, qos)
        self._last_subscribe = time.monotonic()

        if result == 0:
            await self._async_wait_for_mid(mid)
        else:
            _raise_on_error(result)

    async def _async_perform_unsubscribes(self) -> None:
        """Perform pending MQTT client unsubscribes."""
        if not self._pending_unsubscribes:
            return

        topics = list(self._pending_unsubscribes)
        self._pending_unsubscribes = set()

        result, mid = self._mqttc.unsubscribe(topics)
        _raise_on_error(result)
        for topic in topics:
            _LOGGER.debug("Unsubscribing from %s, mid: %s", topic, mid)

        await self._async_wait_for_mid(mid)

    async def _async_resubscribe_and_publish_birth_message(
        self, birth_message: PublishMessage
    ) -> None:
        """Resubscribe to all topics and publish birth message."""
        await self._async_perform_subscriptions()
        await self._ha_started.wait()  # Wait for Home Assistant to start
        await self._discovery_cooldown()  # Wait for MQTT discovery to cool down
        # Update subscribe cooldown period to a shorter time
        # and make sure we flush the debouncer
        await self._subscribe_debouncer.async_fire()
        self._subscribe_debouncer.set_timeout(SUBSCRIBE_COOLDOWN)
        await self.async_publish(
            topic=birth_message.topic,
            payload=birth_message.payload,
            qos=birth_message.qos,
            retain=birth_message.retain,
        )

    @callback
    def _async_mqtt_on_connect(
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
            if result_code in (
                mqtt.CONNACK_REFUSED_BAD_USERNAME_PASSWORD,
                mqtt.CONNACK_REFUSED_NOT_AUTHORIZED,
            ):
                self._should_reconnect = False
                self.hass.async_create_task(self.async_disconnect())
                self.config_entry.async_start_reauth(self.hass)
            _LOGGER.error(
                "Unable to connect to the MQTT broker: %s",
                mqtt.connack_string(result_code),
            )
            self._async_connection_result(False)
            return

        self.connected = True
        async_dispatcher_send(self.hass, MQTT_CONNECTED)
        _LOGGER.info(
            "Connected to MQTT server %s:%s (%s)",
            self.conf[CONF_BROKER],
            self.conf.get(CONF_PORT, DEFAULT_PORT),
            result_code,
        )

        self._async_queue_resubscribe()
        birth: dict[str, Any]
        if birth := self.conf.get(CONF_BIRTH_MESSAGE, DEFAULT_BIRTH):
            birth_message = PublishMessage(**birth)
            self.config_entry.async_create_background_task(
                self.hass,
                self._async_resubscribe_and_publish_birth_message(birth_message),
                name="mqtt re-subscribe and birth",
            )
        else:
            # Update subscribe cooldown period to a shorter time
            self.config_entry.async_create_background_task(
                self.hass,
                self._async_perform_subscriptions(),
                name="mqtt re-subscribe",
            )
            self._subscribe_debouncer.set_timeout(SUBSCRIBE_COOLDOWN)

        self._async_connection_result(True)

    @callback
    def _async_queue_resubscribe(self) -> None:
        """Queue subscriptions on reconnect.

        self._async_perform_subscriptions must be called
        after this method to actually subscribe.
        """
        self._max_qos.clear()
        self._retained_topics.clear()
        # Group subscriptions to only re-subscribe once for each topic.
        keyfunc = attrgetter("topic")
        self._async_queue_subscriptions(
            [
                # Re-subscribe with the highest requested qos
                (topic, max(subscription.qos for subscription in subs))
                for topic, subs in groupby(
                    sorted(self.subscriptions, key=keyfunc), keyfunc
                )
            ],
            queue_only=True,
        )

    @lru_cache(None)  # pylint: disable=method-cache-max-size-none
    def _matching_subscriptions(self, topic: str) -> list[Subscription]:
        subscriptions: list[Subscription] = []
        if topic in self._simple_subscriptions:
            subscriptions.extend(self._simple_subscriptions[topic])
        subscriptions.extend(
            subscription
            for subscription in self._wildcard_subscriptions
            if subscription.matcher(topic)
        )
        return subscriptions

    @callback
    def _async_mqtt_on_message(
        self, _mqttc: mqtt.Client, _userdata: None, msg: mqtt.MQTTMessage
    ) -> None:
        topic = msg.topic
        # msg.topic is a property that decodes the topic to a string
        # every time it is accessed. Save the result to avoid
        # decoding the same topic multiple times.
        _LOGGER.debug(
            "Received%s message on %s (qos=%s): %s",
            " retained" if msg.retain else "",
            topic,
            msg.qos,
            msg.payload[0:8192],
        )
        subscriptions = self._matching_subscriptions(topic)
        msg_cache_by_subscription_topic: dict[str, ReceiveMessage] = {}

        for subscription in subscriptions:
            if msg.retain:
                retained_topics = self._retained_topics.setdefault(subscription, set())
                # Skip if the subscription already received a retained message
                if topic in retained_topics:
                    continue
                # Remember the subscription had an initial retained message
                self._retained_topics[subscription].add(topic)

            payload: SubscribePayloadType = msg.payload
            if subscription.encoding is not None:
                try:
                    payload = msg.payload.decode(subscription.encoding)
                except (AttributeError, UnicodeDecodeError):
                    _LOGGER.warning(
                        "Can't decode payload %s on %s with encoding %s (for %s)",
                        msg.payload[0:8192],
                        topic,
                        subscription.encoding,
                        subscription.job,
                    )
                    continue
            subscription_topic = subscription.topic
            if subscription_topic not in msg_cache_by_subscription_topic:
                # Only make one copy of the message
                # per topic so we avoid storing a separate
                # dataclass in memory for each subscriber
                # to the same topic for retained messages
                receive_msg = ReceiveMessage(
                    topic,
                    payload,
                    msg.qos,
                    msg.retain,
                    subscription_topic,
                    msg.timestamp,
                )
                msg_cache_by_subscription_topic[subscription_topic] = receive_msg
            else:
                receive_msg = msg_cache_by_subscription_topic[subscription_topic]
            self.hass.async_run_hass_job(subscription.job, receive_msg)
        self._mqtt_data.state_write_requests.process_write_state_requests(msg)

    @callback
    def _async_mqtt_on_callback(
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
        # properties and reason codes are not used in Home Assistant
        future = self._async_get_mid_future(mid)
        if future.done() and future.exception():
            # Timed out
            return
        future.set_result(None)

    @callback
    def _async_get_mid_future(self, mid: int) -> asyncio.Future[None]:
        """Get the future for a mid."""
        if future := self._pending_operations.get(mid):
            return future
        future = self.hass.loop.create_future()
        self._pending_operations[mid] = future
        return future

    @callback
    def _async_mqtt_on_disconnect(
        self,
        _mqttc: mqtt.Client,
        _userdata: None,
        result_code: int,
        properties: mqtt.Properties | None = None,
    ) -> None:
        """Disconnected callback."""
        self._async_on_disconnect(result_code)

    @callback
    def _async_on_disconnect(self, result_code: int) -> None:
        if not self.connected:
            # This function is re-entrant and may be called multiple times
            # when there is a broken pipe error.
            return
        # If disconnect is called before the connect
        # result is set make sure the first connection result is set
        self._async_connection_result(False)
        self.connected = False
        async_dispatcher_send(self.hass, MQTT_DISCONNECTED)
        _LOGGER.warning(
            "Disconnected from MQTT server %s:%s (%s)",
            self.conf[CONF_BROKER],
            self.conf.get(CONF_PORT, DEFAULT_PORT),
            result_code,
        )

    @callback
    def _async_timeout_mid(self, future: asyncio.Future[None]) -> None:
        """Timeout waiting for a mid."""
        if not future.done():
            future.set_exception(asyncio.TimeoutError)

    async def _async_wait_for_mid(self, mid: int) -> None:
        """Wait for ACK from broker."""
        # Create the mid event if not created, either _mqtt_handle_mid or _async_wait_for_mid
        # may be executed first.
        future = self._async_get_mid_future(mid)
        loop = self.hass.loop
        timer_handle = loop.call_later(TIMEOUT_ACK, self._async_timeout_mid, future)
        try:
            await future
        except TimeoutError:
            _LOGGER.warning(
                "No ACK from MQTT server in %s seconds (mid: %s)", TIMEOUT_ACK, mid
            )
        finally:
            timer_handle.cancel()
            del self._pending_operations[mid]

    async def _discovery_cooldown(self) -> None:
        """Wait until all discovery and subscriptions are processed."""
        now = time.monotonic()
        # Reset discovery and subscribe cooldowns
        self._mqtt_data.last_discovery = now
        self._last_subscribe = now

        last_discovery = self._mqtt_data.last_discovery
        last_subscribe = now if self._pending_subscriptions else self._last_subscribe
        wait_until = max(
            last_discovery + DISCOVERY_COOLDOWN, last_subscribe + DISCOVERY_COOLDOWN
        )
        while now < wait_until:
            await asyncio.sleep(wait_until - now)
            now = time.monotonic()
            last_discovery = self._mqtt_data.last_discovery
            last_subscribe = (
                now if self._pending_subscriptions else self._last_subscribe
            )
            wait_until = max(
                last_discovery + DISCOVERY_COOLDOWN, last_subscribe + DISCOVERY_COOLDOWN
            )


def _raise_on_error(result_code: int) -> None:
    """Raise error if error result."""
    # pylint: disable-next=import-outside-toplevel
    import paho.mqtt.client as mqtt

    if result_code and (message := mqtt.error_string(result_code)):
        raise HomeAssistantError(f"Error talking to MQTT: {message}")


def _matcher_for_topic(subscription: str) -> Any:
    # pylint: disable-next=import-outside-toplevel
    from paho.mqtt.matcher import MQTTMatcher

    matcher = MQTTMatcher()
    matcher[subscription] = True

    return lambda topic: next(matcher.iter_match(topic), False)
