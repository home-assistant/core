"""Provide a way to assign areas to floors in one's home."""

from __future__ import annotations

from collections.abc import Iterable
import dataclasses
from dataclasses import dataclass
from typing import Literal, TypedDict

from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.util import slugify
from homeassistant.util.event_type import EventType
from homeassistant.util.hass_dict import HassKey

from .normalized_name_base_registry import (
    NormalizedNameBaseRegistryEntry,
    NormalizedNameBaseRegistryItems,
    normalize_name,
)
from .registry import BaseRegistry
from .singleton import singleton
from .storage import Store
from .typing import UNDEFINED, UndefinedType

DATA_REGISTRY: HassKey[FloorRegistry] = HassKey("floor_registry")
EVENT_FLOOR_REGISTRY_UPDATED: EventType[EventFloorRegistryUpdatedData] = EventType(
    "floor_registry_updated"
)
STORAGE_KEY = "core.floor_registry"
STORAGE_VERSION_MAJOR = 1


class _FloorStoreData(TypedDict):
    """Data type for individual floor. Used in FloorRegistryStoreData."""

    aliases: list[str]
    floor_id: str
    icon: str | None
    level: int | None
    name: str


class FloorRegistryStoreData(TypedDict):
    """Store data type for FloorRegistry."""

    floors: list[_FloorStoreData]


class EventFloorRegistryUpdatedData(TypedDict):
    """Event data for when the floor registry is updated."""

    action: Literal["create", "remove", "update"]
    floor_id: str


type EventFloorRegistryUpdated = Event[EventFloorRegistryUpdatedData]


@dataclass(slots=True, kw_only=True, frozen=True)
class FloorEntry(NormalizedNameBaseRegistryEntry):
    """Floor registry entry."""

    aliases: set[str]
    floor_id: str
    icon: str | None = None
    level: int | None = None


class FloorRegistry(BaseRegistry[FloorRegistryStoreData]):
    """Class to hold a registry of floors."""

    floors: NormalizedNameBaseRegistryItems[FloorEntry]
    _floor_data: dict[str, FloorEntry]

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the floor registry."""
        self.hass = hass
        self._store = Store(
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
        return self.floors.get_by_name(name)

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
        level: int | None = None,
    ) -> FloorEntry:
        """Create a new floor."""
        self.hass.verify_event_loop_thread("floor_registry.async_create")
        if floor := self.async_get_floor_by_name(name):
            raise ValueError(
                f"The name {name} ({floor.normalized_name}) is already in use"
            )

        normalized_name = normalize_name(name)

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
        self.hass.bus.async_fire_internal(
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
        self.hass.verify_event_loop_thread("floor_registry.async_delete")
        del self.floors[floor_id]
        self.hass.bus.async_fire_internal(
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
            changes["normalized_name"] = normalize_name(name)

        if not changes:
            return old

        self.hass.verify_event_loop_thread("floor_registry.async_update")
        new = self.floors[floor_id] = dataclasses.replace(old, **changes)  # type: ignore[arg-type]

        self.async_schedule_save()
        self.hass.bus.async_fire_internal(
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
        floors = NormalizedNameBaseRegistryItems[FloorEntry]()

        if data is not None:
            for floor in data["floors"]:
                normalized_name = normalize_name(floor["name"])
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
    def _data_to_save(self) -> FloorRegistryStoreData:
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
@singleton(DATA_REGISTRY)
def async_get(hass: HomeAssistant) -> FloorRegistry:
    """Get floor registry."""
    return FloorRegistry(hass)


async def async_load(hass: HomeAssistant) -> None:
    """Load floor registry."""
    assert DATA_REGISTRY not in hass.data
    await async_get(hass).async_load()
