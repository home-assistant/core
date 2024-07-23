"""Platform for sensor integration."""

from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import SqueezeboxConfigEntry
from .const import STATUS_SENSOR_NEEDSRESTART, STATUS_SENSOR_RESCAN
from .coordinator import LMSStatusDataUpdateCoordinator

SENSORS: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key=STATUS_SENSOR_RESCAN,
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
    BinarySensorEntityDescription(
        key=STATUS_SENSOR_NEEDSRESTART,
        device_class=BinarySensorDeviceClass.UPDATE,
    ),
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SqueezeboxConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Platform setup using common elements."""

    async_add_entities(
        ServerStatusBinarySensor(
            entry.runtime_data.device, entry.runtime_data.coordinator, description
        )
        for description in SENSORS
    )


class ServerStatusBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """LMS Status based sensor from LMS via cooridnatior."""

    _attr_has_entity_name = True

    def __init__(
        self,
        device: DeviceInfo,
        coordinator: LMSStatusDataUpdateCoordinator,
        description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, context=description.key)
        self.coordinator = coordinator
        self.entity_description = description
        self._attr_device_info = device
        self._attr_name = description.key
        self._attr_is_on = coordinator.data[description.key]
        self._attr_unique_id = device["serial_number"]
        self._attr_unique_id += description.key

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_is_on = self.coordinator.data[self.entity_description.key]
        self.async_write_ha_state()
        _LOGGER.debug("Update %s=%s", self.entity_description.key, self._attr_is_on)
