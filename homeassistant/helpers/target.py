"""Helpers for dealing with entity targets."""

from __future__ import annotations

import dataclasses
from logging import Logger
from typing import TypeGuard

from homeassistant.const import (
    ATTR_AREA_ID,
    ATTR_DEVICE_ID,
    ATTR_ENTITY_ID,
    ATTR_FLOOR_ID,
    ATTR_LABEL_ID,
    ENTITY_MATCH_NONE,
)
from homeassistant.core import HomeAssistant

from . import (
    area_registry as ar,
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
    floor_registry as fr,
    group,
    label_registry as lr,
)
from .typing import ConfigType


def _has_match(ids: str | list[str] | None) -> TypeGuard[str | list[str]]:
    """Check if ids can match anything."""
    return ids not in (None, ENTITY_MATCH_NONE)


class TargetSelectorData:
    """Class to hold data of target selector."""

    __slots__ = ("area_ids", "device_ids", "entity_ids", "floor_ids", "label_ids")

    def __init__(self, config: ConfigType) -> None:
        """Extract ids from the config."""
        entity_ids: str | list | None = config.get(ATTR_ENTITY_ID)
        device_ids: str | list | None = config.get(ATTR_DEVICE_ID)
        area_ids: str | list | None = config.get(ATTR_AREA_ID)
        floor_ids: str | list | None = config.get(ATTR_FLOOR_ID)
        label_ids: str | list | None = config.get(ATTR_LABEL_ID)

        self.entity_ids = (
            set(cv.ensure_list(entity_ids)) if _has_match(entity_ids) else set()
        )
        self.device_ids = (
            set(cv.ensure_list(device_ids)) if _has_match(device_ids) else set()
        )
        self.area_ids = set(cv.ensure_list(area_ids)) if _has_match(area_ids) else set()
        self.floor_ids = (
            set(cv.ensure_list(floor_ids)) if _has_match(floor_ids) else set()
        )
        self.label_ids = (
            set(cv.ensure_list(label_ids)) if _has_match(label_ids) else set()
        )

    @property
    def has_any_selector(self) -> bool:
        """Determine if any selectors are present."""
        return bool(
            self.entity_ids
            or self.device_ids
            or self.area_ids
            or self.floor_ids
            or self.label_ids
        )


@dataclasses.dataclass(slots=True)
class SelectedEntities:
    """Class to hold the selected entities."""

    # Entities that were explicitly mentioned.
    referenced: set[str] = dataclasses.field(default_factory=set)

    # Entities that were referenced via device/area/floor/label ID.
    # Should not trigger a warning when they don't exist.
    indirectly_referenced: set[str] = dataclasses.field(default_factory=set)

    # Referenced items that could not be found.
    missing_devices: set[str] = dataclasses.field(default_factory=set)
    missing_areas: set[str] = dataclasses.field(default_factory=set)
    missing_floors: set[str] = dataclasses.field(default_factory=set)
    missing_labels: set[str] = dataclasses.field(default_factory=set)

    referenced_devices: set[str] = dataclasses.field(default_factory=set)
    referenced_areas: set[str] = dataclasses.field(default_factory=set)

    def log_missing(self, missing_entities: set[str], logger: Logger) -> None:
        """Log about missing items."""
        parts = []
        for label, items in (
            ("floors", self.missing_floors),
            ("areas", self.missing_areas),
            ("devices", self.missing_devices),
            ("entities", missing_entities),
            ("labels", self.missing_labels),
        ):
            if items:
                parts.append(f"{label} {', '.join(sorted(items))}")

        if not parts:
            return

        logger.warning(
            "Referenced %s are missing or not currently available",
            ", ".join(parts),
        )


def async_extract_referenced_entity_ids(
    hass: HomeAssistant, selector_data: TargetSelectorData, expand_group: bool = True
) -> SelectedEntities:
    """Extract referenced entity IDs from a target selector."""
    selected = SelectedEntities()

    if not selector_data.has_any_selector:
        return selected

    entity_ids: set[str] | list[str] = selector_data.entity_ids
    if expand_group:
        entity_ids = group.expand_entity_ids(hass, entity_ids)

    selected.referenced.update(entity_ids)

    if (
        not selector_data.device_ids
        and not selector_data.area_ids
        and not selector_data.floor_ids
        and not selector_data.label_ids
    ):
        return selected

    entities = er.async_get(hass).entities
    dev_reg = dr.async_get(hass)
    area_reg = ar.async_get(hass)

    if selector_data.floor_ids:
        floor_reg = fr.async_get(hass)
        for floor_id in selector_data.floor_ids:
            if floor_id not in floor_reg.floors:
                selected.missing_floors.add(floor_id)

    for area_id in selector_data.area_ids:
        if area_id not in area_reg.areas:
            selected.missing_areas.add(area_id)

    for device_id in selector_data.device_ids:
        if device_id not in dev_reg.devices:
            selected.missing_devices.add(device_id)

    if selector_data.label_ids:
        label_reg = lr.async_get(hass)
        for label_id in selector_data.label_ids:
            if label_id not in label_reg.labels:
                selected.missing_labels.add(label_id)

            for entity_entry in entities.get_entries_for_label(label_id):
                if (
                    entity_entry.entity_category is None
                    and entity_entry.hidden_by is None
                ):
                    selected.indirectly_referenced.add(entity_entry.entity_id)

            for device_entry in dev_reg.devices.get_devices_for_label(label_id):
                selected.referenced_devices.add(device_entry.id)

            for area_entry in area_reg.areas.get_areas_for_label(label_id):
                selected.referenced_areas.add(area_entry.id)

    # Find areas for targeted floors
    if selector_data.floor_ids:
        selected.referenced_areas.update(
            area_entry.id
            for floor_id in selector_data.floor_ids
            for area_entry in area_reg.areas.get_areas_for_floor(floor_id)
        )

    selected.referenced_areas.update(selector_data.area_ids)
    selected.referenced_devices.update(selector_data.device_ids)

    if not selected.referenced_areas and not selected.referenced_devices:
        return selected

    # Add indirectly referenced by device
    selected.indirectly_referenced.update(
        entry.entity_id
        for device_id in selected.referenced_devices
        for entry in entities.get_entries_for_device_id(device_id)
        # Do not add entities which are hidden or which are config
        # or diagnostic entities.
        if (entry.entity_category is None and entry.hidden_by is None)
    )

    # Find devices for targeted areas
    referenced_devices_by_area: set[str] = set()
    if selected.referenced_areas:
        for area_id in selected.referenced_areas:
            referenced_devices_by_area.update(
                device_entry.id
                for device_entry in dev_reg.devices.get_devices_for_area_id(area_id)
            )
    selected.referenced_devices.update(referenced_devices_by_area)

    # Add indirectly referenced by area
    selected.indirectly_referenced.update(
        entry.entity_id
        for area_id in selected.referenced_areas
        # The entity's area matches a targeted area
        for entry in entities.get_entries_for_area_id(area_id)
        # Do not add entities which are hidden or which are config
        # or diagnostic entities.
        if entry.entity_category is None and entry.hidden_by is None
    )
    # Add indirectly referenced by area through device
    selected.indirectly_referenced.update(
        entry.entity_id
        for device_id in referenced_devices_by_area
        for entry in entities.get_entries_for_device_id(device_id)
        # Do not add entities which are hidden or which are config
        # or diagnostic entities.
        if (
            entry.entity_category is None
            and entry.hidden_by is None
            and (
                # The entity's device matches a device referenced
                # by an area and the entity
                # has no explicitly set area
                not entry.area_id
            )
        )
    )

    return selected
