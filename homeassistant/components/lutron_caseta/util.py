"""Support for Lutron Caseta."""

from __future__ import annotations

from .const import UNASSIGNED_AREA


def serial_to_unique_id(serial: int) -> str:
    """Convert a lutron serial number to a unique id."""
    return hex(serial)[2:].zfill(8)


def area_name_from_id(areas: dict[str, dict], area_id: str | None) -> str:
    """Return the full area name including parent(s)."""
    if area_id is None:
        return UNASSIGNED_AREA
    return _construct_area_name_from_id(areas, area_id, [])


def _construct_area_name_from_id(
    areas: dict[str, dict], area_id: str, labels: list[str]
) -> str:
    """Recursively construct the full area name including parent(s)."""
    area = areas[area_id]
    parent_area_id = area["parent_id"]
    if parent_area_id is None:
        # This is the root area, return last area
        return " ".join(labels)

    labels.insert(0, area["name"])
    return _construct_area_name_from_id(areas, parent_area_id, labels)
