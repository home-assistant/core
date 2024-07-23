"""Support for Nexia / Trane XL Thermostats."""

from __future__ import annotations

from nexia.home import NexiaHome
from nexia.thermostat import NexiaThermostat

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import NexiaDataUpdateCoordinator
from .entity import NexiaThermostatEntity
from .util import percent_conv


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors for a Nexia device."""
    coordinator: NexiaDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    nexia_home: NexiaHome = coordinator.nexia_home

    entities: list[NexiaThermostatEntity] = []
    for thermostat_id in nexia_home.get_thermostat_ids():
        thermostat = nexia_home.get_thermostat_by_id(thermostat_id)
        if thermostat.has_variable_fan_speed():
            entities.append(
                NexiaFanSpeedEntity(
                    coordinator, thermostat, thermostat.get_variable_fan_speed_limits()
                )
            )
    async_add_entities(entities)


class NexiaFanSpeedEntity(NexiaThermostatEntity, NumberEntity):
    """Provides Nexia Fan Speed support."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_translation_key = "fan_speed"

    def __init__(
        self,
        coordinator: NexiaDataUpdateCoordinator,
        thermostat: NexiaThermostat,
        valid_range: tuple[float, float],
    ) -> None:
        """Initialize the entity."""
        super().__init__(
            coordinator,
            thermostat,
            unique_id=f"{thermostat.thermostat_id}_fan_speed_setpoint",
        )
        min_value, max_value = valid_range
        self._attr_native_min_value = percent_conv(min_value)
        self._attr_native_max_value = percent_conv(max_value)

    @property
    def native_value(self) -> float:
        """Return the current value."""
        fan_speed = self._thermostat.get_fan_speed_setpoint()
        return percent_conv(fan_speed)

    async def async_set_native_value(self, value: float) -> None:
        """Set a new value."""
        await self._thermostat.set_fan_setpoint(value / 100)
        self._signal_thermostat_update()
