"""Coordinator for Place integration — MQTT push for device shadow updates."""

from dataclasses import replace
import logging

from place.messages import PlaceMessages, message_kind, parse_payload
from place.models.discover_device import DiscoverDevice
from place.mqtt_client import MqttClient
from place.provider import Provider

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .models import PlaceDeviceShadow

_LOGGER = logging.getLogger(__name__)

type PlaceConfigEntry = ConfigEntry[PlaceCoordinator]


class PlaceCoordinator(DataUpdateCoordinator[dict[str, PlaceDeviceShadow]]):
    """Coordinate device shadow state via MQTT push."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: PlaceConfigEntry,
        provider: Provider,
        mqtt_client: MqttClient,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name="gentex_place",
            update_interval=None,
        )
        self.provider = provider
        self.mqtt_client = mqtt_client
        self.messages = PlaceMessages(mqtt_client)
        self.devices: list[DiscoverDevice] = []

    async def async_setup(self) -> None:
        """Discover devices, seed shadow state, and start MQTT."""
        self.devices = await self.provider.discover()

        initial: dict[str, PlaceDeviceShadow] = {}
        for device in self.devices:
            if device.thing_name and device.shadow:
                initial[device.thing_name] = PlaceDeviceShadow.from_shadow(
                    device.shadow
                )
        self.async_set_updated_data(initial)

        await self.hass.async_add_executor_job(self._start_mqtt)

    def _start_mqtt(self) -> None:
        """Connect MQTT and subscribe to shadow topics (runs in executor)."""
        self.mqtt_client.connect(
            on_message=self._on_mqtt_message,
            on_connect=self._on_mqtt_connect,
        )
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

        self.hass.loop.call_soon_threadsafe(
            self._async_apply_shadow_update, thing_name, payload
        )

    @callback
    def _async_apply_shadow_update(self, thing_name: str, payload: dict) -> None:
        """Apply a shadow update and broadcast new data on the event loop."""
        current = self.data or {}
        existing = current.get(thing_name)
        if existing is not None:
            # This is a shallow copy. Use deepcopy if caller mutates nested fields
            updated = replace(existing)
            updated.merge(payload)
        else:
            updated = PlaceDeviceShadow.from_shadow(payload)

        new_data = {**current, thing_name: updated}
        _LOGGER.debug("Shadow update for %s: %s", thing_name, payload)
        self.async_set_updated_data(new_data)

    async def async_shutdown(self) -> None:
        """Disconnect MQTT and tear down the coordinator."""
        await self.hass.async_add_executor_job(self._stop_mqtt)
        await super().async_shutdown()

    def _stop_mqtt(self) -> None:
        """Stop the MQTT loop (runs in executor)."""
        self.mqtt_client.disconnect()

    @staticmethod
    def _thing_name_from_topic(topic: str) -> str | None:
        """Extract thing_name from an AWS IoT shadow topic ($aws/things/{name}/shadow/...)."""
        parts = topic.split("/")
        if len(parts) >= 3 and parts[0] == "$aws" and parts[1] == "things":
            return parts[2]
        return None
