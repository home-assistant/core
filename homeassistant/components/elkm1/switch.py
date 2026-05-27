"""Support for control of ElkM1 outputs (relays)."""

from datetime import timedelta
from math import ceil
from typing import Any

from elkm1_lib.const import ThermostatMode, ThermostatSetting
from elkm1_lib.elements import Element
from elkm1_lib.elk import Elk
from elkm1_lib.outputs import Output
from elkm1_lib.thermostats import Thermostat
import voluptuous as vol

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN, SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, service
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import VolDictType

from . import ElkM1ConfigEntry
from .const import ATTR_DURATION, DOMAIN
from .entity import ElkAttachedEntity, ElkEntity, create_elk_entities
from .models import ELKM1Data

SERVICE_SWITCH_OUTPUT_TURN_ON_FOR = "switch_output_turn_on_for"

ELK_OUTPUT_TURN_ON_FOR_SERVICE_SCHEMA: VolDictType = {
    vol.Required(ATTR_DURATION): vol.All(
        cv.time_period,
        vol.Range(min=timedelta(seconds=1), max=timedelta(seconds=65535)),
    ),
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

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SWITCH_OUTPUT_TURN_ON_FOR,
        entity_domain=SWITCH_DOMAIN,
        schema=ELK_OUTPUT_TURN_ON_FOR_SERVICE_SCHEMA,
        func="async_switch_output_turn_on_for",
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

    async def async_switch_output_turn_on_for(self, duration: timedelta) -> None:
        """Turn on an output for specified length of time."""
        self._element.turn_on(ceil(duration.total_seconds()))


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
        return self._element.mode is ThermostatMode.EMERGENCY_HEAT

    def _elk_set(self, mode: ThermostatMode) -> None:
        """Set the thermostat mode."""
        self._element.set(ThermostatSetting.MODE, mode)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the output."""
        self._elk_set(ThermostatMode.EMERGENCY_HEAT)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the output."""
        self._elk_set(ThermostatMode.EMERGENCY_HEAT)

    async def async_switch_output_turn_on_for(self, duration: timedelta) -> None:
        """Turn on an output for specified length of time: not supported for thermostat."""
        raise HomeAssistantError("supported only on ElkM1 output switch entities")
