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
    """Publish message to an MQTT topic."""
    hass.create_task(async_publish(hass, topic, payload, qos, retain, encoding))


async def async_publish(
    hass: HomeAssistant,
    topic: str,
    payload: PublishPayloadType,
    qos: int | None = 0,
    retain: bool | None = False,
    encoding: str | None = DEFAULT_ENCODING,
) -> None:
    """Publish message to an MQTT topic."""
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
            except AttributeError, LookupError, UnicodeEncodeError:
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
    """Subscribe to an MQTT topic.

    Call the return value to unsubscribe.
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
    """HA-aware MQTT client backed by aiolocknalert."""

    _mqtt_data: MqttData

    def __init__(
        self, hass: HomeAssistant, config_entry: ConfigEntry, conf: dict
    ) -> None:
        """Initialize the MQTT client."""
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
        super()._async_mqtt_on_message(_mqttc, _userdata, msg)
        self._mqtt_data.state_write_requests.process_write_state_requests(msg)

    async def async_initialize(self, mqtt_data: MqttData) -> None:
        """Store HA-specific data then start the MQTT client."""
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
        """Set up a subscription to a topic with the provided qos."""
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
        """Publish an MQTT message."""
        try:
            await super().async_publish(topic, payload, qos, retain)
        except MQTTError as err:
            raise HomeAssistantError(
                translation_key="mqtt_broker_error",
                translation_domain=DOMAIN,
                translation_placeholders={"error_message": str(err)},
            ) from err

    def cleanup(self) -> None:
        """Clean up HA listeners."""
        while self._cleanup_on_unload:
            self._cleanup_on_unload.pop()()
        super().cleanup()
