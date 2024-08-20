"""Qbus queue."""

import json
import logging
import queue
import threading

from homeassistant.components import mqtt
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class QbusStateQueue:
    """Qbus queue."""

    _WAIT_TIME = 2

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize Qbus queue."""

        self._hass = hass
        self._items: queue.SimpleQueue[str] = queue.SimpleQueue()

        self._kill: threading.Event | None = None
        self._throttle: threading.Thread | None = None
        self._started = False

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
                mqtt.publish(
                    self._hass, "cloudapp/QBUSMQTTGW/getState", json.dumps(entity_ids)
                )

            # If no kill signal is set, sleep for the interval.
            # If kill signal comes in while sleeping, immediately wake up and handle.
            if self._kill:
                is_killed = self._kill.wait(self._WAIT_TIME)

            if is_killed:
                break
