"""Support for the Hive binary sensors."""

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HiveConfigEntry
from .coordinator import HiveDataUpdateCoordinator
from .entity import HiveEntity


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
    hass: HomeAssistant,
    entry: HiveConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Hive thermostat based on a config entry."""

    coordinator = entry.runtime_data

    sensors: list[BinarySensorEntity] = []

    devices = coordinator.hive.session.deviceList.get("binary_sensor") or []
    sensors.extend(
        HiveBinarySensorEntity(coordinator, dev, description)
        for dev in devices
        for description in BINARY_SENSOR_TYPES
        if dev["hiveType"] == description.key
    )

    devices = coordinator.hive.session.deviceList.get("sensor") or []
    sensors.extend(
        HiveSensorEntity(coordinator, dev, description)
        for dev in devices
        for description in SENSOR_TYPES
        if dev["hiveType"] == description.key
    )

    async_add_entities(sensors, True)


class HiveBinarySensorEntity(HiveEntity, BinarySensorEntity):
    """Representation of a Hive binary sensor."""

    def __init__(
        self,
        coordinator: HiveDataUpdateCoordinator,
        hive_device: dict[str, Any],
        entity_description: BinarySensorEntityDescription,
    ) -> None:
        """Initialise hive binary sensor."""
        super().__init__(coordinator, hive_device)
        self.entity_description = entity_description

    @property
    def available(self) -> bool:
        """Return True if the entity is available."""
        if self.device["hiveType"] != "Connectivity":
            return (
                self.coordinator.last_update_success
                and bool(self.device["deviceData"].get("online"))
                and "status" in self.device
            )
        return self.coordinator.last_update_success

    @callback
    def _update_state_from_device(self) -> None:
        """Update binary sensor attributes from device data."""
        self.attributes = self.device.get("attributes", {})
        if self.available:
            self._attr_is_on = self.device["status"].get("state")


class HiveSensorEntity(HiveEntity, BinarySensorEntity):
    """Hive Sensor Entity."""

    def __init__(
        self,
        coordinator: HiveDataUpdateCoordinator,
        hive_device: dict[str, Any],
        entity_description: BinarySensorEntityDescription,
    ) -> None:
        """Initialise hive sensor."""
        super().__init__(coordinator, hive_device)
        self.entity_description = entity_description

    @callback
    def _update_state_from_device(self) -> None:
        """Update sensor attributes from device data."""
        if self.available:
            self._attr_is_on = self.device["status"]["state"] == "ON"
