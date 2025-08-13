from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.number import (
    DOMAIN as NUMBER_DOMAIN,
    NumberEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, callback, State
import homeassistant.helpers.config_validation as cv

CONF_NAME = "name"
CONF_ENTITIES = "entities"
CONF_WRITE_TARGET = "write_target" 

PLATFORM_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ENTITIES): cv.entities_domain([NUMBER_DOMAIN, "input_number"]),
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_WRITE_TARGET, default="none"): vol.Any(
            "none", "all", "first", cv.entity_id
        ),
    }
)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    data = entry.data
    name = data.get(CONF_NAME) or "Number Group"
    entities: list[str] = data.get(CONF_ENTITIES, [])
    write_target: str = data.get(CONF_WRITE_TARGET, "none")
    async_add_entities([GroupedNumber(hass, name, entities, write_target)])

async def async_setup_platform(hass: HomeAssistant, config, async_add_entities, discovery_info=None):
    name = config.get(CONF_NAME) or "Number Group"
    entities: list[str] = config[CONF_ENTITIES]
    write_target: str = config.get(CONF_WRITE_TARGET, "none")
    async_add_entities([GroupedNumber(hass, name, entities, write_target)])

class GroupedNumber(NumberEntity):
    _attr_has_entity_name = True

    def __init__(self, hass: HomeAssistant, name: str, entity_ids: list[str], write_target: str):
        self.hass = hass
        self._attr_name = name
        self._entity_ids = entity_ids
        self._write_target = write_target
        self._value: float | None = None
        self._unsub = None

    async def async_added_to_hass(self) -> None:
        @callback
        def _state_changed(event):
            self._recompute()
        self._unsub = self.hass.bus.async_listen("state_changed", _state_changed)
        self._recompute()

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub:
            self._unsub()
            self._unsub = None

    @property
    def native_value(self) -> float | None:
        return self._value

    @callback
    def _recompute(self) -> None:
        
        newest: tuple[float, float] | None = None 
        for eid in self._entity_ids:
            st: State | None = self.hass.states.get(eid)
            if not st or st.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                continue
            try:
                val = float(st.state)
            except (TypeError, ValueError):
                continue
            ts = st.last_updated.timestamp() if st.last_updated else 0.0
            if newest is None or ts > newest[0]:
                newest = (ts, val)

        self._value = newest[1] if newest else None
        self.async_write_ha_state()

    async def async_set_native_value(self, value: float) -> None:
        target = self._write_target
        if target == "none":
            return
        if target == "all":
            targets = self._entity_ids
        elif target == "first":
            targets = self._entity_ids[:1]
        else:
            targets = [target] if target in self._entity_ids else []

        for eid in targets:
            if eid.startswith("input_number."):
                await self.hass.services.async_call(
                    "input_number", "set_value", {"entity_id": eid, "value": value}, blocking=True
                )
            else:
                await self.hass.services.async_call(
                    "number", "set_value", {"entity_id": eid, "value": value}, blocking=True
                )
