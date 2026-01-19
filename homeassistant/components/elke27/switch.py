"""Switches for Elke27 outputs and zone bypass controls."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
import logging
from typing import Any

from elke27_lib.errors import Elke27PinRequiredError

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DATA_COORDINATOR, DATA_HUB, DOMAIN
from .coordinator import Elke27DataUpdateCoordinator
from .entity import build_unique_id, device_info_for_entry, sanitize_name, unique_base
from .hub import Elke27Hub

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Elke27 switches from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    hub: Elke27Hub = data[DATA_HUB]
    coordinator: Elke27DataUpdateCoordinator = data[DATA_COORDINATOR]
    known_output_ids: set[int] = set()
    known_zone_ids: set[int] = set()
    skipped_zone_ids: set[int] = set()

    def _async_add_outputs() -> None:
        snapshot = coordinator.data
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
            entities.append(
                Elke27OutputSwitch(coordinator, hub, entry, output_id, output)
            )
        if entities:
            async_add_entities(entities)

    def _async_add_zones() -> None:
        snapshot = coordinator.data
        if snapshot is None:
            _LOGGER.debug(
                "Zone bypass entities skipped because snapshot is unavailable"
            )
            return
        entities: list[Elke27ZoneBypassSwitch] = []
        zones = list(_iter_zones(snapshot))
        if not zones:
            _LOGGER.debug("No zones available for bypass entity creation")
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
                    zone_name = _zone_name(zone, zone_definition)
                    _LOGGER.debug(
                        "Skipping zone bypass entity %s (%s): definition=UNDEFINED",
                        zone_id,
                        zone_name,
                    )
                    skipped_zone_ids.add(zone_id)
                skipped += 1
                continue
            skipped_zone_ids.discard(zone_id)
            if zone_id in known_zone_ids:
                continue
            known_zone_ids.add(zone_id)
            entities.append(
                Elke27ZoneBypassSwitch(
                    coordinator, hub, entry, zone_id, zone, zone_definition
                )
            )
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
    entry.async_on_unload(coordinator.async_add_listener(_async_add_outputs))
    entry.async_on_unload(coordinator.async_add_listener(_async_add_zones))


class Elke27OutputSwitch(CoordinatorEntity[Elke27DataUpdateCoordinator], SwitchEntity):
    """Representation of an Elke27 output."""

    _attr_has_entity_name = True
    _attr_translation_key = "output"

    def __init__(
        self,
        coordinator: Elke27DataUpdateCoordinator,
        hub: Elke27Hub,
        entry: ConfigEntry,
        output_id: int,
        output: Any,
    ) -> None:
        """Initialize the output entity."""
        super().__init__(coordinator)
        self._hub = hub
        self._output_id = output_id
        self._attr_name = (
            sanitize_name(getattr(output, "name", None)) or f"Output {output_id}"
        )
        self._attr_unique_id = build_unique_id(
            unique_base(hub, coordinator, entry),
            "output",
            output_id,
        )
        self._attr_device_info = device_info_for_entry(hub, coordinator, entry)
        self._missing_logged = False

    @property
    def is_on(self) -> bool | None:
        """Return if the output is on."""
        output = _get_output(self.coordinator.data, self._output_id)
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
            and _get_output(self.coordinator.data, self._output_id) is not None
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


class Elke27ZoneBypassSwitch(
    CoordinatorEntity[Elke27DataUpdateCoordinator], SwitchEntity
):
    """Representation of an Elke27 zone bypass switch."""

    _attr_has_entity_name = True
    _attr_translation_key = "zone_bypass"

    def __init__(
        self,
        coordinator: Elke27DataUpdateCoordinator,
        hub: Elke27Hub,
        entry: ConfigEntry,
        zone_id: int,
        zone: Any,
        zone_definition: Any | None,
    ) -> None:
        """Initialize the zone bypass switch."""
        super().__init__(coordinator)
        self._hub = hub
        self._zone_id = zone_id
        zone_name = _zone_name(zone, zone_definition) or f"Zone {zone_id}"
        self._attr_translation_placeholders = {"zone": zone_name}
        self._attr_unique_id = build_unique_id(
            unique_base(hub, coordinator, entry),
            "zone_bypass",
            zone_id,
        )
        self._attr_device_info = device_info_for_entry(hub, coordinator, entry)
        self._missing_logged = False

    @property
    def is_on(self) -> bool | None:
        """Return if the zone is bypassed."""
        zone = _get_zone(self.coordinator.data, self._zone_id)
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
            and _get_zone(self.coordinator.data, self._zone_id) is not None
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

    @property
    def _diagnostic_bypassed(self) -> bool | None:
        """Return the bypassed state for diagnostics."""
        zone = _get_zone(self.coordinator.data, self._zone_id)
        if zone is None:
            return None
        return getattr(zone, "bypassed", None)

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        _LOGGER.debug(
            "Zone bypass update entity_id=%s unique_id=%s zone_id=%s bypassed=%s",
            self.entity_id,
            self.unique_id,
            self._zone_id,
            self._diagnostic_bypassed,
        )
        super()._handle_coordinator_update()


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
    definitions = (
        getattr(snapshot, "zone_definitions", None) if snapshot is not None else None
    )
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
