"""Provide a registry to track entity IDs.

The Entity Registry keeps a registry of entities. Entities are uniquely
identified by their domain, platform and a unique id provided by that platform.

The Entity Registry will persist itself 10 seconds after a new entity is
registered. Registering a new entity while a timer is in progress resets the
timer.

After initializing, call EntityRegistry.async_ensure_loaded to load the data
from disk.
"""
import asyncio
from collections import OrderedDict
from itertools import chain
import logging
import os

import attr

from ..core import callback, split_entity_id
from ..util import ensure_unique_string, slugify
from ..util.yaml import load_yaml, save_yaml

PATH_REGISTRY = 'entity_registry.yaml'
SAVE_DELAY = 10
_LOGGER = logging.getLogger(__name__)


@attr.s(slots=True, frozen=True)
class RegistryEntry:
    """Entity Registry Entry."""

    entity_id = attr.ib(type=str)
    unique_id = attr.ib(type=str)
    platform = attr.ib(type=str)
    name = attr.ib(type=str, default=None)
    domain = attr.ib(type=str, default=None, init=False, repr=False)

    def __attrs_post_init__(self):
        """Computed properties."""
        object.__setattr__(self, "domain", split_entity_id(self.entity_id)[0])


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
                            suggested_object_id=None):
        """Get entity. Create if it doesn't exist."""
        for entity in self.entities.values():
            if entity.domain == domain and entity.platform == platform and \
               entity.unique_id == unique_id:
                return entity

        entity_id = self.async_generate_entity_id(
            domain, suggested_object_id or '{}_{}'.format(platform, unique_id))
        entity = RegistryEntry(
            entity_id=entity_id,
            unique_id=unique_id,
            platform=platform,
        )
        self.entities[entity_id] = entity
        _LOGGER.info('Registered new %s.%s entity: %s',
                     domain, platform, entity_id)
        self.async_schedule_save()
        return entity

    @asyncio.coroutine
    def async_ensure_loaded(self):
        """Load the registry from disk."""
        if self.entities is not None:
            return

        if self._load_task is None:
            self._load_task = self.hass.async_add_job(self._async_load)

        yield from self._load_task

    @asyncio.coroutine
    def _async_load(self):
        """Load the entity registry."""
        path = self.hass.config.path(PATH_REGISTRY)
        entities = OrderedDict()

        if os.path.isfile(path):
            data = yield from self.hass.async_add_job(load_yaml, path)

            for entity_id, info in data.items():
                entities[entity_id] = RegistryEntry(
                    entity_id=entity_id,
                    unique_id=info['unique_id'],
                    platform=info['platform'],
                    name=info.get('name')
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

    @asyncio.coroutine
    def _async_save(self):
        """Save the entity registry to a file."""
        self._sched_save = None
        data = OrderedDict()

        for entry in self.entities.values():
            data[entry.entity_id] = {
                'unique_id': entry.unique_id,
                'platform': entry.platform,
            }

        yield from self.hass.async_add_job(
            save_yaml, self.hass.config.path(PATH_REGISTRY), data)
