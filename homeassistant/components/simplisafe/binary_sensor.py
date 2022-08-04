"""Support for SimpliSafe binary sensors."""
from __future__ import annotations

from simplipy.device import DeviceTypes
from simplipy.device.sensor.v3 import SensorV3
from simplipy.system.v3 import SystemV3

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SimpliSafe, SimpliSafeEntity
from .const import DOMAIN, LOGGER

SUPPORTED_BATTERY_SENSOR_TYPES = [
    DeviceTypes.CARBON_MONOXIDE,
    DeviceTypes.ENTRY,
    DeviceTypes.GLASS_BREAK,
    DeviceTypes.LEAK,
    DeviceTypes.LOCK_KEYPAD,
    DeviceTypes.MOTION,
    DeviceTypes.SIREN,
    DeviceTypes.SMOKE,
    DeviceTypes.TEMPERATURE,
]

TRIGGERED_SENSOR_TYPES = {
    DeviceTypes.CARBON_MONOXIDE: BinarySensorDeviceClass.GAS,
    DeviceTypes.ENTRY: BinarySensorDeviceClass.DOOR,
    DeviceTypes.GLASS_BREAK: BinarySensorDeviceClass.SAFETY,
    DeviceTypes.LEAK: BinarySensorDeviceClass.MOISTURE,
    DeviceTypes.MOTION: BinarySensorDeviceClass.MOTION,
    DeviceTypes.SIREN: BinarySensorDeviceClass.SAFETY,
    DeviceTypes.SMOKE: BinarySensorDeviceClass.SMOKE,
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up SimpliSafe binary sensors based on a config entry."""
    simplisafe = hass.data[DOMAIN][entry.entry_id]

    sensors: list[BatteryBinarySensor | TriggeredBinarySensor] = []

    for system in simplisafe.systems.values():
        if system.version == 2:
            LOGGER.info("Skipping sensor setup for V2 system: %s", system.system_id)
            continue

        for sensor in system.sensors.values():
            if sensor.type in TRIGGERED_SENSOR_TYPES:
                sensors.append(
                    TriggeredBinarySensor(
                        simplisafe,
                        system,
                        sensor,
                        TRIGGERED_SENSOR_TYPES[sensor.type],
                    )
                )
            if sensor.type in SUPPORTED_BATTERY_SENSOR_TYPES:
                sensors.append(BatteryBinarySensor(simplisafe, system, sensor))

    async_add_entities(sensors)


class TriggeredBinarySensor(SimpliSafeEntity, BinarySensorEntity):
    """Define a binary sensor related to whether an entity has been triggered."""

    def __init__(
        self,
        simplisafe: SimpliSafe,
        system: SystemV3,
        sensor: SensorV3,
        device_class: str,
    ) -> None:
        """Initialize."""
        super().__init__(simplisafe, system, device=sensor)

        self._attr_device_class = device_class
        self._device: SensorV3

    @callback
    def async_update_from_rest_api(self) -> None:
        """Update the entity with the provided REST API data."""
        self._attr_is_on = self._device.triggered


class BatteryBinarySensor(SimpliSafeEntity, BinarySensorEntity):
    """Define a SimpliSafe battery binary sensor entity."""

    _attr_device_class = BinarySensorDeviceClass.BATTERY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self, simplisafe: SimpliSafe, system: SystemV3, sensor: SensorV3
    ) -> None:
        """Initialize."""
        super().__init__(simplisafe, system, device=sensor)

        self._attr_name = "Battery"
        self._attr_unique_id = f"{super().unique_id}-battery"
        self._device: SensorV3

    @callback
    def async_update_from_rest_api(self) -> None:
        """Update the entity with the provided REST API data."""
        self._attr_is_on = self._device.low_battery
