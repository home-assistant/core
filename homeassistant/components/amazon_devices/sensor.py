"""Support for sensors."""

from __future__ import annotations

from typing import Final, cast

from aioamazondevices.api import AmazonDevice

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    StateType,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AmazonDevicesCoordinator

SENSORS: Final = (
    SensorEntityDescription(
        key="response_style",
        translation_key="response_style",
        name="Response style",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Comelit sensors."""

    coordinator: AmazonDevicesCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    entities: list[AmazonSensorEntity] = []
    for device in coordinator.data.values():
        entities.extend(
            AmazonSensorEntity(coordinator, device, sensor_desc)
            for sensor_desc in SENSORS
        )

    async_add_entities(entities)


class AmazonSensorEntity(CoordinatorEntity[AmazonDevicesCoordinator], SensorEntity):
    """Sensor device."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AmazonDevicesCoordinator,
        device: AmazonDevice,
        description: SensorEntityDescription,
    ) -> None:
        """Init sensor entity."""
        self._api = coordinator.api
        self._device = device

        super().__init__(coordinator)

        self._attr_unique_id = f"{device.serial_number}-{description.key}"
        self._attr_device_info = coordinator.device_info(device)

        self.entity_description = description

    @property
    def native_value(self) -> StateType:
        """Sensor value."""
        return cast(
            StateType,
            getattr(
                self.coordinator.data[self._device.serial_number],
                self.entity_description.key,
            ),
        )
