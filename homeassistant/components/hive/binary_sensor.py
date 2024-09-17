"""Support for the Hive binary sensors."""

from datetime import timedelta
from typing import Any

from apyhiveapi import Hive

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

SENSOR_TYPES: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key="Heating_State",
        translation_key="heating",
    ),
    BinarySensorEntityDescription(
        key="Heating_Boost",
        translation_key="heating",
    ),
    BinarySensorEntityDescription(
        key="Hotwater_State",
        translation_key="hot_water",
    ),
    BinarySensorEntityDescription(
        key="Hotwater_Boost",
        translation_key="hot_water",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Hive thermostat based on a config entry."""

    hive = hass.data[DOMAIN][entry.entry_id]

    sensors: list[BinarySensorEntity] = []

    devices = hive.session.deviceList.get("binary_sensor")
    sensors.extend(
        HiveBinarySensorEntity(hive, dev, description)
        for dev in devices
        for description in BINARY_SENSOR_TYPES
        if dev["hiveType"] == description.key
    )

    devices = hive.session.deviceList.get("sensor")
    sensors.extend(
        HiveSensorEntity(hive, dev, description)
        for dev in devices
        for description in SENSOR_TYPES
        if dev["hiveType"] == description.key
    )

    async_add_entities(sensors, True)


class HiveBinarySensorEntity(HiveEntity, BinarySensorEntity):
    """Representation of a Hive binary sensor."""

    def __init__(
        self,
        hive: Hive,
        hive_device: dict[str, Any],
        entity_description: BinarySensorEntityDescription,
    ) -> None:
        """Initialise hive binary sensor."""
        super().__init__(hive, hive_device)
        self.entity_description = entity_description

    async def async_update(self) -> None:
        """Update all Node data from Hive."""
        await self.hive.session.updateData(self.device)
        self.device = await self.hive.sensor.getSensor(self.device)
        self.attributes = self.device.get("attributes", {})
        self._attr_is_on = self.device["status"]["state"]
        if self.device["hiveType"] != "Connectivity":
            self._attr_available = self.device["deviceData"].get("online")
        else:
            self._attr_available = True


class HiveSensorEntity(HiveEntity, BinarySensorEntity):
    """Hive Sensor Entity."""

    def __init__(
        self,
        hive: Hive,
        hive_device: dict[str, Any],
        entity_description: BinarySensorEntityDescription,
    ) -> None:
        """Initialise hive sensor."""
        super().__init__(hive, hive_device)
        self.entity_description = entity_description

    async def async_update(self) -> None:
        """Update all Node data from Hive."""
        await self.hive.session.updateData(self.device)
        self.device = await self.hive.sensor.getSensor(self.device)
        self._attr_is_on = self.device["status"]["state"] == "ON"
        self._attr_available = self.device["deviceData"].get("online")
