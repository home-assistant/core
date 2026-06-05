"""HA-aware MQTT client for LocknAlert bridges.

Each LocknAlert bridge runs its own embedded MQTT broker. Users may simultaneously
run the built-in `mqtt` integration connected to a separate broker (e.g. for Tasmota
or Zigbee2MQTT). Because the built-in `mqtt` integration is single-entry and supports
only one broker at a time, this integration manages its own client connections rather
than depending on `mqtt`.
"""

import asyncio
from collections.abc import Callable
import logging
from typing import TYPE_CHECKING

from aiolocknalert.client import MQTT as _LibMQTT, MQTTError
from aiolocknalert.const import DEFAULT_ENCODING, DEFAULT_QOS
from aiolocknalert.models import MessageCallbackType, PublishPayloadType

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    HassJobType,
    HomeAssistant,
    callback,
    get_hassjob_callable_job_type,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.importlib import async_import_module
from homeassistant.helpers.start import async_at_started
from homeassistant.setup import SetupPhases, async_pause_setup
from homeassistant.util.logging import catch_log_exception

from .const import DOMAIN, MQTT_CONNECTION_STATE, MQTT_PROCESSED_SUBSCRIPTIONS
from .models import DATA_MQTT, MqttData
from .util import mqtt_config_entry_enabled

if TYPE_CHECKING:
    import paho.mqtt.client as mqtt

_LOGGER = logging.getLogger(__name__)


def publish(
    hass: HomeAssistant,
    topic: str,
    payload: PublishPayloadType,
    qos: int | None = 0,
    retain: bool | None = False,
    encoding: str | None = DEFAULT_ENCODING,
) -> None:
    """Schedule an MQTT publish as a fire-and-forget task.

    Delegates to async_publish via hass.async_create_task so callers
    do not need to await the result.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        topic (str): MQTT topic to publish to.
        payload (PublishPayloadType): Message payload.
        qos (int | None): MQTT quality-of-service level (0, 1, or 2).
        retain (bool | None): Whether the broker should retain the message.
        encoding (str | None): Encoding used to convert non-bytes payloads.
    """
    hass.async_create_task(async_publish(hass, topic, payload, qos, retain, encoding))


async def async_publish(
    hass: HomeAssistant,
    topic: str,
    payload: PublishPayloadType,
    qos: int | None = 0,
    retain: bool | None = False,
    encoding: str | None = DEFAULT_ENCODING,
) -> None:
    """Publish a message to an MQTT topic asynchronously.

    Encodes non-bytes payloads according to ``encoding`` before forwarding
    them to the underlying client.  Raises if the integration is not set up.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        topic (str): MQTT topic to publish to.
        payload (PublishPayloadType): Message payload.
        qos (int | None): MQTT quality-of-service level (0, 1, or 2).
        retain (bool | None): Whether the broker should retain the message.
        encoding (str | None): Encoding used to convert non-bytes payloads.

    Raises:
        HomeAssistantError: If the integration is not configured or the
            payload cannot be encoded with the requested encoding.
    """
    if not mqtt_config_entry_enabled(hass):
        raise HomeAssistantError(
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


@callback
def async_on_subscribe_done(
    hass: HomeAssistant,
    topic: str,
    qos: int,
    on_subscribe_status: CALLBACK_TYPE,
) -> CALLBACK_TYPE:
    """Invoke a callback once the given topic subscription is acknowledged.

    If an active (non-pending) subscription for the topic already exists,
    ``on_subscribe_status`` is scheduled immediately via the event loop.
    Otherwise it is called when the broker acknowledges the subscription.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        topic (str): The MQTT topic being monitored.
        qos (int): The QoS level of the subscription to monitor.
        on_subscribe_status (CALLBACK_TYPE): Callable invoked once the
            subscription is confirmed.

    Returns:
        CALLBACK_TYPE: Call this to stop monitoring the subscription status.
    """

    async def _sync_mqtt_subscribe(subscriptions: list[tuple[str, int]]) -> None:
        """Dispatch on_subscribe_status when the target subscription appears."""
        if (topic, qos) not in subscriptions:
            return
        hass.loop.call_soon(on_subscribe_status)

    mqtt_data = hass.data[DATA_MQTT]
    lib_client = mqtt_data.client
    if (
        lib_client.connected
        and lib_client.is_active_subscription(topic)
        and not lib_client.is_pending_subscription(topic)
    ):
        hass.loop.call_soon(on_subscribe_status)

    return async_dispatcher_connect(
        hass, MQTT_PROCESSED_SUBSCRIPTIONS, _sync_mqtt_subscribe
    )


async def async_subscribe(
    hass: HomeAssistant,
    topic: str,
    msg_callback: MessageCallbackType,
    qos: int = DEFAULT_QOS,
    encoding: str | None = DEFAULT_ENCODING,
) -> CALLBACK_TYPE:
    """Subscribe to an MQTT topic and return an unsubscribe callback.

    Thin async wrapper around async_subscribe_internal.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        topic (str): MQTT topic filter to subscribe to.
        msg_callback (MessageCallbackType): Callable invoked for each received message.
        qos (int): MQTT quality-of-service level for the subscription.
        encoding (str | None): Encoding used to decode incoming message payloads.

    Returns:
        CALLBACK_TYPE: Call this to remove the subscription.
    """
    return async_subscribe_internal(hass, topic, msg_callback, qos, encoding)


@callback
def async_subscribe_internal(
    hass: HomeAssistant,
    topic: str,
    msg_callback: MessageCallbackType,
    qos: int = DEFAULT_QOS,
    encoding: str | None = DEFAULT_ENCODING,
    job_type: HassJobType | None = None,
) -> CALLBACK_TYPE:
    """Subscribe to an MQTT topic (internal API; subject to change without notice).

    Delegates directly to the underlying MQTT client after validating that
    the integration is configured.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        topic (str): MQTT topic filter to subscribe to.
        msg_callback (MessageCallbackType): Callable invoked for each received message.
        qos (int): MQTT quality-of-service level for the subscription.
        encoding (str | None): Encoding used to decode incoming message payloads.
        job_type (HassJobType | None): Execution model hint for the callback.

    Returns:
        CALLBACK_TYPE: Call this to remove the subscription.

    Raises:
        HomeAssistantError: If the integration is not configured.
    """
    try:
        mqtt_data = hass.data[DATA_MQTT]
    except KeyError as exc:
        raise HomeAssistantError(
            translation_key="mqtt_not_setup_cannot_subscribe",
            translation_domain=DOMAIN,
            translation_placeholders={"topic": topic},
        ) from exc
    if not mqtt_config_entry_enabled(hass):
        raise HomeAssistantError(
            translation_key="mqtt_not_setup_cannot_subscribe",
            translation_domain=DOMAIN,
            translation_placeholders={"topic": topic},
        )
    return mqtt_data.client.async_subscribe(
        topic, msg_callback, qos, encoding, job_type
    )


def subscribe(
    hass: HomeAssistant,
    topic: str,
    msg_callback: MessageCallbackType,
    qos: int = DEFAULT_QOS,
    encoding: str | None = DEFAULT_ENCODING,
) -> Callable[[], None]:
    """Subscribe to an MQTT topic from a non-async (threaded) context.

    Schedules :func:`async_subscribe` on the event-loop thread using
    :func:`asyncio.run_coroutine_threadsafe` and blocks until the
    subscription is registered.  The returned callable uses
    ``loop.call_soon_threadsafe`` to cancel the subscription without
    the overhead of ``hass.add_job``.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        topic (str): MQTT topic filter to subscribe to.
        msg_callback (MessageCallbackType): Callable invoked for each
            received message.
        qos (int): MQTT quality-of-service level for the subscription.
        encoding (str | None): Encoding used to decode incoming payloads.

    Returns:
        Callable[[], None]: Call this from any thread to remove the
            subscription.
    """
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


class MQTT(_LibMQTT):
    """HA-aware MQTT client that wires aiolocknalert into the HA event system.

    Subclasses :class:`aiolocknalert.client.MQTT` and connects the three
    library callback hooks to HA dispatcher signals and lifecycle events:

    * ``on_connection_state_changed`` → :data:`~.const.MQTT_CONNECTION_STATE`
    * ``on_subscriptions_acknowledged`` → :data:`~.const.MQTT_PROCESSED_SUBSCRIPTIONS`
    * ``on_reauth_required`` → :meth:`~homeassistant.config_entries.ConfigEntry.async_start_reauth`

    Also registers ``EVENT_HOMEASSISTANT_STARTED`` and ``EVENT_HOMEASSISTANT_STOP``
    listeners so the client lifecycle is tied to HA startup and shutdown.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        config_entry (ConfigEntry): The locknalert_mqtt config entry owning
            this client, used for reauth triggering.
        conf (dict): Merged config-entry data and options containing broker
            address, credentials, TLS settings, birth/will messages, etc.
    """

    _mqtt_data: MqttData

    def __init__(
        self, hass: HomeAssistant, config_entry: ConfigEntry, conf: dict
    ) -> None:
        """Wire HA dispatcher signals and lifecycle listeners to the library client."""
        super().__init__(conf)
        self.hass = hass
        self.config_entry = config_entry
        self.on_connection_state_changed = lambda connected: async_dispatcher_send(
            hass, MQTT_CONNECTION_STATE, connected
        )
        self.on_subscriptions_acknowledged = lambda subs: async_dispatcher_send(
            hass, MQTT_PROCESSED_SUBSCRIPTIONS, subs
        )
        self.on_reauth_required = lambda: config_entry.async_start_reauth(hass)

        @callback
        def _stop_on_hass_stop(_: Event) -> None:
            hass.async_create_task(self.async_disconnect())

        self._cleanup_on_unload: list[Callable[[], None]] = [
            async_at_started(hass, lambda _: self.async_signal_ha_started()),
            hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, _stop_on_hass_stop),
        ]

    def _async_mqtt_on_message(
        self,
        _mqttc: mqtt.Client,
        _userdata: None,
        msg: mqtt.MQTTMessage,
    ) -> None:
        """Handle an incoming MQTT message and drain pending HA state writes.

        Calls the parent implementation to dispatch the message to all
        matching subscriptions, then flushes any deferred
        :meth:`~.models.EntityTopicState.write_state_request` entries so
        entity states are written to HA in a single batch per message.

        Args:
            _mqttc (mqtt.Client): The paho client instance (unused).
            _userdata (None): paho user data (unused).
            msg (mqtt.MQTTMessage): The received paho MQTT message.
        """
        super()._async_mqtt_on_message(_mqttc, _userdata, msg)
        self._mqtt_data.state_write_requests.process_write_state_requests(msg)

    async def async_initialize(self, mqtt_data: MqttData) -> None:
        """Store runtime data and start the MQTT client.

        Saves *mqtt_data* for use by :meth:`_async_mqtt_on_message`, then
        lazily imports the ``aiolocknalert.async_client`` module under an HA
        setup-phase pause so the import is tracked correctly, before calling
        the library's ``async_start`` to initialise the paho client.

        Args:
            mqtt_data (MqttData): The runtime data store for this config entry.
        """
        self._mqtt_data = mqtt_data
        with async_pause_setup(self.hass, SetupPhases.WAIT_IMPORT_PACKAGES):
            await async_import_module(self.hass, "aiolocknalert.async_client")
        await self.async_start()

    @callback
    def async_subscribe(
        self,
        topic: str,
        msg_callback: MessageCallbackType,
        qos: int = DEFAULT_QOS,
        encoding: str | None = None,
        job_type: HassJobType | None = None,
    ) -> Callable[[], None]:
        """Register an MQTT subscription with HA-aware callback dispatch.

        Wraps the library's ``async_subscribe`` to infer the
        :class:`~homeassistant.core.HassJobType` for *msg_callback* and,
        for non-callback job types, wraps the callable with
        :func:`~homeassistant.util.logging.catch_log_exception` so
        exceptions are logged rather than silently swallowed.

        Args:
            topic (str): MQTT topic filter to subscribe to.
            msg_callback (MessageCallbackType): Callable invoked for each
                received message.
            qos (int): MQTT quality-of-service level (0, 1, or 2).
            encoding (str | None): Payload encoding, or ``None`` for raw
                bytes.
            job_type (HassJobType | None): Execution model override; inferred
                automatically when ``None``.

        Returns:
            Callable[[], None]: Call this to remove the subscription.
        """
        if job_type is None:
            job_type = get_hassjob_callable_job_type(msg_callback)
        if job_type is not HassJobType.Callback:
            msg_callback = catch_log_exception(
                msg_callback, lambda _: f"Exception in '{topic}' listener"
            )
        return super().async_subscribe(topic, msg_callback, qos, encoding)

    async def async_publish(
        self, topic: str, payload: PublishPayloadType, qos: int, retain: bool
    ) -> None:
        """Publish an MQTT message, translating broker errors to HA exceptions.

        Delegates to the library's ``async_publish`` and converts any
        :class:`~aiolocknalert.client.MQTTError` into a
        :class:`~homeassistant.exceptions.HomeAssistantError` with a
        user-readable translation key.

        Args:
            topic (str): MQTT topic to publish to.
            payload (PublishPayloadType): Message payload (``str``, ``bytes``,
                ``int``, ``float``, or ``None``).
            qos (int): MQTT quality-of-service level (0, 1, or 2).
            retain (bool): Whether the broker should retain the message.

        Raises:
            HomeAssistantError: If the broker returns an error for the
                publish operation.
        """
        try:
            await super().async_publish(topic, payload, qos, retain)
        except MQTTError as err:
            raise HomeAssistantError(
                translation_key="mqtt_broker_error",
                translation_domain=DOMAIN,
                translation_placeholders={"error_message": str(err)},
            ) from err

    def cleanup(self) -> None:
        """Cancel all HA event and dispatcher listeners registered during init.

        Pops and invokes each cancellable stored in ``_cleanup_on_unload``
        (the ``EVENT_HOMEASSISTANT_STOP`` bus listener and the
        ``async_at_started`` callback) then delegates to the library's
        ``cleanup`` to release its internal state.
        """
        while self._cleanup_on_unload:
            self._cleanup_on_unload.pop()()
        super().cleanup()
