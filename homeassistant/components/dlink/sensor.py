"""Support for D-Link Power Plug Sensors."""

from __future__ import annotations

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy, UnitOfPower, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import UndefinedType

from .entity import DLinkEntity

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="temperature",
        name="Switch Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="total_consumption",
        name="Total Consumption",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="current_consumption",
        name="Current Consumption",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the D-Link Power Plug sensors."""
    entities = [SmartPlugSensor(entry, sensor) for sensor in SENSOR_TYPES]
    async_add_entities(entities, True)


class SmartPlugSensor(DLinkEntity, SensorEntity):
    """Representation of a D-Link Smart Plug sensor."""

    @property
    def name(self) -> str | UndefinedType | None:
        """Return the name of the sensor."""
        return self.entity_description.name

    @property
    def native_value(self) -> float | None:
        """Return the sensors state."""
        try:
            state = float(getattr(self.data, self.entity_description.key))
        except ValueError:
            return None
        return state

    def update(self) -> None:
        """Get the latest data from the smart plug and updates the states."""
        self.data.update()
