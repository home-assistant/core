"""Support for Rheem EcoNet thermostats with variable fan speeds and fan modes."""

from __future__ import annotations

from homeassistant.components.select import ENTITY_ID_FORMAT, SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from pyeconet.equipment import EquipmentType
from pyeconet.equipment.thermostat import (
    Thermostat,
    ThermostatFanMode,
)

from . import EconetConfigEntry
from .entity import EcoNetEntity


async def async_setup_entry(
        hass: HomeAssistant,
        entry: EconetConfigEntry,
        async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the econet thermostat select entity."""
    equipment = entry.runtime_data
    for thermostat in equipment[EquipmentType.THERMOSTAT]:
        if thermostat.supports_fan_mode:
            async_add_entities(
                [EconetFanModeSelect(thermostat)]
            )


class EconetFanModeSelect(EcoNetEntity[Thermostat], SelectEntity):
    """Select entity."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, thermostat: Thermostat) -> None:
        """Initialize EcoNet platform."""
        super().__init__(thermostat)
        self._attr_name = f"{thermostat.device_name} fan mode"
        self._attr_unique_id = (
            f"{thermostat.device_id}_{thermostat.device_name}_fan_mode"
        )

    @property
    def options(self) -> list[str]:
        """Return available select options."""
        return [e.name for e in self._econet.fan_modes]

    @property
    def current_option(self) -> str:
        """Return current select option."""
        return self._econet.fan_mode.name

    def select_option(self, option: str) -> None:
        """Set the selected option."""
        self._econet.set_fan_mode(ThermostatFanMode.by_string(option))

