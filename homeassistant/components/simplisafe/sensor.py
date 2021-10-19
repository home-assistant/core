"""Support for SimpliSafe freeze sensor."""
from typing import TYPE_CHECKING

from simplipy.device import DeviceTypes
from simplipy.device.sensor.v3 import SensorV3

from homeassistant.components.sensor import STATE_CLASS_MEASUREMENT, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import DEVICE_CLASS_TEMPERATURE, TEMP_FAHRENHEIT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SimpliSafeBaseSensor
from .const import DATA_CLIENT, DOMAIN, LOGGER


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up SimpliSafe freeze sensors based on a config entry."""
    simplisafe = hass.data[DOMAIN][entry.entry_id][DATA_CLIENT]
    sensors = []

    for system in simplisafe.systems.values():
        if system.version == 2:
            LOGGER.info("Skipping sensor setup for V2 system: %s", system.system_id)
            continue

        for sensor in system.sensors.values():
            if sensor.type == DeviceTypes.temperature:
                sensors.append(SimplisafeFreezeSensor(simplisafe, system, sensor))

    async_add_entities(sensors)


class SimplisafeFreezeSensor(SimpliSafeBaseSensor, SensorEntity):
    """Define a SimpliSafe freeze sensor entity."""

    _attr_device_class = DEVICE_CLASS_TEMPERATURE
    _attr_native_unit_of_measurement = TEMP_FAHRENHEIT
    _attr_state_class = STATE_CLASS_MEASUREMENT

    @callback
    def async_update_from_rest_api(self) -> None:
        """Update the entity with the provided REST API data."""
        if TYPE_CHECKING:
            assert isinstance(self._sensor, SensorV3)
        self._attr_native_value = self._sensor.temperature
