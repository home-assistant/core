"""Aquarite Sensor entities."""

from __future__ import annotations

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

from . import AquariteConfigEntry
from .const import (
    PATH_HASCD,
    PATH_HASCL,
    PATH_HASHIDRO,
    PATH_HASPH,
    PATH_HASRX,
    PATH_HASUV,
)
from .coordinator import AquariteDataUpdateCoordinator
from .entity import AquariteEntity

PARALLEL_UPDATES = 1


def _convert_float(value: Any) -> float | None:
    return float(value)


def _convert_hundredths(value: Any) -> float | None:
    return float(value) / 100


def _convert_tenths(value: Any) -> float | None:
    return float(value) / 10


def _convert_minutes_to_hours(value: Any) -> float | None:
    return float(value) / 60


def _convert_int(value: Any) -> int | None:
    return int(value)


@dataclass(frozen=True, kw_only=True)
class AquariteSensorEntityDescription(SensorEntityDescription):
    """Describes an Aquarite sensor entity."""

    value_path: str
    value_fn: Callable[[Any], Any] = _convert_float
    exists_path: str | None = None


SENSOR_DESCRIPTIONS: tuple[AquariteSensorEntityDescription, ...] = (
    AquariteSensorEntityDescription(
        key="temperature",
        translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_path="main.temperature",
    ),
    AquariteSensorEntityDescription(
        key="cd",
        translation_key="cd",
        state_class=SensorStateClass.MEASUREMENT,
        value_path="modules.cd.current",
        value_fn=_convert_hundredths,
        exists_path=PATH_HASCD,
    ),
    AquariteSensorEntityDescription(
        key="cl",
        translation_key="cl",
        state_class=SensorStateClass.MEASUREMENT,
        value_path="modules.cl.current",
        value_fn=_convert_hundredths,
        exists_path=PATH_HASCL,
    ),
    AquariteSensorEntityDescription(
        key="ph",
        translation_key="ph",
        device_class=SensorDeviceClass.PH,
        state_class=SensorStateClass.MEASUREMENT,
        value_path="modules.ph.current",
        value_fn=_convert_hundredths,
        exists_path=PATH_HASPH,
    ),
    AquariteSensorEntityDescription(
        key="rx",
        translation_key="rx",
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        state_class=SensorStateClass.MEASUREMENT,
        value_path="modules.rx.current",
        value_fn=_convert_int,
        exists_path=PATH_HASRX,
    ),
    AquariteSensorEntityDescription(
        key="uv",
        translation_key="uv",
        state_class=SensorStateClass.MEASUREMENT,
        value_path="modules.uv.current",
        value_fn=_convert_hundredths,
        exists_path=PATH_HASUV,
    ),
    AquariteSensorEntityDescription(
        key="filtration_intel_time",
        translation_key="filtration_intel_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.MEASUREMENT,
        value_path="filtration.intel.time",
        value_fn=_convert_minutes_to_hours,
    ),
    AquariteSensorEntityDescription(
        key="rssi",
        translation_key="rssi",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_path="main.RSSI",
        value_fn=_convert_int,
    ),
    AquariteSensorEntityDescription(
        key="pool_name",
        translation_key="pool_name",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_path="",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AquariteConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Aquarite sensors for every pool on the account."""
    entities: list[AquariteSensorEntity] = []

    for coordinator in entry.runtime_data.coordinators.values():
        for description in SENSOR_DESCRIPTIONS:
            if description.exists_path is not None and not coordinator.get_value(
                description.exists_path
            ):
                continue
            entities.append(AquariteSensorEntity(coordinator, description))

        # Electrolysis/hydrolysis: dynamic key based on hardware type
        if coordinator.get_value(PATH_HASHIDRO):
            is_electrolysis = coordinator.get_value("hidro.is_electrolysis")
            entities.append(
                AquariteSensorEntity(
                    coordinator,
                    AquariteSensorEntityDescription(
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


class AquariteSensorEntity(AquariteEntity, SensorEntity):
    """Generic Aquarite sensor driven by an entity description."""

    entity_description: AquariteSensorEntityDescription

    def __init__(
        self,
        coordinator: AquariteDataUpdateCoordinator,
        description: AquariteSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = self.build_unique_id(description.key)

    @property
    def native_value(self) -> float | int | str | None:
        """Return the sensor value, transformed by the description's value_fn."""
        # Pool name is a special case (not from coordinator data)
        if not self.entity_description.value_path:
            return self.coordinator.pool_name

        value = self.coordinator.get_value(self.entity_description.value_path)
        if value is None:
            return None
        try:
            return self.entity_description.value_fn(value)
        except TypeError, ValueError:
            return None
