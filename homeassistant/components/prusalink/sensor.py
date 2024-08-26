"""PrusaLink sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Generic, TypeVar, cast

from pyprusalink.types import JobInfo, PrinterInfo, PrinterState, PrinterStatus
from pyprusalink.types_legacy import LegacyPrinterStatus

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    REVOLUTIONS_PER_MINUTE,
    UnitOfLength,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util.dt import utcnow
from homeassistant.util.variance import ignore_variance

from . import PrusaLinkEntity
from .const import DOMAIN
from .coordinator import PrusaLinkUpdateCoordinator

T = TypeVar("T", PrinterStatus, LegacyPrinterStatus, JobInfo, PrinterInfo)


@dataclass(frozen=True)
class PrusaLinkSensorEntityDescriptionMixin(Generic[T]):
    """Mixin for required keys."""

    value_fn: Callable[[T], datetime | StateType]


@dataclass(frozen=True)
class PrusaLinkSensorEntityDescription(
    SensorEntityDescription, PrusaLinkSensorEntityDescriptionMixin[T], Generic[T]
):
    """Describes PrusaLink sensor entity."""

    available_fn: Callable[[T], bool] = lambda _: True


SENSORS: dict[str, tuple[PrusaLinkSensorEntityDescription, ...]] = {
    "status": (
        PrusaLinkSensorEntityDescription[PrinterStatus](
            key="printer.state",
            name=None,
            value_fn=lambda data: (cast(str, data["printer"]["state"].lower())),
            device_class=SensorDeviceClass.ENUM,
            options=[state.value.lower() for state in PrinterState],
            translation_key="printer_state",
        ),
        PrusaLinkSensorEntityDescription[PrinterStatus](
            key="printer.telemetry.temp-bed",
            translation_key="heatbed_temperature",
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
            value_fn=lambda data: cast(float, data["printer"]["temp_bed"]),
            entity_registry_enabled_default=False,
        ),
        PrusaLinkSensorEntityDescription[PrinterStatus](
            key="printer.telemetry.temp-nozzle",
            translation_key="nozzle_temperature",
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
            value_fn=lambda data: cast(float, data["printer"]["temp_nozzle"]),
            entity_registry_enabled_default=False,
        ),
        PrusaLinkSensorEntityDescription[PrinterStatus](
            key="printer.telemetry.temp-bed.target",
            translation_key="heatbed_target_temperature",
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
            value_fn=lambda data: cast(float, data["printer"]["target_bed"]),
            entity_registry_enabled_default=False,
        ),
        PrusaLinkSensorEntityDescription[PrinterStatus](
            key="printer.telemetry.temp-nozzle.target",
            translation_key="nozzle_target_temperature",
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
            value_fn=lambda data: cast(float, data["printer"]["target_nozzle"]),
            entity_registry_enabled_default=False,
        ),
        PrusaLinkSensorEntityDescription[PrinterStatus](
            key="printer.telemetry.z-height",
            translation_key="z_height",
            native_unit_of_measurement=UnitOfLength.MILLIMETERS,
            device_class=SensorDeviceClass.DISTANCE,
            state_class=SensorStateClass.MEASUREMENT,
            value_fn=lambda data: cast(float, data["printer"]["axis_z"]),
            entity_registry_enabled_default=False,
        ),
        PrusaLinkSensorEntityDescription[PrinterStatus](
            key="printer.telemetry.print-speed",
            translation_key="print_speed",
            native_unit_of_measurement=PERCENTAGE,
            value_fn=lambda data: cast(float, data["printer"]["speed"]),
        ),
        PrusaLinkSensorEntityDescription[PrinterStatus](
            key="printer.telemetry.print-flow",
            translation_key="print_flow",
            native_unit_of_measurement=PERCENTAGE,
            value_fn=lambda data: cast(float, data["printer"]["flow"]),
            entity_registry_enabled_default=False,
        ),
        PrusaLinkSensorEntityDescription[PrinterStatus](
            key="printer.telemetry.fan-hotend",
            translation_key="fan_hotend",
            native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
            value_fn=lambda data: cast(float, data["printer"]["fan_hotend"]),
            entity_registry_enabled_default=False,
        ),
        PrusaLinkSensorEntityDescription[PrinterStatus](
            key="printer.telemetry.fan-print",
            translation_key="fan_print",
            native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
            value_fn=lambda data: cast(float, data["printer"]["fan_print"]),
            entity_registry_enabled_default=False,
        ),
    ),
    "legacy_status": (
        PrusaLinkSensorEntityDescription[LegacyPrinterStatus](
            key="printer.telemetry.material",
            translation_key="material",
            value_fn=lambda data: cast(str, data["telemetry"]["material"]),
        ),
    ),
    "job": (
        PrusaLinkSensorEntityDescription[JobInfo](
            key="job.progress",
            translation_key="progress",
            native_unit_of_measurement=PERCENTAGE,
            value_fn=lambda data: cast(float, data["progress"]),
            available_fn=lambda data: (
                data.get("progress") is not None
                and data.get("state") != PrinterState.IDLE.value
            ),
        ),
        PrusaLinkSensorEntityDescription[JobInfo](
            key="job.filename",
            translation_key="filename",
            value_fn=lambda data: cast(str, data["file"]["display_name"]),
            available_fn=lambda data: (
                data.get("file") is not None
                and data.get("state") != PrinterState.IDLE.value
            ),
        ),
        PrusaLinkSensorEntityDescription[JobInfo](
            key="job.start",
            translation_key="print_start",
            device_class=SensorDeviceClass.TIMESTAMP,
            value_fn=ignore_variance(
                lambda data: (utcnow() - timedelta(seconds=data["time_printing"])),
                timedelta(minutes=2),
            ),
            available_fn=lambda data: (
                data.get("time_printing") is not None
                and data.get("state") != PrinterState.IDLE.value
            ),
        ),
        PrusaLinkSensorEntityDescription[JobInfo](
            key="job.finish",
            translation_key="print_finish",
            device_class=SensorDeviceClass.TIMESTAMP,
            value_fn=ignore_variance(
                lambda data: (utcnow() + timedelta(seconds=data["time_remaining"])),
                timedelta(minutes=2),
            ),
            available_fn=lambda data: (
                data.get("time_remaining") is not None
                and data.get("state") != PrinterState.IDLE.value
            ),
        ),
    ),
    "info": (
        PrusaLinkSensorEntityDescription[PrinterInfo](
            key="info.nozzle_diameter",
            translation_key="nozzle_diameter",
            native_unit_of_measurement=UnitOfLength.MILLIMETERS,
            device_class=SensorDeviceClass.DISTANCE,
            value_fn=lambda data: cast(str, data["nozzle_diameter"]),
            entity_registry_enabled_default=False,
        ),
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up PrusaLink sensor based on a config entry."""
    coordinators: dict[str, PrusaLinkUpdateCoordinator] = hass.data[DOMAIN][
        entry.entry_id
    ]

    entities: list[PrusaLinkEntity] = []

    for coordinator_type, sensors in SENSORS.items():
        coordinator = coordinators[coordinator_type]
        entities.extend(
            PrusaLinkSensorEntity(coordinator, sensor_description)
            for sensor_description in sensors
        )

    async_add_entities(entities)


class PrusaLinkSensorEntity(PrusaLinkEntity, SensorEntity):
    """Defines a PrusaLink sensor."""

    entity_description: PrusaLinkSensorEntityDescription

    def __init__(
        self,
        coordinator: PrusaLinkUpdateCoordinator,
        description: PrusaLinkSensorEntityDescription,
    ) -> None:
        """Initialize a PrusaLink sensor entity."""
        super().__init__(coordinator=coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"

    @property
    def native_value(self) -> datetime | StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def available(self) -> bool:
        """Return if sensor is available."""
        return super().available and self.entity_description.available_fn(
            self.coordinator.data
        )
