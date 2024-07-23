"""Support for SimpliSafe binary sensors."""

from __future__ import annotations

from simplipy.device import DeviceTypes, DeviceV3
from simplipy.device.sensor.v3 import SensorV3
from simplipy.system.v3 import SystemV3

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SimpliSafe, SimpliSafeEntity
from .const import DOMAIN, LOGGER

SUPPORTED_BATTERY_SENSOR_TYPES = [
    DeviceTypes.CARBON_MONOXIDE,
    DeviceTypes.DOORBELL,
    DeviceTypes.ENTRY,
    DeviceTypes.GLASS_BREAK,
    DeviceTypes.KEYCHAIN,
    DeviceTypes.KEYPAD,
    DeviceTypes.LEAK,
    DeviceTypes.LOCK,
    DeviceTypes.LOCK_KEYPAD,
    DeviceTypes.MOTION,
    DeviceTypes.MOTION_V2,
    DeviceTypes.PANIC_BUTTON,
    DeviceTypes.REMOTE,
    DeviceTypes.SIREN,
    DeviceTypes.SMOKE,
    DeviceTypes.SMOKE_AND_CARBON_MONOXIDE,
    DeviceTypes.TEMPERATURE,
]

TRIGGERED_SENSOR_TYPES = {
    DeviceTypes.CARBON_MONOXIDE: BinarySensorDeviceClass.GAS,
    DeviceTypes.ENTRY: BinarySensorDeviceClass.DOOR,
    DeviceTypes.GLASS_BREAK: BinarySensorDeviceClass.SAFETY,
    DeviceTypes.LEAK: BinarySensorDeviceClass.MOISTURE,
    DeviceTypes.MOTION: BinarySensorDeviceClass.MOTION,
    DeviceTypes.MOTION_V2: BinarySensorDeviceClass.MOTION,
    DeviceTypes.SIREN: BinarySensorDeviceClass.SAFETY,
    DeviceTypes.SMOKE: BinarySensorDeviceClass.SMOKE,
    # Although this sensor can technically apply to both smoke and carbon, we use the
    # SMOKE device class for simplicity:
    DeviceTypes.SMOKE_AND_CARBON_MONOXIDE: BinarySensorDeviceClass.SMOKE,
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

        sensors.extend(
            BatteryBinarySensor(simplisafe, system, lock)
            for lock in system.locks.values()
        )

    async_add_entities(sensors)


class TriggeredBinarySensor(SimpliSafeEntity, BinarySensorEntity):
    """Define a binary sensor related to whether an entity has been triggered."""

    def __init__(
        self,
        simplisafe: SimpliSafe,
        system: SystemV3,
        sensor: SensorV3,
        device_class: BinarySensorDeviceClass,
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
        self, simplisafe: SimpliSafe, system: SystemV3, device: DeviceV3
    ) -> None:
        """Initialize."""
        super().__init__(simplisafe, system, device=device)

        self._attr_unique_id = f"{super().unique_id}-battery"
        self._device: DeviceV3

    @callback
    def async_update_from_rest_api(self) -> None:
        """Update the entity with the provided REST API data."""
        self._attr_is_on = self._device.low_battery
