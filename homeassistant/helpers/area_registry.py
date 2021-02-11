"""Provide a way to connect devices to one physical location."""
from asyncio import gather
from collections import OrderedDict
from typing import Container, Dict, Iterable, List, MutableMapping, Optional, cast

import attr

from homeassistant.core import callback
from homeassistant.loader import bind_hass
from homeassistant.util import slugify

from .typing import HomeAssistantType

# mypy: disallow-any-generics

DATA_REGISTRY = "area_registry"
EVENT_AREA_REGISTRY_UPDATED = "area_registry_updated"
STORAGE_KEY = "core.area_registry"
STORAGE_VERSION = 1
SAVE_DELAY = 10


@attr.s(slots=True, frozen=True)
class AreaEntry:
    """Area Registry Entry."""

    name: str = attr.ib()
    id: Optional[str] = attr.ib(default=None)

    def generate_id(self, existing_ids: Container[str]) -> None:
        """Initialize ID."""
        suggestion = suggestion_base = slugify(self.name)
        tries = 1
        while suggestion in existing_ids:
            tries += 1
            suggestion = f"{suggestion_base}_{tries}"
        object.__setattr__(self, "id", suggestion)


class AreaRegistry:
    """Class to hold a registry of areas."""

    def __init__(self, hass: HomeAssistantType) -> None:
        """Initialize the area registry."""
        self.hass = hass
        self.areas: MutableMapping[str, AreaEntry] = {}
        self._store = hass.helpers.storage.Store(STORAGE_VERSION, STORAGE_KEY)

    @callback
    def async_get_area(self, area_id: str) -> Optional[AreaEntry]:
        """Get all areas."""
        return self.areas.get(area_id)

    @callback
    def async_list_areas(self) -> Iterable[AreaEntry]:
        """Get all areas."""
        return self.areas.values()

    @callback
    def async_create(self, name: str) -> AreaEntry:
        """Create a new area."""
        if self._async_is_registered(name):
            raise ValueError("Name is already in use")

        area = AreaEntry(name=name)
        area.generate_id(self.areas)
        assert area.id is not None
        self.areas[area.id] = area
        self.async_schedule_save()
        self.hass.bus.async_fire(
            EVENT_AREA_REGISTRY_UPDATED, {"action": "create", "area_id": area.id}
        )
        return area

    async def async_delete(self, area_id: str) -> None:
        """Delete area."""
        device_registry, entity_registry = await gather(
            self.hass.helpers.device_registry.async_get_registry(),
            self.hass.helpers.entity_registry.async_get_registry(),
        )
        device_registry.async_clear_area_id(area_id)
        entity_registry.async_clear_area_id(area_id)

        del self.areas[area_id]

        self.hass.bus.async_fire(
            EVENT_AREA_REGISTRY_UPDATED, {"action": "remove", "area_id": area_id}
        )

        self.async_schedule_save()

    @callback
    def async_update(self, area_id: str, name: str) -> AreaEntry:
        """Update name of area."""
        updated = self._async_update(area_id, name)
        self.hass.bus.async_fire(
            EVENT_AREA_REGISTRY_UPDATED, {"action": "update", "area_id": area_id}
        )
        return updated

    @callback
    def _async_update(self, area_id: str, name: str) -> AreaEntry:
        """Update name of area."""
        old = self.areas[area_id]

        changes = {}

        if name == old.name:
            return old

        if self._async_is_registered(name):
            raise ValueError("Name is already in use")

        changes["name"] = name

        new = self.areas[area_id] = attr.evolve(old, **changes)
        self.async_schedule_save()
        return new

    @callback
    def _async_is_registered(self, name: str) -> Optional[AreaEntry]:
        """Check if a name is currently registered."""
        for area in self.areas.values():
            if name == area.name:
                return area
        return None

    async def async_load(self) -> None:
        """Load the area registry."""
        data = await self._store.async_load()

        areas: MutableMapping[str, AreaEntry] = OrderedDict()

        if data is not None:
            for area in data["areas"]:
                areas[area["id"]] = AreaEntry(name=area["name"], id=area["id"])

        self.areas = areas

    @callback
    def async_schedule_save(self) -> None:
        """Schedule saving the area registry."""
        self._store.async_delay_save(self._data_to_save, SAVE_DELAY)

    @callback
    def _data_to_save(self) -> Dict[str, List[Dict[str, Optional[str]]]]:
        """Return data of area registry to store in a file."""
        data = {}

        data["areas"] = [
            {"name": entry.name, "id": entry.id} for entry in self.areas.values()
        ]

        return data


@callback
def async_get(hass: HomeAssistantType) -> AreaRegistry:
    """Get area registry."""
    return cast(AreaRegistry, hass.data[DATA_REGISTRY])


async def async_load(hass: HomeAssistantType) -> None:
    """Load area registry."""
    assert DATA_REGISTRY not in hass.data
    hass.data[DATA_REGISTRY] = AreaRegistry(hass)
    await hass.data[DATA_REGISTRY].async_load()


@bind_hass
async def async_get_registry(hass: HomeAssistantType) -> AreaRegistry:
    """Get area registry.

    This is deprecated and will be removed in the future. Use async_get instead.
    """
    return async_get(hass)
