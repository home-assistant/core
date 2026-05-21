"""Support for MQTT message handling."""

import asyncio
from collections.abc import Callable
import logging
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import (
    CALLBACK_TYPE,
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

from aiolocknalert.client import MQTT as _LibMQTT, MQTTError, Subscription
from aiolocknalert.const import DEFAULT_ENCODING, DEFAULT_QOS
from aiolocknalert.models import (
    MessageCallbackType,
    PublishPayloadType,
    ReceiveMessage,
)

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
    """Call on_subscribe_done when the matched subscription was completed.

    If a subscription is already present the callback will call
    on_subscribe_status directly.
    Call the returned callback to stop and cleanup status monitoring.
    """

    async def _sync_mqtt_subscribe(subscriptions: list[tuple[str, int]]) -> None:
        if (topic, qos) not in subscriptions:
            return
        hass.loop.call_soon(on_subscribe_status)

    mqtt_data = hass.data[DATA_MQTT]
    lib_client = mqtt_data.client.client
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
    msg_callback: Callable[[ReceiveMessage], None],
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
    msg_callback: Callable[[ReceiveMessage], None],
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
    if not mqtt_config_entry_enabled(hass):
        raise HomeAssistantError(
            f"Cannot subscribe to topic '{topic}', MQTT is not enabled",
            translation_key="mqtt_not_setup_cannot_subscribe",
            translation_domain=DOMAIN,
            translation_placeholders={"topic": topic},
        )
    return mqtt_data.client.async_subscribe(topic, msg_callback, qos, encoding, job_type)


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


class MQTT(_LibMQTT):
    """Library MQTT client extended with HA entity state write flushing."""

    _mqtt_data: MqttData

    def _async_mqtt_on_message(
        self,
        _mqttc: "mqtt.Client",
        _userdata: None,
        msg: "mqtt.MQTTMessage",
    ) -> None:
        super()._async_mqtt_on_message(_mqttc, _userdata, msg)
        self._mqtt_data.state_write_requests.process_write_state_requests(msg)


class MQTTAdapter:
    """Thin HA wrapper around aiolocknalert.client.MQTT."""

    def __init__(
        self, hass: HomeAssistant, config_entry: ConfigEntry, conf: dict
    ) -> None:
        """Initialize the MQTT adapter."""
        self.hass = hass
        self.config_entry = config_entry

        self.client = MQTT(conf)

        self.client.on_connection_state_changed = (
            lambda connected: async_dispatcher_send(hass, MQTT_CONNECTION_STATE, connected)
        )
        self.client.on_subscriptions_acknowledged = (
            lambda subs: async_dispatcher_send(hass, MQTT_PROCESSED_SUBSCRIPTIONS, subs)
        )
        self.client.on_reauth_required = (
            lambda: config_entry.async_start_reauth(hass)
        )

        self._cleanup_on_unload: list[Callable[[], None]] = [
            async_at_started(hass, lambda _: self.client.async_signal_ha_started()),
            hass.bus.async_listen(
                EVENT_HOMEASSISTANT_STOP,
                lambda _event: hass.async_create_task(self.client.async_disconnect()),
            ),
        ]

    async def async_start(self, mqtt_data: MqttData) -> None:
        """Start the MQTT client."""
        self.client._mqtt_data = mqtt_data  # noqa: SLF001
        with async_pause_setup(self.hass, SetupPhases.WAIT_IMPORT_PACKAGES):
            await async_import_module(self.hass, "aiolocknalert.async_client")
        await self.client.async_start()

    async def async_connect(self, client_available: asyncio.Future[bool]) -> None:
        """Connect to the broker."""
        await self.client.async_connect(client_available)

    async def async_disconnect(self, disconnect_paho_client: bool = False) -> None:
        """Stop the MQTT client."""
        await self.client.async_disconnect(disconnect_paho_client)

    async def async_publish(
        self, topic: str, payload: PublishPayloadType, qos: int, retain: bool
    ) -> None:
        """Publish a MQTT message."""
        try:
            await self.client.async_publish(topic, payload, qos, retain)
        except MQTTError as err:
            raise HomeAssistantError(
                str(err),
                translation_domain=DOMAIN,
                translation_key="mqtt_broker_error",
            ) from err

    @callback
    def async_subscribe(
        self,
        topic: str,
        msg_callback: MessageCallbackType,
        qos: int,
        encoding: str | None = None,
        job_type: HassJobType | None = None,
    ) -> Callable[[], None]:
        """Set up a subscription to a topic with the provided qos."""
        if job_type is None:
            job_type = get_hassjob_callable_job_type(msg_callback)
        if job_type is not HassJobType.Callback:
            msg_callback = catch_log_exception(
                msg_callback, lambda: f"Exception handling msg on '{topic}'"
            )
        return self.client.async_subscribe(topic, msg_callback, qos, encoding)

    @callback
    def async_restore_tracked_subscriptions(
        self, subscriptions: set[Subscription]
    ) -> None:
        """Restore tracked subscriptions after reload."""
        self.client.async_restore_tracked_subscriptions(subscriptions)

    @property
    def connected(self) -> bool:
        """Return whether the client is connected."""
        return self.client.connected

    @property
    def subscriptions(self) -> set[Subscription]:
        """Return the tracked subscriptions."""
        return self.client.subscriptions

    def cleanup(self) -> None:
        """Clean up HA listeners."""
        while self._cleanup_on_unload:
            self._cleanup_on_unload.pop()()
        self.client.cleanup()
