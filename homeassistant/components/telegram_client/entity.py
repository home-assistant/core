"""Telegram client entity class."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntityDescription
from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .device import TelegramClientDevice


class TelegramClientEntity(Entity):
    """Telegram client entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        device: TelegramClientDevice,
        entity_description: BinarySensorEntityDescription | SensorEntityDescription,
    ) -> None:
        """Initialize the entity."""
        self._device = device
        self.entity_description = entity_description
        self._attr_device_info = device.device_info
        self._attr_unique_id = (
            f"{DOMAIN}_{device.entry.unique_id}_{entity_description.key}"
        )
