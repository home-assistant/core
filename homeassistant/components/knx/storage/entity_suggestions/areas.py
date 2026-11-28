"""Areas for entity suggestions from the building structure of project data."""

from collections import Counter
from collections.abc import Iterator
from typing import Final, NamedTuple

from xknxproject.models import Space, SpaceType

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers.normalized_name_base_registry import normalize_name

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


def _iter_spaces(
    locations: dict[str, Space], parents: tuple[str, ...] = ()
) -> Iterator[tuple[Space, tuple[str, ...]]]:
    """Yield each space with the names of itself and the spaces containing it."""
    for space in locations.values():
        path = (*parents, space["name"])
        yield space, path
        yield from _iter_spaces(space["spaces"], path)


def _unique_names(paths: dict[str, tuple[str, ...]]) -> dict[str, str]:
    """A unique name for each path, by its identifier.

    A name used by more than one path is prefixed with the names of the spaces
    containing it, as far as needed to tell them apart - eg. "Ground floor /
    Kitchen" and "First floor / Kitchen". Names are compared like the area and
    floor registries do, so "Kitchen" and "kitchen" are told apart too. Names
    the prefixes don't tell apart, eg. of two rooms "Bath" on one floor, are
    numbered in project order - "Bath" and "Bath (2)".
    """
    depths = dict.fromkeys(paths, 1)
    while True:
        labels = {
            identifier: " / ".join(path[-depths[identifier] :])
            for identifier, path in paths.items()
        }
        counts = Counter(normalize_name(label) for label in labels.values())
        deeper = [
            identifier
            for identifier, label in labels.items()
            if counts[normalize_name(label)] > 1
            and depths[identifier] < len(paths[identifier])
        ]
        if not deeper:
            return _numbered(labels)
        for identifier in deeper:
            depths[identifier] += 1


def _numbered(labels: dict[str, str]) -> dict[str, str]:
    """Number labels that are still used more than once, in project order."""
    used: set[str] = set()
    numbered: dict[str, str] = {}
    for identifier, label in labels.items():
        name, number = label, 1
        while normalize_name(name) in used:
            number += 1
            name = f"{label} ({number})"
        used.add(normalize_name(name))
        numbered[identifier] = name
    return numbered


def space_names(locations: dict[str, Space]) -> dict[str, str]:
    """A name of each space unique among all spaces, by its identifier."""
    return _unique_names(
        {space["identifier"]: path for space, path in _iter_spaces(locations)}
    )


def device_space_ids(locations: dict[str, Space]) -> dict[str, str]:
    """The identifier of the space listing each device, by its individual address.

    The first listing in project order wins, like `Device["space_id"]` of
    xknxproject 3.11, which projects parsed by older versions don't have.
    """
    found: dict[str, str] = {}
    for space, _ in _iter_spaces(locations):
        for device in space["devices"]:
            found.setdefault(device, space["identifier"])
    return found


def _area_and_floor_names(locations: dict[str, Space]) -> dict[str, str]:
    """Names of areas unique among areas, and of floors among floors."""
    spaces = list(_iter_spaces(locations))
    return _unique_names(
        {
            space["identifier"]: path
            for space, path in spaces
            if space["type"] in AREA_SPACE_TYPES
        }
    ) | _unique_names(
        {
            space["identifier"]: path
            for space, path in spaces
            if space["type"] == SpaceType.FLOOR.value
        }
    )


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
            locations, _area_and_floor_names(locations)
        ).items()
    }
