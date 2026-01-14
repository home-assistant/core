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
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DATA_COORDINATOR, DATA_HUB, DOMAIN
from .coordinator import Elke27DataUpdateCoordinator
from .entity import (
    build_unique_id,
    device_info_for_entry,
    sanitize_name,
    unique_base,
)
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
    data = hass.data[DOMAIN][entry.entry_id]
    hub: Elke27Hub = data[DATA_HUB]
    coordinator: Elke27DataUpdateCoordinator = data[DATA_COORDINATOR]
    known_ids: set[int] = set()
    skipped_zone_ids: set[int] = set()

    def _async_add_zones() -> None:
        snapshot = coordinator.data
        if snapshot is None:
            _LOGGER.debug("Zone entities skipped because snapshot is unavailable")
            return
        entities: list[Elke27ZoneBinarySensor] = []
        zones = list(_iter_zones(snapshot))
        if not zones:
            _LOGGER.debug("No zones available for entity creation")
            return
        added = 0
        skipped = 0
        for zone in zones:
            zone_id = getattr(zone, "zone_id", None)
            if not isinstance(zone_id, int):
                continue
            zone_definition = _zone_definition_entry(snapshot, zone_id)
            definition = _zone_definition_value(zone, zone_definition)
            if definition == "UNDEFINED":
                if zone_id not in skipped_zone_ids:
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
                    skipped_zone_ids.add(zone_id)
                skipped += 1
                continue
            skipped_zone_ids.discard(zone_id)
            if zone_id in known_ids:
                continue
            known_ids.add(zone_id)
            entities.append(
                Elke27ZoneBinarySensor(
                    coordinator, hub, entry, zone_id, zone, zone_definition
                )
            )
            added += 1
        _LOGGER.debug(
            "Adding %s zone entities (skipped %s UNDEFINED)",
            added,
            skipped,
        )
        if entities:
            async_add_entities(entities)

    _async_add_zones()
    entry.async_on_unload(coordinator.async_add_listener(_async_add_zones))


class Elke27ZoneBinarySensor(
    CoordinatorEntity[Elke27DataUpdateCoordinator], BinarySensorEntity
):
    """Representation of an Elke27 zone."""

    _attr_device_class = BinarySensorDeviceClass.OPENING
    _attr_has_entity_name = True
    _attr_translation_key = "zone"

    def __init__(
        self,
        coordinator: Elke27DataUpdateCoordinator,
        hub: Elke27Hub,
        entry: ConfigEntry,
        zone_id: int,
        zone: Any,
        zone_definition: Any | None,
    ) -> None:
        """Initialize the zone entity."""
        super().__init__(coordinator)
        self._hub = hub
        self._entry = entry
        self._zone_id = zone_id
        self._attr_name = _zone_name(zone, zone_definition) or f"Zone {zone_id}"
        self._attr_unique_id = build_unique_id(
            unique_base(hub, coordinator, entry),
            "zone",
            zone_id,
        )
        self._attr_device_info = device_info_for_entry(hub, coordinator, entry)
        self._missing_logged = False
        self._attr_device_class = _zone_device_class(zone, zone_definition)

    @property
    def is_on(self) -> bool | None:
        """Return if the zone is open."""
        zone = _get_zone(self.coordinator.data, self._zone_id)
        if zone is None:
            self._log_missing()
            return None
        is_open = getattr(zone, "open", None)
        return bool(is_open) if isinstance(is_open, bool) else None

    @property
    def icon(self) -> str | None:
        """Return the icon based on zone definition and state."""
        zone = _get_zone(self.coordinator.data, self._zone_id)
        if zone is None:
            return None
        zone_definition = _zone_definition_entry(self.coordinator.data, self._zone_id)
        definition = _zone_definition_value(zone, zone_definition)
        if not definition:
            return None
        is_open = getattr(zone, "open", None)
        if isinstance(is_open, bool) and is_open:
            return _ZONE_OPEN_ICON_BY_DEFINITION.get(definition) or _ZONE_ICON_BY_DEFINITION.get(definition)
        return _ZONE_ICON_BY_DEFINITION.get(definition)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        zone = _get_zone(self.coordinator.data, self._zone_id)
        if zone is None:
            return {}
        return {
            "definition": _zone_definition_value(
                zone, _zone_definition_entry(self.coordinator.data, self._zone_id)
            ),
            "bypassed": getattr(zone, "bypassed", None),
            "trouble": getattr(zone, "trouble", None),
        }

    @property
    def available(self) -> bool:
        """Return if the entity is available."""
        return self._hub.is_ready and _get_zone(self.coordinator.data, self._zone_id) is not None

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


def _zone_definition_entry(snapshot: Any | None, zone_id: int) -> Any | None:
    definitions = getattr(snapshot, "zone_definitions", None) if snapshot is not None else None
    if isinstance(definitions, Mapping):
        return definitions.get(zone_id)
    return None


def _zone_definition_value(zone: Any, zone_definition: Any | None) -> str | None:
    definition = getattr(zone_definition, "definition", None)
    if definition:
        return str(definition)
    definition = (
        zone.get("definition")
        if isinstance(zone, Mapping)
        else getattr(zone, "definition", None)
    )
    return str(definition) if definition else None


def _zone_name(zone: Any, zone_definition: Any | None) -> str | None:
    name = getattr(zone_definition, "name", None)
    if name:
        return sanitize_name(name)
    return sanitize_name(getattr(zone, "name", None))


def _zone_device_class(
    zone: Any, zone_definition: Any | None
) -> BinarySensorDeviceClass:
    zone_type = getattr(zone_definition, "zone_type", None) or getattr(
        zone_definition, "kind", None
    )
    if zone_type is None:
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
