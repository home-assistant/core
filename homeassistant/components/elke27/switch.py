"""Switches for Elke27 outputs and zone bypass controls."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any, Iterable

from elke27_lib.errors import Elke27PinRequiredError

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .entity import device_info_for_entry, sanitize_name, unique_base
from .hub import Elke27Hub

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Elke27 switches from a config entry."""
    hub: Elke27Hub = hass.data[DOMAIN][entry.entry_id]
    known_output_ids: set[int] = set()
    known_zone_ids: set[int] = set()

    @callback
    def _async_add_outputs() -> None:
        snapshot = hub.snapshot
        if snapshot is None:
            _LOGGER.debug("Output switches skipped because snapshot is unavailable")
            return
        entities: list[Elke27OutputSwitch] = []
        outputs = list(_iter_outputs(snapshot))
        if not outputs:
            _LOGGER.debug("No outputs available for entity creation")
            return
        for output in outputs:
            output_id = getattr(output, "output_id", None)
            if not isinstance(output_id, int):
                continue
            if output_id in known_output_ids:
                continue
            known_output_ids.add(output_id)
            entities.append(Elke27OutputSwitch(hub, entry, output_id, output))
        if entities:
            async_add_entities(entities)

    @callback
    def _async_add_zones() -> None:
        snapshot = hub.snapshot
        if snapshot is None:
            _LOGGER.debug("Zone bypass entities skipped because snapshot is unavailable")
            return
        entities: list[Elke27ZoneBypassSwitch] = []
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
            _LOGGER.debug("No zones available for bypass entity creation")
            return
        added = 0
        skipped = 0
        for zone in zones:
            definition = (
                zone.get("definition")
                if isinstance(zone, Mapping)
                else getattr(zone, "definition", None)
            )
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
                    "Skipping zone bypass entity %s (%s): definition=UNDEFINED",
                    zone_id,
                    zone_name,
                )
                skipped += 1
                known_ids.add(zone_id)
                continue
            if zone_id in known_zone_ids:
                continue
            known_zone_ids.add(zone_id)
            entities.append(Elke27ZoneBypassSwitch(hub, entry, zone_id, zone))
            added += 1
        _LOGGER.debug(
            "Adding %s zone bypass entities (skipped %s UNDEFINED)",
            added,
            skipped,
        )
        if entities:
            async_add_entities(entities)

    _async_add_outputs()
    _async_add_zones()
    entry.async_on_unload(hub.async_add_output_listener(_async_add_outputs))
    entry.async_on_unload(hub.async_add_zone_listener(_async_add_zones))


class Elke27OutputSwitch(SwitchEntity):
    """Representation of an Elke27 output."""

    _attr_has_entity_name = True
    _attr_translation_key = "output"

    def __init__(
        self,
        hub: Elke27Hub,
        entry: ConfigEntry,
        output_id: int,
        output: Any,
    ) -> None:
        """Initialize the output entity."""
        self._hub = hub
        self._output_id = output_id
        self._attr_name = (
            sanitize_name(getattr(output, "name", None)) or f"Output {output_id}"
        )
        self._attr_unique_id = f"{unique_base(hub, entry)}_output_{output_id}"
        self._attr_device_info = device_info_for_entry(hub, entry)
        self._missing_logged = False

    async def async_added_to_hass(self) -> None:
        """Register for hub updates."""
        self.async_on_remove(self._hub.async_add_output_listener(self._handle_update))

    @callback
    def _handle_update(self) -> None:
        """Write updated state."""
        self.async_write_ha_state()

    @property
    def is_on(self) -> bool | None:
        """Return if the output is on."""
        output = _get_output(self._hub.snapshot, self._output_id)
        if output is None:
            self._log_missing()
            return None
        is_on = getattr(output, "state", None)
        return bool(is_on) if isinstance(is_on, bool) else None

    @property
    def available(self) -> bool:
        """Return if the entity is available."""
        return (
            self._hub.is_ready
            and _get_output(self._hub.snapshot, self._output_id) is not None
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the output on if supported by the client."""
        try:
            await self._hub.async_set_output(self._output_id, True)
        except Elke27PinRequiredError as err:
            raise HomeAssistantError("PIN required to perform this action.") from err

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the output off if supported by the client."""
        try:
            await self._hub.async_set_output(self._output_id, False)
        except Elke27PinRequiredError as err:
            raise HomeAssistantError("PIN required to perform this action.") from err

    def _log_missing(self) -> None:
        """Log when the output snapshot is missing."""
        if self._missing_logged:
            return
        self._missing_logged = True
        _LOGGER.debug("Output %s missing from snapshot", self._output_id)


class Elke27ZoneBypassSwitch(SwitchEntity):
    """Representation of an Elke27 zone bypass switch."""

    _attr_has_entity_name = True
    _attr_translation_key = "zone_bypass"

    def __init__(self, hub: Elke27Hub, entry: ConfigEntry, zone_id: int, zone: Any) -> None:
        """Initialize the zone bypass switch."""
        self._hub = hub
        self._zone_id = zone_id
        zone_name = sanitize_name(getattr(zone, "name", None)) or f"Zone {zone_id}"
        self._attr_translation_placeholders = {"zone": zone_name}
        self._attr_unique_id = f"{unique_base(hub, entry)}_zone_{zone_id}_bypass"
        self._attr_device_info = device_info_for_entry(hub, entry)
        self._missing_logged = False

    async def async_added_to_hass(self) -> None:
        """Register for hub updates."""
        self.async_on_remove(self._hub.async_add_zone_listener(self._handle_update))

    @callback
    def _handle_update(self) -> None:
        """Write updated state."""
        self.async_write_ha_state()

    @property
    def is_on(self) -> bool | None:
        """Return if the zone is bypassed."""
        zone = _get_zone(self._hub.snapshot, self._zone_id)
        if zone is None:
            self._log_missing()
            return None
        bypassed = getattr(zone, "bypassed", None)
        return bool(bypassed) if isinstance(bypassed, bool) else None

    @property
    def available(self) -> bool:
        """Return if the entity is available."""
        return (
            self._hub.is_ready
            and _get_zone(self._hub.snapshot, self._zone_id) is not None
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Bypass the zone."""
        try:
            await self._hub.async_set_zone_bypass(self._zone_id, True)
        except Elke27PinRequiredError as err:
            raise HomeAssistantError("PIN required to perform this action.") from err

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Clear the zone bypass."""
        try:
            await self._hub.async_set_zone_bypass(self._zone_id, False)
        except Elke27PinRequiredError as err:
            raise HomeAssistantError("PIN required to perform this action.") from err

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


def _iter_outputs(snapshot: Any) -> Iterable[Any]:
    outputs = getattr(snapshot, "outputs", None)
    if outputs is None:
        return []
    if isinstance(outputs, Mapping):
        return list(outputs.values())
    if isinstance(outputs, list | tuple):
        return outputs
    return []


def _get_output(snapshot: Any, output_id: int) -> Any | None:
    for output in _iter_outputs(snapshot):
        if getattr(output, "output_id", None) == output_id:
            return output
    return None
