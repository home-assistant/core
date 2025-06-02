"""Support for MQTT message handling."""

from __future__ import annotations

import asyncio
from collections import defaultdict
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
from uuid import uuid4

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
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    HassJob,
    HassJobType,
    HomeAssistant,
    callback,
    get_hassjob_callable_job_type,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.importlib import async_import_module
from homeassistant.helpers.start import async_at_started
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import bind_hass
from homeassistant.setup import SetupPhases, async_pause_setup
from homeassistant.util.collection import chunked_or_all
from homeassistant.util.logging import catch_log_exception, log_exception

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
    MQTT_CONNECTION_STATE,
    PROTOCOL_5,
    PROTOCOL_31,
    TRANSPORT_WEBSOCKETS,
)
from .models import (
    DATA_MQTT,
    MessageCallbackType,
    MqttData,
    PublishMessage,
    PublishPayloadType,
    ReceiveMessage,
)
from .util import EnsureJobAfterCooldown, get_file_path, mqtt_config_entry_enabled

if TYPE_CHECKING:
    # Only import for paho-mqtt type checking here, imports are done locally
    # because integrations should be able to optionally rely on MQTT.
    import paho.mqtt.client as mqtt

    from .async_client import AsyncMQTTClient

_LOGGER = logging.getLogger(__name__)

MIN_BUFFER_SIZE = 131072  # Minimum buffer size to use if preferred size fails
PREFERRED_BUFFER_SIZE = 8 * 1024 * 1024  # Set receive buffer size to 8MiB

DISCOVERY_COOLDOWN = 5
# The initial subscribe cooldown controls how long to wait to group
# subscriptions together. This is to avoid making too many subscribe
# requests in a short period of time. If the number is too low, the
# system will be flooded with subscribe requests. If the number is too
# high, we risk being flooded with responses to the subscribe requests
# which can exceed the receive buffer size of the socket. To mitigate
# this, we increase the receive buffer size of the socket as well.
INITIAL_SUBSCRIBE_COOLDOWN = 0.5
SUBSCRIBE_COOLDOWN = 0.1
UNSUBSCRIBE_COOLDOWN = 0.1
TIMEOUT_ACK = 10
RECONNECT_INTERVAL_SECONDS = 10

MAX_WILDCARD_SUBSCRIBES_PER_CALL = 1
MAX_SUBSCRIBES_PER_CALL = 500
MAX_UNSUBSCRIBES_PER_CALL = 500

MAX_PACKETS_TO_READ = 500

type SocketType = socket.socket | ssl.SSLSocket | mqtt._WebsocketWrapper | Any  # noqa: SLF001

type SubscribePayloadType = str | bytes | bytearray  # Only bytes if encoding is None


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
    mqtt_data = hass.data[DATA_MQTT]
    outgoing_payload = payload
    if not isinstance(payload, bytes) and payload is not None:
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
    msg_callback: Callable[[ReceiveMessage], Coroutine[Any, Any, None] | None],
    qos: int = DEFAULT_QOS,
    encoding: str | None = DEFAULT_ENCODING,
) -> CALLBACK_TYPE:
    """Subscribe to an MQTT topic.

    Call the return value to unsubscribe.
    """
    return async_subscribe_internal(hass, topic, msg_callback, qos, encoding)


@callback
def async_subscribe_internal(
    hass: HomeAssistant,
    topic: str,
    msg_callback: Callable[[ReceiveMessage], Coroutine[Any, Any, None] | None],
    qos: int = DEFAULT_QOS,
    encoding: str | None = DEFAULT_ENCODING,
    job_type: HassJobType | None = None,
) -> CALLBACK_TYPE:
    """Subscribe to an MQTT topic.

    This function is internal to the MQTT integration
    and may change at any time. It should not be considered
    a stable API.

    Call the return value to unsubscribe.
    """
    try:
        mqtt_data = hass.data[DATA_MQTT]
    except KeyError as exc:
        raise HomeAssistantError(
            f"Cannot subscribe to topic '{topic}', make sure MQTT is set up correctly",
            translation_key="mqtt_not_setup_cannot_subscribe",
            translation_domain=DOMAIN,
            translation_placeholders={"topic": topic},
        ) from exc
    client = mqtt_data.client
    if not mqtt_config_entry_enabled(hass):
        raise HomeAssistantError(
            f"Cannot subscribe to topic '{topic}', MQTT is not enabled",
            translation_key="mqtt_not_setup_cannot_subscribe",
            translation_domain=DOMAIN,
            translation_placeholders={"topic": topic},
        )
    return client.async_subscribe(topic, msg_callback, qos, encoding, job_type)


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


@dataclass(slots=True, frozen=True)
class Subscription:
    """Class to hold data about an active subscription."""

    topic: str
    is_simple_match: bool
    complex_matcher: Callable[[str], bool] | None
    job: HassJob[[ReceiveMessage], Coroutine[Any, Any, None] | None]
    qos: int = 0
    encoding: str | None = "utf-8"


class MqttClientSetup:
    """Helper class to setup the paho mqtt client from config."""

    _client: AsyncMQTTClient

    def __init__(self, config: ConfigType) -> None:
        """Initialize the MQTT client setup helper.

        self.setup must be run in an executor job.
        """

        self._config = config

    def setup(self) -> None:
        """Set up the MQTT client.

        The setup of the MQTT client should be run in an executor job,
        because it accesses files, so it does IO.
        """
        # We don't import on the top because some integrations
        # should be able to optionally rely on MQTT.
        from paho.mqtt import client as mqtt  # pylint: disable=import-outside-toplevel

        # pylint: disable-next=import-outside-toplevel
        from .async_client import AsyncMQTTClient

        config = self._config
        clean_session: bool | None = None
        if (protocol := config.get(CONF_PROTOCOL, DEFAULT_PROTOCOL)) == PROTOCOL_31:
            proto = mqtt.MQTTv31
            clean_session = True
        elif protocol == PROTOCOL_5:
            proto = mqtt.MQTTv5
        else:
            proto = mqtt.MQTTv311
            clean_session = True

        if (client_id := config.get(CONF_CLIENT_ID)) is None:
            # PAHO MQTT relies on the MQTT server to generate random client ID
            # for protocol version 3.1, however, that feature is not mandatory
            # so we generate our own.
            client_id = mqtt._base62(uuid4().int, padding=22)  # noqa: SLF001
        transport: str = config.get(CONF_TRANSPORT, DEFAULT_TRANSPORT)
        self._client = AsyncMQTTClient(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=client_id,
            # See: https://eclipse.dev/paho/files/paho.mqtt.python/html/client.html
            # clean_session (bool defaults to None)
            # a boolean that determines the client type.
            # If True, the broker will remove all information about this client when it
            # disconnects. If False, the client is a persistent client and subscription
            # information and queued messages will be retained when the client
            # disconnects. Note that a client will never discard its own outgoing
            # messages on disconnect. Calling connect() or reconnect() will cause the
            # messages to be resent. Use reinitialise() to reset a client to its
            # original state. The clean_session argument only applies to MQTT versions
            # v3.1.1 and v3.1. It is not accepted if the MQTT version is v5.0 - use the
            # clean_start argument on connect() instead.
            clean_session=clean_session,
            protocol=proto,
            transport=transport,  # type: ignore[arg-type]
            reconnect_on_failure=False,
        )
        self._client.setup()

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
    def client(self) -> AsyncMQTTClient:
        """Return the paho MQTT client."""
        return self._client


class MQTT:
    """Home Assistant MQTT client."""

    _mqttc: AsyncMQTTClient
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
        self.is_mqttv5 = conf.get(CONF_PROTOCOL, DEFAULT_PROTOCOL) == PROTOCOL_5

        self._simple_subscriptions: defaultdict[str, set[Subscription]] = defaultdict(
            set
        )
        # To ensure the wildcard subscriptions order is preserved, we use a dict
        # with `None` values instead of a set.
        self._wildcard_subscriptions: dict[Subscription, None] = {}
        # _retained_topics prevents a Subscription from receiving a
        # retained message more than once per topic. This prevents flooding
        # already active subscribers when new subscribers subscribe to a topic
        # which has subscribed messages.
        self._retained_topics: defaultdict[Subscription, set[str]] = defaultdict(set)
        self.connected = False
        self._ha_started = asyncio.Event()
        self._cleanup_on_unload: list[Callable[[], None]] = []

        self._connection_lock = asyncio.Lock()
        self._pending_operations: dict[int, asyncio.Future[None]] = {}
        self._subscribe_debouncer = EnsureJobAfterCooldown(
            INITIAL_SUBSCRIBE_COOLDOWN, self._async_perform_subscriptions
        )
        self._misc_timer: asyncio.TimerHandle | None = None
        self._reconnect_task: asyncio.Task | None = None
        self._should_reconnect: bool = True
        self._available_future: asyncio.Future[bool] | None = None

        self._max_qos: defaultdict[str, int] = defaultdict(int)  # topic, max qos
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
        self._socket_buffersize: int | None = None

    @callback
    def _async_ha_started(self, _hass: HomeAssistant) -> None:
        """Handle HA started."""
        self._ha_started.set()

    async def _async_ha_stop(self, _event: Event) -> None:
        """Handle HA stop."""
        await self.async_disconnect()

    async def async_start(
        self,
        mqtt_data: MqttData,
    ) -> None:
        """Start Home Assistant MQTT client."""
        self._mqtt_data = mqtt_data
        await self.async_init_client()

    @property
    def subscriptions(self) -> set[Subscription]:
        """Return the tracked subscriptions."""
        return {
            *chain.from_iterable(self._simple_subscriptions.values()),
            *self._wildcard_subscriptions,
        }

    def cleanup(self) -> None:
        """Clean up listeners."""
        while self._cleanup_on_unload:
            self._cleanup_on_unload.pop()()

    @contextlib.asynccontextmanager
    async def _async_connect_in_executor(self) -> AsyncGenerator[None]:
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

    async def async_init_client(self) -> None:
        """Initialize paho client."""
        with async_pause_setup(self.hass, SetupPhases.WAIT_IMPORT_PACKAGES):
            await async_import_module(
                self.hass, "homeassistant.components.mqtt.async_client"
            )

        mqttc_setup = MqttClientSetup(self.conf)
        await self.hass.async_add_executor_job(mqttc_setup.setup)
        mqttc = mqttc_setup.client
        # on_socket_unregister_write and _async_on_socket_close
        # are only ever called in the event loop
        mqttc.on_socket_close = self._async_on_socket_close
        mqttc.on_socket_unregister_write = self._async_on_socket_unregister_write

        # These will be called in the event loop
        mqttc.on_connect = self._async_mqtt_on_connect
        mqttc.on_disconnect = self._async_mqtt_on_disconnect
        mqttc.on_message = self._async_mqtt_on_message
        mqttc.on_publish = self._async_mqtt_on_publish
        mqttc.on_subscribe = self._async_mqtt_on_subscribe_unsubscribe
        mqttc.on_unsubscribe = self._async_mqtt_on_subscribe_unsubscribe

        # suppress exceptions at callback
        mqttc.suppress_exceptions = True

        if will := self.conf.get(CONF_WILL_MESSAGE, DEFAULT_WILL):
            will_message = PublishMessage(**will)
            mqttc.will_set(
                topic=will_message.topic,
                payload=will_message.payload,
                qos=will_message.qos,
                retain=will_message.retain,
            )

        self._mqttc = mqttc

    @callback
    def _async_reader_callback(self, client: mqtt.Client) -> None:
        """Handle reading data from the socket."""
        if (status := client.loop_read(MAX_PACKETS_TO_READ)) != 0:
            self._async_handle_callback_exception(status)

    @callback
    def _async_start_misc_periodic(self) -> None:
        """Start the misc periodic."""
        assert self._misc_timer is None, "Misc periodic already started"
        _LOGGER.debug("%s: Starting client misc loop", self.config_entry.title)
        # pylint: disable=import-outside-toplevel
        import paho.mqtt.client as mqtt

        # Inner function to avoid having to check late import
        # each time the function is called.
        @callback
        def _async_misc() -> None:
            """Start the MQTT client misc loop."""
            if self._mqttc.loop_misc() == mqtt.MQTT_ERR_SUCCESS:
                self._misc_timer = self.loop.call_at(self.loop.time() + 1, _async_misc)

        self._misc_timer = self.loop.call_at(self.loop.time() + 1, _async_misc)

    def _increase_socket_buffer_size(self, sock: SocketType) -> None:
        """Increase the socket buffer size."""
        if not hasattr(sock, "setsockopt") and hasattr(sock, "_socket"):
            # The WebsocketWrapper does not wrap setsockopt
            # so we need to get the underlying socket
            # Remove this once
            # https://github.com/eclipse/paho.mqtt.python/pull/843
            # is available.
            sock = sock._socket  # noqa: SLF001

        new_buffer_size = PREFERRED_BUFFER_SIZE
        while True:
            try:
                # Some operating systems do not allow us to set the preferred
                # buffer size. In that case we try some other size options.
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, new_buffer_size)  # type: ignore[union-attr]
            except OSError as err:
                if new_buffer_size <= MIN_BUFFER_SIZE:
                    _LOGGER.warning(
                        "Unable to increase the socket buffer size to %s; "
                        "The connection may be unstable if the MQTT broker "
                        "sends data at volume or a large amount of subscriptions "
                        "need to be processed: %s",
                        new_buffer_size,
                        err,
                    )
                    return
                new_buffer_size //= 2
            else:
                return

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
            self._increase_socket_buffer_size(sock)
            self.loop.add_reader(sock, partial(self._async_reader_callback, client))
        if not self._misc_timer:
            self._async_start_misc_periodic()
        # Try to consume the buffer right away so it doesn't fill up
        # since add_reader will wait for the next loop iteration
        self._async_reader_callback(client)

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
        if self._misc_timer:
            self._misc_timer.cancel()
            self._misc_timer = None

    @callback
    def _async_writer_callback(self, client: mqtt.Client) -> None:
        """Handle writing data to the socket."""
        if (status := client.loop_write()) != 0:
            self._async_handle_callback_exception(status)

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
        await self._async_wait_for_mid_or_raise(msg_info.mid, msg_info.rc)

    async def async_connect(self, client_available: asyncio.Future[bool]) -> None:
        """Connect to the host. Does not process messages yet."""
        # pylint: disable-next=import-outside-toplevel
        import paho.mqtt.client as mqtt

        result: int | None = None
        self._available_future = client_available
        self._should_reconnect = True
        connect_partial = partial(
            self._mqttc.connect,
            host=self.conf[CONF_BROKER],
            port=self.conf.get(CONF_PORT, DEFAULT_PORT),
            keepalive=self.conf.get(CONF_KEEPALIVE, DEFAULT_KEEPALIVE),
            # See:
            # https://eclipse.dev/paho/files/paho.mqtt.python/html/client.html
            # `clean_start` (bool) – (MQTT v5.0 only) `True`, `False` or
            # `MQTT_CLEAN_START_FIRST_ONLY`. Sets the MQTT v5.0 clean_start flag
            #  always, never or on the first successful connect only,
            # respectively. MQTT session data (such as outstanding messages and
            # subscriptions) is cleared on successful connect when the
            # clean_start flag is set. For MQTT v3.1.1, the clean_session
            # argument of Client should be used for similar result.
            clean_start=True if self.is_mqttv5 else mqtt.MQTT_CLEAN_START_FIRST_ONLY,
        )
        try:
            async with self._connection_lock, self._async_connect_in_executor():
                result = await self.hass.async_add_executor_job(connect_partial)
        except (OSError, mqtt.WebsocketConnectionError) as err:
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
        # pylint: disable-next=import-outside-toplevel
        import paho.mqtt.client as mqtt

        while True:
            if not self.connected:
                try:
                    async with self._connection_lock, self._async_connect_in_executor():
                        await self.hass.async_add_executor_job(self._mqttc.reconnect)
                except (OSError, mqtt.WebsocketConnectionError) as err:
                    _LOGGER.debug(
                        "Error re-connecting to MQTT server due to exception: %s", err
                    )

            await asyncio.sleep(RECONNECT_INTERVAL_SECONDS)

    async def async_disconnect(self, disconnect_paho_client: bool = False) -> None:
        """Stop the MQTT client.

        We only disconnect grafully if disconnect_paho_client is set, but not
        when Home Assistant is shut down.
        """

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
            # the broker publishes the will message unless the entry is reloaded
            if disconnect_paho_client:
                self._mqttc.disconnect()

    @callback
    def async_restore_tracked_subscriptions(
        self, subscriptions: set[Subscription]
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
        if subscription.is_simple_match:
            self._simple_subscriptions[subscription.topic].add(subscription)
        else:
            self._wildcard_subscriptions[subscription] = None

    @callback
    def _async_untrack_subscription(self, subscription: Subscription) -> None:
        """Untrack a subscription.

        This method does not send an UNSUBSCRIBE message to the broker.

        The caller is responsible clearing the cache of _matching_subscriptions.
        """
        topic = subscription.topic
        try:
            if subscription.is_simple_match:
                simple_subscriptions = self._simple_subscriptions
                simple_subscriptions[topic].remove(subscription)
                if not simple_subscriptions[topic]:
                    del simple_subscriptions[topic]
            else:
                del self._wildcard_subscriptions[subscription]
        except (KeyError, ValueError) as exc:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="mqtt_not_setup_cannot_unsubscribe_twice",
                translation_placeholders={"topic": topic},
            ) from exc

    @callback
    def _async_queue_subscriptions(
        self, subscriptions: Iterable[tuple[str, int]], queue_only: bool = False
    ) -> None:
        """Queue requested subscriptions."""
        for subscription in subscriptions:
            topic, qos = subscription
            if (max_qos := self._max_qos[topic]) < qos:
                self._max_qos[topic] = (max_qos := qos)
            self._pending_subscriptions[topic] = max_qos
            # Cancel any pending unsubscribe since we are subscribing now
            if topic in self._pending_unsubscribes:
                self._pending_unsubscribes.remove(topic)
        if queue_only:
            return
        self._subscribe_debouncer.async_schedule()

    def _exception_message(
        self,
        msg_callback: Callable[[ReceiveMessage], Coroutine[Any, Any, None] | None],
        msg: ReceiveMessage,
    ) -> str:
        """Return a string with the exception message."""
        # if msg_callback is a partial we return the name of the first argument
        if isinstance(msg_callback, partial):
            call_back_name = msg_callback.args[0].__name__
        else:
            call_back_name = msg_callback.__name__
        return (
            f"Exception in {call_back_name} when handling msg on "
            f"'{msg.topic}': '{msg.payload}'"  # type: ignore[str-bytes-safe]
        )

    @callback
    def async_subscribe(
        self,
        topic: str,
        msg_callback: Callable[[ReceiveMessage], Coroutine[Any, Any, None] | None],
        qos: int,
        encoding: str | None = None,
        job_type: HassJobType | None = None,
    ) -> Callable[[], None]:
        """Set up a subscription to a topic with the provided qos."""
        if not isinstance(topic, str):
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="mqtt_topic_not_a_string",
                translation_placeholders={"topic": topic},
            )

        if job_type is None:
            job_type = get_hassjob_callable_job_type(msg_callback)
        if job_type is not HassJobType.Callback:
            # Only wrap the callback with catch_log_exception
            # if it is not a simple callback since we catch
            # exceptions for simple callbacks inline for
            # performance reasons.
            msg_callback = catch_log_exception(
                msg_callback, partial(self._exception_message, msg_callback)
            )

        job = HassJob(msg_callback, job_type=job_type)
        is_simple_match = not ("+" in topic or "#" in topic)
        matcher = None if is_simple_match else _matcher_for_topic(topic)

        subscription = Subscription(topic, is_simple_match, matcher, job, qos, encoding)
        self._async_track_subscription(subscription)
        self._matching_subscriptions.cache_clear()

        # Only subscribe if currently connected.
        if self.connected:
            self._async_queue_subscriptions(((topic, qos),))

        return partial(self._async_remove, subscription)

    @callback
    def _async_remove(self, subscription: Subscription) -> None:
        """Remove subscription."""
        self._async_untrack_subscription(subscription)
        self._matching_subscriptions.cache_clear()
        if subscription in self._retained_topics:
            del self._retained_topics[subscription]
        # Only unsubscribe if currently connected
        if self.connected:
            self._async_unsubscribe(subscription.topic)

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

        # Split out the wildcard subscriptions, we subscribe to them one by one
        pending_subscriptions: dict[str, int] = self._pending_subscriptions
        pending_wildcard_subscriptions = {
            subscription.topic: pending_subscriptions.pop(subscription.topic)
            for subscription in self._wildcard_subscriptions
            if subscription.topic in pending_subscriptions
        }

        self._pending_subscriptions = {}

        debug_enabled = _LOGGER.isEnabledFor(logging.DEBUG)

        for chunk in chain(
            chunked_or_all(
                pending_wildcard_subscriptions.items(), MAX_WILDCARD_SUBSCRIBES_PER_CALL
            ),
            chunked_or_all(pending_subscriptions.items(), MAX_SUBSCRIBES_PER_CALL),
        ):
            chunk_list = list(chunk)
            if not chunk_list:
                continue

            result, mid = self._mqttc.subscribe(chunk_list)

            if debug_enabled:
                _LOGGER.debug(
                    "Subscribing with mid: %s to topics with qos: %s", mid, chunk_list
                )
            self._last_subscribe = time.monotonic()

            await self._async_wait_for_mid_or_raise(mid, result)

    async def _async_perform_unsubscribes(self) -> None:
        """Perform pending MQTT client unsubscribes."""
        if not self._pending_unsubscribes:
            return

        topics = list(self._pending_unsubscribes)
        self._pending_unsubscribes = set()
        debug_enabled = _LOGGER.isEnabledFor(logging.DEBUG)

        for chunk in chunked_or_all(topics, MAX_UNSUBSCRIBES_PER_CALL):
            chunk_list = list(chunk)

            result, mid = self._mqttc.unsubscribe(chunk_list)
            if debug_enabled:
                _LOGGER.debug(
                    "Unsubscribing with mid: %s to topics: %s", mid, chunk_list
                )

            await self._async_wait_for_mid_or_raise(mid, result)

    async def _async_resubscribe_and_publish_birth_message(
        self, birth_message: PublishMessage
    ) -> None:
        """Resubscribe to all topics and publish birth message."""
        self._async_queue_resubscribe()
        self._subscribe_debouncer.async_schedule()
        await self._ha_started.wait()  # Wait for Home Assistant to start
        await self._discovery_cooldown()  # Wait for MQTT discovery to cool down
        # Update subscribe cooldown period to a shorter time
        # and make sure we flush the debouncer
        await self._subscribe_debouncer.async_execute()
        self._subscribe_debouncer.set_timeout(SUBSCRIBE_COOLDOWN)
        await self.async_publish(
            topic=birth_message.topic,
            payload=birth_message.payload,
            qos=birth_message.qos,
            retain=birth_message.retain,
        )
        _LOGGER.info("MQTT client initialized, birth message sent")

    @callback
    def _async_mqtt_on_connect(
        self,
        _mqttc: mqtt.Client,
        _userdata: None,
        _connect_flags: mqtt.ConnectFlags,
        reason_code: mqtt.ReasonCode,
        _properties: mqtt.Properties | None = None,
    ) -> None:
        """On connect callback.

        Resubscribe to all topics we were subscribed to and publish birth
        message.
        """
        if reason_code.is_failure:
            # 24: Continue authentication
            # 25: Re-authenticate
            # 134: Bad user name or password
            # 135: Not authorized
            # 140: Bad authentication method
            if reason_code.value in (24, 25, 134, 135, 140):
                self._should_reconnect = False
                self.hass.async_create_task(self.async_disconnect())
                self.config_entry.async_start_reauth(self.hass)
            _LOGGER.error(
                "Unable to connect to the MQTT broker: %s",
                reason_code.getName(),  # type: ignore[no-untyped-call]
            )
            self._async_connection_result(False)
            return

        self.connected = True
        async_dispatcher_send(self.hass, MQTT_CONNECTION_STATE, True)
        _LOGGER.debug(
            "Connected to MQTT server %s:%s (%s)",
            self.conf[CONF_BROKER],
            self.conf.get(CONF_PORT, DEFAULT_PORT),
            reason_code,
        )

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
            self._async_queue_resubscribe()
            self._subscribe_debouncer.async_schedule()

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
            # mypy doesn't know that complex_matcher is always set when
            # is_simple_match is False
            if subscription.complex_matcher(topic)  # type: ignore[misc]
        )
        return subscriptions

    @callback
    def _async_mqtt_on_message(
        self, _mqttc: mqtt.Client, _userdata: None, msg: mqtt.MQTTMessage
    ) -> None:
        try:
            # msg.topic is a property that decodes the topic to a string
            # every time it is accessed. Save the result to avoid
            # decoding the same topic multiple times.
            topic = msg.topic
        except UnicodeDecodeError:
            bare_topic: bytes = msg._topic  # noqa: SLF001
            _LOGGER.warning(
                "Skipping received%s message on invalid topic %s (qos=%s): %s",
                " retained" if msg.retain else "",
                bare_topic,
                msg.qos,
                msg.payload[0:8192],
            )
            return
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
                retained_topics = self._retained_topics[subscription]
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
            job = subscription.job
            if job.job_type is HassJobType.Callback:
                # We do not wrap Callback jobs in catch_log_exception since
                # its expensive and we have to do it 2x for every entity
                try:
                    job.target(receive_msg)
                except Exception:  # noqa: BLE001
                    log_exception(
                        partial(self._exception_message, job.target, receive_msg)
                    )
            else:
                self.hass.async_run_hass_job(job, receive_msg)
        self._mqtt_data.state_write_requests.process_write_state_requests(msg)

    @callback
    def _async_mqtt_on_publish(
        self,
        _mqttc: mqtt.Client,
        _userdata: None,
        mid: int,
        _reason_code: mqtt.ReasonCode,
        _properties: mqtt.Properties | None,
    ) -> None:
        """Publish callback."""
        self._async_mqtt_on_callback(mid)

    @callback
    def _async_mqtt_on_subscribe_unsubscribe(
        self,
        _mqttc: mqtt.Client,
        _userdata: None,
        mid: int,
        _reason_code: list[mqtt.ReasonCode],
        _properties: mqtt.Properties | None,
    ) -> None:
        """Subscribe / Unsubscribe callback."""
        self._async_mqtt_on_callback(mid)

    @callback
    def _async_mqtt_on_callback(self, mid: int) -> None:
        """Publish / Subscribe / Unsubscribe callback."""
        future = self._async_get_mid_future(mid)
        if future.done() and (future.cancelled() or future.exception()):
            # Timed out or cancelled
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
    def _async_handle_callback_exception(self, status: mqtt.MQTTErrorCode) -> None:
        """Handle a callback exception."""
        # We don't import on the top because some integrations
        # should be able to optionally rely on MQTT.
        import paho.mqtt.client as mqtt  # pylint: disable=import-outside-toplevel

        _LOGGER.warning(
            "Error returned from MQTT server: %s",
            mqtt.error_string(status),
        )

    @callback
    def _async_mqtt_on_disconnect(
        self,
        _mqttc: mqtt.Client,
        _userdata: None,
        _disconnect_flags: mqtt.DisconnectFlags,
        reason_code: mqtt.ReasonCode,
        properties: mqtt.Properties | None = None,
    ) -> None:
        """Disconnected callback."""
        if not self.connected:
            # This function is re-entrant and may be called multiple times
            # when there is a broken pipe error.
            return
        # If disconnect is called before the connect
        # result is set make sure the first connection result is set
        self._async_connection_result(False)
        self.connected = False
        async_dispatcher_send(self.hass, MQTT_CONNECTION_STATE, False)
        _LOGGER.log(
            logging.INFO if reason_code == 0 else logging.DEBUG,
            "Disconnected from MQTT server %s:%s (%s)",
            self.conf[CONF_BROKER],
            self.conf.get(CONF_PORT, DEFAULT_PORT),
            reason_code,
        )

    @callback
    def _async_timeout_mid(self, future: asyncio.Future[None]) -> None:
        """Timeout waiting for a mid."""
        if not future.done():
            future.set_exception(asyncio.TimeoutError)

    async def _async_wait_for_mid_or_raise(
        self, mid: int | None, result_code: int
    ) -> None:
        """Wait for ACK from broker or raise on error."""
        if result_code != 0:
            # pylint: disable-next=import-outside-toplevel
            import paho.mqtt.client as mqtt

            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="mqtt_broker_error",
                translation_placeholders={
                    "error_message": mqtt.error_string(result_code)
                },
            )

        # Create the mid event if not created, either _mqtt_handle_mid or
        # _async_wait_for_mid_or_raise may be executed first.
        if TYPE_CHECKING:
            assert mid is not None
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
        wait_until = max(last_discovery, last_subscribe) + DISCOVERY_COOLDOWN
        while now < wait_until:
            await asyncio.sleep(wait_until - now)
            now = time.monotonic()
            last_discovery = self._mqtt_data.last_discovery
            last_subscribe = (
                now if self._pending_subscriptions else self._last_subscribe
            )
            wait_until = max(last_discovery, last_subscribe) + DISCOVERY_COOLDOWN


def _matcher_for_topic(subscription: str) -> Callable[[str], bool]:
    # pylint: disable-next=import-outside-toplevel
    from paho.mqtt.matcher import MQTTMatcher

    matcher = MQTTMatcher()  # type: ignore[no-untyped-call]
    matcher[subscription] = True

    return lambda topic: next(matcher.iter_match(topic), False)  # type: ignore[no-untyped-call]
