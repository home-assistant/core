"""Telegram client entity class."""

from __future__ import annotations

from telethon import TelegramClient

from homeassistant.components.binary_sensor import BinarySensorEntityDescription
from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .device import TelegramClientDevice


class TelegramClientEntity(Entity):
    """Telegram client entity."""

    _attr_has_entity_name = True
    _device: TelegramClient = None
    _entity_description: BinarySensorEntityDescription | SensorEntityDescription

    def __init__(
        self,
        device: TelegramClientDevice,
        entity_description: BinarySensorEntityDescription | SensorEntityDescription,
    ) -> None:
        """Initialize the entity."""
        self._device = device
        self._entity_description = entity_description

    @property
    def device(self):
        """Device."""
        return self._device

    @property
    def name(self):
        """Entity name."""
        return self._entity_description.name

    @property
    def device_info(self):
        """Device information."""
        return self._device.device_info

    @property
    def unique_id(self):
        """Return a unique ID to use for this entity."""
        return f"{DOMAIN}_{self.device.entry.unique_id}_{self._entity_description.key}"
