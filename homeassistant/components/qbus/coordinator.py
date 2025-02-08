"""Qbus coordinator."""

from __future__ import annotations

from datetime import datetime
import logging
from typing import cast

from qbusmqttapi.discovery import QbusDiscovery, QbusMqttDevice, QbusMqttOutput
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
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util.hass_dict import HassKey

from .const import CONF_SERIAL_NUMBER, DOMAIN, MANUFACTURER

_LOGGER = logging.getLogger(__name__)


type QbusConfigEntry = ConfigEntry[QbusControllerCoordinator]
QBUS_KEY: HassKey[QbusConfigCoordinator] = HassKey(DOMAIN)


class QbusControllerCoordinator(DataUpdateCoordinator[list[QbusMqttOutput]]):
    """Qbus data coordinator."""

    _STATE_REQUEST_DELAY = 3

    def __init__(self, hass: HomeAssistant, entry: QbusConfigEntry) -> None:
        """Initialize Qbus coordinator."""

        _LOGGER.debug("%s - Initializing coordinator", entry.unique_id)
        self.config_entry: QbusConfigEntry

        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=entry.unique_id or entry.entry_id,
            always_update=False,
        )

        self._message_factory = QbusMqttMessageFactory()
        self._topic_factory = QbusMqttTopicFactory()

        self._controller_activated = False
        self._subscribed_to_controller_state = False
        self._controller: QbusMqttDevice | None = None

        # Clean up when HA stops
        self.config_entry.async_on_unload(
            hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self.shutdown)
        )

    async def _async_update_data(self) -> list[QbusMqttOutput]:
        return self._controller.outputs if self._controller else []

    def shutdown(self, event: Event | None = None) -> None:
        """Shutdown Qbus coordinator."""
        _LOGGER.debug(
            "%s - Shutting down entry coordinator", self.config_entry.unique_id
        )

        self._controller_activated = False
        self._subscribed_to_controller_state = False
        self._controller = None

    async def async_update_controller_config(self, config: QbusDiscovery) -> None:
        """Update the controller based on the config."""
        _LOGGER.debug("%s - Updating config", self.config_entry.unique_id)
        serial = self.config_entry.data.get(CONF_SERIAL_NUMBER, "")
        controller = config.get_device_by_serial(serial)

        if controller is None:
            _LOGGER.warning(
                "%s - Controller with serial %s not found",
                self.config_entry.unique_id,
                serial,
            )
            return

        self._controller = controller

        self._update_device_info()
        await self._async_subscribe_to_controller_state()
        await self.async_refresh()
        self._request_controller_state()
        self._request_entity_states()

    def _update_device_info(self) -> None:
        if self._controller is None:
            return

        device_registry = dr.async_get(self.hass)
        device_registry.async_get_or_create(
            config_entry_id=self.config_entry.entry_id,
            identifiers={(DOMAIN, format_mac(self._controller.mac))},
            manufacturer=MANUFACTURER,
            model="CTD3.x",
            name=f"CTD {self._controller.serial_number}",
            serial_number=self._controller.serial_number,
            sw_version=self._controller.version,
        )

    async def _async_subscribe_to_controller_state(self) -> None:
        if self._controller is None or self._subscribed_to_controller_state is True:
            return

        controller_state_topic = self._topic_factory.get_device_state_topic(
            self._controller.id
        )
        _LOGGER.debug(
            "%s - Subscribing to %s",
            self.config_entry.unique_id,
            controller_state_topic,
        )
        self._subscribed_to_controller_state = True
        self.config_entry.async_on_unload(
            await mqtt.async_subscribe(
                self.hass,
                controller_state_topic,
                self._controller_state_received,
            )
        )

    async def _controller_state_received(self, msg: ReceiveMessage) -> None:
        _LOGGER.debug(
            "%s - Receiving controller state %s", self.config_entry.unique_id, msg.topic
        )

        if self._controller is None or self._controller_activated:
            return

        state = self._message_factory.parse_device_state(msg.payload)

        if state and state.properties and state.properties.connectable is False:
            _LOGGER.debug(
                "%s - Activating controller %s", self.config_entry.unique_id, state.id
            )
            self._controller_activated = True
            request = self._message_factory.create_device_activate_request(
                self._controller
            )
            await mqtt.async_publish(self.hass, request.topic, request.payload)

    def _request_entity_states(self) -> None:
        async def request_state(_: datetime) -> None:
            if self._controller is None:
                return

            _LOGGER.debug(
                "%s - Requesting %s entity states",
                self.config_entry.unique_id,
                len(self._controller.outputs),
            )

            request = self._message_factory.create_state_request(
                [item.id for item in self._controller.outputs]
            )

            await mqtt.async_publish(self.hass, request.topic, request.payload)

        if self._controller and len(self._controller.outputs) > 0:
            async_call_later(self.hass, self._STATE_REQUEST_DELAY, request_state)

    def _request_controller_state(self) -> None:
        async def request_controller_state(_: datetime) -> None:
            if self._controller is None:
                return

            _LOGGER.debug(
                "%s - Requesting controller state", self.config_entry.unique_id
            )
            request = self._message_factory.create_device_state_request(
                self._controller
            )
            await mqtt.async_publish(self.hass, request.topic, request.payload)

        if self._controller:
            async_call_later(
                self.hass, self._STATE_REQUEST_DELAY, request_controller_state
            )


class QbusConfigCoordinator:
    """Class responsible for Qbus config updates."""

    _qbus_config: QbusDiscovery | None = None

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

        if not await async_wait_for_mqtt_client(self._hass):
            _LOGGER.debug("MQTT client not ready yet")
            return None

        # Request config
        _LOGGER.debug("Publishing config request")
        await mqtt.async_publish(
            self._hass, self._topic_factory.get_get_config_topic(), b""
        )

        return self._qbus_config

    def store_config(self, config: QbusDiscovery) -> None:
        "Store the Qbus config."
        _LOGGER.debug("Storing config")

        self._qbus_config = config

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
