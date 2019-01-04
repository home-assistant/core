"""Provide a registry to track entity IDs.

The Entity Registry keeps a registry of entities. Entities are uniquely
identified by their domain, platform and a unique id provided by that platform.

The Entity Registry will persist itself 10 seconds after a new entity is
registered. Registering a new entity while a timer is in progress resets the
timer.
"""
from collections import OrderedDict
from itertools import chain
import logging
from typing import Optional
import weakref

import attr

from homeassistant.core import callback, split_entity_id, valid_entity_id
from homeassistant.loader import bind_hass
from homeassistant.util import ensure_unique_string, slugify
from homeassistant.util.yaml import load_yaml

PATH_REGISTRY = 'entity_registry.yaml'
DATA_REGISTRY = 'entity_registry'
SAVE_DELAY = 10
_LOGGER = logging.getLogger(__name__)
_UNDEF = object()
DISABLED_HASS = 'hass'
DISABLED_USER = 'user'

STORAGE_VERSION = 1
STORAGE_KEY = 'core.entity_registry'


@attr.s(slots=True, frozen=True)
class RegistryEntry:
    """Entity Registry Entry."""

    entity_id = attr.ib(type=str)
    unique_id = attr.ib(type=str)
    platform = attr.ib(type=str)
    name = attr.ib(type=str, default=None)
    device_id = attr.ib(type=str, default=None)
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

        Returns function to unlisten.
        """
        weak_listener = weakref.ref(listener)
        self.update_listeners.append(weak_listener)

        return lambda: self.update_listeners.remove(weak_listener)


class EntityRegistry:
    """Class to hold a registry of entities."""

    def __init__(self, hass):
        """Initialize the registry."""
        self.hass = hass
        self.entities = None
        self._store = hass.helpers.storage.Store(STORAGE_VERSION, STORAGE_KEY)

    @callback
    def async_is_registered(self, entity_id):
        """Check if an entity_id is currently registered."""
        return entity_id in self.entities

    @callback
    def async_get(self, entity_id: str) -> Optional[RegistryEntry]:
        """Get EntityEntry for an entity_id."""
        return self.entities.get(entity_id)

    @callback
    def async_get_entity_id(self, domain: str, platform: str, unique_id: str):
        """Check if an entity_id is currently registered."""
        for entity in self.entities.values():
            if entity.domain == domain and entity.platform == platform and \
               entity.unique_id == unique_id:
                return entity.entity_id
        return None

    @callback
    def async_generate_entity_id(self, domain, suggested_object_id,
                                 known_object_ids=None):
        """Generate an entity ID that does not conflict.

        Conflicts checked against registered and currently existing entities.
        """
        return ensure_unique_string(
            '{}.{}'.format(domain, slugify(suggested_object_id)),
            chain(self.entities.keys(),
                  self.hass.states.async_entity_ids(domain),
                  known_object_ids if known_object_ids else [])
        )

    @callback
    def async_get_or_create(self, domain, platform, unique_id, *,
                            suggested_object_id=None, config_entry_id=None,
                            device_id=None, known_object_ids=None):
        """Get entity. Create if it doesn't exist."""
        entity_id = self.async_get_entity_id(domain, platform, unique_id)
        if entity_id:
            return self._async_update_entity(
                entity_id, config_entry_id=config_entry_id,
                device_id=device_id)

        entity_id = self.async_generate_entity_id(
            domain, suggested_object_id or '{}_{}'.format(platform, unique_id),
            known_object_ids)

        entity = RegistryEntry(
            entity_id=entity_id,
            config_entry_id=config_entry_id,
            device_id=device_id,
            unique_id=unique_id,
            platform=platform,
        )
        self.entities[entity_id] = entity
        _LOGGER.info('Registered new %s.%s entity: %s',
                     domain, platform, entity_id)
        self.async_schedule_save()
        return entity

    @callback
    def async_update_entity(self, entity_id, *, name=_UNDEF,
                            new_entity_id=_UNDEF):
        """Update properties of an entity."""
        return self._async_update_entity(
            entity_id,
            name=name,
            new_entity_id=new_entity_id
        )

    @callback
    def _async_update_entity(self, entity_id, *, name=_UNDEF,
                             config_entry_id=_UNDEF, new_entity_id=_UNDEF,
                             device_id=_UNDEF):
        """Private facing update properties method."""
        old = self.entities[entity_id]

        changes = {}

        if name is not _UNDEF and name != old.name:
            changes['name'] = name

        if (config_entry_id is not _UNDEF and
                config_entry_id != old.config_entry_id):
            changes['config_entry_id'] = config_entry_id

        if (device_id is not _UNDEF and device_id != old.device_id):
            changes['device_id'] = device_id

        if new_entity_id is not _UNDEF and new_entity_id != old.entity_id:
            if self.async_is_registered(new_entity_id):
                raise ValueError('Entity is already registered')

            if not valid_entity_id(new_entity_id):
                raise ValueError('Invalid entity ID')

            if (split_entity_id(new_entity_id)[0] !=
                    split_entity_id(entity_id)[0]):
                raise ValueError('New entity ID should be same domain')

            self.entities.pop(entity_id)
            entity_id = changes['entity_id'] = new_entity_id

        if not changes:
            return old

        new = self.entities[entity_id] = attr.evolve(old, **changes)

        to_remove = []
        for listener_ref in new.update_listeners:
            listener = listener_ref()
            if listener is None:
                to_remove.append(listener_ref)
            else:
                try:
                    listener.async_registry_updated(old, new)
                except Exception:  # pylint: disable=broad-except
                    _LOGGER.exception('Error calling update listener')

        for ref in to_remove:
            new.update_listeners.remove(ref)

        self.async_schedule_save()

        return new

    async def async_load(self):
        """Load the entity registry."""
        data = await self.hass.helpers.storage.async_migrator(
            self.hass.config.path(PATH_REGISTRY), self._store,
            old_conf_load_func=load_yaml,
            old_conf_migrate_func=_async_migrate
        )
        entities = OrderedDict()

        if data is not None:
            for entity in data['entities']:
                entities[entity['entity_id']] = RegistryEntry(
                    entity_id=entity['entity_id'],
                    config_entry_id=entity.get('config_entry_id'),
                    device_id=entity.get('device_id'),
                    unique_id=entity['unique_id'],
                    platform=entity['platform'],
                    name=entity.get('name'),
                    disabled_by=entity.get('disabled_by')
                )

        self.entities = entities

    @callback
    def async_schedule_save(self):
        """Schedule saving the entity registry."""
        self._store.async_delay_save(self._data_to_save, SAVE_DELAY)

    @callback
    def _data_to_save(self):
        """Return data of entity registry to store in a file."""
        data = {}

        data['entities'] = [
            {
                'entity_id': entry.entity_id,
                'config_entry_id': entry.config_entry_id,
                'device_id': entry.device_id,
                'unique_id': entry.unique_id,
                'platform': entry.platform,
                'name': entry.name,
                'disabled_by': entry.disabled_by,
            } for entry in self.entities.values()
        ]

        return data

    @callback
    def async_clear_config_entry(self, config_entry):
        """Clear config entry from registry entries."""
        for entity_id, entry in self.entities.items():
            if config_entry == entry.config_entry_id:
                self._async_update_entity(entity_id, config_entry_id=None)


@bind_hass
async def async_get_registry(hass) -> EntityRegistry:
    """Return entity registry instance."""
    task = hass.data.get(DATA_REGISTRY)

    if task is None:
        async def _load_reg():
            registry = EntityRegistry(hass)
            await registry.async_load()
            return registry

        task = hass.data[DATA_REGISTRY] = hass.async_create_task(_load_reg())

    return await task


async def _async_migrate(entities):
    """Migrate the YAML config file to storage helper format."""
    return {
        'entities': [
            {'entity_id': entity_id, **info}
            for entity_id, info in entities.items()
        ]
    }
