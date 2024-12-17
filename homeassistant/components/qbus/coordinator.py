"""Qbus coordinator."""

from __future__ import annotations

import asyncio
from datetime import datetime
import logging
from typing import Final, cast

from qbusmqttapi.discovery import QbusDiscovery, QbusMqttDevice
from qbusmqttapi.factory import QbusMqttMessageFactory, QbusMqttTopicFactory

from homeassistant.components.mqtt import (
    ReceiveMessage,
    async_wait_for_mqtt_client,
    client as mqtt,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later
from homeassistant.util.hass_dict import HassKey

from .const import CONF_SERIAL_NUMBER, DOMAIN, MANUFACTURER
from .entity import QbusEntity

_LOGGER = logging.getLogger(__name__)


type QbusConfigEntry = ConfigEntry[QbusControllerCoordinator]
QBUS_KEY: HassKey[QbusConfigCoordinator] = HassKey(DOMAIN)


class QbusControllerCoordinator:
    """Qbus data coordinator."""

    _WAIT_TIME = 3

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize Qbus coordinator."""
        _LOGGER.debug("%s - Initializing coordinator", entry.unique_id)

        self._hass = hass
        self._entry = entry

        self._message_factory = QbusMqttMessageFactory()
        self._topic_factory = QbusMqttTopicFactory()

        self._cleanup_callbacks: list[CALLBACK_TYPE] = []
        self._platform_register: dict[
            str, tuple[type[QbusEntity], AddEntitiesCallback]
        ] = {}
        self._registered_entity_ids: list[str] = []
        self._controller_activated = False
        self._subscribed_to_controller_state = False
        self._controller: QbusMqttDevice | None

        # Clean up when HA stops
        self._cleanup_callbacks.append(
            hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self.shutdown)
        )

    def shutdown(self, event: Event | None = None) -> None:
        """Shutdown Qbus coordinator."""
        _LOGGER.debug("%s - Shutting down coordinator for entry", self._entry.unique_id)

        while self._cleanup_callbacks:
            cleanup_callback = self._cleanup_callbacks.pop()
            cleanup_callback()

        self._cleanup_callbacks = []
        self._registered_entity_ids = []
        self._controller_activated = False
        self._subscribed_to_controller_state = False
        self._controller = None

    def register_platform(
        self,
        qbus_type: str,
        entity_class: type[QbusEntity],
        add_entities: AddEntitiesCallback,
    ) -> None:
        """Register the platform so adding entities can be postponed to when the Qbus config is received."""
        _LOGGER.debug("%s - Registering %s", self._entry.unique_id, qbus_type)
        self._platform_register[qbus_type.lower()] = (entity_class, add_entities)

    async def async_update_controller_config(self, config: QbusDiscovery) -> None:
        """Update the controller based on the config."""
        _LOGGER.debug("%s - Updating config", self._entry.unique_id)
        serial = self._entry.data.get(CONF_SERIAL_NUMBER, "")
        controller = config.get_device_by_serial(serial)

        if controller is None:
            _LOGGER.warning(
                "%s - Controller with serial %s not found",
                self._entry.unique_id,
                serial,
            )
            return

        self._controller = controller

        self._update_device_info(self._controller)
        await self._async_subscribe_to_controller_state(self._controller)
        self._add_entities(self._controller)
        self._request_controller_state(self._controller)

    def _update_device_info(self, controller: QbusMqttDevice) -> None:
        device_registry = dr.async_get(self._hass)
        device_registry.async_get_or_create(
            config_entry_id=self._entry.entry_id,
            identifiers={(DOMAIN, format_mac(controller.mac))},
            manufacturer=MANUFACTURER,
            model=f"{controller.type} {controller.name}",
            name=f"CTD {controller.serial_number}",
            serial_number=controller.serial_number,
            sw_version=controller.version,
        )

    async def _async_subscribe_to_controller_state(
        self, controller: QbusMqttDevice
    ) -> None:
        if self._subscribed_to_controller_state is True:
            return

        controller_state_topic = self._topic_factory.get_device_state_topic(
            controller.id
        )
        _LOGGER.debug(
            "%s - Subscribing to %s", self._entry.unique_id, controller_state_topic
        )
        self._subscribed_to_controller_state = True
        self._cleanup_callbacks.append(
            await mqtt.async_subscribe(
                self._hass,
                controller_state_topic,
                self._controller_state_received,
            )
        )

    async def _controller_state_received(self, msg: ReceiveMessage) -> None:
        _LOGGER.debug(
            "%s - Receiving controller state %s", self._entry.unique_id, msg.topic
        )

        if self._controller_activated:
            return

        state = self._message_factory.parse_device_state(msg.payload)

        if (
            state
            and state.properties
            and state.properties.connectable is False
            and self._controller is not None
        ):
            _LOGGER.debug(
                "%s - Activating controller %s", self._entry.unique_id, state.id
            )
            self._controller_activated = True
            request = self._message_factory.create_device_activate_request(
                self._controller
            )
            await mqtt.async_publish(self._hass, request.topic, request.payload)

    def _add_entities(self, controller: QbusMqttDevice) -> None:
        """Create the Qbus entities in Home Assistant."""

        _LOGGER.debug(
            "%s - Adding entities for %s registered IDs",
            self._entry.unique_id,
            len(self._registered_entity_ids),
        )
        items: dict[str, list[QbusEntity]] = {}

        if controller.id not in self._registered_entity_ids:
            self._registered_entity_ids.append(controller.id)

        # Build list of HA entities based on Qbus configuration
        for output in controller.outputs:
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
        _LOGGER.debug(
            "%s - Adding %s entities to HA", self._entry.unique_id, len(items)
        )
        for qbusType, entities in items.items():
            add_entities = self._platform_register[qbusType][1]
            add_entities(entities)

        self._request_entity_states()

    def _request_entity_states(self) -> None:
        async def request_state(_: datetime) -> None:
            request = self._message_factory.create_state_request(
                self._registered_entity_ids
            )

            await mqtt.async_publish(self._hass, request.topic, request.payload)

        if len(self._registered_entity_ids) > 0:
            async_call_later(self._hass, self._WAIT_TIME, request_state)

    def _request_controller_state(self, controller: QbusMqttDevice) -> None:
        async def request_controller_state(_: datetime) -> None:
            request = self._message_factory.create_device_state_request(controller)
            await mqtt.async_publish(self._hass, request.topic, request.payload)

        async_call_later(self._hass, self._WAIT_TIME, request_controller_state)


class QbusConfigCoordinator:
    """Class responsible for Qbus config updates."""

    _WAIT_TIMEOUT: Final[int] = 5

    _qbus_config: QbusDiscovery | None = None
    _request_config_event: asyncio.Event | None = None

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize config coordinator."""

        self._hass = hass
        self._message_factory = QbusMqttMessageFactory()
        self._topic_factory = QbusMqttTopicFactory()
        self._cleanup_callbacks: list[CALLBACK_TYPE] = []

        self._cleanup_callbacks.append(
            hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self.shutdown)
        )

    @classmethod
    def get_or_create(cls, hass: HomeAssistant) -> QbusConfigCoordinator:
        """Get the coordinator and create if necessary."""
        if (coordinator := hass.data.get(QBUS_KEY)) is None:
            coordinator = cls(hass)
            hass.data[QBUS_KEY] = coordinator

        return coordinator

    def shutdown(self, event: Event | None = None) -> None:
        """Shutdown Qbus config coordinator."""
        _LOGGER.debug("Shutting down Qbus config coordinator")
        while self._cleanup_callbacks:
            cleanup_callback = self._cleanup_callbacks.pop()
            cleanup_callback()

    async def async_subscribe_to_config(self) -> None:
        """Subscribe to config changes."""
        config_topic = self._topic_factory.get_config_topic()
        _LOGGER.debug("Subscribing to %s", config_topic)

        self._cleanup_callbacks.append(
            await mqtt.async_subscribe(self._hass, config_topic, self._config_received)
        )

    async def async_get_or_request_config(self) -> QbusDiscovery | None:
        """Get or request Qbus config."""
        _LOGGER.debug("Requesting Qbus config")

        # Config already available
        if self._qbus_config:
            _LOGGER.debug("Qbus config already available")
            return self._qbus_config

        # Setup event
        _LOGGER.debug("Qbus config missing")
        if self._request_config_event is None:
            # Create event
            _LOGGER.debug("Creating config event")
            self._request_config_event = asyncio.Event()

        if not await async_wait_for_mqtt_client(self._hass):
            _LOGGER.debug("MQTT client not ready yet")
            return None

        # Request config
        _LOGGER.debug("Publishing config request")
        await mqtt.async_publish(
            self._hass, self._topic_factory.get_get_config_topic(), b""
        )

        # Wait
        try:
            await asyncio.wait_for(
                self._request_config_event.wait(), self._WAIT_TIMEOUT
            )
        except TimeoutError:
            _LOGGER.debug("Timeout while waiting for config")
            return None

        return self._qbus_config

    def store_config(self, config: QbusDiscovery) -> None:
        "Store the Qbus config."
        _LOGGER.debug("Storing config")

        self._qbus_config = config

        if self._request_config_event and not self._request_config_event.is_set():
            _LOGGER.debug("Mark config event as finished")
            self._request_config_event.set()

    async def _config_received(self, msg: ReceiveMessage) -> None:
        """Handle the received MQTT message containing the Qbus config."""
        _LOGGER.debug("Receiving Qbus config")

        config = self._message_factory.parse_discovery(msg.payload)

        if config is None:
            _LOGGER.debug("Incomplete Qbus config")
            return

        self.store_config(config)

        for entry in self._hass.config_entries.async_loaded_entries(DOMAIN):
            entry = cast(QbusConfigEntry, entry)
            await entry.runtime_data.async_update_controller_config(config)
