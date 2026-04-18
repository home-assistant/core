"""Floor functions for Home Assistant templates."""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
    floor_registry as fr,
)
from homeassistant.helpers.template.helpers import resolve_area_id

from .base import BaseTemplateExtension, TemplateFunction

if TYPE_CHECKING:
    from homeassistant.helpers.template import TemplateEnvironment


class FloorExtension(BaseTemplateExtension):
    """Extension for floor-related template functions."""

    def __init__(self, environment: TemplateEnvironment) -> None:
        """Initialize the floor extension."""
        super().__init__(
            environment,
            functions=[
                TemplateFunction(
                    "floors",
                    self.floors,
                    as_global=True,
                    requires_hass=True,
                ),
                TemplateFunction(
                    "floor_id",
                    self.floor_id,
                    as_global=True,
                    as_filter=True,
                    requires_hass=True,
                    limited_ok=False,
                ),
                TemplateFunction(
                    "floor_name",
                    self.floor_name,
                    as_global=True,
                    as_filter=True,
                    requires_hass=True,
                    limited_ok=False,
                ),
                TemplateFunction(
                    "floor_areas",
                    self.floor_areas,
                    as_global=True,
                    as_filter=True,
                    requires_hass=True,
                ),
                TemplateFunction(
                    "floor_entities",
                    self.floor_entities,
                    as_global=True,
                    as_filter=True,
                    requires_hass=True,
                ),
            ],
        )

    def floors(self) -> Iterable[str | None]:
        """Return all floors."""
        floor_registry = fr.async_get(self.hass)
        return [floor.floor_id for floor in floor_registry.async_list_floors()]

    def floor_id(self, lookup_value: Any) -> str | None:
        """Get the floor ID from a floor or area name, alias, device id, or entity id."""
        floor_registry = fr.async_get(self.hass)
        lookup_str = str(lookup_value)

        # Check if it's a floor name or alias
        if floor := floor_registry.async_get_floor_by_name(lookup_str):
            return floor.floor_id
        floors_list = floor_registry.async_get_floors_by_alias(lookup_str)
        if floors_list:
            return floors_list[0].floor_id

        # Resolve to area ID and get floor from area
        if aid := resolve_area_id(self.hass, lookup_value):
            area_reg = ar.async_get(self.hass)
            if area := area_reg.async_get_area(aid):
                return area.floor_id

        return None

    def floor_name(self, lookup_value: str) -> str | None:
        """Get the floor name from a floor id."""
        floor_registry = fr.async_get(self.hass)

        # Check if it's a floor ID
        if floor := floor_registry.async_get_floor(lookup_value):
            return floor.name

        # Resolve to area ID and get floor name from area's floor
        if aid := resolve_area_id(self.hass, lookup_value):
            area_reg = ar.async_get(self.hass)
            if (
                (area := area_reg.async_get_area(aid))
                and area.floor_id
                and (floor := floor_registry.async_get_floor(area.floor_id))
            ):
                return floor.name

        return None

    def _floor_id_or_name(self, floor_id_or_name: str) -> str | None:
        """Get the floor ID from a floor name or ID."""
        # If floor_name returns a value, we know the input was an ID, otherwise we
        # assume it's a name, and if it's neither, we return early.
        if self.floor_name(floor_id_or_name) is not None:
            return floor_id_or_name
        return self.floor_id(floor_id_or_name)

    def floor_areas(self, floor_id_or_name: str) -> Iterable[str]:
        """Return area IDs for a given floor ID or name."""
        if (_floor_id := self._floor_id_or_name(floor_id_or_name)) is None:
            return []

        area_reg = ar.async_get(self.hass)
        entries = ar.async_entries_for_floor(area_reg, _floor_id)
        return [entry.id for entry in entries if entry.id]

    def floor_entities(self, floor_id_or_name: str) -> Iterable[str]:
        """Return entity_ids for a given floor ID or name."""
        ent_reg = er.async_get(self.hass)
        dev_reg = dr.async_get(self.hass)
        entity_ids = []

        for area_id in self.floor_areas(floor_id_or_name):
            # Get entities directly assigned to the area
            entity_ids.extend(
                [
                    entry.entity_id
                    for entry in er.async_entries_for_area(ent_reg, area_id)
                ]
            )

            # Also add entities tied to a device in the area that don't themselves
            # have an area specified since they inherit the area from the device
            entity_ids.extend(
                [
                    entity.entity_id
                    for device in dr.async_entries_for_area(dev_reg, area_id)
                    for entity in er.async_entries_for_device(ent_reg, device.id)
                    if entity.area_id is None
                ]
            )

        return entity_ids
