"""Class to manage the entities for a single platform."""
import asyncio
from datetime import timedelta

from homeassistant.const import DEVICE_DEFAULT_NAME
from homeassistant.core import callback, valid_entity_id, split_entity_id
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util.async import (
    run_callback_threadsafe, run_coroutine_threadsafe)
from .entity_registry import EntityRegistry

DATA_REGISTRY = 'entity_registry'


class EntityPlatform(object):
    """Manage the entities for a single platform."""

    def __init__(self, component, platform, scan_interval, parallel_updates,
                 entity_namespace):
        """Initialize the entity platform.

        component: EntityComponent
        platform: str
        scan_interval: timedelta
        parallel_updates: int
        entity_namespace: str
        """
        self.component = component
        self.platform = platform
        self.scan_interval = scan_interval
        self.parallel_updates = None
        self.entity_namespace = entity_namespace
        self.entities = {}
        self._tasks = []
        self._async_unsub_polling = None
        self._process_updates = asyncio.Lock(loop=component.hass.loop)

        if parallel_updates:
            self.parallel_updates = asyncio.Semaphore(
                parallel_updates, loop=component.hass.loop)

    @asyncio.coroutine
    def async_block_entities_done(self):
        """Wait until all entities add to hass."""
        if self._tasks:
            pending = [task for task in self._tasks if not task.done()]
            self._tasks.clear()

            if pending:
                yield from asyncio.wait(pending, loop=self.component.hass.loop)

    def schedule_add_entities(self, new_entities, update_before_add=False):
        """Add entities for a single platform."""
        run_callback_threadsafe(
            self.component.hass.loop,
            self.async_schedule_add_entities, list(new_entities),
            update_before_add
        ).result()

    @callback
    def async_schedule_add_entities(self, new_entities,
                                    update_before_add=False):
        """Add entities for a single platform async."""
        self._tasks.append(self.component.hass.async_add_job(
            self.async_add_entities(
                new_entities, update_before_add=update_before_add)
        ))

    def add_entities(self, new_entities, update_before_add=False):
        """Add entities for a single platform."""
        # That avoid deadlocks
        if update_before_add:
            self.component.logger.warning(
                "Call 'add_entities' with update_before_add=True "
                "only inside tests or you can run into a deadlock!")

        run_coroutine_threadsafe(
            self.async_add_entities(list(new_entities), update_before_add),
            self.component.hass.loop).result()

    @asyncio.coroutine
    def async_add_entities(self, new_entities, update_before_add=False):
        """Add entities for a single platform async.

        This method must be run in the event loop.
        """
        # handle empty list from component/platform
        if not new_entities:
            return

        hass = self.component.hass
        component_entities = set(entity.entity_id for entity
                                 in self.component.entities)

        registry = hass.data.get(DATA_REGISTRY)

        if registry is None:
            registry = hass.data[DATA_REGISTRY] = EntityRegistry(hass)

        yield from registry.async_ensure_loaded()

        tasks = [
            self._async_add_entity(entity, update_before_add,
                                   component_entities, registry)
            for entity in new_entities]

        yield from asyncio.wait(tasks, loop=self.component.hass.loop)
        self.component.async_update_group()

        if self._async_unsub_polling is not None or \
           not any(entity.should_poll for entity
                   in self.entities.values()):
            return

        self._async_unsub_polling = async_track_time_interval(
            self.component.hass, self._update_entity_states, self.scan_interval
        )

    @asyncio.coroutine
    def _async_add_entity(self, entity, update_before_add, component_entities,
                          registry):
        """Helper method to add an entity to the platform."""
        if entity is None:
            raise ValueError('Entity cannot be None')

        entity.hass = self.component.hass
        entity.platform = self
        entity.parallel_updates = self.parallel_updates

        # Update properties before we generate the entity_id
        if update_before_add:
            try:
                yield from entity.async_device_update(warning=False)
            except Exception:  # pylint: disable=broad-except
                self.component.logger.exception(
                    "%s: Error on device update!", self.platform)
                return

        suggested_object_id = None

        # Get entity_id from unique ID registration
        if entity.unique_id is not None:
            if entity.entity_id is not None:
                suggested_object_id = split_entity_id(entity.entity_id)[1]
            else:
                suggested_object_id = entity.name

            entry = registry.async_get_or_create(
                self.component.domain, self.platform, entity.unique_id,
                suggested_object_id=suggested_object_id)
            entity.entity_id = entry.entity_id

        # We won't generate an entity ID if the platform has already set one
        # We will however make sure that platform cannot pick a registered ID
        elif (entity.entity_id is not None and
              registry.async_is_registered(entity.entity_id)):
            # If entity already registered, convert entity id to suggestion
            suggested_object_id = split_entity_id(entity.entity_id)[1]
            entity.entity_id = None

        # Generate entity ID
        if entity.entity_id is None:
            suggested_object_id = \
                suggested_object_id or entity.name or DEVICE_DEFAULT_NAME

            if self.entity_namespace is not None:
                suggested_object_id = '{} {}'.format(self.entity_namespace,
                                                     suggested_object_id)

            entity.entity_id = registry.async_generate_entity_id(
                self.component.domain, suggested_object_id)

        # Make sure it is valid in case an entity set the value themselves
        if not valid_entity_id(entity.entity_id):
            raise HomeAssistantError(
                'Invalid entity id: {}'.format(entity.entity_id))
        elif entity.entity_id in component_entities:
            raise HomeAssistantError(
                'Entity id already exists: {}'.format(entity.entity_id))

        self.entities[entity.entity_id] = entity
        component_entities.add(entity.entity_id)

        if hasattr(entity, 'async_added_to_hass'):
            yield from entity.async_added_to_hass()

        yield from entity.async_update_ha_state()

    @asyncio.coroutine
    def async_reset(self):
        """Remove all entities and reset data.

        This method must be run in the event loop.
        """
        if not self.entities:
            return

        tasks = [self._async_remove_entity(entity_id)
                 for entity_id in self.entities]

        yield from asyncio.wait(tasks, loop=self.component.hass.loop)

        if self._async_unsub_polling is not None:
            self._async_unsub_polling()
            self._async_unsub_polling = None

    @asyncio.coroutine
    def async_remove_entity(self, entity_id):
        """Remove entity id from platform."""
        yield from self._async_remove_entity(entity_id)

        # Clean up polling job if no longer needed
        if (self._async_unsub_polling is not None and
                not any(entity.should_poll for entity
                        in self.entities.values())):
            self._async_unsub_polling()
            self._async_unsub_polling = None

    @asyncio.coroutine
    def _async_remove_entity(self, entity_id):
        """Remove entity id from platform."""
        entity = self.entities.pop(entity_id)

        if hasattr(entity, 'async_will_remove_from_hass'):
            yield from entity.async_will_remove_from_hass()

        self.component.hass.states.async_remove(entity_id)

    @asyncio.coroutine
    def _update_entity_states(self, now):
        """Update the states of all the polling entities.

        To protect from flooding the executor, we will update async entities
        in parallel and other entities sequential.

        This method must be run in the event loop.
        """
        if self._process_updates.locked():
            self.component.logger.warning(
                "Updating %s %s took longer than the scheduled update "
                "interval %s", self.platform, self.component.domain,
                self.scan_interval)
            return

        with (yield from self._process_updates):
            tasks = []
            for entity in self.entities.values():
                if not entity.should_poll:
                    continue
                tasks.append(entity.async_update_ha_state(True))

            if tasks:
                yield from asyncio.wait(tasks, loop=self.component.hass.loop)
