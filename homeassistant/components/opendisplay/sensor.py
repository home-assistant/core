"""Sensor platform for OpenDisplay devices."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from opendisplay import voltage_to_percent
from opendisplay.models.advertisement import AdvertisementData, Sht40Reading
from opendisplay.models.config import SensorData
from opendisplay.models.enums import CapacityEstimator, PowerMode, SensorType

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import OpenDisplayConfigEntry
from .entity import OpenDisplayEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class OpenDisplaySensorEntityDescription(SensorEntityDescription):
    """Describes an OpenDisplay sensor entity."""

    value_fn: Callable[[AdvertisementData], float | int | None]


# The key stays "temperature": it is part of the unique_id of existing entities.
_CHIP_TEMPERATURE_DESCRIPTION = OpenDisplaySensorEntityDescription(
    key="temperature",
    translation_key="chip_temperature",
    device_class=SensorDeviceClass.TEMPERATURE,
    native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    state_class=SensorStateClass.MEASUREMENT,
    entity_category=EntityCategory.DIAGNOSTIC,
    entity_registry_enabled_default=False,
    value_fn=lambda adv: adv.temperature_c,
)

_BATTERY_POWER_MODES = {PowerMode.BATTERY, PowerMode.SOLAR}

_BATTERY_VOLTAGE_DESCRIPTION = OpenDisplaySensorEntityDescription(
    key="battery_voltage",
    translation_key="battery_voltage",
    device_class=SensorDeviceClass.VOLTAGE,
    native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
    state_class=SensorStateClass.MEASUREMENT,
    entity_category=EntityCategory.DIAGNOSTIC,
    entity_registry_enabled_default=False,
    value_fn=lambda adv: adv.battery_mv,
)


def _sht40_descriptions(
    sensor: SensorData,
) -> list[OpenDisplaySensorEntityDescription]:
    """Build ambient temperature and humidity entities for one SHT40.

    The offset of the reading within the dynamic block is per-board -- the
    reTerminal E1001/E1002/E1004 use 1 while the firmware default is 7 -- so it
    comes from the device's own config.
    """
    start_byte = sensor.sht40_msd_start_byte

    def _reading(adv: AdvertisementData) -> Sht40Reading | None:
        return adv.sht40_reading(start_byte)

    def _temperature(adv: AdvertisementData) -> float | None:
        reading = _reading(adv)
        return None if reading is None else reading.temperature_c

    def _humidity(adv: AdvertisementData) -> float | None:
        reading = _reading(adv)
        return None if reading is None else reading.humidity_percent

    return [
        OpenDisplaySensorEntityDescription(
            key=f"sht40_{sensor.instance_number}_temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_display_precision=1,
            value_fn=_temperature,
        ),
        OpenDisplaySensorEntityDescription(
            key=f"sht40_{sensor.instance_number}_humidity",
            device_class=SensorDeviceClass.HUMIDITY,
            native_unit_of_measurement=PERCENTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_display_precision=1,
            value_fn=_humidity,
        ),
    ]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OpenDisplayConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up OpenDisplay sensor entities."""
    coordinator = entry.runtime_data.coordinator
    device_config = entry.runtime_data.device_config
    power_config = device_config.power
    descriptions: list[OpenDisplaySensorEntityDescription] = [
        _CHIP_TEMPERATURE_DESCRIPTION
    ]

    for sensor in device_config.sensors:
        if sensor.sensor_type_enum is SensorType.SHT40:
            descriptions += _sht40_descriptions(sensor)

    if power_config.power_mode_enum in _BATTERY_POWER_MODES:
        capacity_estimator = power_config.capacity_estimator or CapacityEstimator.LI_ION
        descriptions += [
            _BATTERY_VOLTAGE_DESCRIPTION,
            OpenDisplaySensorEntityDescription(
                key="battery",
                device_class=SensorDeviceClass.BATTERY,
                native_unit_of_measurement=PERCENTAGE,
                state_class=SensorStateClass.MEASUREMENT,
                entity_category=EntityCategory.DIAGNOSTIC,
                value_fn=lambda adv: voltage_to_percent(
                    adv.battery_mv, capacity_estimator
                ),
            ),
        ]

    async_add_entities(
        OpenDisplaySensorEntity(coordinator, description)
        for description in descriptions
    )


class OpenDisplaySensorEntity(OpenDisplayEntity, SensorEntity):
    """A sensor entity for an OpenDisplay device."""

    entity_description: OpenDisplaySensorEntityDescription

    @property
    @override
    def native_value(self) -> float | int | None:
        """Return the sensor value."""
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data.advertisement)
