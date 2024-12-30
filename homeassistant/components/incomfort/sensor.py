"""Support for an Intergas heater via an InComfort/InTouch Lan2RF gateway."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from incomfortclient import Heater as InComfortHeater

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfPressure, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import InComfortConfigEntry
from .coordinator import InComfortDataCoordinator
from .entity import IncomfortBoilerEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class IncomfortSensorEntityDescription(SensorEntityDescription):
    """Describes Incomfort sensor entity."""

    value_key: str
    extra_key: str | None = None


SENSOR_TYPES: tuple[IncomfortSensorEntityDescription, ...] = (
    IncomfortSensorEntityDescription(
        key="cv_pressure",
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPressure.BAR,
        value_key="pressure",
    ),
    IncomfortSensorEntityDescription(
        key="cv_temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        extra_key="is_pumping",
        value_key="heater_temp",
    ),
    IncomfortSensorEntityDescription(
        key="tap_temp",
        translation_key="tap_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        extra_key="is_tapping",
        value_key="tap_temp",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: InComfortConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up InComfort/InTouch sensor entities."""
    incomfort_coordinator = entry.runtime_data
    heaters = incomfort_coordinator.data.heaters
    async_add_entities(
        IncomfortSensor(incomfort_coordinator, heater, description)
        for heater in heaters
        for description in SENSOR_TYPES
    )


class IncomfortSensor(IncomfortBoilerEntity, SensorEntity):
    """Representation of an InComfort/InTouch sensor device."""

    entity_description: IncomfortSensorEntityDescription

    def __init__(
        self,
        coordinator: InComfortDataCoordinator,
        heater: InComfortHeater,
        description: IncomfortSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, heater)
        self.entity_description = description
        self._attr_unique_id = f"{heater.serial_no}_{description.key}"

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self._heater.status[self.entity_description.value_key]

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the device state attributes."""
        if (extra_key := self.entity_description.extra_key) is None:
            return None
        return {extra_key: self._heater.status[extra_key]}
