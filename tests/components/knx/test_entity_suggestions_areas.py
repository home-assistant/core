"""Test the areas of KNX entity suggestions from the building structure."""

from typing import Any

from homeassistant.components.knx.storage.entity_suggestions.areas import (
    _space_names,
    async_suggested_areas,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar


def _space(
    identifier: str,
    space_type: str,
    name: str,
    spaces: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "type": space_type,
        "identifier": identifier,
        "name": name,
        "usage_id": None,
        "usage_text": "",
        "number": "",
        "description": "",
        "project_uid": None,
        "devices": [],
        "spaces": spaces or {},
        "functions": [],
    }


LOCATIONS: dict[str, Any] = {
    "B-1": _space(
        "B-1",
        "Building",
        "House",
        {
            "F-1": _space(
                "F-1",
                "Floor",
                "Ground floor",
                {
                    "R-1": _space(
                        "R-1",
                        "Room",
                        "Kitchen",
                        {
                            "S-1": _space("S-1", "Segment", "Island"),
                            "D-1": _space(
                                "D-1",
                                "DistributionBoard",
                                "Board",
                                {"S-2": _space("S-2", "Segment", "Field 1")},
                            ),
                        },
                    ),
                    "C-1": _space("C-1", "Corridor", "Hall"),
                    "T-1": _space("T-1", "Stairway", "Stairs"),
                    "D-2": _space("D-2", "DistributionBoard", "Main board"),
                    "S-3": _space("S-3", "Segment", "Niche"),
                },
            ),
            "F-2": _space(
                "F-2",
                "Floor",
                "First floor",
                {"R-2": _space("R-2", "Room", "Kitchen")},
            ),
            "P-1": _space(
                "P-1",
                "BuildingPart",
                "Wing",
                {"R-3": _space("R-3", "Room", "Workshop")},
            ),
        },
    ),
    "B-2": _space(
        "B-2",
        "Building",
        "Annex",
        {
            "F-3": _space(
                "F-3",
                "Floor",
                "Ground floor",
                {"R-4": _space("R-4", "Room", "Bath")},
            ),
        },
    ),
    "G-1": _space(
        "G-1",
        "Ground",
        "Plot",
        {"A-1": _space("A-1", "Area", "Garden")},
    ),
}


def test_space_names() -> None:
    """Test repeated space names are told apart by the spaces containing them."""
    locations = {
        "P-1": _space(
            "P-1",
            "Building",
            "House",
            {
                "P-2": _space(
                    "P-2",
                    "Floor",
                    "Ground floor",
                    {
                        "P-3": _space("P-3", "Room", "Kitchen"),
                        "P-4": _space("P-4", "Room", "Hall"),
                    },
                ),
                "P-5": _space(
                    "P-5",
                    "Floor",
                    "First floor",
                    {
                        "P-6": _space("P-6", "Room", "Kitchen"),
                        "P-7": _space("P-7", "Room", "Bath"),
                    },
                ),
            },
        ),
        "P-8": _space(
            "P-8",
            "Building",
            "Annex",
            {
                "P-9": _space(
                    "P-9",
                    "Floor",
                    "Ground floor",
                    {"P-10": _space("P-10", "Room", "Kitchen")},
                ),
                "P-11": _space("P-11", "Room", "Hall"),
            },
        ),
    }
    assert _space_names(locations) == {
        "P-1": "House",
        "P-2": "House / Ground floor",
        "P-3": "House / Ground floor / Kitchen",
        "P-4": "Ground floor / Hall",
        "P-5": "First floor",
        "P-6": "First floor / Kitchen",
        "P-7": "Bath",
        "P-8": "Annex",
        "P-9": "Annex / Ground floor",
        "P-10": "Annex / Ground floor / Kitchen",
        "P-11": "Annex / Hall",
    }


async def test_suggested_areas(
    hass: HomeAssistant, area_registry: ar.AreaRegistry
) -> None:
    """Test the area of each space within a room, corridor, stairway or area.

    Spaces missing in the result - buildings, floors, distribution boards and
    everything outside of a room - have no area.
    """
    garden = area_registry.async_create("garden")

    assert async_suggested_areas(hass, LOCATIONS) == {
        "R-1": {
            "name": "Ground floor / Kitchen",
            "floor": "House / Ground floor",
            "area_id": None,
        },
        # a segment belongs to the room it is in
        "S-1": {
            "name": "Ground floor / Kitchen",
            "floor": "House / Ground floor",
            "area_id": None,
        },
        "C-1": {"name": "Hall", "floor": "House / Ground floor", "area_id": None},
        "T-1": {"name": "Stairs", "floor": "House / Ground floor", "area_id": None},
        "R-2": {
            "name": "First floor / Kitchen",
            "floor": "First floor",
            "area_id": None,
        },
        "R-3": {"name": "Workshop", "floor": None, "area_id": None},
        "R-4": {"name": "Bath", "floor": "Annex / Ground floor", "area_id": None},
        # an existing area is found by its normalized name
        "A-1": {"name": "Garden", "floor": None, "area_id": garden.id},
    }
