"""Support for SimpliSafe freeze sensor."""

from __future__ import annotations

from typing import cast

from simplipy.device import DeviceTypes
from simplipy.device.sensor.v3 import SensorV3
from simplipy.system.v3 import SystemV3

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SimpliSafe, SimpliSafeConfigEntry
from .const import LOGGER
from .entity import SimpliSafeEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SimpliSafeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up SimpliSafe freeze sensors based on a config entry."""
    simplisafe = entry.runtime_data
    sensors: list[SimplisafeFreezeSensor] = []

    for system in simplisafe.systems.values():
        if system.version == 2:
            LOGGER.warning("Skipping sensor setup for V2 system: %s", system.system_id)
            continue

        sensors.extend(
            SimplisafeFreezeSensor(
                simplisafe, cast(SystemV3, system), cast(SensorV3, sensor)
            )
            for sensor in system.sensors.values()
            if sensor.type == DeviceTypes.TEMPERATURE
        )

    async_add_entities(sensors)


class SimplisafeFreezeSensor(SimpliSafeEntity, SensorEntity):
    """Define a SimpliSafe freeze sensor entity."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.FAHRENHEIT
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
