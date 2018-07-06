"""Provide a registry to track entity IDs.

The Entity Registry keeps a registry of entities. Entities are uniquely
identified by their domain, platform and a unique id provided by that platform.

The Entity Registry will persist itself 10 seconds after a new entity is
registered. Registering a new entity while a timer is in progress resets the
timer.

After initializing, call EntityRegistry.async_ensure_loaded to load the data
from disk.
"""

from collections import OrderedDict
from itertools import chain
import logging
import os
import weakref

import attr

from ..core import callback, split_entity_id
from ..loader import bind_hass
from ..util import ensure_unique_string, slugify
from ..util.yaml import load_yaml, save_yaml

PATH_REGISTRY = 'entity_registry.yaml'
DATA_REGISTRY = 'entity_registry'
SAVE_DELAY = 10
_LOGGER = logging.getLogger(__name__)
_UNDEF = object()
DISABLED_HASS = 'hass'
DISABLED_USER = 'user'


@attr.s(slots=True, frozen=True)
class RegistryEntry:
    """Entity Registry Entry."""

    entity_id = attr.ib(type=str)
    unique_id = attr.ib(type=str)
    platform = attr.ib(type=str)
    name = attr.ib(type=str, default=None)
    config_entry_id = attr.ib(type=str, default=None)
    disabled_by = attr.ib(
        type=str, default=None,
        validator=attr.validators.in_((DISABLED_HASS, DISABLED_USER, None)))
    update_listeners = attr.ib(type=list, default=attr.Factory(list),
                               repr=False)
    domain = attr.ib(type=str, init=False, repr=False)

    @domain.default
    def _domain_default(self):
        """Compute domain value."""
        return split_entity_id(self.entity_id)[0]

    @property
    def disabled(self):
        """Return if entry is disabled."""
        return self.disabled_by is not None

    def add_update_listener(self, listener):
        """Listen for when entry is updated.

        Listener: Callback function(old_entry, new_entry)
        """
        self.update_listeners.append(weakref.ref(listener))


class EntityRegistry:
    """Class to hold a registry of entities."""

    def __init__(self, hass):
        """Initialize the registry."""
        self.hass = hass
        self.entities = None
        self._load_task = None
        self._sched_save = None

    @callback
    def async_is_registered(self, entity_id):
        """Check if an entity_id is currently registered."""
        return entity_id in self.entities

    @callback
    def async_get_entity_id(self, domain: str, platform: str, unique_id: str):
        """Check if an entity_id is currently registered."""
        for entity in self.entities.values():
            if entity.domain == domain and entity.platform == platform and \
               entity.unique_id == unique_id:
                return entity.entity_id
        return None

    @callback
    def async_generate_entity_id(self, domain, suggested_object_id):
        """Generate an entity ID that does not conflict.

        Conflicts checked against registered and currently existing entities.
        """
        return ensure_unique_string(
            '{}.{}'.format(domain, slugify(suggested_object_id)),
            chain(self.entities.keys(),
                  self.hass.states.async_entity_ids(domain))
        )

    @callback
    def async_get_or_create(self, domain, platform, unique_id, *,
                            suggested_object_id=None, config_entry_id=None):
        """Get entity. Create if it doesn't exist."""
        entity_id = self.async_get_entity_id(domain, platform, unique_id)
        if entity_id:
            return self.entities[entity_id]

        entity_id = self.async_generate_entity_id(
            domain, suggested_object_id or '{}_{}'.format(platform, unique_id))

        entity = RegistryEntry(
            entity_id=entity_id,
            config_entry_id=config_entry_id,
            unique_id=unique_id,
            platform=platform,
        )
        self.entities[entity_id] = entity
        _LOGGER.info('Registered new %s.%s entity: %s',
                     domain, platform, entity_id)
        self.async_schedule_save()
        return entity

    @callback
    def async_update_entity(self, entity_id, *, name=_UNDEF):
        """Update properties of an entity."""
        old = self.entities[entity_id]

        changes = {}

        if name is not _UNDEF and name != old.name:
            changes['name'] = name

        if not changes:
            return old

        new = self.entities[entity_id] = attr.evolve(old, **changes)

        to_remove = []
        for listener_ref in new.update_listeners:
            listener = listener_ref()
            if listener is None:
                to_remove.append(listener)
            else:
                try:
                    listener.async_registry_updated(old, new)
                except Exception:  # pylint: disable=broad-except
                    _LOGGER.exception('Error calling update listener')

        for ref in to_remove:
            new.update_listeners.remove(ref)

        self.async_schedule_save()

        return new

    async def async_ensure_loaded(self):
        """Load the registry from disk."""
        if self.entities is not None:
            return

        if self._load_task is None:
            self._load_task = self.hass.async_add_job(self._async_load)

        await self._load_task

    async def _async_load(self):
        """Load the entity registry."""
        path = self.hass.config.path(PATH_REGISTRY)
        entities = OrderedDict()

        if os.path.isfile(path):
            data = await self.hass.async_add_job(load_yaml, path)

            for entity_id, info in data.items():
                entities[entity_id] = RegistryEntry(
                    entity_id=entity_id,
                    config_entry_id=info.get('config_entry_id'),
                    unique_id=info['unique_id'],
                    platform=info['platform'],
                    name=info.get('name'),
                    disabled_by=info.get('disabled_by')
                )

        self.entities = entities
        self._load_task = None

    @callback
    def async_schedule_save(self):
        """Schedule saving the entity registry."""
        if self._sched_save is not None:
            self._sched_save.cancel()

        self._sched_save = self.hass.loop.call_later(
            SAVE_DELAY, self.hass.async_add_job, self._async_save
        )

    async def _async_save(self):
        """Save the entity registry to a file."""
        self._sched_save = None
        data = OrderedDict()

        for entry in self.entities.values():
            data[entry.entity_id] = {
                'config_entry_id': entry.config_entry_id,
                'unique_id': entry.unique_id,
                'platform': entry.platform,
                'name': entry.name,
            }

        await self.hass.async_add_job(
            save_yaml, self.hass.config.path(PATH_REGISTRY), data)


@bind_hass
async def async_get_registry(hass) -> EntityRegistry:
    """Return entity registry instance."""
    registry = hass.data.get(DATA_REGISTRY)

    if registry is None:
        registry = hass.data[DATA_REGISTRY] = EntityRegistry(hass)

    await registry.async_ensure_loaded()
    return registry
