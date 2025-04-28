"""Support for control of ElkM1 binary sensors."""

from __future__ import annotations

from typing import Any

from elkm1_lib.const import ZoneLogicalStatus, ZoneType
from elkm1_lib.elements import Element
from elkm1_lib.zones import Zone

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import ElkM1ConfigEntry
from .entity import ElkAttachedEntity, ElkEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ElkM1ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the Elk-M1 sensor platform."""
    elk_data = config_entry.runtime_data
    elk = elk_data.elk
    auto_configure = elk_data.auto_configure

    entities: list[ElkEntity] = []
    for element in elk.zones:
        # Don't create binary sensors for zones that are analog
        if element.definition in {ZoneType.TEMPERATURE, ZoneType.ANALOG_ZONE}:  # type: ignore[attr-defined]
            continue

        if auto_configure:
            if not element.configured:
                continue
        elif not elk_data.config["zone"]["included"][element.index]:
            continue

        entities.append(ElkBinarySensor(element, elk, elk_data))

    async_add_entities(entities)


class ElkBinarySensor(ElkAttachedEntity, BinarySensorEntity):
    """Representation of ElkM1 binary sensor."""

    _element: Zone
    _attr_entity_registry_enabled_default = False

    def _element_changed(self, element: Element, changeset: dict[str, Any]) -> None:
        # Zone in NORMAL state is OFF; any other state is ON
        self._attr_is_on = bool(
            self._element.logical_status != ZoneLogicalStatus.NORMAL
        )
