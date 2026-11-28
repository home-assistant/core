"""Areas for entity suggestions from the building structure of project data."""

from collections import Counter
from typing import Final, NamedTuple

from xknxproject.models import Space, SpaceType

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import area_registry as ar

from .const import SuggestedArea

# spaces an area is created for - spaces within them belong to their area
AREA_SPACE_TYPES: Final = frozenset(
    {
        SpaceType.ROOM.value,
        SpaceType.CORRIDOR.value,
        SpaceType.STAIRWAY.value,
        SpaceType.AREA.value,
    }
)


class _SpaceArea(NamedTuple):
    """Names of the area and floor of a space."""

    name: str
    floor: str | None


def _space_paths(
    locations: dict[str, Space], parents: tuple[str, ...] = ()
) -> dict[str, tuple[str, ...]]:
    """The names of each space and the spaces containing it, by its identifier."""
    found: dict[str, tuple[str, ...]] = {}
    for space in locations.values():
        path = (*parents, space["name"])
        found[space["identifier"]] = path
        found |= _space_paths(space["spaces"], path)
    return found


def _space_names(locations: dict[str, Space]) -> dict[str, str]:
    """The name of each space by its identifier.

    A name used by more than one space is prefixed with the names of the spaces
    containing it, as far as needed to tell them apart - eg. "Ground floor /
    Kitchen" and "First floor / Kitchen".
    """
    paths = _space_paths(locations)
    depths = dict.fromkeys(paths, 1)
    while True:
        labels = {
            identifier: path[-depths[identifier] :]
            for identifier, path in paths.items()
        }
        counts = Counter(labels.values())
        deeper = [
            identifier
            for identifier, label in labels.items()
            if counts[label] > 1 and depths[identifier] < len(paths[identifier])
        ]
        if not deeper:
            return {
                identifier: " / ".join(label) for identifier, label in labels.items()
            }
        for identifier in deeper:
            depths[identifier] += 1


def _space_areas(
    spaces: dict[str, Space],
    names: dict[str, str],
    floor: str | None = None,
    area: _SpaceArea | None = None,
) -> dict[str, _SpaceArea]:
    """Names of the area and floor of each space within a room, by its identifier."""
    found: dict[str, _SpaceArea] = {}
    for space in spaces.values():
        identifier = space["identifier"]
        space_floor, space_area = floor, area
        if space["type"] == SpaceType.FLOOR.value:
            space_floor = names[identifier]
        elif space["type"] in AREA_SPACE_TYPES:
            space_area = _SpaceArea(names[identifier], space_floor)
        elif space["type"] == SpaceType.DISTRIBUTION_BOARD.value:
            # actuators in a board don't belong to the room the board is in
            space_area = None
        if space_area is not None:
            found[identifier] = space_area
        found |= _space_areas(space["spaces"], names, space_floor, space_area)
    return found


@callback
def async_suggested_areas(
    hass: HomeAssistant, locations: dict[str, Space]
) -> dict[str, SuggestedArea]:
    """The suggested area of each space within a room, by its identifier."""
    area_registry = ar.async_get(hass)
    return {
        identifier: SuggestedArea(
            name=space_area.name,
            floor=space_area.floor,
            area_id=area.id
            if (area := area_registry.async_get_area_by_name(space_area.name))
            else None,
        )
        for identifier, space_area in _space_areas(
            locations, _space_names(locations)
        ).items()
    }
