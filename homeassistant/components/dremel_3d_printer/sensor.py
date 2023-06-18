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


@dataclass
class Dremel3DPrinterSensorEntityMixin:
    """Mixin for Dremel 3D Printer sensor."""

    value_fn: Callable[[Dremel3DPrinter, str], StateType | datetime]


@dataclass
class Dremel3DPrinterSensorEntityDescription(
    SensorEntityDescription, Dremel3DPrinterSensorEntityMixin
):
    """Describes a Dremel 3D Printer sensor."""

    available_fn: Callable[[Dremel3DPrinter, str], bool] = lambda api, _: True


SENSOR_TYPES: tuple[Dremel3DPrinterSensorEntityDescription, ...] = (
    Dremel3DPrinterSensorEntityDescription(
        key="job_phase",
        name="Job phase",
        icon="mdi:printer-3d",
        value_fn=lambda api, _: api.get_printing_status(),
    ),
    Dremel3DPrinterSensorEntityDescription(
        key="remaining_time",
        name="Remaining time",
        device_class=SensorDeviceClass.TIMESTAMP,
        available_fn=lambda api, key: api.get_job_status()[key] > 0,
        value_fn=ignore_variance(
            lambda api, key: utcnow() - timedelta(seconds=api.get_job_status()[key]),
            timedelta(minutes=2),
        ),
    ),
    Dremel3DPrinterSensorEntityDescription(
        key="progress",
        name="Progress",
        icon="mdi:printer-3d-nozzle",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda api, _: api.get_printing_progress(),
    ),
    Dremel3DPrinterSensorEntityDescription(
        key="chamber",
        name="Chamber",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda api, key: api.get_temperature_type(key),
    ),
    Dremel3DPrinterSensorEntityDescription(
        key="platform_temperature",
        name="Platform temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda api, _: api.get_temperature_type(ATTR_PLATFORM),
    ),
    Dremel3DPrinterSensorEntityDescription(
        key="target_platform_temperature",
        name="Target platform temperature",
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
        name="Max platform temperature",
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
        name="Extruder",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda api, key: api.get_temperature_type(key),
    ),
    Dremel3DPrinterSensorEntityDescription(
        key="target_extruder_temperature",
        name="Target extruder temperature",
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
        name="Max extruder temperature",
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
        name="Network build",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda api, key: api.get_job_status()[key],
    ),
    Dremel3DPrinterSensorEntityDescription(
        key="filament",
        name="Filament",
        icon="mdi:printer-3d-nozzle",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda api, key: api.get_job_status()[key],
    ),
    Dremel3DPrinterSensorEntityDescription(
        key="elapsed_time",
        name="Elapsed time",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        available_fn=lambda api, _: api.get_printing_status() == "building",
        value_fn=ignore_variance(
            lambda api, key: utcnow() - timedelta(seconds=api.get_job_status()[key]),
            timedelta(minutes=2),
        ),
    ),
    Dremel3DPrinterSensorEntityDescription(
        key="estimated_total_time",
        name="Estimated total time",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        available_fn=lambda api, key: api.get_job_status()[key] > 0,
        value_fn=ignore_variance(
            lambda api, key: utcnow() - timedelta(seconds=api.get_job_status()[key]),
            timedelta(minutes=2),
        ),
    ),
    Dremel3DPrinterSensorEntityDescription(
        key="job_status",
        name="Job status",
        icon="mdi:printer-3d",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda api, key: api.get_job_status()[key],
    ),
    Dremel3DPrinterSensorEntityDescription(
        key="job_name",
        name="Job name",
        icon="mdi:file",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda api, _: api.get_job_name(),
    ),
    Dremel3DPrinterSensorEntityDescription(
        key="api_version",
        name="API version",
        icon="mdi:api",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda api, key: api.get_printer_info()[key],
    ),
    Dremel3DPrinterSensorEntityDescription(
        key="host",
        name="Host",
        icon="mdi:ip-network",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda api, key: api.get_printer_info()[key],
    ),
    Dremel3DPrinterSensorEntityDescription(
        key="connection_type",
        name="Connection type",
        icon="mdi:network",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda api, key: api.get_printer_info()[key],
    ),
    Dremel3DPrinterSensorEntityDescription(
        key="available_storage",
        name="Available storage",
        native_unit_of_measurement=UnitOfInformation.MEGABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda api, key: api.get_printer_info()[key] * 100,
    ),
    Dremel3DPrinterSensorEntityDescription(
        key="hours_used",
        name="Hours used",
        icon="mdi:clock",
        native_unit_of_measurement=UnitOfTime.HOURS,
        device_class=SensorDeviceClass.DURATION,
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
    """Representation of an Dremel 3D Printer sensor."""

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
