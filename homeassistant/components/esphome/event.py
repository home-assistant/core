"""Support for ESPHome event components."""

from functools import partial
import math
from typing import override

from aioesphomeapi import EntityInfo, Event, EventInfo, EventVariableType

from homeassistant.components.event import EventDeviceClass, EventEntity
from homeassistant.core import callback
from homeassistant.util.enum import try_parse_enum

from .entity import EsphomeEntity, platform_async_setup_entry

PARALLEL_UPDATES = 0

_VALUE_FIELD: dict[EventVariableType | None, str] = {
    EventVariableType.BOOL: "bool_",
    EventVariableType.INT: "int_",
    EventVariableType.FLOAT: "float_",
    EventVariableType.STRING: "string_",
}


class EsphomeEvent(EsphomeEntity[EventInfo, Event], EventEntity):
    """An event implementation for ESPHome."""

    @callback
    @override
    def _on_static_info_update(self, static_info: EntityInfo) -> None:
        """Set attrs from static info."""
        super()._on_static_info_update(static_info)
        static_info = self._static_info
        if event_types := static_info.event_types:
            self._attr_event_types = event_types
        self._attr_device_class = try_parse_enum(
            EventDeviceClass, static_info.device_class
        )

    @callback
    @override
    def _on_state_update(self) -> None:
        self._update_state_from_entry_data()
        state = self._state
        variables = self._static_info.variables
        attributes: dict[str, bool | int | float | str | None] = {}
        for value in state.values:
            if value.index >= len(variables):
                continue
            variable = variables[value.index]
            # types this version does not know are skipped
            if (field := _VALUE_FIELD.get(variable.type)) is None:
                continue
            attribute = getattr(value, field)
            # Home Assistant doesn't use NaN or inf values in the state machine
            if isinstance(attribute, float) and not math.isfinite(attribute):
                attribute = None
            attributes[variable.name] = attribute
        self._trigger_event(state.event_type, attributes or None)
        self.async_write_ha_state()

    @callback
    @override
    def _on_device_update(self) -> None:
        """Call when device updates or entry data changes."""
        super()._on_device_update()
        if self._entry_data.available:
            # Event entities should go available directly
            # when the device comes online and not wait
            # for the next data push.
            self.async_write_ha_state()


async_setup_entry = partial(
    platform_async_setup_entry,
    info_type=EventInfo,
    entity_type=EsphomeEvent,
    state_type=Event,
)
