"""PrusaLink sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import cast

from pyprusalink.types import JobInfo, PrinterInfo, PrinterState, PrinterStatus
from pyprusalink.types_legacy import LegacyPrinterStatus, LegacyPrinterTelemetry

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    REVOLUTIONS_PER_MINUTE,
    UnitOfLength,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util.dt import utcnow

from .coordinator import PrusaLinkConfigEntry, PrusaLinkUpdateCoordinator
from .entity import PrusaLinkEntity, PrusaLinkEntityDescription


def _job_progress(data: JobInfo | None) -> float | None:
    """Return job progress or None if no active job is running."""
    if data is None or data.get("state") == PrinterState.IDLE.value:
        return None
    return data["progress"]


def _job_filename(data: JobInfo | None) -> str | None:
    """Return job filename or None if no active job is running."""
    if data is None or data.get("state") == PrinterState.IDLE.value:
        return None
    file_data = data["file"]
    if file_data is None:
        return None
    return file_data["display_name"]


def _job_start(data: JobInfo | None) -> datetime | None:
    """Return print start timestamp or None if no active job is running."""
    if data is None or data.get("state") == PrinterState.IDLE.value:
        return None
    return utcnow() - timedelta(seconds=data["time_printing"])


def _job_finish(data: JobInfo | None) -> datetime | None:
    """Return print finish timestamp or None if no active job is running."""
    if data is None or data.get("state") == PrinterState.IDLE.value:
        return None
    time_remaining = data["time_remaining"]
    if time_remaining is None:
        return None
    return utcnow() + timedelta(seconds=time_remaining)

@dataclass(frozen=True, kw_only=True)
class PrusaLinkSensorEntityDescription[
    T: PrinterStatus | LegacyPrinterStatus | JobInfo | None | PrinterInfo
](
    SensorEntityDescription,
    PrusaLinkEntityDescription,
):
    """Describes PrusaLink sensor entity."""

    value_fn: Callable[[T], datetime | StateType]


SENSORS: dict[str, tuple[PrusaLinkSensorEntityDescription, ...]] = {
    "status": (
        PrusaLinkSensorEntityDescription[PrinterStatus](
            key="printer.state",
            name=None,
            value_fn=lambda data: cast(str, data["printer"]["state"]).lower(),
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
            key="printer.telemetry.x-position",
            translation_key="x_position",
            native_unit_of_measurement=UnitOfLength.MILLIMETERS,
            device_class=SensorDeviceClass.DISTANCE,
            state_class=SensorStateClass.MEASUREMENT,
            value_fn=lambda data: cast(float, data["printer"]["axis_x"]),
            supported_fn=lambda data: data["printer"].get("axis_x") is not None,
            entity_registry_enabled_default=False,
        ),
        PrusaLinkSensorEntityDescription[PrinterStatus](
            key="printer.telemetry.y-position",
            translation_key="y_position",
            native_unit_of_measurement=UnitOfLength.MILLIMETERS,
            device_class=SensorDeviceClass.DISTANCE,
            state_class=SensorStateClass.MEASUREMENT,
            value_fn=lambda data: cast(float, data["printer"]["axis_y"]),
            supported_fn=lambda data: data["printer"].get("axis_y") is not None,
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
            # `available_fn` guarantees `telemetry` is not None at this
            # point; the inner cast narrows the Optional for the index.
            value_fn=lambda data: cast(
                str, cast(LegacyPrinterTelemetry, data["telemetry"])["material"]
            ),
            available_fn=lambda data: data.get("telemetry") is not None,
        ),
    ),
    "job": (
        PrusaLinkSensorEntityDescription[JobInfo | None](
            key="job.progress",
            translation_key="progress",
            native_unit_of_measurement=PERCENTAGE,
            value_fn=_job_progress,
            available_fn=lambda _: True,
        ),
        PrusaLinkSensorEntityDescription[JobInfo | None](
            key="job.filename",
            translation_key="filename",
            value_fn=_job_filename,
            available_fn=lambda _: True,
        ),
        PrusaLinkSensorEntityDescription[JobInfo | None](
            key="job.start",
            translation_key="print_start",
            device_class=SensorDeviceClass.TIMESTAMP,
            value_fn=_job_start,
            available_fn=lambda _: True,
        ),
        PrusaLinkSensorEntityDescription[JobInfo | None](
            key="job.finish",
            translation_key="print_finish",
            device_class=SensorDeviceClass.TIMESTAMP,
            value_fn=_job_finish,
            available_fn=lambda _: True,
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
        PrusaLinkSensorEntityDescription[PrinterInfo](
            key="info.min_extrusion_temp",
            translation_key="min_extrusion_temp",
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            device_class=SensorDeviceClass.TEMPERATURE,
            value_fn=lambda data: data["min_extrusion_temp"],
            supported_fn=lambda data: data.get("min_extrusion_temp") is not None,
            entity_registry_enabled_default=False,
        ),
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PrusaLinkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up PrusaLink sensor based on a config entry."""
    coordinators = entry.runtime_data

    entities: list[PrusaLinkEntity] = []

    for coordinator_type, sensors in SENSORS.items():
        coordinator = coordinators[coordinator_type]
        entities.extend(
            PrusaLinkSensorEntity(coordinator, sensor_description)
            for sensor_description in sensors
            if sensor_description.supported_fn(coordinator.data)
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
