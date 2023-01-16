"""Provide a way to connect devices to one physical location."""
from __future__ import annotations

from collections import OrderedDict
from collections.abc import Container, Iterable, MutableMapping
from typing import Any, cast

import attr

from homeassistant.core import HomeAssistant, callback
from homeassistant.loader import bind_hass
from homeassistant.util import slugify

from . import device_registry as dr, entity_registry as er
from .frame import report
from .storage import Store
from .typing import UNDEFINED, UndefinedType

DATA_REGISTRY = "area_registry"
EVENT_AREA_REGISTRY_UPDATED = "area_registry_updated"
STORAGE_KEY = "core.area_registry"
STORAGE_VERSION_MAJOR = 1
STORAGE_VERSION_MINOR = 3
SAVE_DELAY = 10


@attr.s(slots=True, frozen=True)
class AreaEntry:
    """Area Registry Entry."""

    name: str = attr.ib()
    normalized_name: str = attr.ib()
    aliases: set[str] = attr.ib(
        converter=attr.converters.default_if_none(factory=set)  # type: ignore[misc]
    )
    id: str | None = attr.ib(default=None)
    picture: str | None = attr.ib(default=None)

    def generate_id(self, existing_ids: Container[str]) -> None:
        """Initialize ID."""
        suggestion = suggestion_base = slugify(self.name)
        tries = 1
        while suggestion in existing_ids:
            tries += 1
            suggestion = f"{suggestion_base}_{tries}"
        object.__setattr__(self, "id", suggestion)


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

        if old_major_version > 1:
            raise NotImplementedError
        return old_data


class AreaRegistry:
    """Class to hold a registry of areas."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the area registry."""
        self.hass = hass
        self.areas: MutableMapping[str, AreaEntry] = {}
        self._store = AreaRegistryStore(
            hass,
            STORAGE_VERSION_MAJOR,
            STORAGE_KEY,
            atomic_writes=True,
            minor_version=STORAGE_VERSION_MINOR,
        )
        self._normalized_name_area_idx: dict[str, str] = {}

    @callback
    def async_get_area(self, area_id: str) -> AreaEntry | None:
        """Get area by id."""
        return self.areas.get(area_id)

    @callback
    def async_get_area_by_name(self, name: str) -> AreaEntry | None:
        """Get area by name."""
        normalized_name = normalize_area_name(name)
        if normalized_name not in self._normalized_name_area_idx:
            return None
        return self.areas[self._normalized_name_area_idx[normalized_name]]

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
        picture: str | None = None,
    ) -> AreaEntry:
        """Create a new area."""
        normalized_name = normalize_area_name(name)

        if self.async_get_area_by_name(name):
            raise ValueError(f"The name {name} ({normalized_name}) is already in use")

        area = AreaEntry(
            aliases=aliases, name=name, normalized_name=normalized_name, picture=picture
        )
        area.generate_id(self.areas)
        assert area.id is not None
        self.areas[area.id] = area
        self._normalized_name_area_idx[normalized_name] = area.id
        self.async_schedule_save()
        self.hass.bus.async_fire(
            EVENT_AREA_REGISTRY_UPDATED, {"action": "create", "area_id": area.id}
        )
        return area

    @callback
    def async_delete(self, area_id: str) -> None:
        """Delete area."""
        area = self.areas[area_id]
        device_registry = dr.async_get(self.hass)
        entity_registry = er.async_get(self.hass)
        device_registry.async_clear_area_id(area_id)
        entity_registry.async_clear_area_id(area_id)

        del self.areas[area_id]
        del self._normalized_name_area_idx[area.normalized_name]

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
        name: str | UndefinedType = UNDEFINED,
        picture: str | None | UndefinedType = UNDEFINED,
    ) -> AreaEntry:
        """Update name of area."""
        updated = self._async_update(
            area_id, aliases=aliases, name=name, picture=picture
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
        name: str | UndefinedType = UNDEFINED,
        picture: str | None | UndefinedType = UNDEFINED,
    ) -> AreaEntry:
        """Update name of area."""
        old = self.areas[area_id]

        new_values = {}

        for attr_name, value in (
            ("aliases", aliases),
            ("picture", picture),
        ):
            if value is not UNDEFINED and value != getattr(old, attr_name):
                new_values[attr_name] = value

        normalized_name = None

        if name is not UNDEFINED and name != old.name:
            normalized_name = normalize_area_name(name)

            if normalized_name != old.normalized_name and self.async_get_area_by_name(
                name
            ):
                raise ValueError(
                    f"The name {name} ({normalized_name}) is already in use"
                )

            new_values["name"] = name
            new_values["normalized_name"] = normalized_name

        if not new_values:
            return old

        new = self.areas[area_id] = attr.evolve(old, **new_values)
        if normalized_name is not None:
            self._normalized_name_area_idx[
                normalized_name
            ] = self._normalized_name_area_idx.pop(old.normalized_name)

        self.async_schedule_save()
        return new

    async def async_load(self) -> None:
        """Load the area registry."""
        data = await self._store.async_load()

        areas: MutableMapping[str, AreaEntry] = OrderedDict()

        if data is not None:
            for area in data["areas"]:
                assert area["name"] is not None and area["id"] is not None
                normalized_name = normalize_area_name(area["name"])
                areas[area["id"]] = AreaEntry(
                    aliases=set(area["aliases"]),
                    id=area["id"],
                    name=area["name"],
                    normalized_name=normalized_name,
                    picture=area["picture"],
                )
                self._normalized_name_area_idx[normalized_name] = area["id"]

        self.areas = areas

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
                "name": entry.name,
                "id": entry.id,
                "picture": entry.picture,
            }
            for entry in self.areas.values()
        ]

        return data


@callback
def async_get(hass: HomeAssistant) -> AreaRegistry:
    """Get area registry."""
    return cast(AreaRegistry, hass.data[DATA_REGISTRY])


async def async_load(hass: HomeAssistant) -> None:
    """Load area registry."""
    assert DATA_REGISTRY not in hass.data
    hass.data[DATA_REGISTRY] = AreaRegistry(hass)
    await hass.data[DATA_REGISTRY].async_load()


@bind_hass
async def async_get_registry(hass: HomeAssistant) -> AreaRegistry:
    """Get area registry.

    This is deprecated and will be removed in the future. Use async_get instead.
    """
    report(
        "uses deprecated `async_get_registry` to access area registry, use async_get"
        " instead"
    )
    return async_get(hass)


def normalize_area_name(area_name: str) -> str:
    """Normalize an area name by removing whitespace and case folding."""
    return area_name.casefold().replace(" ", "")
