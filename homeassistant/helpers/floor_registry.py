"""Provide a way to assign areas to floors in ones home."""
from __future__ import annotations

from collections.abc import Iterable, MutableMapping
import dataclasses
from dataclasses import dataclass
from typing import cast

from homeassistant.core import HomeAssistant, callback
from homeassistant.util import slugify

from . import area_registry as ar
from .typing import UNDEFINED, UndefinedType

DATA_REGISTRY = "floor_registry"
EVENT_FLOOR_REGISTRY_UPDATED = "floor_registry_updated"
STORAGE_KEY = "core.floor_registry"
STORAGE_VERSION_MAJOR = 1
SAVE_DELAY = 10


@dataclass(slots=True, frozen=True)
class FloorEntry:
    """Floor registry entry."""

    floor_id: str
    name: str
    normalized_name: str
    icon: str | None = None


class FloorRegistry:
    """Class to hold a registry of floors."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the floor registry."""
        self.hass = hass
        self.floors: MutableMapping[str, FloorEntry] = {}
        self._store = hass.helpers.storage.Store(
            STORAGE_VERSION_MAJOR,
            STORAGE_KEY,
            atomic_writes=True,
        )
        self._normalized_name_floor_idx: dict[str, str] = {}
        self.children: dict[str, set[str]] = {}

    @callback
    def async_get_floor(self, floor_id: str) -> FloorEntry | None:
        """Get floor by id."""
        return self.floors.get(floor_id)

    @callback
    def async_get_floor_by_name(self, name: str) -> FloorEntry | None:
        """Get floor by name."""
        normalized_name = normalize_floor_name(name)
        if normalized_name not in self._normalized_name_floor_idx:
            return None
        return self.floors[self._normalized_name_floor_idx[normalized_name]]

    @callback
    def async_list_floors(self) -> Iterable[FloorEntry]:
        """Get all floors."""
        return self.floors.values()

    @callback
    def async_get_or_create(self, name: str) -> FloorEntry:
        """Get or create an floor."""
        if floor := self.async_get_floor_by_name(name):
            return floor
        return self.async_create(name)

    @callback
    def _generate_id(self, name: str) -> str:
        """Initialize ID."""
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
        icon: str | None = None,
    ) -> FloorEntry:
        """Create a new floor."""
        normalized_name = normalize_floor_name(name)

        if self.async_get_floor_by_name(name):
            raise ValueError(f"The name {name} ({normalized_name}) is already in use")

        floor = FloorEntry(
            icon=icon,
            floor_id=self._generate_id(name),
            name=name,
            normalized_name=normalized_name,
        )
        self.floors[floor.floor_id] = floor
        self._normalized_name_floor_idx[normalized_name] = floor.floor_id
        self.async_schedule_save()
        self.hass.bus.async_fire(
            EVENT_FLOOR_REGISTRY_UPDATED,
            {"action": "create", "floor_id": floor.floor_id},
        )
        return floor

    @callback
    def async_delete(self, floor_id: str) -> None:
        """Delete floor."""
        floor = self.floors[floor_id]

        # Clean up any references to this floor
        ar.async_get(self.hass).async_clear_floor_id(floor_id)

        del self.floors[floor_id]
        del self._normalized_name_floor_idx[floor.normalized_name]

        self.hass.bus.async_fire(
            EVENT_FLOOR_REGISTRY_UPDATED, {"action": "remove", "floor_id": floor_id}
        )

        self.async_schedule_save()

    @callback
    def async_update(
        self,
        floor_id: str,
        icon: str | None | UndefinedType = UNDEFINED,
        name: str | UndefinedType = UNDEFINED,
    ) -> FloorEntry:
        """Update name of the floor."""
        old = self.floors[floor_id]
        changes = {}

        if icon is not UNDEFINED and old.icon != icon:
            changes["icon"] = icon

        normalized_name = None
        if name is not UNDEFINED and name != old.name:
            normalized_name = normalize_floor_name(name)
            if normalized_name != old.normalized_name and self.async_get_floor_by_name(
                name
            ):
                raise ValueError(
                    f"The name {name} ({normalized_name}) is already in use"
                )

            changes["name"] = name
            changes["normalized_name"] = normalized_name

        if not changes:
            return old

        new = self.floors[floor_id] = dataclasses.replace(old, **changes)  # type: ignore[arg-type]
        if normalized_name is not None:
            self._normalized_name_floor_idx[
                normalized_name
            ] = self._normalized_name_floor_idx.pop(old.normalized_name)

        self.async_schedule_save()
        self.hass.bus.async_fire(
            EVENT_FLOOR_REGISTRY_UPDATED, {"action": "update", "floor_id": floor_id}
        )

        return new

    async def async_load(self) -> None:
        """Load the floor registry."""
        data = await self._store.async_load()
        floors: MutableMapping[str, FloorEntry] = {}

        if data is not None:
            for floor in data["floors"]:
                normalized_name = normalize_floor_name(floor["name"])
                floors[floor["floor_id"]] = FloorEntry(
                    icon=floor["icon"],
                    floor_id=floor["floor_id"],
                    name=floor["name"],
                    normalized_name=normalized_name,
                )
                self._normalized_name_floor_idx[normalized_name] = floor["floor_id"]

        self.floors = floors

    @callback
    def async_schedule_save(self) -> None:
        """Schedule saving the floor registry."""
        self._store.async_delay_save(self._data_to_save, SAVE_DELAY)

    @callback
    def _data_to_save(self) -> dict[str, list[dict[str, str | None]]]:
        """Return data of floor registry to store in a file."""
        return {
            "floors": [
                {
                    "icon": entry.icon,
                    "floor_id": entry.floor_id,
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


def normalize_floor_name(floor_name: str) -> str:
    """Normalize an floor name by removing whitespace and case folding."""
    return floor_name.casefold().replace(" ", "")
