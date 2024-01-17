"""Support for OSO Energy sensors."""
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from apyosoenergyapi import OSOEnergy
from apyosoenergyapi.helper.const import OSOEnergySensorData

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy, UnitOfPower, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
import homeassistant.util.dt as dt_util

from . import OSOEnergyEntity
from .const import DOMAIN

ENUM_VALUE_MAPPING: dict[str, dict[str, Any]] = {
    "heater_mode": {"powersave": "power_save", "extraenergy": "extra_energy"},
    "optimization_mode": {
        "gridcompany": "grid_company",
        "smartcompany": "smart_company",
    },
}


def _get_local_hour(utc_hour: int):
    """Get the local hour."""
    now = dt_util.utcnow()
    now_local = dt_util.now()
    utc_time = now.replace(hour=utc_hour, minute=0, second=0, microsecond=0)
    local_hour = dt_util.as_local(utc_time)
    local_hour = local_hour.replace(
        year=now_local.year, month=now_local.month, day=now_local.day
    )
    return local_hour


def _convert_profile_to_local(values):
    """Convert UTC profile to local."""
    profile = [None] * 24
    for hour in range(24):
        local_hour = _get_local_hour(hour)
        profile[local_hour.hour] = values[hour]

    return profile


@dataclass(frozen=True)
class OSOEnergySensorEntityDescription(SensorEntityDescription):
    """Class describing OSO Energy heater sensor entities."""

    value: Callable[[OSOEnergy], StateType] = round


SENSOR_TYPES: tuple[OSOEnergySensorEntityDescription, ...] = (
    OSOEnergySensorEntityDescription(
        key="profile",
        translation_key="profile",
        value=lambda device: _convert_profile_to_local(device.state),
    ),
    OSOEnergySensorEntityDescription(
        key="heater_mode",
        translation_key="heater_mode",
        device_class=SensorDeviceClass.ENUM,
        value=lambda device: ENUM_VALUE_MAPPING["heater_mode"].get(
            device.state.lower(), device.state.lower()
        ),
    ),
    OSOEnergySensorEntityDescription(
        key="optimization_mode",
        translation_key="optimization_mode",
        device_class=SensorDeviceClass.ENUM,
        value=lambda device: ENUM_VALUE_MAPPING["optimization_mode"].get(
            device.state.lower(), device.state.lower()
        ),
    ),
    OSOEnergySensorEntityDescription(
        key="power_load",
        translation_key="power_load",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        value=lambda device: device.state,
    ),
    OSOEnergySensorEntityDescription(
        key="tapping_capacity_kwh",
        translation_key="tapping_capacity_kwh",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value=lambda device: device.state,
    ),
    OSOEnergySensorEntityDescription(
        key="capacity_mixed_water_40",
        translation_key="capacity_mixed_water_40",
        device_class=SensorDeviceClass.VOLUME,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        value=lambda device: device.state,
    ),
    OSOEnergySensorEntityDescription(
        key="v40_min",
        translation_key="v40_min",
        device_class=SensorDeviceClass.VOLUME,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        value=lambda device: device.state,
    ),
    OSOEnergySensorEntityDescription(
        key="v40_level_min",
        translation_key="v40_level_min",
        device_class=SensorDeviceClass.VOLUME,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        value=lambda device: device.state,
    ),
    OSOEnergySensorEntityDescription(
        key="v40_level_max",
        translation_key="v40_level_max",
        device_class=SensorDeviceClass.VOLUME,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        value=lambda device: device.state,
    ),
    OSOEnergySensorEntityDescription(
        key="volume",
        translation_key="volume",
        device_class=SensorDeviceClass.VOLUME,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        value=lambda device: device.state,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up OSO Energy sensor."""
    osoenergy = hass.data[DOMAIN][entry.entry_id]
    devices = osoenergy.session.device_list.get("sensor")
    entities = []
    if devices:
        for dev in devices:
            for description in SENSOR_TYPES:
                if dev.osoEnergyType.lower() == description.key:
                    entities.append(OSOEnergySensor(osoenergy, description, dev))

    async_add_entities(entities, True)


class OSOEnergySensor(OSOEnergyEntity[OSOEnergySensorData], SensorEntity):
    """OSO Energy Sensor Entity."""

    _attr_has_entity_name = True
    entity_description: OSOEnergySensorEntityDescription

    def __init__(
        self,
        instance: OSOEnergy,
        description: OSOEnergySensorEntityDescription,
        osoenergy_device: OSOEnergySensorData,
    ) -> None:
        """Initialize the OSO Energy sensor."""
        super().__init__(instance, osoenergy_device)

        device_id = osoenergy_device.device_id
        self._attr_unique_id = f"{device_id}_{description.key}"
        self.entity_description = description

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value(self.device)

    async def async_update(self) -> None:
        """Update all data for OSO Energy."""
        await self.osoenergy.session.update_data()
        self.device = await self.osoenergy.sensor.get_sensor(self.device)
