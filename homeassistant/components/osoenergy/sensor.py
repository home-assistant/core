"""Support for OSO Energy sensors."""

from collections.abc import Callable
from dataclasses import dataclass

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

from . import OSOEnergyEntity
from .const import DOMAIN


@dataclass(frozen=True, kw_only=True)
class OSOEnergySensorEntityDescription(SensorEntityDescription):
    """Class describing OSO Energy heater sensor entities."""

    value_fn: Callable[[OSOEnergy], StateType]


SENSOR_TYPES: dict[str, OSOEnergySensorEntityDescription] = {
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
