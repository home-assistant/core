"""Support for using switch with ecoNet thermostats."""

from __future__ import annotations

import logging
from typing import Any

from pyeconet.equipment import EquipmentType
from pyeconet.equipment.thermostat import ThermostatOperationMode

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, EQUIPMENT
from .entity import EcoNetEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the ecobee thermostat switch entity."""
    equipment = hass.data[DOMAIN][EQUIPMENT][entry.entry_id]
    async_add_entities(
        EcoNetSwitchAuxHeatOnly(thermostat)
        for thermostat in equipment[EquipmentType.THERMOSTAT]
    )


class EcoNetSwitchAuxHeatOnly(EcoNetEntity, SwitchEntity):
    """Representation of a aux_heat_only EcoNet switch."""

    def __init__(self, thermostat) -> None:
        """Initialize EcoNet ventilator platform."""
        super().__init__(thermostat)
        self._attr_name = f"{thermostat.device_name} emergency heat"
        self._attr_unique_id = (
            f"{thermostat.device_id}_{thermostat.device_name}_auxheat"
        )

    def turn_on(self, **kwargs: Any) -> None:
        """Set the hvacMode to auxHeatOnly."""
        self._econet.set_mode(ThermostatOperationMode.EMERGENCY_HEAT)

    def turn_off(self, **kwargs: Any) -> None:
        """Set the hvacMode back to the prior setting."""
        self._econet.set_mode(ThermostatOperationMode.HEATING)

    @property
    def is_on(self) -> bool:
        """Return true if auxHeatOnly mode is active."""
        return self._econet.mode == ThermostatOperationMode.EMERGENCY_HEAT
