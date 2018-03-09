"""Class to manage the entities for a single platform."""
import asyncio
from datetime import timedelta

from homeassistant.const import DEVICE_DEFAULT_NAME
from homeassistant.core import callback, valid_entity_id, split_entity_id
from homeassistant.exceptions import HomeAssistantError, PlatformNotReady
from homeassistant.util.async import (
    run_callback_threadsafe, run_coroutine_threadsafe)
import homeassistant.util.dt as dt_util

from .event import async_track_time_interval, async_track_point_in_time
from .entity_registry import async_get_registry

SLOW_SETUP_WARNING = 10
SLOW_SETUP_MAX_WAIT = 60
PLATFORM_NOT_READY_RETRIES = 10


class EntityPlatform(object):
    """Manage the entities for a single platform."""

    def __init__(self, *, hass, logger, domain, platform_name, scan_interval,
                 parallel_updates, entity_namespace,
                 async_entities_added_callback):
        """Initialize the entity platform.

        hass: HomeAssistant
        logger: Logger
        domain: str
        platform_name: str
        scan_interval: timedelta
        parallel_updates: int
        entity_namespace: str
        async_entities_added_callback: @callback method
        """
        self.hass = hass
        self.logger = logger
        self.domain = domain
        self.platform_name = platform_name
        self.scan_interval = scan_interval
        self.parallel_updates = None
        self.entity_namespace = entity_namespace
        self.async_entities_added_callback = async_entities_added_callback
        self.entities = {}
        self._tasks = []
        self._async_unsub_polling = None
        self._process_updates = asyncio.Lock(loop=hass.loop)

        if parallel_updates:
            self.parallel_updates = asyncio.Semaphore(
                parallel_updates, loop=hass.loop)

    async def async_setup(self, platform, platform_config, discovery_info=None,
                          tries=0):
        """Setup the platform."""
        logger = self.logger
        hass = self.hass
        full_name = '{}.{}'.format(self.domain, self.platform_name)

        logger.info("Setting up %s", full_name)
        warn_task = hass.loop.call_later(
            SLOW_SETUP_WARNING, logger.warning,
            "Setup of platform %s is taking over %s seconds.",
            self.platform_name, SLOW_SETUP_WARNING)

        try:
            if getattr(platform, 'async_setup_platform', None):
                task = platform.async_setup_platform(
                    hass, platform_config,
                    self._async_schedule_add_entities, discovery_info
                )
            else:
                # This should not be replaced with hass.async_add_job because
                # we don't want to track this task in case it blocks startup.
                task = hass.loop.run_in_executor(
                    None, platform.setup_platform, hass, platform_config,
                    self._schedule_add_entities, discovery_info
                )
            await asyncio.wait_for(
                asyncio.shield(task, loop=hass.loop),
                SLOW_SETUP_MAX_WAIT, loop=hass.loop)

            # Block till all entities are done
            if self._tasks:
                pending = [task for task in self._tasks if not task.done()]
                self._tasks.clear()

                if pending:
                    await asyncio.wait(
                        pending, loop=self.hass.loop)

            hass.config.components.add(full_name)
        except PlatformNotReady:
            tries += 1
            wait_time = min(tries, 6) * 30
            logger.warning(
                'Platform %s not ready yet. Retrying in %d seconds.',
                self.platform_name, wait_time)
            async_track_point_in_time(
                hass, self.async_setup(
                    platform, platform_config, discovery_info, tries),
                dt_util.utcnow() + timedelta(seconds=wait_time))
        except asyncio.TimeoutError:
            logger.error(
                "Setup of platform %s is taking longer than %s seconds."
                " Startup will proceed without waiting any longer.",
                self.platform_name, SLOW_SETUP_MAX_WAIT)
        except Exception:  # pylint: disable=broad-except
            logger.exception(
                "Error while setting up platform %s", self.platform_name)
        finally:
            warn_task.cancel()

    def _schedule_add_entities(self, new_entities, update_before_add=False):
        """Synchronously schedule adding entities for a single platform."""
        run_callback_threadsafe(
            self.hass.loop,
            self._async_schedule_add_entities, list(new_entities),
            update_before_add
        ).result()

    @callback
    def _async_schedule_add_entities(self, new_entities,
                                     update_before_add=False):
        """Schedule adding entities for a single platform async."""
        self._tasks.append(self.hass.async_add_job(
            self.async_add_entities(
                new_entities, update_before_add=update_before_add)
        ))

    def add_entities(self, new_entities, update_before_add=False):
        """Add entities for a single platform."""
        # That avoid deadlocks
        if update_before_add:
            self.logger.warning(
                "Call 'add_entities' with update_before_add=True "
                "only inside tests or you can run into a deadlock!")

        run_coroutine_threadsafe(
            self.async_add_entities(list(new_entities), update_before_add),
            self.hass.loop).result()

    async def async_add_entities(self, new_entities, update_before_add=False):
        """Add entities for a single platform async.

        This method must be run in the event loop.
        """
        # handle empty list from component/platform
        if not new_entities:
            return

        hass = self.hass
        component_entities = set(hass.states.async_entity_ids(self.domain))

        registry = await async_get_registry(hass)

        tasks = [
            self._async_add_entity(entity, update_before_add,
                                   component_entities, registry)
            for entity in new_entities]

        await asyncio.wait(tasks, loop=self.hass.loop)
        self.async_entities_added_callback()

        if self._async_unsub_polling is not None or \
           not any(entity.should_poll for entity
                   in self.entities.values()):
            return

        self._async_unsub_polling = async_track_time_interval(
            self.hass, self._update_entity_states, self.scan_interval
        )

    async def _async_add_entity(self, entity, update_before_add,
                                component_entities, registry):
        """Helper method to add an entity to the platform."""
        if entity is None:
            raise ValueError('Entity cannot be None')

        entity.hass = self.hass
        entity.platform = self
        entity.parallel_updates = self.parallel_updates

        # Update properties before we generate the entity_id
        if update_before_add:
            try:
                await entity.async_device_update(warning=False)
            except Exception:  # pylint: disable=broad-except
                self.logger.exception(
                    "%s: Error on device update!", self.platform_name)
                return

        suggested_object_id = None

        # Get entity_id from unique ID registration
        if entity.unique_id is not None:
            if entity.entity_id is not None:
                suggested_object_id = split_entity_id(entity.entity_id)[1]
            else:
                suggested_object_id = entity.name

            if self.entity_namespace is not None:
                suggested_object_id = '{} {}'.format(
                    self.entity_namespace, suggested_object_id)

            entry = registry.async_get_or_create(
                self.domain, self.platform_name, entity.unique_id,
                suggested_object_id=suggested_object_id)

            if entry.disabled:
                self.logger.info(
                    "Not adding entity %s because it's disabled",
                    entry.name or entity.name or
                    '"{} {}"'.format(self.platform_name, entity.unique_id))
                return

            entity.entity_id = entry.entity_id
            entity.registry_name = entry.name
            entry.add_update_listener(entity)

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
                self.domain, suggested_object_id)

        # Make sure it is valid in case an entity set the value themselves
        if not valid_entity_id(entity.entity_id):
            raise HomeAssistantError(
                'Invalid entity id: {}'.format(entity.entity_id))
        elif entity.entity_id in component_entities:
            msg = 'Entity id already exists: {}'.format(entity.entity_id)
            if entity.unique_id is not None:
                msg += '. Platform {} does not generate unique IDs'.format(
                    self.platform_name)
            raise HomeAssistantError(
                msg)

        self.entities[entity.entity_id] = entity
        component_entities.add(entity.entity_id)

        if hasattr(entity, 'async_added_to_hass'):
            await entity.async_added_to_hass()

        await entity.async_update_ha_state()

    async def async_reset(self):
        """Remove all entities and reset data.

        This method must be run in the event loop.
        """
        if not self.entities:
            return

        tasks = [self._async_remove_entity(entity_id)
                 for entity_id in self.entities]

        await asyncio.wait(tasks, loop=self.hass.loop)

        if self._async_unsub_polling is not None:
            self._async_unsub_polling()
            self._async_unsub_polling = None

    async def async_remove_entity(self, entity_id):
        """Remove entity id from platform."""
        await self._async_remove_entity(entity_id)

        # Clean up polling job if no longer needed
        if (self._async_unsub_polling is not None and
                not any(entity.should_poll for entity
                        in self.entities.values())):
            self._async_unsub_polling()
            self._async_unsub_polling = None

    async def _async_remove_entity(self, entity_id):
        """Remove entity id from platform."""
        entity = self.entities.pop(entity_id)

        if hasattr(entity, 'async_will_remove_from_hass'):
            await entity.async_will_remove_from_hass()

        self.hass.states.async_remove(entity_id)

    async def _update_entity_states(self, now):
        """Update the states of all the polling entities.

        To protect from flooding the executor, we will update async entities
        in parallel and other entities sequential.

        This method must be run in the event loop.
        """
        if self._process_updates.locked():
            self.logger.warning(
                "Updating %s %s took longer than the scheduled update "
                "interval %s", self.platform_name, self.domain,
                self.scan_interval)
            return

        with (await self._process_updates):
            tasks = []
            for entity in self.entities.values():
                if not entity.should_poll:
                    continue
                tasks.append(entity.async_update_ha_state(True))

            if tasks:
                await asyncio.wait(tasks, loop=self.hass.loop)
