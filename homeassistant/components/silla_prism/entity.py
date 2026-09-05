"""Contains sensors exposed by the Prism integration."""

from datetime import datetime
import logging
from typing import Any

from homeassistant.components import mqtt
from homeassistant.core import CALLBACK_TYPE, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.event import async_call_later

from .entry_data import RuntimeEntryData

_LOGGER = logging.getLogger(__name__)


def _get_unique_id(serial: str, key: str) -> str:
    """Get a unique entity id."""
    return "prism_" + key + "_001" if serial == "" else f"prism_{serial}_{key}"


class PrismBaseEntityDescription(EntityDescription, frozen_or_thawed=True):
    """A class that describes base prism entities."""

    expire_after: float = 600
    topic: str | None = None


class PrismBaseEntity(Entity):
    """A base Entity that is registered under a Prism device."""

    _expire_after: float | None
    _expiration_trigger: CALLBACK_TYPE | None = None
    _attr_should_poll = False

    def __init__(
        self,
        entry_data: RuntimeEntryData,
        sensor_domain: str,
        description: Any,
        device: DeviceInfo,
    ) -> None:
        """Initialize the device info and set the update coordinator."""
        # Create device instance
        self._attr_device_info = device
        self.entity_description = description
        # Preload attributes
        self._attr_unique_id = _get_unique_id(entry_data.serial, description.key)
        self._topic = entry_data.topic + description.topic
        self._expire_after = description.expire_after
        # Init expire proceudre
        if self._expire_after is not None and self._expire_after > 0:
            self._attr_available = False

    @callback
    def value_is_expired(self, *_: datetime) -> None:
        """Triggered when value is expired."""
        _LOGGER.debug("entity value_is_expired for topic %s", self._topic)
        self._expiration_trigger = None
        self._value_is_expired()
        self.async_write_ha_state()

    async def _subscribe_topic(self):
        """Subscribe to mqtt topic."""
        _LOGGER.debug("_subscribe_topic: %s", self._topic)
        await mqtt.async_subscribe(self.hass, self._topic, self.message_received)

    def _value_is_expired(self):
        """Triggered when value is expired. To be overridden."""
        self._attr_available = False

    def _message_received(self, msg) -> None:
        """Change the selected option."""
        raise NotImplementedError

    def message_received(self, msg) -> None:
        """Update the sensor with the most recent event."""
        self.hass.loop.call_soon_threadsafe(self._message_received, msg)

    def schedule_expiration_callback(self) -> None:
        """When self._expire_after is set, and we receive a message, assume device is not expired since it has to be to receive the message."""
        if self._expire_after is not None and self._expire_after > 0:
            self._attr_available = True
            if self._expiration_trigger:
                # Reset old trigger
                self._expiration_trigger()
            else:
                # Set new trigger
                self._expiration_trigger = async_call_later(
                    self.hass, self._expire_after, self.value_is_expired
                )

    def cleanup_expiration_trigger(self) -> None:
        """Clean up expiration triggers."""
        if self._expiration_trigger:
            self._expiration_trigger()
            self._expiration_trigger = None
            self._attr_available = True
