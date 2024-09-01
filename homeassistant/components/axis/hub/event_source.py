"""Axis network device abstraction."""

from __future__ import annotations

import axis
from axis.errors import Unauthorized
from axis.interfaces.mqtt import mqtt_json_to_event
from axis.models.mqtt import ClientState
from axis.stream_manager import Signal, State

from homeassistant.components import mqtt
from homeassistant.components.mqtt import DOMAIN as MQTT_DOMAIN
from homeassistant.components.mqtt.models import ReceiveMessage
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.setup import async_when_setup


class AxisEventSource:
    """Manage connection to event sources from an Axis device."""

    def __init__(
        self, hass: HomeAssistant, config_entry: ConfigEntry, api: axis.AxisDevice
    ) -> None:
        """Initialize the device."""
        self.hass = hass
        self.config_entry = config_entry
        self.api = api

        self.signal_reachable = f"axis_reachable_{config_entry.entry_id}"

        self.available = True

    @callback
    def setup(self) -> None:
        """Set up the device events."""
        self.api.stream.connection_status_callback.append(self._connection_status_cb)
        self.api.enable_events()
        self.api.stream.start()

        if self.api.vapix.mqtt.supported:
            async_when_setup(self.hass, MQTT_DOMAIN, self._async_use_mqtt)

    @callback
    def teardown(self) -> None:
        """Tear down connections."""
        self._disconnect_from_stream()

    @callback
    def _disconnect_from_stream(self) -> None:
        """Stop stream."""
        if self.api.stream.state != State.STOPPED:
            self.api.stream.connection_status_callback.clear()
        self.api.stream.stop()

    async def _async_use_mqtt(self, hass: HomeAssistant, component: str) -> None:
        """Set up to use MQTT."""
        try:
            status = await self.api.vapix.mqtt.get_client_status()
        except Unauthorized:
            # This means the user has too low privileges
            return

        if status.status.state == ClientState.ACTIVE:
            self.config_entry.async_on_unload(
                await mqtt.async_subscribe(
                    hass, f"{status.config.device_topic_prefix}/#", self._mqtt_message
                )
            )

    @callback
    def _mqtt_message(self, message: ReceiveMessage) -> None:
        """Receive Axis MQTT message."""
        self._disconnect_from_stream()

        if message.topic.endswith("event/connection"):
            return

        event = mqtt_json_to_event(message.payload)
        self.api.event.handler(event)

    @callback
    def _connection_status_cb(self, status: Signal) -> None:
        """Handle signals of device connection status.

        This is called on every RTSP keep-alive message.
        Only signal state change if state change is true.
        """

        if self.available != (status == Signal.PLAYING):
            self.available = not self.available
            async_dispatcher_send(self.hass, self.signal_reachable)
