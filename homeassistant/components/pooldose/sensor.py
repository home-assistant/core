"""Sensors for the Seko PoolDose integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PooldoseConfigEntry, PooldoseCoordinator
from .entity import PooldoseEntity, device_info

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class PooldoseSensorEntityDescription(SensorEntityDescription):
    """Describe a PoolDose sensor entity."""

    entity_category: EntityCategory | None = None


SENSOR_DESCRIPTIONS: tuple[PooldoseSensorEntityDescription, ...] = (
    PooldoseSensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        # Unit comes from API (°C or °F)
    ),
    PooldoseSensorEntityDescription(
        key="ph",
        device_class=SensorDeviceClass.PH,
        # has no unit
    ),
    PooldoseSensorEntityDescription(
        key="orp",
        translation_key="orp",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement="mV",
    ),
    PooldoseSensorEntityDescription(
        key="ph_type_dosing",
        translation_key="ph_type_dosing",
        entity_category=EntityCategory.DIAGNOSTIC,
        # has no unit
    ),
    PooldoseSensorEntityDescription(
        key="peristaltic_ph_dosing",
        translation_key="peristaltic_ph_dosing",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        # has no unit
    ),
    PooldoseSensorEntityDescription(
        key="ofa_ph_value",
        translation_key="ofa_ph_value",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.DURATION,
        entity_registry_enabled_default=False,
        native_unit_of_measurement="min",
    ),
    PooldoseSensorEntityDescription(
        key="orp_type_dosing",
        translation_key="orp_type_dosing",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        # has no unit
    ),
    PooldoseSensorEntityDescription(
        key="peristaltic_orp_dosing",
        translation_key="peristaltic_orp_dosing",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        # has no unit
    ),
    PooldoseSensorEntityDescription(
        key="ofa_orp_value",
        translation_key="ofa_orp_value",
        device_class=SensorDeviceClass.DURATION,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        native_unit_of_measurement="min",
    ),
    PooldoseSensorEntityDescription(
        key="ph_calibration_type",
        translation_key="ph_calibration_type",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        # has no unit
    ),
    PooldoseSensorEntityDescription(
        key="ph_calibration_offset",
        translation_key="ph_calibration_offset",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.VOLTAGE,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        native_unit_of_measurement="mV",
    ),
    PooldoseSensorEntityDescription(
        key="ph_calibration_slope",
        translation_key="ph_calibration_slope",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.VOLTAGE,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        native_unit_of_measurement="mV",
    ),
    PooldoseSensorEntityDescription(
        key="orp_calibration_type",
        translation_key="orp_calibration_type",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        # has no unit
    ),
    PooldoseSensorEntityDescription(
        key="orp_calibration_offset",
        translation_key="orp_calibration_offset",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.VOLTAGE,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        native_unit_of_measurement="mV",
    ),
    PooldoseSensorEntityDescription(
        key="orp_calibration_slope",
        translation_key="orp_calibration_slope",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.VOLTAGE,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        native_unit_of_measurement="mV",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: PooldoseConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up PoolDose sensor entities from a config entry."""
    coordinator = config_entry.runtime_data.coordinator
    client = config_entry.runtime_data.client
    serial_number = config_entry.unique_id
    device_properties = config_entry.runtime_data.device_properties

    # Ensure serial_number is not None
    if not serial_number:
        raise ValueError("Config entry must have a unique_id set")

    available = client.available_sensors()
    entities: list[SensorEntity] = []

    for description in SENSOR_DESCRIPTIONS:
        if description.key not in available:
            continue

        entities.append(
            PooldoseSensor(
                coordinator,
                description,
                serial_number,
                device_properties,
            )
        )

    async_add_entities(entities)


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
        # Use static unit if defined
        if self.entity_description.native_unit_of_measurement:
            return self.entity_description.native_unit_of_measurement

        # For temperature, get unit from API data
        if self.entity_description.key == "temperature" and self.coordinator.data:
            sensor_data = self.coordinator.data.get("temperature")
            if isinstance(sensor_data, (list, tuple)) and len(sensor_data) > 1:
                return sensor_data[1]  # °C or °F

        return None
