"""The lookin integration sensor platform."""
from __future__ import annotations

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTemperature
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
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="humidity",
        name="Humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up lookin sensors from the config entry."""
    lookin_data: LookinData = hass.data[DOMAIN][config_entry.entry_id]

    if lookin_data.lookin_device.model >= 2:
        async_add_entities(
            [
                LookinSensorEntity(description, lookin_data)
                for description in SENSOR_TYPES
            ]
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
