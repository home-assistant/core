"""Axis network device abstraction."""

from __future__ import annotations

from typing import Any

import axis
from axis.errors import Unauthorized
from axis.interfaces.mqtt import mqtt_json_to_event
from axis.models.mqtt import ClientState
from axis.stream_manager import Signal, State

from homeassistant.components import mqtt
from homeassistant.components.mqtt import DOMAIN as MQTT_DOMAIN
from homeassistant.components.mqtt.models import ReceiveMessage
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, format_mac
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.setup import async_when_setup

from ..const import ATTR_MANUFACTURER, DOMAIN as AXIS_DOMAIN
from .config import AxisConfig
from .entity_loader import AxisEntityLoader


class AxisHub:
    """Manages a Axis device."""

    def __init__(
        self, hass: HomeAssistant, config_entry: ConfigEntry, api: axis.AxisDevice
    ) -> None:
        """Initialize the device."""
        self.hass = hass
        self.config = AxisConfig.from_config_entry(config_entry)
        self.entity_loader = AxisEntityLoader(self)
        self.api = api

        self.available = True
        self.fw_version = api.vapix.firmware_version
        self.product_type = api.vapix.product_type
        self.unique_id = format_mac(api.vapix.serial_number)

        self.additional_diagnostics: dict[str, Any] = {}

    @callback
    @staticmethod
    def get_hub(hass: HomeAssistant, config_entry: ConfigEntry) -> AxisHub:
        """Get Axis hub from config entry."""
        hub: AxisHub = hass.data[AXIS_DOMAIN][config_entry.entry_id]
        return hub

    # Signals

    @property
    def signal_reachable(self) -> str:
        """Device specific event to signal a change in connection status."""
        return f"axis_reachable_{self.config.entry.entry_id}"

    @property
    def signal_new_address(self) -> str:
        """Device specific event to signal a change in device address."""
        return f"axis_new_address_{self.config.entry.entry_id}"

    # Callbacks

    @callback
    def connection_status_callback(self, status: Signal) -> None:
        """Handle signals of device connection status.

        This is called on every RTSP keep-alive message.
        Only signal state change if state change is true.
        """

        if self.available != (status == Signal.PLAYING):
            self.available = not self.available
            async_dispatcher_send(self.hass, self.signal_reachable)

    @staticmethod
    async def async_new_address_callback(
        hass: HomeAssistant, config_entry: ConfigEntry
    ) -> None:
        """Handle signals of device getting new address.

        Called when config entry is updated.
        This is a static method because a class method (bound method),
        cannot be used with weak references.
        """
        hub = AxisHub.get_hub(hass, config_entry)
        hub.config = AxisConfig.from_config_entry(config_entry)
        hub.api.config.host = hub.config.host
        async_dispatcher_send(hass, hub.signal_new_address)

    async def async_update_device_registry(self) -> None:
        """Update device registry."""
        device_registry = dr.async_get(self.hass)
        device_registry.async_get_or_create(
            config_entry_id=self.config.entry.entry_id,
            configuration_url=self.api.config.url,
            connections={(CONNECTION_NETWORK_MAC, self.unique_id)},
            identifiers={(AXIS_DOMAIN, self.unique_id)},
            manufacturer=ATTR_MANUFACTURER,
            model=f"{self.config.model} {self.product_type}",
            name=self.config.name,
            sw_version=self.fw_version,
        )

    async def async_use_mqtt(self, hass: HomeAssistant, component: str) -> None:
        """Set up to use MQTT."""
        try:
            status = await self.api.vapix.mqtt.get_client_status()
        except Unauthorized:
            # This means the user has too low privileges
            return
        if status.status.state == ClientState.ACTIVE:
            self.config.entry.async_on_unload(
                await mqtt.async_subscribe(
                    hass, f"{status.config.device_topic_prefix}/#", self.mqtt_message
                )
            )

    @callback
    def mqtt_message(self, message: ReceiveMessage) -> None:
        """Receive Axis MQTT message."""
        self.disconnect_from_stream()
        if message.topic.endswith("event/connection"):
            return
        event = mqtt_json_to_event(message.payload)
        self.api.event.handler(event)

    # Setup and teardown methods

    @callback
    def setup(self) -> None:
        """Set up the device events."""
        self.entity_loader.initialize_platforms()

        self.api.stream.connection_status_callback.append(
            self.connection_status_callback
        )
        self.api.enable_events()
        self.api.stream.start()

        if self.api.vapix.mqtt.supported:
            async_when_setup(self.hass, MQTT_DOMAIN, self.async_use_mqtt)

    @callback
    def disconnect_from_stream(self) -> None:
        """Stop stream."""
        if self.api.stream.state != State.STOPPED:
            self.api.stream.connection_status_callback.clear()
        self.api.stream.stop()

    async def shutdown(self, event: Event) -> None:
        """Stop the event stream."""
        self.disconnect_from_stream()

    @callback
    def teardown(self) -> None:
        """Reset this device to default state."""
        self.disconnect_from_stream()
