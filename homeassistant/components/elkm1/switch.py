"""Support for control of ElkM1 outputs (relays)."""

from __future__ import annotations

from typing import Any

from elkm1_lib.const import ThermostatMode, ThermostatSetting
from elkm1_lib.elements import Element
from elkm1_lib.elk import Elk
from elkm1_lib.outputs import Output
from elkm1_lib.thermostats import Thermostat

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import ElkM1ConfigEntry
from .entity import ElkAttachedEntity, ElkEntity, create_elk_entities
from .models import ELKM1Data


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ElkM1ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the Elk-M1 switch platform."""
    elk_data = config_entry.runtime_data
    elk = elk_data.elk
    entities: list[ElkEntity] = []
    create_elk_entities(elk_data, elk.outputs, "output", ElkOutput, entities)
    create_elk_entities(
        elk_data, elk.thermostats, "thermostat", ElkThermostatEMHeat, entities
    )
    async_add_entities(entities)


class ElkOutput(ElkAttachedEntity, SwitchEntity):
    """Elk output as switch."""

    _element: Output

    @property
    def is_on(self) -> bool:
        """Get the current output status."""
        return self._element.output_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the output."""
        self._element.turn_on(0)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the output."""
        self._element.turn_off()


class ElkThermostatEMHeat(ElkEntity, SwitchEntity):
    """Elk Thermostat emergency heat as switch."""

    _element: Thermostat

    def __init__(self, element: Element, elk: Elk, elk_data: ELKM1Data) -> None:
        """Initialize the emergency heat switch."""
        super().__init__(element, elk, elk_data)
        self._unique_id = f"{self._unique_id}emheat"
        self._attr_name = f"{element.name} emergency heat"

    @property
    def is_on(self) -> bool:
        """Get the current emergency heat status."""
        return self._element.mode == ThermostatMode.EMERGENCY_HEAT

    def _elk_set(self, mode: ThermostatMode) -> None:
        """Set the thermostat mode."""
        self._element.set(ThermostatSetting.MODE, mode)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the output."""
        self._elk_set(ThermostatMode.EMERGENCY_HEAT)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the output."""
        self._elk_set(ThermostatMode.EMERGENCY_HEAT)
