"""The lookin integration sensor platform."""
from __future__ import annotations

import logging

from homeassistant.components.sensor import (
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_TEMPERATURE,
    STATE_CLASS_MEASUREMENT,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, TEMP_CELSIUS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import LookinDeviceCoordinatorEntity
from .models import LookinData

LOGGER = logging.getLogger(__name__)


SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="temperature",
        name="Temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=DEVICE_CLASS_TEMPERATURE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        key="humidity",
        name="Humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=DEVICE_CLASS_HUMIDITY,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up lookin sensors from the config entry."""
    lookin_data: LookinData = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        [LookinSensorEntity(description, lookin_data) for description in SENSOR_TYPES]
    )


class LookinSensorEntity(LookinDeviceCoordinatorEntity, SensorEntity):
    """A lookin device sensor entity."""

    def __init__(
        self, description: SensorEntityDescription, lookin_data: LookinData
    ) -> None:
        """Init the lookin sensor entity."""
        super().__init__(lookin_data)
        self.entity_description = description
        self._attr_name = f"{self._lookin_device.name} {description.name}"
        self._attr_native_value = getattr(self.coordinator.data, description.key)
        self._attr_unique_id = f"{self._lookin_device.id}-{description.key}"

    def _handle_coordinator_update(self) -> None:
        """Update the state of the entity."""
        self._attr_native_value = getattr(
            self.coordinator.data, self.entity_description.key
        )
        super()._handle_coordinator_update()
