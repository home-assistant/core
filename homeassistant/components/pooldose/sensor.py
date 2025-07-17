"""Sensors for the Seko Pooldose integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any

from pooldose.request_handler import RequestStatus

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PooldoseConfigEntry, PooldoseCoordinator
from .const import device_info
from .entity import PooldoseEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class PooldoseSensorEntityDescription(SensorEntityDescription):
    """Describe a Pooldose sensor entity."""

    entity_category: EntityCategory | None = None
    value_fn: Callable[[Any], Any] = lambda data: data[0] if data else None


SENSOR_DESCRIPTIONS: tuple[PooldoseSensorEntityDescription, ...] = (
    PooldoseSensorEntityDescription(
        key="temperature",
        translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    PooldoseSensorEntityDescription(
        key="ph",
        translation_key="ph",
        device_class=SensorDeviceClass.PH,
    ),
    PooldoseSensorEntityDescription(
        key="orp",
        translation_key="orp",
        device_class=SensorDeviceClass.VOLTAGE,
    ),
    PooldoseSensorEntityDescription(
        key="ph_type_dosing",
        translation_key="ph_type_dosing",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    PooldoseSensorEntityDescription(
        key="peristaltic_ph_dosing",
        translation_key="peristaltic_ph_dosing",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    PooldoseSensorEntityDescription(
        key="ofa_ph_value",
        translation_key="ofa_ph_value",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.DURATION,
        entity_registry_enabled_default=False,
    ),
    PooldoseSensorEntityDescription(
        key="orp_type_dosing",
        translation_key="orp_type_dosing",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    PooldoseSensorEntityDescription(
        key="peristaltic_orp_dosing",
        translation_key="peristaltic_orp_dosing",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    PooldoseSensorEntityDescription(
        key="ofa_orp_value",
        translation_key="ofa_orp_value",
        device_class=SensorDeviceClass.DURATION,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    PooldoseSensorEntityDescription(
        key="ph_calibration_type",
        translation_key="ph_calibration_type",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    PooldoseSensorEntityDescription(
        key="ph_calibration_offset",
        translation_key="ph_calibration_offset",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.VOLTAGE,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
    ),
    PooldoseSensorEntityDescription(
        key="ph_calibration_slope",
        translation_key="ph_calibration_slope",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.VOLTAGE,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
    ),
    PooldoseSensorEntityDescription(
        key="orp_calibration_type",
        translation_key="orp_calibration_type",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    PooldoseSensorEntityDescription(
        key="orp_calibration_offset",
        translation_key="orp_calibration_offset",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.VOLTAGE,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
    ),
    PooldoseSensorEntityDescription(
        key="orp_calibration_slope",
        translation_key="orp_calibration_slope",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.VOLTAGE,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PooldoseConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Pooldose sensor entities from a config entry."""
    coordinator = entry.runtime_data.coordinator
    client = entry.runtime_data.client
    serial_number = entry.data["serialnumber"]
    device_info_dict = entry.runtime_data.device_info

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
                device_info_dict,
            )
        )

    async_add_entities(entities)


class PooldoseSensor(PooldoseEntity, SensorEntity):
    """Sensor entity for the Seko Pooldose API."""

    entity_description: PooldoseSensorEntityDescription

    def __init__(
        self,
        coordinator: PooldoseCoordinator,
        description: PooldoseSensorEntityDescription,
        serialnumber: str,
        device_info_dict: dict[str, Any],
    ) -> None:
        """Initialize a Pooldose sensor entity."""
        self.entity_description = description
        super().__init__(
            coordinator,
            serialnumber,
            device_info(device_info_dict),
        )

    @property
    def native_value(self) -> float | int | str | None:
        """Return the current value of the sensor."""
        if not self.coordinator.data:
            return None

        status, data = self.coordinator.data
        if status != RequestStatus.SUCCESS:
            _LOGGER.warning(
                "Pooldose API returned status %s, entities will be unavailable", status
            )
            return None

        sensor_data = data.get(self.entity_description.key)
        if not sensor_data:
            return None

        return self.entity_description.value_fn(sensor_data)

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement, determined dynamically from API data."""
        if not self.coordinator.data:
            return None

        _, data = self.coordinator.data
        sensor_data = data.get(self.entity_description.key)
        if sensor_data and len(sensor_data) > 1:
            unit = sensor_data[1]
            if unit and unit.lower() != "ph":  # Avoid None or "ph" as unit
                return unit

        return None
