"""Support for Senziio devices."""

from collections.abc import Callable
import logging

from senziio import Senziio, SenziioMQTT

from homeassistant.components.mqtt import async_publish, async_subscribe
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .exceptions import MQTTNotEnabled

_LOGGER = logging.getLogger(__name__)


class SenziioDevice(Senziio):
    """Senziio device interaction."""

    def __init__(self, device_id: str, device_model: str, hass: HomeAssistant) -> None:
        """Initialize Senziio instance."""
        super().__init__(device_id, device_model, mqtt=SenziioHAMQTT(hass))


class SenziioHAMQTT(SenziioMQTT):
    """Senziio MQTT interface using available integration."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize MQTT interface for Senziio devices."""
        self._hass = hass

    async def publish(self, topic: str, payload: str) -> None:
        """Publish to topic with a payload."""
        try:
            return await async_publish(self._hass, topic, payload)
        except HomeAssistantError as error:
            _LOGGER.error("Could not publish to MQTT topic")
            raise MQTTNotEnabled from error

    async def subscribe(self, topic: str, callback: Callable) -> Callable:
        """Subscribe to topic with a callback."""
        try:
            return await async_subscribe(self._hass, topic, callback)
        except HomeAssistantError as error:
            _LOGGER.error("Could not subscribe to MQTT topic")
            raise MQTTNotEnabled from error
