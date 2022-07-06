"""Support for control of ElkM1 binary sensors."""
from __future__ import annotations

from typing import Any

from elkm1_lib.const import ZoneLogicalStatus, ZoneType
from elkm1_lib.elements import Element
from elkm1_lib.elk import Elk
from elkm1_lib.zones import Zone

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ElkAttachedEntity, ElkEntity
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the Elk-M1 sensor platform."""

    elk_data = hass.data[DOMAIN][config_entry.entry_id]
    auto_configure = elk_data["auto_configure"]
    elk = elk_data["elk"]

    entities: list[ElkEntity] = []
    for element in elk.zones:
        # Don't create binary sensors for zones that are analog
        if element.definition in {ZoneType.TEMPERATURE, ZoneType.ANALOG_ZONE}:
            continue

        if auto_configure:
            if not element.configured:
                continue
        elif not elk_data["config"]["zone"]["included"][element.index]:
            continue

        entities.append(ElkBinarySensor(element, elk, elk_data))

    async_add_entities(entities, True)


class ElkBinarySensor(ElkAttachedEntity, BinarySensorEntity):
    """Representation of ElkM1 binary sensor."""

    _element: Zone

    def __init__(self, element: Element, elk: Elk, elk_data: dict[str, Any]) -> None:
        """Initialize the base of all Elk sensors."""
        super().__init__(element, elk, elk_data)
        self._state: bool = False
        self._attr_entity_registry_enabled_default = False

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self._state

    def _element_changed(self, _: Element, changeset: Any) -> None:
        # Zone in NORMAL state is OFF; any other state is ON
        self._state = self._element.logical_status != ZoneLogicalStatus.NORMAL
