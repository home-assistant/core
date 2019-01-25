"""Provide a way to connect devices to one physical location."""
import logging
import uuid

from collections import OrderedDict

import attr

from homeassistant.core import callback
from homeassistant.loader import bind_hass

_LOGGER = logging.getLogger(__name__)

DATA_REGISTRY = 'area_registry'

STORAGE_KEY = 'core.area_registry'
STORAGE_VERSION = 1
SAVE_DELAY = 10


@attr.s(slots=True, frozen=True)
class AreaEntry:
    """Area Registry Entry."""

    name = attr.ib(type=str, default=None)
    id = attr.ib(type=str, default=attr.Factory(lambda: uuid.uuid4().hex))


class AreaRegistry:
    """Class to hold a registry of areas."""

    def __init__(self, hass):
        """Initialize the area registry."""
        self.hass = hass
        self.areas = None
        self._store = hass.helpers.storage.Store(STORAGE_VERSION, STORAGE_KEY)

    @callback
    def async_get_by_name(self, name):
        """Get AreaEntry by name."""
        for area in self.areas.values():
            if name == area.name:
                return area
        return None

    @callback
    def async_get_by_id(self, area_id: str):
        """Get AreaEntry by id."""
        return self.areas[area_id]

    @callback
    def async_get_or_create(self, *, name):
        """Get area. Create if it doesn't exist."""
        area = self.async_get_by_name(name)

        if area is None:
            area = AreaEntry()

        self.areas[area.id] = area

        return self._async_update_area(area.id, name=name)

    @callback
    def async_update_area(self, area_id, *, new_name):
        """Update area attributes."""
        return self._async_update_area(area_id, name=new_name)

    @callback
    def _async_update_area(self, area_id, *, name):
        """Private facing update properties method."""
        old = self.areas[area_id]

        changes = {}

        if name != old.name:
            changes['name'] = name

        if not changes:
            return old

        new = self.areas[area_id] = attr.evolve(old, **changes)
        self.async_schedule_save()
        return new

    async def async_load(self):
        """Load the area registry."""
        data = await self._store.async_load()

        areas = OrderedDict()

        if data is not None:
            for area in data['area']:
                areas[area['id']] = AreaEntry(
                    name=area['name'],
                    id=area['id']
                )

        self.areas = areas

    @callback
    def async_schedule_save(self):
        """Schedule saving the area registry."""
        self._store.async_delay_save(self._data_to_save, SAVE_DELAY)

    @callback
    def _data_to_save(self):
        """Return data of area registry to store in a file."""
        data = {}

        data['areas'] = [
            {
                'name': entry.name,
                'id': entry.id,
            } for entry in self.areas.values()
        ]

        return data


@bind_hass
async def async_get_registry(hass) -> AreaRegistry:
    """Return area registry instance."""
    task = hass.data.get(DATA_REGISTRY)

    if task is None:
        async def _load_reg():
            registry = AreaRegistry(hass)
            await registry.async_load()
            return registry

        task = hass.data[DATA_REGISTRY] = hass.async_create_task(_load_reg())

    return await task
