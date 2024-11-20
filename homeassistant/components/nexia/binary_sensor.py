"""Support for Nexia / Trane XL Thermostats."""

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import NexiaThermostatEntity
from .types import NexiaConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: NexiaConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors for a Nexia device."""
    coordinator = config_entry.runtime_data
    nexia_home = coordinator.nexia_home

    entities = []
    for thermostat_id in nexia_home.get_thermostat_ids():
        thermostat = nexia_home.get_thermostat_by_id(thermostat_id)
        entities.append(
            NexiaBinarySensor(
                coordinator, thermostat, "is_blower_active", "blower_active"
            )
        )
        if thermostat.has_emergency_heat():
            entities.append(
                NexiaBinarySensor(
                    coordinator,
                    thermostat,
                    "is_emergency_heat_active",
                    "emergency_heat_active",
                )
            )

    async_add_entities(entities)


class NexiaBinarySensor(NexiaThermostatEntity, BinarySensorEntity):
    """Provides Nexia BinarySensor support."""

    def __init__(self, coordinator, thermostat, sensor_call, translation_key):
        """Initialize the nexia sensor."""
        super().__init__(
            coordinator,
            thermostat,
            unique_id=f"{thermostat.thermostat_id}_{sensor_call}",
        )
        self._call = sensor_call
        self._state = None
        self._attr_translation_key = translation_key

    @property
    def is_on(self):
        """Return the status of the sensor."""
        return getattr(self._thermostat, self._call)()
