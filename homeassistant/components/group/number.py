from __future__ import annotations

from typing import Any, List, Iterable, Tuple

import voluptuous as vol

from homeassistant.components.number import DOMAIN as NUMBER_DOMAIN, NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_TYPE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, callback, State
from homeassistant.helpers.event import async_track_state_change_event
import homeassistant.helpers.config_validation as cv

CONF_NAME = "name"
CONF_ENTITIES = "entities"
CONF_WRITE_TARGET = "write_target"

_STATISTIC_MEASURES = ["max", "mean", "median", "min", "product", "range", "stdev", "sum"]

PARALLEL_UPDATES = 0

PLATFORM_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ENTITIES): cv.entities_domain([NUMBER_DOMAIN, "input_number"]),
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_TYPE, default="mean"): vol.In(_STATISTIC_MEASURES),
        vol.Optional(CONF_WRITE_TARGET, default="none"): vol.Any(
            "none", "all", "first", cv.entity_id
        ),
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    data = entry.data
    name: str = data.get(CONF_NAME) or "Number Group"
    entities: List[str] = data.get(CONF_ENTITIES, [])
    stat: str = data.get(CONF_TYPE, "mean")
    write_target: str = data.get(CONF_WRITE_TARGET, "none")
    async_add_entities([GroupedNumber(hass, name, entities, stat, write_target)])


async def async_setup_platform(
    hass: HomeAssistant, config: dict, async_add_entities, discovery_info=None
):
    name = config.get(CONF_NAME) or "Number Group"
    entities: List[str] = config[CONF_ENTITIES]
    stat: str = config.get(CONF_TYPE, "mean")
    write_target: str = config.get(CONF_WRITE_TARGET, "none")
    async_add_entities([GroupedNumber(hass, name, entities, stat, write_target)])


@callback
def async_create_preview_number(hass: HomeAssistant, name: str, validated_config: dict[str, Any]) -> "GroupedNumber":
    entities: List[str] = validated_config[CONF_ENTITIES]
    stat: str = validated_config.get(CONF_TYPE, "mean")
    write_target: str = validated_config.get(CONF_WRITE_TARGET, "none")
    return GroupedNumber(hass, name, entities, stat, write_target)


class GroupedNumber(NumberEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        name: str,
        entity_ids: List[str],
        stat: str,
        write_target: str,
    ):
        self.hass = hass
        self._attr_name = name
        self._entity_ids = entity_ids
        self._stat = stat
        self._write_target = write_target
        self._value: float | None = None
        self._unsub: Any = None
        self._attr_extra_state_attributes = {ATTR_ENTITY_ID: list(entity_ids)}

    async def async_added_to_hass(self) -> None:
        @callback
        def _on_change(event):
            self._recompute()

        self._unsub = async_track_state_change_event(
            self.hass, self._entity_ids, _on_change
        )
        self._recompute()

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub:
            self._unsub()
            self._unsub = None

    @property
    def available(self) -> bool:
        return any(True for _ in self._iter_member_values())

    @property
    def native_value(self) -> float | None:
        return self._value

    @property
    def native_unit_of_measurement(self) -> str | None:
        unit, *_ = self._collect_meta()
        return unit

    @property
    def native_min_value(self) -> float | None:
        _, min_v, _, _ = self._collect_meta()
        return min_v

    @property
    def native_max_value(self) -> float | None:
        _, _, max_v, _ = self._collect_meta()
        return max_v

    @property
    def native_step(self) -> float | None:
        *_, step_v = self._collect_meta()
        return step_v

    @callback
    def _recompute(self) -> None:
        vals: list[float] = [v for _, v in self._iter_member_values()]

        if not vals:
            self._value = None
        else:
            stat = self._stat
            if stat == "max":
                self._value = max(vals)
            elif stat == "min":
                self._value = min(vals)
            elif stat == "mean":
                self._value = sum(vals) / len(vals)
            elif stat == "median":
                s = sorted(vals)
                n = len(s)
                mid = n // 2
                self._value = s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2
            elif stat == "sum":
                self._value = sum(vals)
            elif stat == "product":
                p = 1.0
                for v in vals:
                    p *= v
                self._value = p
            elif stat == "range":
                self._value = max(vals) - min(vals)
            elif stat == "stdev":
                m = sum(vals) / len(vals)
                self._value = (sum((v - m) ** 2 for v in vals) / len(vals)) ** 0.5
            else:
                self._value = sum(vals) / len(vals)

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
            v = self._clamp_to_member_bounds(eid, value)
            if eid.startswith("input_number."):
                await self.hass.services.async_call(
                    "input_number",
                    "set_value",
                    {"entity_id": eid, "value": v},
                    blocking=True,
                )
            else:
                await self.hass.services.async_call(
                    "number",
                    "set_value",
                    {"entity_id": eid, "value": v},
                    blocking=True,
                )

    def _iter_member_values(self) -> Iterable[Tuple[State, float]]:
        """Yield (State, numeric_value) for valid numeric member states."""
        for eid in self._entity_ids:
            st: State | None = self.hass.states.get(eid)
            if not st or st.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                continue
            try:
                val = float(st.state)
            except (TypeError, ValueError):
                continue
            yield st, val

    def _collect_meta(self) -> tuple[str | None, float | None, float | None, float | None]:
        unit: str | None = None
        unit_mixed = False
        mins: list[float] = []
        maxs: list[float] = []
        steps: list[float] = []

        for st, _ in self._iter_member_values():
            u = st.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
            if u:
                if unit is None:
                    unit = u
                elif unit != u:
                    unit_mixed = True

            def _flt(x: Any) -> float | None:
                try:
                    return float(x)
                except (TypeError, ValueError):
                    return None

            mi = _flt(st.attributes.get("min"))
            ma = _flt(st.attributes.get("max"))
            stp = _flt(st.attributes.get("step"))

            if mi is not None:
                mins.append(mi)
            if ma is not None:
                maxs.append(ma)
            if stp is not None:
                steps.append(stp)

        if unit_mixed:
            unit = None

        min_v = max(mins) if mins else None
        max_v = min(maxs) if maxs else None
        step_v = max(steps) if steps else None

        if (min_v is not None and max_v is not None) and min_v >= max_v:
            min_v = max_v = None

        return unit, min_v, max_v, step_v

    def _clamp_to_member_bounds(self, eid: str, value: float) -> float:
        """Clamp value to a specific member's min/max if present."""
        st = self.hass.states.get(eid)
        if not st:
            return value

        def _flt(x: Any) -> float | None:
            try:
                return float(x)
            except (TypeError, ValueError):
                return None

        mi = _flt(st.attributes.get("min"))
        ma = _flt(st.attributes.get("max"))
        v = value
        if mi is not None:
            v = max(v, mi)
        if ma is not None:
            v = min(v, ma)
        return v
