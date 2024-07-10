"""Telegram client entity class."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.core import callback
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TelegramClientCoordinator


class TelegramClientEntity(Entity):
    """Telegram client entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: TelegramClientCoordinator,
        entity_description: EntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__()
        self.entity_description = entity_description
        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = (
            f"{DOMAIN}_{coordinator.unique_id}_{entity_description.key}"
        )


class TelegramClientCoordinatorEntity(CoordinatorEntity):
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


class TelegramClientBinarySensor(TelegramClientCoordinatorEntity, BinarySensorEntity):
    """Telegram client binary_sensor entity class."""

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_is_on = self.coordinator.data.get(self.entity_description.key)
        self.async_write_ha_state()


class TelegramClientSensor(TelegramClientEntity, SensorEntity):
    """Telegram client sensor entity class."""

    def set_state(self, state):
        """Update the sensor's state."""
        self._attr_native_value = state
        self.async_write_ha_state()


class TelegramClientCoordinatorSensor(
    TelegramClientCoordinatorEntity, TelegramClientSensor
):
    """Telegram client sensor entity class."""

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_native_value = self.coordinator.data.get(self.entity_description.key)
        self.async_write_ha_state()
