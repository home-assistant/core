"""Provide a way to connect devices to one physical location."""
from __future__ import annotations

from collections import UserDict
from collections.abc import Iterable, ValuesView
import dataclasses
from typing import Any, Literal, TypedDict, cast

from homeassistant.core import HomeAssistant, callback
from homeassistant.util import slugify

from . import device_registry as dr, entity_registry as er
from .storage import Store
from .typing import UNDEFINED, UndefinedType

DATA_REGISTRY = "area_registry"
EVENT_AREA_REGISTRY_UPDATED = "area_registry_updated"
STORAGE_KEY = "core.area_registry"
STORAGE_VERSION_MAJOR = 1
STORAGE_VERSION_MINOR = 4
SAVE_DELAY = 10


class EventAreaRegistryUpdatedData(TypedDict):
    """EventAreaRegistryUpdated data."""

    action: Literal["create", "remove", "update"]
    area_id: str


@dataclasses.dataclass(frozen=True, kw_only=True, slots=True)
class AreaEntry:
    """Area Registry Entry."""

    aliases: set[str]
    icon: str | None
    id: str
    name: str
    normalized_name: str
    picture: str | None


class AreaRegistryItems(UserDict[str, AreaEntry]):
    """Container for area registry items, maps area id -> entry.

    Maintains an additional index:
    - normalized name -> entry
    """

    def __init__(self) -> None:
        """Initialize the container."""
        super().__init__()
        self._normalized_names: dict[str, AreaEntry] = {}

    def values(self) -> ValuesView[AreaEntry]:
        """Return the underlying values to avoid __iter__ overhead."""
        return self.data.values()

    def __setitem__(self, key: str, entry: AreaEntry) -> None:
        """Add an item."""
        data = self.data
        normalized_name = normalize_area_name(entry.name)

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
        normalized_name = normalize_area_name(entry.name)
        del self._normalized_names[normalized_name]
        super().__delitem__(key)

    def get_area_by_name(self, name: str) -> AreaEntry | None:
        """Get area by name."""
        return self._normalized_names.get(normalize_area_name(name))


class AreaRegistryStore(Store[dict[str, list[dict[str, Any]]]]):
    """Store area registry data."""

    async def _async_migrate_func(
        self,
        old_major_version: int,
        old_minor_version: int,
        old_data: dict[str, list[dict[str, Any]]],
    ) -> dict[str, Any]:
        """Migrate to the new version."""
        if old_major_version < 2:
            if old_minor_version < 2:
                # Version 1.2 implements migration and freezes the available keys
                for area in old_data["areas"]:
                    # Populate keys which were introduced before version 1.2
                    area.setdefault("picture", None)

            if old_minor_version < 3:
                # Version 1.3 adds aliases
                for area in old_data["areas"]:
                    area["aliases"] = []

            if old_minor_version < 4:
                # Version 1.4 adds icon
                for area in old_data["areas"]:
                    area["icon"] = None

        if old_major_version > 1:
            raise NotImplementedError
        return old_data


class AreaRegistry:
    """Class to hold a registry of areas."""

    areas: AreaRegistryItems
    _area_data: dict[str, AreaEntry]

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the area registry."""
        self.hass = hass
        self._store = AreaRegistryStore(
            hass,
            STORAGE_VERSION_MAJOR,
            STORAGE_KEY,
            atomic_writes=True,
            minor_version=STORAGE_VERSION_MINOR,
        )

    @callback
    def async_get_area(self, area_id: str) -> AreaEntry | None:
        """Get area by id.

        We retrieve the DeviceEntry from the underlying dict to avoid
        the overhead of the UserDict __getitem__.
        """
        return self._area_data.get(area_id)

    @callback
    def async_get_area_by_name(self, name: str) -> AreaEntry | None:
        """Get area by name."""
        return self.areas.get_area_by_name(name)

    @callback
    def async_list_areas(self) -> Iterable[AreaEntry]:
        """Get all areas."""
        return self.areas.values()

    @callback
    def async_get_or_create(self, name: str) -> AreaEntry:
        """Get or create an area."""
        if area := self.async_get_area_by_name(name):
            return area
        return self.async_create(name)

    @callback
    def async_create(
        self,
        name: str,
        *,
        aliases: set[str] | None = None,
        icon: str | None = None,
        picture: str | None = None,
    ) -> AreaEntry:
        """Create a new area."""
        normalized_name = normalize_area_name(name)

        if self.async_get_area_by_name(name):
            raise ValueError(f"The name {name} ({normalized_name}) is already in use")

        area_id = self._generate_area_id(name)
        area = AreaEntry(
            aliases=aliases or set(),
            icon=icon,
            id=area_id,
            name=name,
            normalized_name=normalized_name,
            picture=picture,
        )
        assert area.id is not None
        self.areas[area.id] = area
        self.async_schedule_save()
        self.hass.bus.async_fire(
            EVENT_AREA_REGISTRY_UPDATED, {"action": "create", "area_id": area.id}
        )
        return area

    @callback
    def async_delete(self, area_id: str) -> None:
        """Delete area."""
        device_registry = dr.async_get(self.hass)
        entity_registry = er.async_get(self.hass)
        device_registry.async_clear_area_id(area_id)
        entity_registry.async_clear_area_id(area_id)

        del self.areas[area_id]

        self.hass.bus.async_fire(
            EVENT_AREA_REGISTRY_UPDATED, {"action": "remove", "area_id": area_id}
        )

        self.async_schedule_save()

    @callback
    def async_update(
        self,
        area_id: str,
        *,
        aliases: set[str] | UndefinedType = UNDEFINED,
        icon: str | None | UndefinedType = UNDEFINED,
        name: str | UndefinedType = UNDEFINED,
        picture: str | None | UndefinedType = UNDEFINED,
    ) -> AreaEntry:
        """Update name of area."""
        updated = self._async_update(
            area_id,
            aliases=aliases,
            icon=icon,
            name=name,
            picture=picture,
        )
        self.hass.bus.async_fire(
            EVENT_AREA_REGISTRY_UPDATED, {"action": "update", "area_id": area_id}
        )
        return updated

    @callback
    def _async_update(
        self,
        area_id: str,
        *,
        aliases: set[str] | UndefinedType = UNDEFINED,
        icon: str | None | UndefinedType = UNDEFINED,
        name: str | UndefinedType = UNDEFINED,
        picture: str | None | UndefinedType = UNDEFINED,
    ) -> AreaEntry:
        """Update name of area."""
        old = self.areas[area_id]

        new_values = {}

        for attr_name, value in (
            ("aliases", aliases),
            ("icon", icon),
            ("picture", picture),
        ):
            if value is not UNDEFINED and value != getattr(old, attr_name):
                new_values[attr_name] = value

        if name is not UNDEFINED and name != old.name:
            new_values["name"] = name
            new_values["normalized_name"] = normalize_area_name(name)

        if not new_values:
            return old

        new = self.areas[area_id] = dataclasses.replace(old, **new_values)  # type: ignore[arg-type]

        self.async_schedule_save()
        return new

    async def async_load(self) -> None:
        """Load the area registry."""
        data = await self._store.async_load()

        areas = AreaRegistryItems()

        if data is not None:
            for area in data["areas"]:
                assert area["name"] is not None and area["id"] is not None
                normalized_name = normalize_area_name(area["name"])
                areas[area["id"]] = AreaEntry(
                    aliases=set(area["aliases"]),
                    icon=area["icon"],
                    id=area["id"],
                    name=area["name"],
                    normalized_name=normalized_name,
                    picture=area["picture"],
                )

        self.areas = areas
        self._area_data = areas.data

    @callback
    def async_schedule_save(self) -> None:
        """Schedule saving the area registry."""
        self._store.async_delay_save(self._data_to_save, SAVE_DELAY)

    @callback
    def _data_to_save(self) -> dict[str, list[dict[str, Any]]]:
        """Return data of area registry to store in a file."""
        data = {}

        data["areas"] = [
            {
                "aliases": list(entry.aliases),
                "icon": entry.icon,
                "id": entry.id,
                "name": entry.name,
                "picture": entry.picture,
            }
            for entry in self.areas.values()
        ]

        return data

    def _generate_area_id(self, name: str) -> str:
        """Generate area ID."""
        suggestion = suggestion_base = slugify(name)
        tries = 1
        while suggestion in self.areas:
            tries += 1
            suggestion = f"{suggestion_base}_{tries}"
        return suggestion


@callback
def async_get(hass: HomeAssistant) -> AreaRegistry:
    """Get area registry."""
    return cast(AreaRegistry, hass.data[DATA_REGISTRY])


async def async_load(hass: HomeAssistant) -> None:
    """Load area registry."""
    assert DATA_REGISTRY not in hass.data
    hass.data[DATA_REGISTRY] = AreaRegistry(hass)
    await hass.data[DATA_REGISTRY].async_load()


def normalize_area_name(area_name: str) -> str:
    """Normalize an area name by removing whitespace and case folding."""
    return area_name.casefold().replace(" ", "")
