"""Support for SimpliSafe freeze sensor."""
from __future__ import annotations

from simplipy.device import DeviceTypes
from simplipy.device.sensor.v3 import SensorV3
from simplipy.system.v3 import SystemV3

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import TEMP_FAHRENHEIT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SimpliSafe, SimpliSafeEntity
from .const import DOMAIN, LOGGER


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up SimpliSafe freeze sensors based on a config entry."""
    simplisafe = hass.data[DOMAIN][entry.entry_id]
    sensors = []

    for system in simplisafe.systems.values():
        if system.version == 2:
            LOGGER.info("Skipping sensor setup for V2 system: %s", system.system_id)
            continue

        for sensor in system.sensors.values():
            if sensor.type == DeviceTypes.TEMPERATURE:
                sensors.append(SimplisafeFreezeSensor(simplisafe, system, sensor))

    async_add_entities(sensors)


class SimplisafeFreezeSensor(SimpliSafeEntity, SensorEntity):
    """Define a SimpliSafe freeze sensor entity."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = TEMP_FAHRENHEIT
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self, simplisafe: SimpliSafe, system: SystemV3, sensor: SensorV3
    ) -> None:
        """Initialize."""
        super().__init__(simplisafe, system, device=sensor)

        self._device: SensorV3

    @callback
    def async_update_from_rest_api(self) -> None:
        """Update the entity with the provided REST API data."""
        self._attr_native_value = self._device.temperature
