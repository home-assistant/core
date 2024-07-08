"""Telegram client entity class."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntityDescription
from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TelegramClientCoordinator


class TelegramClientEntity(CoordinatorEntity):
    """Telegram client entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: TelegramClientCoordinator,
        entity_description: EntityDescription
        | BinarySensorEntityDescription
        | SensorEntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = (
            f"{DOMAIN}_{coordinator.unique_id}_{entity_description.key}"
        )
