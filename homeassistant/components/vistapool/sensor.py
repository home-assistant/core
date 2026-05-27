"""Vistapool Sensor entities."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import VistapoolConfigEntry
from .const import (
    PATH_HASCD,
    PATH_HASCL,
    PATH_HASHIDRO,
    PATH_HASPH,
    PATH_HASRX,
    PATH_HASUV,
)
from .coordinator import VistapoolDataUpdateCoordinator
from .entity import VistapoolEntity

PARALLEL_UPDATES = 1


def _convert_hundredths(value: Any) -> float:
    return float(value) / 100


def _convert_tenths(value: Any) -> float:
    return float(value) / 10


@dataclass(frozen=True, kw_only=True)
class VistapoolSensorEntityDescription(SensorEntityDescription):
    """Describes a Vistapool sensor entity."""

    value_path: str
    value_fn: Callable[[Any], float | int] = float
    exists_path: str | None = None


SENSOR_DESCRIPTIONS: tuple[VistapoolSensorEntityDescription, ...] = (
    VistapoolSensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_path="main.temperature",
    ),
    VistapoolSensorEntityDescription(
        key="conductivity",
        translation_key="conductivity",
        state_class=SensorStateClass.MEASUREMENT,
        value_path="modules.cd.current",
        value_fn=_convert_hundredths,
        exists_path=PATH_HASCD,
    ),
    VistapoolSensorEntityDescription(
        key="chlorine",
        translation_key="chlorine",
        state_class=SensorStateClass.MEASUREMENT,
        value_path="modules.cl.current",
        value_fn=_convert_hundredths,
        exists_path=PATH_HASCL,
    ),
    VistapoolSensorEntityDescription(
        key="ph",
        device_class=SensorDeviceClass.PH,
        state_class=SensorStateClass.MEASUREMENT,
        value_path="modules.ph.current",
        value_fn=_convert_hundredths,
        exists_path=PATH_HASPH,
    ),
    VistapoolSensorEntityDescription(
        key="redox_potential",
        translation_key="redox_potential",
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        state_class=SensorStateClass.MEASUREMENT,
        value_path="modules.rx.current",
        value_fn=int,
        exists_path=PATH_HASRX,
    ),
    VistapoolSensorEntityDescription(
        key="uv",
        translation_key="uv",
        state_class=SensorStateClass.MEASUREMENT,
        value_path="modules.uv.current",
        value_fn=_convert_hundredths,
        exists_path=PATH_HASUV,
    ),
    VistapoolSensorEntityDescription(
        key="filtration_intel_time",
        translation_key="filtration_intel_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.MEASUREMENT,
        value_path="filtration.intel.time",
        value_fn=int,
    ),
    VistapoolSensorEntityDescription(
        key="rssi",
        translation_key="rssi",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_path="main.RSSI",
        value_fn=int,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VistapoolConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Vistapool sensors for every pool on the account."""
    entities: list[VistapoolSensorEntity] = []

    for coordinator in entry.runtime_data.coordinators.values():
        for description in SENSOR_DESCRIPTIONS:
            if description.exists_path is not None and not coordinator.get_value(
                description.exists_path
            ):
                continue
            entities.append(VistapoolSensorEntity(coordinator, description))

        # Electrolysis/hydrolysis: dynamic key based on hardware type
        if coordinator.get_value(PATH_HASHIDRO):
            is_electrolysis = coordinator.get_value("hidro.is_electrolysis")
            entities.append(
                VistapoolSensorEntity(
                    coordinator,
                    VistapoolSensorEntityDescription(
                        key="electrolysis" if is_electrolysis else "hydrolysis",
                        translation_key=(
                            "electrolysis" if is_electrolysis else "hydrolysis"
                        ),
                        native_unit_of_measurement="g/h",
                        state_class=SensorStateClass.MEASUREMENT,
                        value_path="hidro.current",
                        value_fn=_convert_tenths,
                    ),
                )
            )

    async_add_entities(entities)


class VistapoolSensorEntity(VistapoolEntity, SensorEntity):
    """Generic Vistapool sensor driven by an entity description."""

    entity_description: VistapoolSensorEntityDescription

    def __init__(
        self,
        coordinator: VistapoolDataUpdateCoordinator,
        description: VistapoolSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = self.build_unique_id(description.key)

    @property
    def native_value(self) -> float | int | None:
        """Return the sensor value, transformed by the description's value_fn."""
        value = self.coordinator.get_value(self.entity_description.value_path)
        if value is None:
            return None
        return self.entity_description.value_fn(value)
