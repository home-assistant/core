"""Support for Aseko Pool Live sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from aioaseko import Unit

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfElectricPotential, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import AsekoConfigEntry
from .entity import AsekoEntity


@dataclass(frozen=True, kw_only=True)
class AsekoSensorEntityDescription(SensorEntityDescription):
    """Describes an Aseko sensor entity."""

    value_fn: Callable[[Unit], StateType]


SENSORS: list[AsekoSensorEntityDescription] = [
    AsekoSensorEntityDescription(
        key="airTemp",
        translation_key="air_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda unit: unit.air_temperature,
    ),
    AsekoSensorEntityDescription(
        key="electrolyzer",
        translation_key="electrolyzer",
        native_unit_of_measurement="g/h",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda unit: unit.electrolyzer,
    ),
    AsekoSensorEntityDescription(
        key="free_chlorine",
        translation_key="free_chlorine",
        native_unit_of_measurement="mg/l",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda unit: unit.cl_free,
    ),
    AsekoSensorEntityDescription(
        key="ph",
        device_class=SensorDeviceClass.PH,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda unit: unit.ph,
    ),
    AsekoSensorEntityDescription(
        key="rx",
        translation_key="redox",
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda unit: unit.redox,
    ),
    AsekoSensorEntityDescription(
        key="salinity",
        translation_key="salinity",
        native_unit_of_measurement="kg/m³",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda unit: unit.salinity,
    ),
    AsekoSensorEntityDescription(
        key="waterTemp",
        translation_key="water_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda unit: unit.water_temperature,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: AsekoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Aseko Pool Live sensors."""
    coordinator = config_entry.runtime_data
    units = coordinator.data.values()
    async_add_entities(
        AsekoSensorEntity(unit, coordinator, description)
        for description in SENSORS
        for unit in units
        if description.value_fn(unit) is not None
    )


class AsekoSensorEntity(AsekoEntity, SensorEntity):
    """Representation of an Aseko unit sensor entity."""

    entity_description: AsekoSensorEntityDescription

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.unit)
