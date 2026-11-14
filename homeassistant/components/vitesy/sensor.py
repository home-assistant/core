"""Sensor platform for the Vitesy integration."""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import override

from aiovitesy.api import VitesyDevice
from aiovitesy.const import PROGRAM_LEVELS

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfDensity,
    UnitOfRatio,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util import dt as dt_util

from .const import LOGGER
from .coordinator import VitesyConfigEntry, VitesyDataUpdateCoordinator
from .entity import VitesyEntity, async_add_device_entities

PARALLEL_UPDATES = 0

# Groups within a measurement payload.
_SENSORS_DATA = "sensors_data"
_STATUS_DATA = "status_data"

# Reading ids within those groups (Shelfy).
_FRIDGE_TEMPERATURE = "TMP01-SY"
_DOOR_OPENINGS = "DOC-SY"
_DOOR_OPEN_DURATION = "DOT-SY"
_BATTERY = "battery"

# Sensor types of a device's readings (Natede, Eteria).
_TEMPERATURE = "tmp"
_HUMIDITY = "hum"
_VOC = "voc"
_CO2 = "co2"
_CO = "co"
_PM25 = "pm25"


def _reading(device: VitesyDevice, group: str, reading_id: str) -> float | None:
    """Return a numeric value from a measurement group entry by its id."""
    for entry in device.measurement.get(group, ()):
        if entry.get("id") == reading_id:
            value = entry.get("value")
            value = value.get("avg") if isinstance(value, dict) else value
            if isinstance(value, (int, float)):
                return value
            LOGGER.warning(
                "Ignoring non-numeric value for reading %s on %s: %r",
                reading_id,
                device.name,
                value,
            )
            return None
    return None


def _air_quality_score(device: VitesyDevice) -> float | None:
    """Return the air quality score.

    The Hub reports it as a 0-1 fraction; Vitesy's canonical scale is 0-100.
    """
    score = device.measurement.get("score")
    return score * 100 if score is not None else None


def _parse_timestamp(device: VitesyDevice, label: str, value: str) -> datetime | None:
    """Parse a timestamp reported by Vitesy Hub, warning when it is invalid."""
    try:
        return dt_util.parse_datetime(value, raise_on_error=True)
    except ValueError:
        LOGGER.warning("Ignoring unparsable %s for %s: %s", label, device.name, value)
        return None


def _last_update(device: VitesyDevice) -> datetime | None:
    """Return when the device last reported a measurement."""
    timestamp = device.measurement.get("timestamp")
    if not timestamp:
        return None
    return _parse_timestamp(device, "measurement timestamp", timestamp)


def _has_reading(sensor_type: str) -> Callable[[VitesyDevice], bool]:
    """Return an exists function for a reading of the given sensor type."""

    def _exists(device: VitesyDevice) -> bool:
        reading = device.readings.get(sensor_type)
        # Shelfy's fridge temperature is already its own sensor.
        return reading is not None and reading.sensor_id != _FRIDGE_TEMPERATURE

    return _exists


def _reading_value(sensor_type: str) -> Callable[[VitesyDevice], float | None]:
    """Return a value function for a reading of the given sensor type."""

    def _value(device: VitesyDevice) -> float | None:
        reading = device.readings.get(sensor_type)
        return reading.value if reading is not None else None

    return _value


def _maintenance_due(component: str) -> Callable[[VitesyDevice], datetime | None]:
    """Return a value function for a maintenance component's due date."""

    def _value(device: VitesyDevice) -> datetime | None:
        due_date = device.maintenance.get(component, {}).get("due_date")
        if not due_date:
            return None
        return _parse_timestamp(device, f"{component} due date", due_date)

    return _value


def _program_level(field: str) -> Callable[[VitesyDevice], str | None]:
    """Return a value function for a level in the active program's metadata."""

    def _value(device: VitesyDevice) -> str | None:
        program = device.programs.get(device.program_id)
        if program is None:
            return None
        level = program.get("metadata", {}).get(field)
        if level is None:
            return None
        if (level := str(level).lower()) in PROGRAM_LEVELS:
            return level
        LOGGER.warning(
            "Ignoring unknown program %s level for %s: %s", field, device.name, level
        )
        return None

    return _value


@dataclass(frozen=True, kw_only=True)
class VitesySensorEntityDescription(SensorEntityDescription):
    """Describes a Vitesy sensor entity."""

    value_fn: Callable[[VitesyDevice], StateType | datetime]
    exists_fn: Callable[[VitesyDevice], bool] | None = None


SENSORS: tuple[VitesySensorEntityDescription, ...] = (
    VitesySensorEntityDescription(
        key="air_quality_score",
        translation_key="air_quality_score",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=_air_quality_score,
    ),
    VitesySensorEntityDescription(
        key="fridge_temperature",
        translation_key="fridge_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: _reading(device, _SENSORS_DATA, _FRIDGE_TEMPERATURE),
    ),
    VitesySensorEntityDescription(
        key="door_openings",
        translation_key="door_openings",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: _reading(device, _SENSORS_DATA, _DOOR_OPENINGS),
    ),
    VitesySensorEntityDescription(
        key="door_open_duration",
        translation_key="door_open_duration",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: _reading(device, _SENSORS_DATA, _DOOR_OPEN_DURATION),
    ),
    VitesySensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        exists_fn=_has_reading(_TEMPERATURE),
        value_fn=_reading_value(_TEMPERATURE),
    ),
    VitesySensorEntityDescription(
        key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        exists_fn=_has_reading(_HUMIDITY),
        value_fn=_reading_value(_HUMIDITY),
    ),
    VitesySensorEntityDescription(
        key="volatile_organic_compounds",
        device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS_PARTS,
        native_unit_of_measurement=UnitOfRatio.PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
        exists_fn=_has_reading(_VOC),
        value_fn=_reading_value(_VOC),
    ),
    VitesySensorEntityDescription(
        key="carbon_dioxide",
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=UnitOfRatio.PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
        exists_fn=_has_reading(_CO2),
        value_fn=_reading_value(_CO2),
    ),
    VitesySensorEntityDescription(
        key="carbon_monoxide",
        device_class=SensorDeviceClass.CO,
        native_unit_of_measurement=UnitOfRatio.PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
        exists_fn=_has_reading(_CO),
        value_fn=_reading_value(_CO),
    ),
    VitesySensorEntityDescription(
        key="pm25",
        device_class=SensorDeviceClass.PM25,
        native_unit_of_measurement=UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        exists_fn=_has_reading(_PM25),
        value_fn=_reading_value(_PM25),
    ),
    VitesySensorEntityDescription(
        key="battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: _reading(device, _STATUS_DATA, _BATTERY),
    ),
    VitesySensorEntityDescription(
        key="fan_speed",
        translation_key="fan_speed",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=list(PROGRAM_LEVELS),
        value_fn=_program_level("fan"),
    ),
    VitesySensorEntityDescription(
        key="power_level",
        translation_key="power_level",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=list(PROGRAM_LEVELS),
        value_fn=_program_level("power"),
    ),
    VitesySensorEntityDescription(
        key="last_update",
        translation_key="last_update",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_last_update,
    ),
    VitesySensorEntityDescription(
        key="filter_change_due",
        translation_key="filter_change_due",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_maintenance_due("filter"),
    ),
    VitesySensorEntityDescription(
        key="fridge_cleaning_due",
        translation_key="fridge_cleaning_due",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_maintenance_due("fridge"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VitesyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Vitesy sensors from a config entry."""
    coordinator = entry.runtime_data

    def _entities(device_id: str, device: VitesyDevice) -> Iterable[VitesySensor]:
        return (
            VitesySensor(coordinator, device_id, description)
            for description in SENSORS
            if (
                description.exists_fn(device)
                if description.exists_fn
                else description.value_fn(device) is not None
            )
        )

    async_add_device_entities(coordinator, async_add_entities, _entities)


class VitesySensor(VitesyEntity, SensorEntity):
    """Representation of a Vitesy sensor."""

    entity_description: VitesySensorEntityDescription

    def __init__(
        self,
        coordinator: VitesyDataUpdateCoordinator,
        device_id: str,
        description: VitesySensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, device_id)
        self.entity_description = description
        self._attr_unique_id = f"{device_id}_{description.key}"

    @property
    @override
    def native_value(self) -> StateType | datetime:
        """Return the current value of the sensor."""
        return self.entity_description.value_fn(self.device)
