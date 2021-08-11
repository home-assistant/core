"""Support for SimpliSafe freeze sensor."""
from simplipy.entity import EntityTypes

from homeassistant.components.sensor import SensorEntity
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
    simplisafe = hass.data[DOMAIN][DATA_CLIENT][entry.entry_id]
    sensors = []

    for system in simplisafe.systems.values():
        if system.version == 2:
            LOGGER.info("Skipping sensor setup for V2 system: %s", system.system_id)
            continue

        for sensor in system.sensors.values():
            if sensor.type == EntityTypes.temperature:
                sensors.append(SimplisafeFreezeSensor(simplisafe, system, sensor))

    async_add_entities(sensors)


class SimplisafeFreezeSensor(SimpliSafeBaseSensor, SensorEntity):
    """Define a SimpliSafe freeze sensor entity."""

    _attr_device_class = DEVICE_CLASS_TEMPERATURE
    _attr_unit_of_measurement = TEMP_FAHRENHEIT

    @callback
    def async_update_from_rest_api(self) -> None:
        """Update the entity with the provided REST API data."""
        self._attr_state = self._sensor.temperature
