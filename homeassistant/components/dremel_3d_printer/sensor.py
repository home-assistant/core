"""Support for monitoring Dremel 3D Printer sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from dremel3dpy import Dremel3DPrinter

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfInformation,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util.dt import utcnow
from homeassistant.util.variance import ignore_variance

from .const import ATTR_EXTRUDER, ATTR_PLATFORM, DOMAIN
from .entity import Dremel3DPrinterEntity


@dataclass(frozen=True, kw_only=True)
class Dremel3DPrinterSensorEntityDescription(SensorEntityDescription):
    """Describes a Dremel 3D Printer sensor."""

    value_fn: Callable[[Dremel3DPrinter, str], StateType | datetime]
    available_fn: Callable[[Dremel3DPrinter, str], bool] = lambda api, _: True


SENSOR_TYPES: tuple[Dremel3DPrinterSensorEntityDescription, ...] = (
    Dremel3DPrinterSensorEntityDescription(
        key="job_phase",
        translation_key="job_phase",
        value_fn=lambda api, _: api.get_printing_status(),
    ),
    Dremel3DPrinterSensorEntityDescription(
        key="remaining_time",
        translation_key="completion_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        available_fn=lambda api, key: api.get_job_status()[key] > 0,
        value_fn=ignore_variance(
            lambda api, key: utcnow() + timedelta(seconds=api.get_job_status()[key]),
            timedelta(minutes=2),
        ),
    ),
    Dremel3DPrinterSensorEntityDescription(
        key="progress",
        translation_key="progress",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda api, _: api.get_printing_progress(),
    ),
    Dremel3DPrinterSensorEntityDescription(
        key="chamber",
        translation_key="chamber",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda api, key: api.get_temperature_type(key),
    ),
    Dremel3DPrinterSensorEntityDescription(
        key="platform_temperature",
        translation_key="platform_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda api, _: api.get_temperature_type(ATTR_PLATFORM),
    ),
    Dremel3DPrinterSensorEntityDescription(
        key="target_platform_temperature",
        translation_key="target_platform_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda api, _: api.get_temperature_attributes(ATTR_PLATFORM)[
            "target_temp"
        ],
    ),
    Dremel3DPrinterSensorEntityDescription(
        key="max_platform_temperature",
        translation_key="max_platform_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda api, _: api.get_temperature_attributes(ATTR_PLATFORM)[
            "max_temp"
        ],
    ),
    Dremel3DPrinterSensorEntityDescription(
        key=ATTR_EXTRUDER,
        translation_key="extruder",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda api, key: api.get_temperature_type(key),
    ),
    Dremel3DPrinterSensorEntityDescription(
        key="target_extruder_temperature",
        translation_key="target_extruder_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda api, _: api.get_temperature_attributes(ATTR_EXTRUDER)[
            "target_temp"
        ],
    ),
    Dremel3DPrinterSensorEntityDescription(
        key="max_extruder_temperature",
        translation_key="max_extruder_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda api, _: api.get_temperature_attributes(ATTR_EXTRUDER)[
            "max_temp"
        ],
    ),
    Dremel3DPrinterSensorEntityDescription(
        key="network_build",
        translation_key="network_build",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda api, key: api.get_job_status()[key],
    ),
    Dremel3DPrinterSensorEntityDescription(
        key="filament",
        translation_key="filament",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda api, key: api.get_job_status()[key],
    ),
    Dremel3DPrinterSensorEntityDescription(
        key="elapsed_time",
        translation_key="elapsed_time",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        available_fn=lambda api, _: api.get_printing_status() == "building",
        value_fn=lambda api, key: api.get_job_status()[key],
    ),
    Dremel3DPrinterSensorEntityDescription(
        key="estimated_total_time",
        translation_key="estimated_total_time",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        available_fn=lambda api, key: api.get_job_status()[key] > 0,
        value_fn=lambda api, key: api.get_job_status()[key],
    ),
    Dremel3DPrinterSensorEntityDescription(
        key="job_status",
        translation_key="job_status",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda api, key: api.get_job_status()[key],
    ),
    Dremel3DPrinterSensorEntityDescription(
        key="job_name",
        translation_key="job_name",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda api, _: api.get_job_name(),
    ),
    Dremel3DPrinterSensorEntityDescription(
        key="api_version",
        translation_key="api_version",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda api, key: api.get_printer_info()[key],
    ),
    Dremel3DPrinterSensorEntityDescription(
        key="host",
        translation_key="host",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda api, key: api.get_printer_info()[key],
    ),
    Dremel3DPrinterSensorEntityDescription(
        key="connection_type",
        translation_key="connection_type",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda api, key: api.get_printer_info()[key],
    ),
    Dremel3DPrinterSensorEntityDescription(
        key="available_storage",
        translation_key="available_storage",
        native_unit_of_measurement=UnitOfInformation.MEGABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda api, key: api.get_printer_info()[key] * 100,
    ),
    Dremel3DPrinterSensorEntityDescription(
        key="hours_used",
        translation_key="hours_used",
        native_unit_of_measurement=UnitOfTime.HOURS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda api, key: api.get_printer_info()[key],
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the available Dremel 3D Printer sensors."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        Dremel3DPrinterSensor(coordinator, description) for description in SENSOR_TYPES
    )


class Dremel3DPrinterSensor(Dremel3DPrinterEntity, SensorEntity):
    """Representation of a Dremel 3D Printer sensor."""

    entity_description: Dremel3DPrinterSensorEntityDescription

    @property
    def available(self) -> bool:
        """Return True if the entity is available."""
        return super().available and self.entity_description.available_fn(
            self._api, self.entity_description.key
        )

    @property
    def native_value(self) -> StateType | datetime:
        """Return the sensor state."""
        return self.entity_description.value_fn(self._api, self.entity_description.key)
