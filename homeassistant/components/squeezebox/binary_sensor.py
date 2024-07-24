"""Platform for sensor integration."""

from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SqueezeboxConfigEntry
from .const import STATUS_SENSOR_NEEDSRESTART, STATUS_SENSOR_RESCAN
from .coordinator import LMSStatusDataUpdateCoordinator
from .entity import LMSStatusEntity

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
        ServerStatusBinarySensor(entry.runtime_data.coordinator, description)
        for description in SENSORS
    )


class ServerStatusBinarySensor(LMSStatusEntity, BinarySensorEntity):
    """LMS Status based sensor from LMS via cooridnatior."""

    def __init__(
        self,
        coordinator: LMSStatusDataUpdateCoordinator,
        description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, description)
        # needs to be set as auto update is off
        self._attr_is_on = coordinator.data[description.key]

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_is_on = self.coordinator.data[self.entity_description.key]
        self.async_write_ha_state()
        _LOGGER.debug("Update %s=%s", self.entity_description.key, self._attr_is_on)
