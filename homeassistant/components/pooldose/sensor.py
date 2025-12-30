"""Sensors for the Seko PoolDose integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PooldoseConfigEntry
from .const import UNIT_MAPPING
from .entity import PooldoseEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class PooldoseSensorEntityDescription(SensorEntityDescription):
    """Describes PoolDose sensor entity."""

    use_unit_conversion: bool = False


SENSOR_DESCRIPTIONS: tuple[PooldoseSensorEntityDescription, ...] = (
    PooldoseSensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        use_unit_conversion=True,
    ),
    PooldoseSensorEntityDescription(key="ph", device_class=SensorDeviceClass.PH),
    PooldoseSensorEntityDescription(
        key="orp",
        translation_key="orp",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
    ),
    PooldoseSensorEntityDescription(
        key="cl",
        translation_key="cl",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
    ),
    PooldoseSensorEntityDescription(
        key="flow_rate",
        translation_key="flow_rate",
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        use_unit_conversion=True,
    ),
    PooldoseSensorEntityDescription(
        key="water_meter_total_permanent",
        translation_key="water_meter_total_permanent",
        device_class=SensorDeviceClass.VOLUME,
        state_class=SensorStateClass.TOTAL_INCREASING,
        use_unit_conversion=True,
    ),
    PooldoseSensorEntityDescription(
        key="ph_type_dosing",
        translation_key="ph_type_dosing",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENUM,
        options=["alcalyne", "acid"],
    ),
    PooldoseSensorEntityDescription(
        key="peristaltic_ph_dosing",
        translation_key="peristaltic_ph_dosing",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.ENUM,
        options=["proportional", "on_off", "timed"],
    ),
    PooldoseSensorEntityDescription(
        key="ofa_ph_time",
        translation_key="ofa_ph_time",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.DURATION,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfTime.MINUTES,
    ),
    PooldoseSensorEntityDescription(
        key="orp_type_dosing",
        translation_key="orp_type_dosing",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.ENUM,
        options=["low", "high"],
    ),
    PooldoseSensorEntityDescription(
        key="peristaltic_orp_dosing",
        translation_key="peristaltic_orp_dosing",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.ENUM,
        options=["off", "proportional", "on_off", "timed"],
    ),
    PooldoseSensorEntityDescription(
        key="cl_type_dosing",
        translation_key="cl_type_dosing",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.ENUM,
        options=["low", "high"],
    ),
    PooldoseSensorEntityDescription(
        key="peristaltic_cl_dosing",
        translation_key="peristaltic_cl_dosing",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.ENUM,
        options=["off", "proportional", "on_off", "timed"],
    ),
    PooldoseSensorEntityDescription(
        key="ofa_orp_time",
        translation_key="ofa_orp_time",
        device_class=SensorDeviceClass.DURATION,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfTime.MINUTES,
    ),
    PooldoseSensorEntityDescription(
        key="ph_calibration_type",
        translation_key="ph_calibration_type",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.ENUM,
        options=["off", "reference", "1_point", "2_points"],
    ),
    PooldoseSensorEntityDescription(
        key="ph_calibration_offset",
        translation_key="ph_calibration_offset",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.VOLTAGE,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
    ),
    PooldoseSensorEntityDescription(
        key="ph_calibration_slope",
        translation_key="ph_calibration_slope",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.VOLTAGE,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
    ),
    PooldoseSensorEntityDescription(
        key="orp_calibration_type",
        translation_key="orp_calibration_type",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.ENUM,
        options=["off", "reference", "1_point"],
    ),
    PooldoseSensorEntityDescription(
        key="orp_calibration_offset",
        translation_key="orp_calibration_offset",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.VOLTAGE,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
    ),
    PooldoseSensorEntityDescription(
        key="orp_calibration_slope",
        translation_key="orp_calibration_slope",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.VOLTAGE,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: PooldoseConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up PoolDose sensor entities from a config entry."""
    if TYPE_CHECKING:
        assert config_entry.unique_id is not None

    coordinator = config_entry.runtime_data
    sensor_data = coordinator.data["sensor"]
    serial_number = config_entry.unique_id

    async_add_entities(
        PooldoseSensor(
            coordinator,
            serial_number,
            coordinator.device_info,
            description,
            "sensor",
        )
        for description in SENSOR_DESCRIPTIONS
        if description.key in sensor_data
    )


class PooldoseSensor(PooldoseEntity, SensorEntity):
    """Sensor entity for the Seko PoolDose Python API."""

    entity_description: PooldoseSensorEntityDescription

    @property
    def native_value(self) -> float | int | str | None:
        """Return the current value of the sensor."""
        data = self.get_data()
        if data is not None:
            return data["value"]
        return None

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement."""
        if (
            self.entity_description.use_unit_conversion
            and (data := self.get_data()) is not None
            and (device_unit := data.get("unit"))
        ):
            # Map device unit to Home Assistant unit, return None if unknown
            return UNIT_MAPPING.get(device_unit)

        # Fall back to static unit from entity description
        return super().native_unit_of_measurement
