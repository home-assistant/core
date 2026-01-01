"""Binary sensors for Elke27 zones."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
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
    """Set up Elke27 zone binary sensors from a config entry."""
    hub: Elke27Hub = hass.data[DOMAIN][entry.entry_id]
    known_ids: set[int] = set()

    @callback
    def _async_add_zones() -> None:
        entities: list[Elke27ZoneBinarySensor] = []
        for zone_id, zone in _iter_zones(hub.zones):
            if zone_id in known_ids:
                continue
            known_ids.add(zone_id)
            entities.append(Elke27ZoneBinarySensor(hub, entry, zone_id, zone))
        if entities:
            _LOGGER.debug("Adding %s zone entities", len(entities))
            async_add_entities(entities)

    _async_add_zones()
    entry.async_on_unload(hub.async_add_zone_listener(_async_add_zones))


class Elke27ZoneBinarySensor(BinarySensorEntity):
    """Representation of an Elke27 zone."""

    _attr_device_class = BinarySensorDeviceClass.OPENING
    _attr_has_entity_name = True
    _attr_translation_key = "zone"

    def __init__(
        self, hub: Elke27Hub, entry: ConfigEntry, zone_id: int, zone: dict[str, Any]
    ) -> None:
        """Initialize the zone entity."""
        self._hub = hub
        self._entry = entry
        self._zone_id = zone_id
        self._attr_name = zone.get("name") or f"Zone {zone_id}"
        self._attr_unique_id = f"{unique_base(hub, entry)}_zone_{zone_id}"
        self._attr_device_info = device_info_for_entry(hub, entry)

    async def async_added_to_hass(self) -> None:
        """Register for hub updates."""
        self.async_on_remove(self._hub.async_add_zone_listener(self._handle_update))

    @callback
    def _handle_update(self) -> None:
        """Write updated state."""
        self.async_write_ha_state()

    @property
    def is_on(self) -> bool | None:
        """Return if the zone is open."""
        zone = _get_zone(self._hub.zones, self._zone_id)
        if not zone:
            return None
        if isinstance(zone.get("open"), bool):
            return zone["open"]
        if isinstance(zone.get("is_open"), bool):
            return zone["is_open"]
        if isinstance(zone.get("closed"), bool):
            return not zone["closed"]
        state = zone.get("state") or zone.get("status")
        if state is None:
            return None
        normalized = str(state).lower().replace(" ", "_")
        if normalized in {"open", "opened", "violated", "alarm", "triggered"}:
            return True
        if normalized in {"closed", "restored", "normal", "secure"}:
            return False
        return None

    @property
    def available(self) -> bool:
        """Return if the entity is available."""
        return (
            self._hub.is_ready
            and _get_zone(self._hub.zones, self._zone_id) is not None
        )


def _iter_zones(snapshot: Any) -> list[tuple[int, dict[str, Any]]]:
    if isinstance(snapshot, dict):
        zones: list[tuple[int, dict[str, Any]]] = []
        for key, zone in snapshot.items():
            if not isinstance(zone, dict):
                continue
            zone_id = _coerce_zone_id(key, zone)
            if zone_id is None:
                continue
            zones.append((zone_id, zone))
        return zones
    if isinstance(snapshot, list | tuple):
        return [
            (index + 1, zone)
            for index, zone in enumerate(snapshot)
            if isinstance(zone, dict)
        ]
    return []


def _coerce_zone_id(key: Any, zone: dict[str, Any]) -> int | None:
    for candidate in (zone.get("zone_index"), zone.get("index"), key):
        if isinstance(candidate, int):
            return candidate
        if isinstance(candidate, str) and candidate.isdigit():
            return int(candidate)
    return None


def _get_zone(snapshot: Any, zone_id: int) -> dict[str, Any] | None:
    if isinstance(snapshot, dict):
        zone = snapshot.get(zone_id)
        if zone is None:
            zone = snapshot.get(str(zone_id))
        return zone if isinstance(zone, dict) else None
    if isinstance(snapshot, list | tuple):
        index = zone_id - 1
        if 0 <= index < len(snapshot):
            zone = snapshot[index]
            return zone if isinstance(zone, dict) else None
    return None
