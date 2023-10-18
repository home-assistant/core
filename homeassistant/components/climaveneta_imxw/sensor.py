"""Support for the Mitsubishi-Climaveneta iMXW fancoil series."""
from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import ClimavenetaIMXWCoordinator
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up a config entry."""
    coordinator: ClimavenetaIMXWCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list = []

    entities.append(ClimavenetaIMXWSensor(coordinator))
    async_add_entities(entities)


class ClimavenetaIMXWSensor(
    CoordinatorEntity[ClimavenetaIMXWCoordinator], SensorEntity
):
    """Representation of a Sensor."""

    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(self, coordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self._name = "Water Temperature"
        self._state = 0.0
        self._attr_unique_id = (
            f"{str(coordinator.hub.name)}_{str(self._name)}_{str(coordinator.slave_id)}"
        )

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def device_class(self) -> SensorDeviceClass | None:
        """Return the device class."""
        return SensorDeviceClass.TEMPERATURE

    #    @property
    #    def unique_id(self) -> str:
    #        """Return a unique ID."""
    #        return f"{self.coordinator.hub}-{self.coordinator.slave_id}-water_temperature"

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if self.coordinator.data_modbus is not None:
            self._state = self.coordinator.data_modbus["exchanger_temperature"]

        return self._state

    async def async_update(self) -> None:
        """Retrieve latest state."""
        self._state = self.coordinator.data_modbus["exchanger_temperature"]
