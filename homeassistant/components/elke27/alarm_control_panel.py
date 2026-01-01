"""Alarm control panel platform for Elke27 areas."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .entity import device_info_for_entry, unique_base
from .hub import Elke27Hub

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Elke27 area alarm control panels from a config entry."""
    hub: Elke27Hub = hass.data[DOMAIN][entry.entry_id]
    known_ids: set[int] = set()

    @callback
    def _async_add_areas() -> None:
        entities: list[Elke27AreaAlarmControlPanel] = []
        for area_id, area in _iter_areas(hub.areas):
            if area_id in known_ids:
                continue
            known_ids.add(area_id)
            entities.append(Elke27AreaAlarmControlPanel(hub, entry, area_id, area))
        if entities:
            _LOGGER.debug("Adding %s area entities", len(entities))
            async_add_entities(entities)

    _async_add_areas()
    entry.async_on_unload(hub.async_add_area_listener(_async_add_areas))


class Elke27AreaAlarmControlPanel(AlarmControlPanelEntity):
    """Representation of an Elke27 area."""

    _attr_has_entity_name = True
    _attr_supported_features = AlarmControlPanelEntityFeature(0)

    def __init__(
        self, hub: Elke27Hub, entry: ConfigEntry, area_id: int, area: dict[str, Any]
    ) -> None:
        """Initialize the area entity."""
        self._hub = hub
        self._entry = entry
        self._area_id = area_id
        self._attr_name = area.get("name") or f"Area {area_id}"
        self._attr_unique_id = f"{unique_base(hub, entry)}_area_{area_id}"
        self._attr_device_info = device_info_for_entry(hub, entry)

    async def async_added_to_hass(self) -> None:
        """Register for hub updates."""
        self.async_on_remove(self._hub.async_add_area_listener(self._handle_update))

    @callback
    def _handle_update(self) -> None:
        """Write updated state."""
        self.async_write_ha_state()

    @property
    def state(self) -> AlarmControlPanelState | None:
        """Return the current state."""
        area = _get_area(self._hub.areas, self._area_id)
        if not area:
            return None
        state = area.get("state") or area.get("status")
        if not state:
            return None
        return _map_state(str(state))

    @property
    def available(self) -> bool:
        """Return if the entity is available."""
        return self._hub.is_ready and _get_area(self._hub.areas, self._area_id) is not None


def _iter_areas(snapshot: Any) -> list[tuple[int, dict[str, Any]]]:
    if isinstance(snapshot, dict) and isinstance(snapshot.get("areas"), dict | list | tuple):
        snapshot = snapshot["areas"]
    if isinstance(snapshot, dict):
        areas: list[tuple[int, dict[str, Any]]] = []
        for key, area in snapshot.items():
            if not isinstance(area, dict):
                continue
            area_id = _coerce_area_id(key, area)
            if area_id is None:
                continue
            areas.append((area_id, area))
        return areas
    if isinstance(snapshot, list | tuple):
        return [
            (index + 1, area)
            for index, area in enumerate(snapshot)
            if isinstance(area, dict)
        ]
    return []


def _coerce_area_id(key: Any, area: dict[str, Any]) -> int | None:
    for candidate in (area.get("area_id"), area.get("area_index"), area.get("index"), key):
        if isinstance(candidate, int):
            return candidate
        if isinstance(candidate, str) and candidate.isdigit():
            return int(candidate)
    return None


def _get_area(snapshot: Any, area_id: int) -> dict[str, Any] | None:
    if isinstance(snapshot, dict) and isinstance(snapshot.get("areas"), dict | list | tuple):
        snapshot = snapshot["areas"]
    if isinstance(snapshot, dict):
        area = snapshot.get(area_id)
        if area is None:
            area = snapshot.get(str(area_id))
        return area if isinstance(area, dict) else None
    if isinstance(snapshot, list | tuple):
        index = area_id - 1
        if 0 <= index < len(snapshot):
            area = snapshot[index]
            return area if isinstance(area, dict) else None
    return None


def _map_state(state: str) -> AlarmControlPanelState | None:
    normalized = state.lower().replace(" ", "_")
    return {
        "disarmed": AlarmControlPanelState.DISARMED,
        "armed_home": AlarmControlPanelState.ARMED_HOME,
        "armed_away": AlarmControlPanelState.ARMED_AWAY,
        "armed_night": AlarmControlPanelState.ARMED_NIGHT,
        "armed_vacation": AlarmControlPanelState.ARMED_VACATION,
        "armed_custom_bypass": AlarmControlPanelState.ARMED_CUSTOM_BYPASS,
        "arming": AlarmControlPanelState.ARMING,
        "pending": AlarmControlPanelState.PENDING,
        "triggered": AlarmControlPanelState.TRIGGERED,
    }.get(normalized)
