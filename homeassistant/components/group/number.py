# homeassistant/components/group/number.py
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from statistics import mean, median
from typing import Any

import voluptuous as vol

from homeassistant.components.number import (
    DOMAIN as NUMBER_DOMAIN,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.const import CONF_NAME, ATTR_ENTITY_ID, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
import homeassistant.helpers.config_validation as cv

from . import DOMAIN as GROUP_DOMAIN
from .util import (
    GroupEntityTracker,              # create this tiny helper or reuse existing patterns
)

CONF_ENTITIES = "entities"
CONF_MODE = "mode"
CONF_WRITE_TARGET = "write_target"   # "all" | "first" | specific entity_id | "none"

MODES = {"mean", "min", "max", "median", "last"}

PLATFORM_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ENTITIES): cv.entities_domain([NUMBER_DOMAIN, "input_number"]),
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_MODE, default="last"): vol.In(MODES),
        vol.Optional(CONF_WRITE_TARGET, default="none"): vol.Any(
            "none", "all", "first", cv.entity_id
        ),
    }
)

async def async_setup_platform(hass: HomeAssistant,
                               config: ConfigType,
                               async_add_entities,
                               discovery_info: DiscoveryInfoType | None = None) -> None:
    """Set up a number group from YAML."""
    name = config.get(CONF_NAME) or "Number Group"
    entities = config[CONF_ENTITIES]
    mode = config[CONF_MODE]
    write_target = config[CONF_WRITE_TARGET]
    async_add_entities([GroupedNumber(hass, name, entities, mode, write_target)])


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities) -> None:
    """Set up a number group from a config entry."""
    data = entry.data
    name = data.get(CONF_NAME)
    entities = data[CONF_ENTITIES]
    mode = data.get(CONF_MODE, "last")
    write_target = data.get(CONF_WRITE_TARGET, "none")
    async_add_entities([GroupedNumber(hass, name, entities, mode, write_target)])


class GroupedNumber(NumberEntity):
    _attr_has_entity_name = True
    _attr_entity_category = None

    def __init__(self, hass: HomeAssistant, name: str, entity_ids: list[str], mode: str, write_target: str):
        self.hass = hass
        self._attr_name = name
        self._mode = mode
        self._write_target = write_target
        self._entity_ids = entity_ids
        self._current_value: float | None = None
        self._tracker = GroupEntityTracker(hass, entity_ids, self._recompute)

    @property
    def native_value(self) -> float | None:
        return self._current_value

    @callback
    def _recompute(self) -> None:
        vals: list[float] = []
        for eid in self._entity_ids:
            st = self.hass.states.get(eid)
            if not st or st.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                continue
            try:
                vals.append(float(st.state))
            except (TypeError, ValueError):
                continue

        if not vals:
            self._current_value = None
        else:
            if self._mode == "mean":
                self._current_value = mean(vals)
            elif self._mode == "min":
                self._current_value = min(vals)
            elif self._mode == "max":
                self._current_value = max(vals)
            elif self._mode == "median":
                self._current_value = median(vals)
            else:  # "last"
                # last non-unknown by recency from tracker
                last = self._tracker.last_updated_value(float)
                self._current_value = last

        self.async_write_ha_state()

    async def async_set_native_value(self, value: float) -> None:
        """Write behavior — configurable."""
        target = self._write_target
        calls: list[str] = []

        if target == "none":
            return
        elif target == "all":
            calls = self._entity_ids
        elif target == "first":
            calls = self._entity_ids[:1]
        else:
            # assume specific entity_id
            calls = [target] if target in self._entity_ids else []

        for eid in calls:
            # number.set_value for number.*, input_number.set_value for input_number.*
            if eid.startswith("input_number."):
                await self.hass.services.async_call(
                    "input_number", "set_value", {"entity_id": eid, "value": value}, blocking=True
                )
            else:
                await self.hass.services.async_call(
                    "number", "set_value", {"entity_id": eid, "value": value}, blocking=True
                )
