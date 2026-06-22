"""Coordinator for Place integration — MQTT push for device shadow updates."""

from collections.abc import Callable
import logging

from place.messages import PlaceMessages, message_kind, parse_payload
from place.models.discover_device import DiscoverDevice
from place.mqtt_client import MqttClient
from place.provider import Provider

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback

from .models import PlaceDeviceShadow

_LOGGER = logging.getLogger(__name__)

type PlaceConfigEntry = ConfigEntry[PlaceCoordinator]


class PlaceCoordinator:
    """Coordinate device shadow state via MQTT push."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: PlaceConfigEntry,
        provider: Provider,
        mqtt_client: MqttClient,
    ) -> None:
        """Initialize the coordinator."""
        self.hass = hass
        self.config_entry = config_entry
        self.provider = provider
        self.mqtt_client = mqtt_client
        self.messages = PlaceMessages(mqtt_client)
        self.devices: list[DiscoverDevice] = []
        self.shadows: dict[str, PlaceDeviceShadow] = {}
        self._listeners: list[Callable[[], None]] = []

    async def async_setup(self) -> None:
        """Discover devices, seed shadow state, and start MQTT."""
        self.devices = await self.provider.discover()

        for device in self.devices:
            if device.thing_name and device.shadow:
                self.shadows[device.thing_name] = PlaceDeviceShadow.from_shadow(
                    device.shadow
                )

        await self.hass.async_add_executor_job(self._start_mqtt)

    def _start_mqtt(self) -> None:
        """Connect MQTT and subscribe to shadow topics (runs in executor)."""
        self.mqtt_client.connect(
            on_message=self._on_mqtt_message,
            on_connect=self._on_mqtt_connect,
        )
        # loop_start runs paho's network loop in a background thread
        self.mqtt_client.loop_start()

    def _on_mqtt_connect(self) -> None:
        """Subscribe to shadow topics for all discovered devices."""
        for device in self.devices:
            if device.thing_name:
                self.messages.subscribe_shadow(device.thing_name)
                self.messages.publish_shadow_get(device.thing_name)
                _LOGGER.debug("Subscribed to shadow for %s", device.thing_name)

    def _on_mqtt_message(self, topic: str, raw: bytes) -> None:
        """Handle incoming MQTT messages (called from paho thread)."""
        payload = parse_payload(raw)
        kind = message_kind(topic, payload)

        if kind != "shadow":
            return

        thing_name = self._thing_name_from_topic(topic)
        if not thing_name:
            return

        if thing_name in self.shadows:
            self.shadows[thing_name].merge(payload)
        else:
            self.shadows[thing_name] = PlaceDeviceShadow.from_shadow(payload)

        _LOGGER.debug("Shadow update for %s: %s", thing_name, payload)

        self.hass.loop.call_soon_threadsafe(self._async_notify_listeners)

    @callback
    def _async_notify_listeners(self) -> None:
        """Notify all registered listeners of a state change."""
        for update_callback in self._listeners:
            update_callback()

    @callback
    def async_add_listener(
        self, update_callback: Callable[[], None]
    ) -> Callable[[], None]:
        """Register a listener for shadow updates. Returns an unsubscribe callable."""
        self._listeners.append(update_callback)

        @callback
        def remove_listener() -> None:
            self._listeners.remove(update_callback)

        return remove_listener

    async def async_shutdown(self) -> None:
        """Disconnect MQTT."""
        await self.hass.async_add_executor_job(self._stop_mqtt)

    def _stop_mqtt(self) -> None:
        """Stop the MQTT loop (runs in executor)."""
        self.mqtt_client.disconnect()

    @staticmethod
    def _thing_name_from_topic(topic: str) -> str | None:
        """Extract thing_name from an AWS IoT shadow topic.

        Topics look like: $aws/things/{thing_name}/shadow/...
        """
        parts = topic.split("/")
        if len(parts) >= 3 and parts[0] == "$aws" and parts[1] == "things":
            return parts[2]
        return None
