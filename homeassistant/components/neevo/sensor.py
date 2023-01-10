"""Support for Nee-Vo Tank Monitors."""
from __future__ import annotations

from contextlib import suppress
import logging

from pyneevo.tank import Tank

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfPressure
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import NeeVoEntity
from .const import DOMAIN, TANKS

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="level",
        name="Tank Level",
        icon="mdi:propane-tank",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="tank_last_pressure",
        name="Tank Last Pressure",
        icon="mdi:gauge",
        native_unit_of_measurement=UnitOfPressure.KPA,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Nee-Vo sensor based on a config entry."""

    tanks = hass.data[DOMAIN][TANKS][entry.entry_id]
    all_tanks = tanks.copy()

    sensors = [
        NeeVoSensor(_equip, description)
        for _equip in all_tanks.values()
        for description in SENSOR_TYPES
        if getattr(_equip, description.key, False) is not False
    ]

    async_add_entities(sensors)


class NeeVoSensor(NeeVoEntity, SensorEntity):
    """Define a Nee-Vo sensor."""

    def __init__(self, neevo_tank: Tank, description: SensorEntityDescription) -> None:
        """Initialize."""
        super().__init__(neevo_tank)
        self.entity_description = description
        self._attr_has_entity_name = True
        self._attr_name = f"{description.name}"
        self._attr_unique_id = f"{neevo_tank.id}_{neevo_tank.name}_{description.key}"

    @property
    def native_value(self) -> float:
        """Return sensors state."""
        value = getattr(self._neevo, self.entity_description.key)
        if isinstance(value, float):
            value = round(value, 2)

        return value

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        if self.entity_description.key == "tank_last_pressure":
            if self._neevo.tank_last_pressure_unit is not None:
                with suppress(TypeError):
                    return UnitOfPressure(self._neevo.tank_last_pressure_unit)
        return super().native_unit_of_measurement
