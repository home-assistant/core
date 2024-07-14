"""Telegram client entities."""

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
        """Handle Telegram client entity initialization."""
        super().__init__()
        self.entity_description = entity_description
        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = (
            f"{DOMAIN}_{coordinator.unique_id}_{entity_description.key}"
        )


class TelegramClientCoordinatorEntity(CoordinatorEntity):
    """Telegram client coordinator entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: TelegramClientCoordinator,
        entity_description: EntityDescription
        | BinarySensorEntityDescription
        | SensorEntityDescription,
    ) -> None:
        """Handle Telegram client coordinator entity initialization."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = (
            f"{DOMAIN}_{coordinator.unique_id}_{entity_description.key}"
        )


class TelegramClientCoordinatorBinarySensor(
    TelegramClientCoordinatorEntity, BinarySensorEntity
):
    """Telegram client coordinator binary sensor entity."""

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle state update from coordinator."""
        self._attr_is_on = self.coordinator.data.get(self.entity_description.key)
        self.async_write_ha_state()


class TelegramClientSensor(TelegramClientEntity, SensorEntity):
    """Telegram client sensor entity."""

    def set_state(self, state):
        """Handle sensor's state update."""
        self._attr_native_value = state
        self.async_write_ha_state()


class TelegramClientCoordinatorSensor(
    TelegramClientCoordinatorEntity, TelegramClientSensor
):
    """Telegram client coordinator sensor entity."""

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle state update from coordinator."""
        self._attr_native_value = self.coordinator.data.get(self.entity_description.key)
        self.async_write_ha_state()
