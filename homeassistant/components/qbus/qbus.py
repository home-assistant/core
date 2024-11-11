"""Qbus classes."""

import asyncio
import logging
import queue
import threading
from typing import Final

from qbusmqttapi.discovery import QbusDiscovery
from qbusmqttapi.factory import QbusMqttMessageFactory, QbusMqttTopicFactory

from homeassistant.components.mqtt import async_wait_for_mqtt_client, client as mqtt
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_SERIAL, DATA_QBUS_CONFIG, DATA_QBUS_CONFIG_EVENT, DOMAIN

_LOGGER = logging.getLogger(__name__)


class QbusConfigContainer:
    """Helper to handle the Qbus config."""

    _WAIT_TIMEOUT: Final[int] = 30
    _topic_factory = QbusMqttTopicFactory()

    @staticmethod
    async def async_get_or_request_config(hass: HomeAssistant) -> QbusDiscovery | None:
        """Get or request Qbus config."""
        hass.data.setdefault(DOMAIN, {})
        domain_data: dict = hass.data[DOMAIN]
        config: QbusDiscovery | None = domain_data.get(DATA_QBUS_CONFIG)

        # Data already available
        if config:
            _LOGGER.debug("Config already available")
            return config

        # Setup event
        _LOGGER.debug("Config missing")
        event: asyncio.Event | None = domain_data.get(DATA_QBUS_CONFIG_EVENT)

        if event is None:
            # Create event
            _LOGGER.debug("Creating config event")
            event = asyncio.Event()
            domain_data[DATA_QBUS_CONFIG_EVENT] = event

        if not await async_wait_for_mqtt_client(hass):
            _LOGGER.debug("MQTT client not ready yet")
            return None

        # Request data
        _LOGGER.debug("Requesting config")
        await mqtt.async_publish(
            hass, QbusConfigContainer._topic_factory.get_get_config_topic(), b""
        )

        # Wait
        try:
            await asyncio.wait_for(event.wait(), QbusConfigContainer._WAIT_TIMEOUT)
        except TimeoutError:
            _LOGGER.debug("Timeout while waiting for config")
            return None

        return domain_data.get(DATA_QBUS_CONFIG)

    @staticmethod
    def store_config(hass: HomeAssistant, config: QbusDiscovery) -> None:
        "Store the Qbus config."
        _LOGGER.debug("Storing config")

        hass.data.setdefault(DOMAIN, {})
        domain_data: dict = hass.data[DOMAIN]
        domain_data[DATA_QBUS_CONFIG] = config

        event: asyncio.Event | None = domain_data.get(DATA_QBUS_CONFIG_EVENT)

        if isinstance(event, asyncio.Event) and not event.is_set():
            _LOGGER.debug("Mark config event as finished")
            event.set()


class QbusStateQueue:
    """Qbus queue."""

    _WAIT_TIME: Final[int] = 2

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize Qbus queue."""

        self._hass = hass
        self._items: queue.SimpleQueue[str] = queue.SimpleQueue()

        self._kill: threading.Event | None = None
        self._throttle: threading.Thread | None = None
        self._started = False

        self._message_factory = QbusMqttMessageFactory()

    def start(self) -> None:
        """Start Qbus queue."""

        if self._started:
            return

        self._kill = threading.Event()

        self._throttle = threading.Thread(target=self._process_queue)
        self._throttle.start()
        self._started = True
        _LOGGER.debug("Queue %s started", self._throttle.native_id)

    def close(self) -> None:
        """Close Qbus queue."""
        if self._throttle:
            _LOGGER.debug("Killing queue %s", self._throttle.native_id)
            if self._kill:
                self._kill.set()
                self._started = False

    def add(self, qbus_id: str) -> None:
        """Add a Qbus id to the queue."""
        self._items.put(qbus_id)

    def _process_queue(self) -> None:
        if self._kill:
            self._kill.wait(self._WAIT_TIME)

        while True:
            size = self._items.qsize()
            entity_ids = []

            try:
                for _ in range(size):
                    item = self._items.get()

                    if item not in entity_ids:
                        entity_ids.append(item)
            except queue.Empty:
                pass

            # Publish to MQTT
            if len(entity_ids) > 0:
                _LOGGER.debug("Requesting state for %s", entity_ids)
                request = self._message_factory.create_state_request(entity_ids)
                mqtt.publish(self._hass, request.topic, request.payload)

            # If no kill signal is set, sleep for the interval.
            # If kill signal comes in while sleeping, immediately wake up and handle.
            if self._kill:
                is_killed = self._kill.wait(self._WAIT_TIME)

            if is_killed:
                break


class QbusEntry:
    """Qbus Config Entry wrapper."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the Qbus Config Entry wrapper."""
        self._hass = hass
        self._config_entry = entry
        self._state_queue = QbusStateQueue(hass)

    @property
    def config_entry(self) -> ConfigEntry:
        """Return the Config Entry."""
        return self._config_entry

    @property
    def state_queue(self) -> QbusStateQueue:
        """Return the Qbus State Queue."""
        return self._state_queue

    @property
    def serial(self) -> str:
        """Return the controller serial."""
        return self._config_entry.data.get(CONF_SERIAL, "")
