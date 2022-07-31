"""Support for Nexia / Trane XL Thermostats."""
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import NexiaDataUpdateCoordinator
from .entity import NexiaThermostatEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors for a Nexia device."""
    coordinator: NexiaDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    nexia_home = coordinator.nexia_home

    entities = []
    for thermostat_id in nexia_home.get_thermostat_ids():
        thermostat = nexia_home.get_thermostat_by_id(thermostat_id)
        entities.append(
            NexiaBinarySensor(
                coordinator, thermostat, "is_blower_active", "Blower Active"
            )
        )
        if thermostat.has_emergency_heat():
            entities.append(
                NexiaBinarySensor(
                    coordinator,
                    thermostat,
                    "is_emergency_heat_active",
                    "Emergency Heat Active",
                )
            )

    async_add_entities(entities)


class NexiaBinarySensor(NexiaThermostatEntity, BinarySensorEntity):
    """Provices Nexia BinarySensor support."""

    def __init__(self, coordinator, thermostat, sensor_call, sensor_name):
        """Initialize the nexia sensor."""
        super().__init__(
            coordinator,
            thermostat,
            name=f"{thermostat.get_name()} {sensor_name}",
            unique_id=f"{thermostat.thermostat_id}_{sensor_call}",
        )
        self._call = sensor_call
        self._state = None

    @property
    def is_on(self):
        """Return the status of the sensor."""
        return getattr(self._thermostat, self._call)()
