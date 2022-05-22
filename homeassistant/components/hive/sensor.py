"""Support for the Hive sensors."""
from datetime import timedelta

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, POWER_KILO_WATT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HiveEntity
from .const import DOMAIN

PARALLEL_UPDATES = 0
SCAN_INTERVAL = timedelta(seconds=15)

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(key="Heating_Mode", icon="mdi:radiator"),
    SensorEntityDescription(key="Hotwater_Mode", icon="mdi:water-pump"),
    SensorEntityDescription(key="Hotwater_Boost", icon="mdi:water-pump"),
    SensorEntityDescription(key="Mode", icon="mdi:eye"),
    SensorEntityDescription(
        key="Battery",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="Availability",
        icon="mdi:check-circle",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="Connectivity",
        icon="mdi:check-circle",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="Power",
        native_unit_of_measurement=POWER_KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Hive thermostat based on a config entry."""
    hive = hass.data[DOMAIN][entry.entry_id]
    devices = hive.session.deviceList.get("sensor")
    entities = []
    if devices:
        for description in SENSOR_TYPES:
            for dev in devices:
                if dev["hiveType"] == description.key:
                    entities.append(HiveSensorEntity(hive, dev, description))
    async_add_entities(entities, True)


class HiveSensorEntity(HiveEntity, SensorEntity):
    """Hive Sensor Entity."""

    def __init__(self, hive, hive_device, entity_description):
        """Initialise hive sensor."""
        super().__init__(hive, hive_device)
        self.entity_description = entity_description

    async def async_update(self):
        """Update all Node data from Hive."""
        await self.hive.session.updateData(self.device)
        self.device = await self.hive.sensor.getSensor(self.device)
        if self.entity_description.key != "Availability":
            self._attr_available = self.device["deviceData"].get("online")
        else:
            self._attr_available = True
        if self._attr_available or self.entity_description.key == "Availability":
            self._attr_native_value = self.device["status"]["state"]
