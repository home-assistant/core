"""Sensors for the Seko PoolDose integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import EntityCategory, UnitOfElectricPotential, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PooldoseConfigEntry, PooldoseCoordinator
from .entity import PooldoseEntity, device_info

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class PooldoseSensorEntityDescription(SensorEntityDescription):
    """Describe a PoolDose sensor entity."""


SENSOR_DESCRIPTIONS: tuple[PooldoseSensorEntityDescription, ...] = (
    PooldoseSensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        # Unit dynamically determined via API
    ),
    PooldoseSensorEntityDescription(key="ph", device_class=SensorDeviceClass.PH),
    PooldoseSensorEntityDescription(
        key="orp",
        translation_key="orp",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
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
        key="ofa_ph_value",
        translation_key="ofa_ph_value",
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
        key="ofa_orp_value",
        translation_key="ofa_orp_value",
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

    coordinator = config_entry.runtime_data.coordinator
    client = config_entry.runtime_data.client
    serial_number = config_entry.unique_id
    device_properties = config_entry.runtime_data.device_properties

    available = client.available_sensors()

    async_add_entities(
        PooldoseSensor(
            coordinator,
            description,
            serial_number,
            device_properties,
        )
        for description in SENSOR_DESCRIPTIONS
        if description.key in available
    )


class PooldoseSensor(PooldoseEntity, SensorEntity):
    """Sensor entity for the Seko PoolDose Python API."""

    entity_description: PooldoseSensorEntityDescription

    def __init__(
        self,
        coordinator: PooldoseCoordinator,
        description: PooldoseSensorEntityDescription,
        serial_number: str,
        device_properties: dict[str, Any],
    ) -> None:
        """Initialize a PoolDose sensor entity."""
        super().__init__(
            coordinator,
            serial_number,
            device_info(device_properties, serial_number),
            entity_description=description,
        )

    @property
    def native_value(self) -> float | int | str | None:
        """Return the current value of the sensor."""
        sensor_data = self.coordinator.data.get(self.entity_description.key)
        if isinstance(sensor_data, (list, tuple)) and sensor_data:
            return sensor_data[0]
        return None

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement."""
        if self.entity_description.key == "temperature" and self.coordinator.data:
            sensor_data = self.coordinator.data.get("temperature")
            if isinstance(sensor_data, (list, tuple)) and len(sensor_data) > 1:
                return sensor_data[1]  # °C or °F

        return super().native_unit_of_measurement
