"""Qbus coordinator."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from qbusmqttapi.discovery import QbusDiscovery, QbusMqttDevice
from qbusmqttapi.factory import QbusMqttMessageFactory, QbusMqttTopicFactory

from homeassistant.components.mqtt import ReceiveMessage, client as mqtt
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later

from .const import CONF_SERIAL
from .entity import QbusEntity
from .qbus import QbusConfigContainer

_LOGGER = logging.getLogger(__name__)


@dataclass
class QbusRuntimeData:
    """Runtime data for Qbus integration."""

    coordinator: QbusDataCoordinator


type QbusConfigEntry = ConfigEntry[QbusRuntimeData]


class QbusDataCoordinator:
    """Qbus data coordinator."""

    _WAIT_TIME = 3

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize Qbus coordinator."""
        _LOGGER.debug("Initializing coordinator %s", entry.entry_id)

        self._message_factory = QbusMqttMessageFactory()
        self._topic_factory = QbusMqttTopicFactory()

        self._hass = hass
        self._entry = entry

        self._platform_register: dict[
            str, tuple[type[QbusEntity], AddEntitiesCallback]
        ] = {}
        self._registered_entity_ids: list[str] = []
        self._device_activated = False
        self._subscribed_to_device_state = False
        self._device: QbusMqttDevice | None

        # Clean up when HA stops
        entry.async_on_unload(
            hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self.shutdown)
        )

        # Subscribe to option updates
        entry.async_on_unload(entry.add_update_listener(self._options_update_listener))

    def shutdown(self, event: Event | None = None) -> None:
        """Shutdown Qbus coordinator."""
        _LOGGER.debug("Shutting down coordinator for entry %s", self._entry.entry_id)

        self._registered_entity_ids = []
        self._device_activated = False
        self._subscribed_to_device_state = False

    def remove(self) -> None:
        """Remove Qbus coordinator."""
        _LOGGER.debug("Removing coordinator")

        self.shutdown()

    def register_platform(
        self,
        qbus_type: str,
        entity_class: type[QbusEntity],
        add_entities: AddEntitiesCallback,
    ) -> None:
        """Register the platform so adding entities can be postponed to when the Qbus config is received."""
        _LOGGER.debug("Registering %s", qbus_type)
        self._platform_register[qbus_type.lower()] = (entity_class, add_entities)

    async def config_received(self, msg: ReceiveMessage) -> None:
        """Handle the received MQTT message containing the Qbus config."""
        _LOGGER.debug("Receiving config in entry %s", self._entry.entry_id)

        config = self._message_factory.parse_discovery(msg.payload)

        if config is not None:
            QbusConfigContainer.store_config(self._hass, config)
            await self.async_update_config(config)

    async def async_update_config(self, config: QbusDiscovery) -> None:
        """Process the new config."""
        serial = self._entry.data.get(CONF_SERIAL, "")
        device = config.get_device_by_serial(serial)

        if device is None:
            _LOGGER.warning("Device with serial %s not found", serial)
            return

        self._device = device
        device_state_topic = self._topic_factory.get_device_state_topic(self._device.id)

        if self._subscribed_to_device_state is False:
            _LOGGER.debug("Subscribing to %s", device_state_topic)
            self._subscribed_to_device_state = True
            self._entry.async_on_unload(
                await mqtt.async_subscribe(
                    self._hass,
                    device_state_topic,
                    self._device_state_received,
                )
            )

        self._add_entities(self._device)
        self._request_device_state(self._device)

    async def _device_state_received(self, msg: ReceiveMessage) -> None:
        _LOGGER.debug("Receiving device state %s", msg.topic)

        if self._device_activated:
            return

        state = self._message_factory.parse_device_state(msg.payload)

        if (
            state
            and state.properties
            and state.properties.connectable is False
            and self._device is not None
        ):
            _LOGGER.debug("Activating device %s", state.id)
            self._device_activated = True
            request = self._message_factory.create_device_activate_request(self._device)
            await mqtt.async_publish(self._hass, request.topic, request.payload)

    def _add_entities(self, device: QbusMqttDevice) -> None:
        """Create the Qbus entities in Home Assistant."""

        _LOGGER.debug(
            "Adding entities for %s registered IDs", len(self._registered_entity_ids)
        )
        items: dict[str, list[QbusEntity]] = {}

        if device.id not in self._registered_entity_ids:
            self._registered_entity_ids.append(device.id)

        # Build list of HA entities based on Qbus configuration
        for output in device.outputs:
            if output.id in self._registered_entity_ids:
                continue

            qbusType = output.type.lower()

            if qbusType not in self._platform_register:
                continue

            self._registered_entity_ids.append(output.id)

            entity_class = self._platform_register[qbusType][0]
            entity = entity_class.create(output)
            items.setdefault(qbusType, []).append(entity)

        # Add entities to HA
        _LOGGER.debug("Adding %s entities to HA", len(items))
        for qbusType, entities in items.items():
            add_entities = self._platform_register[qbusType][1]
            add_entities(entities)

        self._request_entity_states()

    def _request_entity_states(self) -> None:
        async def request_state(_) -> None:
            request = self._message_factory.create_state_request(
                self._registered_entity_ids
            )

            await mqtt.async_publish(self._hass, request.topic, request.payload)

        if len(self._registered_entity_ids) > 0:
            async_call_later(self._hass, self._WAIT_TIME, request_state)

    def _request_device_state(self, device: QbusMqttDevice) -> None:
        async def request_device_state(_) -> None:
            request = self._message_factory.create_device_state_request(device)
            await mqtt.async_publish(self._hass, request.topic, request.payload)

        async_call_later(self._hass, self._WAIT_TIME, request_device_state)

    async def _options_update_listener(
        self, hass: HomeAssistant, entry: ConfigEntry
    ) -> None:
        """Handle options update."""
        _LOGGER.debug("Update options %s", entry.entry_id)

        await hass.config_entries.async_reload(entry.entry_id)
