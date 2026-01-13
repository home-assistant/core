"""Binary sensors for Elke27 zones."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any, Iterable

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .entity import device_info_for_entry, sanitize_name, unique_base
from .hub import Elke27Hub

_LOGGER = logging.getLogger(__name__)

_ZONE_ICON_BY_DEFINITION = {
    "UNDEFINED": "mdi:help-circle-outline",
    "BURG EE DELAY": "mdi:door-closed-lock",
    "BURG PERIM INST": "mdi:window-closed",
    "BURG INTERIOR": "mdi:motion-sensor",
    "BURG 24HR": "mdi:shield-alert",
    "BURG BOX TAMPER": "mdi:shield-off-outline",
    "FIRE": "mdi:fire",
    "CARBON MONOXIDE": "mdi:molecule-co",
    "PANIC": "mdi:alert-octagon",
    "MEDICAL": "mdi:medical-bag",
    "AUTOMATION": "mdi:home-automation",
    "POWER SUPERVISION": "mdi:power",
    "WATER": "mdi:water",
    "HILO TEMP": "mdi:thermometer",
}
_ZONE_OPEN_ICON_BY_DEFINITION = {
    "BURG EE DELAY": "mdi:door-open",
    "BURG PERIM INST": "mdi:window-open",
    "BURG INTERIOR": "mdi:motion-sensor",
    "BURG 24HR": "mdi:shield-alert",
    "BURG BOX TAMPER": "mdi:shield-off-outline",
    "FIRE": "mdi:fire-alert",
    "CARBON MONOXIDE": "mdi:molecule-co",
    "PANIC": "mdi:alert-octagon",
    "MEDICAL": "mdi:medical-bag",
    "AUTOMATION": "mdi:home-automation",
    "POWER SUPERVISION": "mdi:power-alert",
    "WATER": "mdi:water-alert",
    "HILO TEMP": "mdi:thermometer-alert",
}


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
        snapshot = hub.snapshot
        if snapshot is None:
            _LOGGER.debug("Zone entities skipped because snapshot is unavailable")
            return
        entities: list[Elke27ZoneBinarySensor] = []
        client = hub.client
        zones_by_id = None
        if client is not None:
            zones_by_id = getattr(getattr(client, "state", None), "zones", None)
        zones = (
            list(zones_by_id.values())
            if isinstance(zones_by_id, Mapping)
            else list(_iter_zones(snapshot))
        )
        if not zones:
            _LOGGER.debug("No zones available for entity creation")
            return
        added = 0
        skipped = 0
        for zone in zones:
            definition = _zone_definition(zone)
            zone_id = getattr(zone, "zone_id", None)
            if not isinstance(zone_id, int):
                continue
            if definition == "UNDEFINED":
                zone_name = (
                    zone.get("name")
                    if isinstance(zone, Mapping)
                    else getattr(zone, "name", None)
                )
                _LOGGER.debug(
                    "Skipping zone entity %s (%s): definition=UNDEFINED",
                    zone_id,
                    zone_name,
                )
                skipped += 1
                known_ids.add(zone_id)
                continue
            if zone_id in known_ids:
                continue
            known_ids.add(zone_id)
            entities.append(Elke27ZoneBinarySensor(hub, entry, zone_id, zone))
            added += 1
        _LOGGER.debug(
            "Adding %s zone entities (skipped %s UNDEFINED)",
            added,
            skipped,
        )
        if entities:
            async_add_entities(entities)

    _async_add_zones()
    entry.async_on_unload(hub.async_add_zone_listener(_async_add_zones))


class Elke27ZoneBinarySensor(BinarySensorEntity):
    """Representation of an Elke27 zone."""

    _attr_device_class = BinarySensorDeviceClass.OPENING
    _attr_has_entity_name = True
    _attr_translation_key = "zone"

    def __init__(self, hub: Elke27Hub, entry: ConfigEntry, zone_id: int, zone: Any) -> None:
        """Initialize the zone entity."""
        self._hub = hub
        self._entry = entry
        self._zone_id = zone_id
        self._attr_name = sanitize_name(getattr(zone, "name", None)) or f"Zone {zone_id}"
        self._attr_unique_id = f"{unique_base(hub, entry)}_zone_{zone_id}"
        self._attr_device_info = device_info_for_entry(hub, entry)
        self._missing_logged = False
        self._attr_device_class = _zone_device_class(zone)

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
        zone = _get_zone(self._hub.snapshot, self._zone_id)
        if zone is None:
            self._log_missing()
            return None
        is_open = getattr(zone, "open", None)
        return bool(is_open) if isinstance(is_open, bool) else None

    @property
    def icon(self) -> str | None:
        """Return the icon based on zone definition and state."""
        zone = _get_zone(self._hub.snapshot, self._zone_id)
        if zone is None:
            return None
        definition = _zone_definition(zone)
        if not definition:
            return None
        is_open = getattr(zone, "open", None)
        if isinstance(is_open, bool) and is_open:
            return _ZONE_OPEN_ICON_BY_DEFINITION.get(definition) or _ZONE_ICON_BY_DEFINITION.get(definition)
        return _ZONE_ICON_BY_DEFINITION.get(definition)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        zone = _get_zone(self._hub.snapshot, self._zone_id)
        if zone is None:
            return {}
        return {
            "definition": _zone_definition(zone),
            "bypassed": getattr(zone, "bypassed", None),
            "trouble": getattr(zone, "trouble", None),
        }

    @property
    def available(self) -> bool:
        """Return if the entity is available."""
        return self._hub.is_ready and _get_zone(self._hub.snapshot, self._zone_id) is not None

    def _log_missing(self) -> None:
        """Log when the zone snapshot is missing."""
        if self._missing_logged:
            return
        self._missing_logged = True
        _LOGGER.debug("Zone %s missing from snapshot", self._zone_id)


def _iter_zones(snapshot: Any) -> Iterable[Any]:
    zones = getattr(snapshot, "zones", None)
    if zones is None:
        return []
    if isinstance(zones, Mapping):
        return list(zones.values())
    if isinstance(zones, list | tuple):
        return zones
    return []


def _get_zone(snapshot: Any, zone_id: int) -> Any | None:
    for zone in _iter_zones(snapshot):
        if getattr(zone, "zone_id", None) == zone_id:
            return zone
    return None


def _zone_definition(zone: Any) -> str | None:
    definition = (
        zone.get("definition")
        if isinstance(zone, Mapping)
        else getattr(zone, "definition", None)
    )
    return str(definition) if definition else None


def _zone_device_class(zone: Any) -> BinarySensorDeviceClass:
    zone_type = getattr(zone, "zone_type", None) or getattr(zone, "kind", None)
    if isinstance(zone_type, str):
        normalized = zone_type.lower()
        if "motion" in normalized:
            return BinarySensorDeviceClass.MOTION
        if "window" in normalized:
            return BinarySensorDeviceClass.WINDOW
        if "door" in normalized:
            return BinarySensorDeviceClass.DOOR
    return BinarySensorDeviceClass.OPENING
