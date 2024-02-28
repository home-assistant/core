"""Provide a way to assign areas to floors in one's home."""
from __future__ import annotations

from collections import UserDict
from collections.abc import Iterable, ValuesView
import dataclasses
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, TypedDict, cast

from homeassistant.core import HomeAssistant, callback
from homeassistant.util import slugify

from .storage import Store
from .typing import UNDEFINED, EventType, UndefinedType

DATA_REGISTRY = "floor_registry"
EVENT_FLOOR_REGISTRY_UPDATED = "floor_registry_updated"
STORAGE_KEY = "core.floor_registry"
STORAGE_VERSION_MAJOR = 1
SAVE_DELAY = 10


class EventFloorRegistryUpdatedData(TypedDict):
    """Event data for when the floor registry is updated."""

    action: Literal["create", "remove", "update"]
    floor_id: str


EventFloorRegistryUpdated = EventType[EventFloorRegistryUpdatedData]


@dataclass(slots=True, kw_only=True, frozen=True)
class FloorEntry:
    """Floor registry entry."""

    aliases: set[str]
    floor_id: str
    icon: str | None = None
    level: int = 0
    name: str
    normalized_name: str


class FloorRegistryItems(UserDict[str, FloorEntry]):
    """Container for floor registry items, maps floor id -> entry.

    Maintains an additional index:
    - normalized name -> entry
    """

    def __init__(self) -> None:
        """Initialize the container."""
        super().__init__()
        self._normalized_names: dict[str, FloorEntry] = {}

    def values(self) -> ValuesView[FloorEntry]:
        """Return the underlying values to avoid __iter__ overhead."""
        return self.data.values()

    def __setitem__(self, key: str, entry: FloorEntry) -> None:
        """Add an item."""
        data = self.data
        normalized_name = _normalize_floor_name(entry.name)

        if key in data:
            old_entry = data[key]
            if (
                normalized_name != old_entry.normalized_name
                and normalized_name in self._normalized_names
            ):
                raise ValueError(
                    f"The name {entry.name} ({normalized_name}) is already in use"
                )
            del self._normalized_names[old_entry.normalized_name]
        data[key] = entry
        self._normalized_names[normalized_name] = entry

    def __delitem__(self, key: str) -> None:
        """Remove an item."""
        entry = self[key]
        normalized_name = _normalize_floor_name(entry.name)
        del self._normalized_names[normalized_name]
        super().__delitem__(key)

    def get_floor_by_name(self, name: str) -> FloorEntry | None:
        """Get floor by name."""
        return self._normalized_names.get(_normalize_floor_name(name))


class FloorRegistry:
    """Class to hold a registry of floors."""

    floors: FloorRegistryItems
    _floor_data: dict[str, FloorEntry]

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the floor registry."""
        self.hass = hass
        self._store: Store[
            dict[str, list[dict[str, str | int | list[str] | None]]]
        ] = Store(
            hass,
            STORAGE_VERSION_MAJOR,
            STORAGE_KEY,
            atomic_writes=True,
        )

    @callback
    def async_get_floor(self, floor_id: str) -> FloorEntry | None:
        """Get floor by id.

        We retrieve the FloorEntry from the underlying dict to avoid
        the overhead of the UserDict __getitem__.
        """
        return self._floor_data.get(floor_id)

    @callback
    def async_get_floor_by_name(self, name: str) -> FloorEntry | None:
        """Get floor by name."""
        return self.floors.get_floor_by_name(name)

    @callback
    def async_list_floors(self) -> Iterable[FloorEntry]:
        """Get all floors."""
        return self.floors.values()

    @callback
    def _generate_id(self, name: str) -> str:
        """Generate floor ID."""
        suggestion = suggestion_base = slugify(name)
        tries = 1
        while suggestion in self.floors:
            tries += 1
            suggestion = f"{suggestion_base}_{tries}"
        return suggestion

    @callback
    def async_create(
        self,
        name: str,
        *,
        aliases: set[str] | None = None,
        icon: str | None = None,
        level: int = 0,
    ) -> FloorEntry:
        """Create a new floor."""
        if floor := self.async_get_floor_by_name(name):
            raise ValueError(
                f"The name {name} ({floor.normalized_name}) is already in use"
            )

        normalized_name = _normalize_floor_name(name)

        floor = FloorEntry(
            aliases=aliases or set(),
            icon=icon,
            floor_id=self._generate_id(name),
            name=name,
            normalized_name=normalized_name,
            level=level,
        )
        floor_id = floor.floor_id
        self.floors[floor_id] = floor
        self.async_schedule_save()
        self.hass.bus.async_fire(
            EVENT_FLOOR_REGISTRY_UPDATED,
            EventFloorRegistryUpdatedData(
                action="create",
                floor_id=floor_id,
            ),
        )
        return floor

    @callback
    def async_delete(self, floor_id: str) -> None:
        """Delete floor."""
        del self.floors[floor_id]
        self.hass.bus.async_fire(
            EVENT_FLOOR_REGISTRY_UPDATED,
            EventFloorRegistryUpdatedData(
                action="remove",
                floor_id=floor_id,
            ),
        )
        self.async_schedule_save()

    @callback
    def async_update(
        self,
        floor_id: str,
        *,
        aliases: set[str] | UndefinedType = UNDEFINED,
        icon: str | None | UndefinedType = UNDEFINED,
        level: int | UndefinedType = UNDEFINED,
        name: str | UndefinedType = UNDEFINED,
    ) -> FloorEntry:
        """Update name of the floor."""
        old = self.floors[floor_id]
        changes = {
            attr_name: value
            for attr_name, value in (
                ("aliases", aliases),
                ("icon", icon),
                ("level", level),
            )
            if value is not UNDEFINED and value != getattr(old, attr_name)
        }
        if name is not UNDEFINED and name != old.name:
            changes["name"] = name
            changes["normalized_name"] = _normalize_floor_name(name)

        if not changes:
            return old

        new = self.floors[floor_id] = dataclasses.replace(old, **changes)  # type: ignore[arg-type]

        self.async_schedule_save()
        self.hass.bus.async_fire(
            EVENT_FLOOR_REGISTRY_UPDATED,
            EventFloorRegistryUpdatedData(
                action="update",
                floor_id=floor_id,
            ),
        )

        return new

    async def async_load(self) -> None:
        """Load the floor registry."""
        data = await self._store.async_load()
        floors = FloorRegistryItems()

        if data is not None:
            for floor in data["floors"]:
                if TYPE_CHECKING:
                    assert isinstance(floor["aliases"], list)
                    assert isinstance(floor["icon"], str)
                    assert isinstance(floor["level"], int)
                    assert isinstance(floor["name"], str)
                    assert isinstance(floor["floor_id"], str)

                normalized_name = _normalize_floor_name(floor["name"])
                floors[floor["floor_id"]] = FloorEntry(
                    aliases=set(floor["aliases"]),
                    icon=floor["icon"],
                    floor_id=floor["floor_id"],
                    name=floor["name"],
                    level=floor["level"],
                    normalized_name=normalized_name,
                )

        self.floors = floors
        self._floor_data = floors.data

    @callback
    def async_schedule_save(self) -> None:
        """Schedule saving the floor registry."""
        self._store.async_delay_save(self._data_to_save, SAVE_DELAY)

    @callback
    def _data_to_save(self) -> dict[str, list[dict[str, str | int | list[str] | None]]]:
        """Return data of floor registry to store in a file."""
        return {
            "floors": [
                {
                    "aliases": list(entry.aliases),
                    "floor_id": entry.floor_id,
                    "icon": entry.icon,
                    "level": entry.level,
                    "name": entry.name,
                }
                for entry in self.floors.values()
            ]
        }


@callback
def async_get(hass: HomeAssistant) -> FloorRegistry:
    """Get floor registry."""
    return cast(FloorRegistry, hass.data[DATA_REGISTRY])


async def async_load(hass: HomeAssistant) -> None:
    """Load floor registry."""
    assert DATA_REGISTRY not in hass.data
    hass.data[DATA_REGISTRY] = FloorRegistry(hass)
    await hass.data[DATA_REGISTRY].async_load()


def _normalize_floor_name(floor_name: str) -> str:
    """Normalize a floor name by removing whitespace and case folding."""
    return floor_name.casefold().replace(" ", "")
