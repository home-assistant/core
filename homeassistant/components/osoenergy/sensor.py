"""Support for OSO Energy sensors."""

from collections.abc import Callable
from dataclasses import dataclass
import datetime as dt

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


def _get_local_hour(utc_hour: int) -> dt.datetime:
    """Convert the requested utc hour to a local hour for the day.

    Args:
        utc_hour: the utc hour (0-23) for the current day to be converted.

    Returns:
        Datetime representation for the requested hour in local time for the day.

    """
    now = dt_util.utcnow()
    now_local = dt_util.now()
    utc_time = now.replace(hour=utc_hour, minute=0, second=0, microsecond=0)
    local_hour = dt_util.as_local(utc_time)
    return local_hour.replace(
        year=now_local.year, month=now_local.month, day=now_local.day
    )


def _convert_profile_to_local(values: list[float]) -> str:
    """Convert UTC profile to local.

    Receives a device temperature schedule - 24 values for the day where the index represents the hour of the day in UTC.
    Converts the schedule to string in local time with comma separated values.

    Args:
        values: list of floats representing the 24 hour temperature schedule for the device

    Returns:
        The device temperature schedule in local time - 24 comma separated values.

    """
    profile = [0.0] * 24
    for hour in range(24):
        local_hour = _get_local_hour(hour)
        profile[local_hour.hour] = float(values[hour])

    return ",".join(str(hour_local) for hour_local in profile)


@dataclass(frozen=True, kw_only=True)
class OSOEnergySensorEntityDescription(SensorEntityDescription):
    """Class describing OSO Energy heater sensor entities."""

    value_fn: Callable[[OSOEnergy], StateType]


SENSOR_TYPES: dict[str, OSOEnergySensorEntityDescription] = {
    "profile": OSOEnergySensorEntityDescription(
        key="profile",
        translation_key="profile",
        value_fn=lambda entity_data: _convert_profile_to_local(entity_data.state),
    ),
    "heater_mode": OSOEnergySensorEntityDescription(
        key="heater_mode",
        translation_key="heater_mode",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "auto",
            "manual",
            "off",
            "legionella",
            "powersave",
            "extraenergy",
            "voltage",
            "ffr",
        ],
        value_fn=lambda entity_data: entity_data.state.lower(),
    ),
    "optimization_mode": OSOEnergySensorEntityDescription(
        key="optimization_mode",
        translation_key="optimization_mode",
        device_class=SensorDeviceClass.ENUM,
        options=["off", "oso", "gridcompany", "smartcompany", "advanced"],
        value_fn=lambda entity_data: entity_data.state.lower(),
    ),
    "power_load": OSOEnergySensorEntityDescription(
        key="power_load",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        value_fn=lambda entity_data: entity_data.state,
    ),
    "tapping_capacity": OSOEnergySensorEntityDescription(
        key="tapping_capacity",
        translation_key="tapping_capacity",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value_fn=lambda entity_data: entity_data.state,
    ),
    "capacity_mixed_water_40": OSOEnergySensorEntityDescription(
        key="capacity_mixed_water_40",
        translation_key="capacity_mixed_water_40",
        device_class=SensorDeviceClass.VOLUME,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        value_fn=lambda entity_data: entity_data.state,
    ),
    "v40_min": OSOEnergySensorEntityDescription(
        key="v40_min",
        translation_key="v40_min",
        device_class=SensorDeviceClass.VOLUME,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        value_fn=lambda entity_data: entity_data.state,
    ),
    "v40_level_min": OSOEnergySensorEntityDescription(
        key="v40_level_min",
        translation_key="v40_level_min",
        device_class=SensorDeviceClass.VOLUME,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        value_fn=lambda entity_data: entity_data.state,
    ),
    "v40_level_max": OSOEnergySensorEntityDescription(
        key="v40_level_max",
        translation_key="v40_level_max",
        device_class=SensorDeviceClass.VOLUME,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        value_fn=lambda entity_data: entity_data.state,
    ),
    "volume": OSOEnergySensorEntityDescription(
        key="volume",
        device_class=SensorDeviceClass.VOLUME,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        value_fn=lambda entity_data: entity_data.state,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up OSO Energy sensor."""
    osoenergy = hass.data[DOMAIN][entry.entry_id]
    devices = osoenergy.session.device_list.get("sensor")
    entities = []
    if devices:
        for dev in devices:
            sensor_type = dev.osoEnergyType.lower()
            if sensor_type in SENSOR_TYPES:
                entities.append(
                    OSOEnergySensor(osoenergy, SENSOR_TYPES[sensor_type], dev)
                )

    async_add_entities(entities, True)


class OSOEnergySensor(OSOEnergyEntity[OSOEnergySensorData], SensorEntity):
    """OSO Energy Sensor Entity."""

    entity_description: OSOEnergySensorEntityDescription

    def __init__(
        self,
        instance: OSOEnergy,
        description: OSOEnergySensorEntityDescription,
        entity_data: OSOEnergySensorData,
    ) -> None:
        """Initialize the OSO Energy sensor."""
        super().__init__(instance, entity_data)

        device_id = entity_data.device_id
        self._attr_unique_id = f"{device_id}_{description.key}"
        self.entity_description = description

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.entity_data)

    async def async_update(self) -> None:
        """Update all data for OSO Energy."""
        await self.osoenergy.session.update_data()
        self.entity_data = await self.osoenergy.sensor.get_sensor(self.entity_data)
