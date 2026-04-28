"""Support for control of ElkM1 outputs (relays)."""

from __future__ import annotations

from typing import Any

from elkm1_lib.const import ThermostatMode, ThermostatSetting
from elkm1_lib.elements import Element
from elkm1_lib.elk import Elk
from elkm1_lib.outputs import Output
from elkm1_lib.thermostats import Thermostat
import voluptuous as vol

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import VolDictType

from . import ElkM1ConfigEntry
from .const import ATTR_VALUE
from .entity import ElkAttachedEntity, ElkEntity, create_elk_entities
from .models import ELKM1Data

SERVICE_SWITCH_OUTPUT_TURN_ON = "switch_output_turn_on"

ELK_OUTPUT_TURN_ON_SERVICE_SCHEMA: VolDictType = {
    vol.Required(ATTR_VALUE): vol.All(vol.Coerce(int), vol.Range(0, 65535))
}


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

    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(
        SERVICE_SWITCH_OUTPUT_TURN_ON,
        ELK_OUTPUT_TURN_ON_SERVICE_SCHEMA,
        "async_switch_output_turn_on",
    )


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

    async def async_switch_output_turn_on(self, value: int | None = None) -> None:
        """Set the value of a counter on the panel."""
        if not isinstance(self, ElkOutput):
            raise HomeAssistantError("supported only on ElkM1 Outputs")
        if value is not None:
            self._element.turn_on(value)


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
