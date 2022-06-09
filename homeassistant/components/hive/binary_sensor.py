"""Support for the Hive binary sensors."""
from datetime import timedelta

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HiveEntity
from .const import DOMAIN

PARALLEL_UPDATES = 0
SCAN_INTERVAL = timedelta(seconds=15)


BINARY_SENSOR_TYPES: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key="contactsensor", device_class=BinarySensorDeviceClass.OPENING
    ),
    BinarySensorEntityDescription(
        key="motionsensor",
        device_class=BinarySensorDeviceClass.MOTION,
    ),
    BinarySensorEntityDescription(
        key="Connectivity",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
    ),
    BinarySensorEntityDescription(
        key="SMOKE_CO",
        device_class=BinarySensorDeviceClass.SMOKE,
    ),
    BinarySensorEntityDescription(
        key="DOG_BARK",
        device_class=BinarySensorDeviceClass.SOUND,
    ),
    BinarySensorEntityDescription(
        key="GLASS_BREAK",
        device_class=BinarySensorDeviceClass.SOUND,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Hive thermostat based on a config entry."""

    hive = hass.data[DOMAIN][entry.entry_id]
    devices = hive.session.deviceList.get("binary_sensor")
    entities = []
    if devices:
        for description in BINARY_SENSOR_TYPES:
            for dev in devices:
                if dev["hiveType"] == description.key:
                    entities.append(HiveBinarySensorEntity(hive, dev, description))
    async_add_entities(entities, True)


class HiveBinarySensorEntity(HiveEntity, BinarySensorEntity):
    """Representation of a Hive binary sensor."""

    def __init__(self, hive, hive_device, entity_description):
        """Initialise hive binary sensor."""
        super().__init__(hive, hive_device)
        self.entity_description = entity_description

    async def async_update(self):
        """Update all Node data from Hive."""
        await self.hive.session.updateData(self.device)
        self.device = await self.hive.sensor.getSensor(self.device)
        self.attributes = self.device.get("attributes", {})
        self._attr_is_on = self.device["status"]["state"]
        if self.device["hiveType"] != "Connectivity":
            self._attr_available = self.device["deviceData"].get("online")
        else:
            self._attr_available = True
