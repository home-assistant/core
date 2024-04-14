"""Support for Nee-Vo Tank Monitors."""

from __future__ import annotations

from contextlib import suppress
import logging
from typing import Any

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
from .const import COORDINATOR, DOMAIN

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="level",
        name="Tank Level",
        icon="mdi:propane-tank",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    SensorEntityDescription(
        key="tank_last_pressure",
        name="Tank Last Pressure",
        icon="mdi:gauge",
        native_unit_of_measurement=UnitOfPressure.KPA,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Nee-Vo sensor based on a config entry."""

    instance = hass.data[DOMAIN][entry.entry_id]

    sensors = [
        NeeVoSensor(instance, tank_id, description)
        for tank_id, _equip in instance[COORDINATOR].data.items()
        for description in SENSOR_TYPES
        if getattr(_equip, description.key, False) is not False
    ]

    async_add_entities(sensors)


class NeeVoSensor(NeeVoEntity, SensorEntity):
    """Define a Nee-Vo sensor."""

    def __init__(
        self,
        instance: dict[str, Any],
        tank_id: str,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(instance, tank_id)
        self.entity_description = description
        self._attr_has_entity_name = True
        self._attr_name = f"{description.name}"
        self._attr_unique_id = f"{self._neevo.id}_{description.key}"
        self._attr_native_value = getattr(self._neevo, self.entity_description.key)

        if self.entity_description.key == "tank_last_pressure":
            if self._neevo.tank_last_pressure_unit is not None:
                with suppress(TypeError):
                    self._attr_native_unit_of_measurement = UnitOfPressure(
                        self._neevo.tank_last_pressure_unit
                    )
