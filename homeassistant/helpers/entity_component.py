"""Helpers for components that manage entities."""
import asyncio
from datetime import timedelta
from itertools import chain

from homeassistant import config as conf_util
from homeassistant.setup import async_prepare_setup_platform
from homeassistant.const import (
    ATTR_ENTITY_ID, CONF_SCAN_INTERVAL, CONF_ENTITY_NAMESPACE,
    DEVICE_DEFAULT_NAME)
from homeassistant.core import callback, valid_entity_id
from homeassistant.exceptions import HomeAssistantError, PlatformNotReady
from homeassistant.helpers import config_per_platform, discovery
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.event import (
    async_track_time_interval, async_track_point_in_time)
from homeassistant.helpers.service import extract_entity_ids
from homeassistant.util import slugify
from homeassistant.util.async import (
    run_callback_threadsafe, run_coroutine_threadsafe)
import homeassistant.util.dt as dt_util

DEFAULT_SCAN_INTERVAL = timedelta(seconds=15)
SLOW_SETUP_WARNING = 10
SLOW_SETUP_MAX_WAIT = 60
PLATFORM_NOT_READY_RETRIES = 10


class EntityComponent(object):
    """The EntityComponent manages platforms that manages entities.

    This class has the following responsibilities:
     - Process the configuration and set up a platform based component.
     - Manage the platforms and their entities.
     - Help extract the entities from a service call.
     - Maintain a group that tracks all platform entities.
     - Listen for discovery events for platforms related to the domain.
    """

    def __init__(self, logger, domain, hass,
                 scan_interval=DEFAULT_SCAN_INTERVAL, group_name=None):
        """Initialize an entity component."""
        self.logger = logger
        self.hass = hass

        self.domain = domain
        self.entity_id_format = domain + '.{}'
        self.scan_interval = scan_interval
        self.group_name = group_name

        self.config = None

        self._platforms = {
            'core': EntityPlatform(self, domain, self.scan_interval, 0, None),
        }
        self.async_add_entities = self._platforms['core'].async_add_entities
        self.add_entities = self._platforms['core'].add_entities

    @property
    def entities(self):
        """Return an iterable that returns all entities."""
        return chain.from_iterable(platform.entities.values() for platform
                                   in self._platforms.values())

    def get_entity(self, entity_id):
        """Helper method to get an entity."""
        for platform in self._platforms.values():
            entity = platform.entities.get(entity_id)
            if entity is not None:
                return entity
        return None

    def setup(self, config):
        """Set up a full entity component.

        This doesn't block the executor to protect from deadlocks.
        """
        self.hass.add_job(self.async_setup(config))

    @asyncio.coroutine
    def async_setup(self, config):
        """Set up a full entity component.

        Loads the platforms from the config and will listen for supported
        discovered platforms.

        This method must be run in the event loop.
        """
        self.config = config

        # Look in config for Domain, Domain 2, Domain 3 etc and load them
        tasks = []
        for p_type, p_config in config_per_platform(config, self.domain):
            tasks.append(self._async_setup_platform(p_type, p_config))

        if tasks:
            yield from asyncio.wait(tasks, loop=self.hass.loop)

        # Generic discovery listener for loading platform dynamically
        # Refer to: homeassistant.components.discovery.load_platform()
        @asyncio.coroutine
        def component_platform_discovered(platform, info):
            """Handle the loading of a platform."""
            yield from self._async_setup_platform(platform, {}, info)

        discovery.async_listen_platform(
            self.hass, self.domain, component_platform_discovered)

    def extract_from_service(self, service, expand_group=True):
        """Extract all known entities from a service call.

        Will return all entities if no entities specified in call.
        Will return an empty list if entities specified but unknown.
        """
        return run_callback_threadsafe(
            self.hass.loop, self.async_extract_from_service, service,
            expand_group
        ).result()

    @callback
    def async_extract_from_service(self, service, expand_group=True):
        """Extract all known and available entities from a service call.

        Will return all entities if no entities specified in call.
        Will return an empty list if entities specified but unknown.

        This method must be run in the event loop.
        """
        if ATTR_ENTITY_ID not in service.data:
            return [entity for entity in self.entities if entity.available]

        entity_ids = set(extract_entity_ids(self.hass, service, expand_group))
        return [entity for entity in self.entities
                if entity.available and entity.entity_id in entity_ids]

    @asyncio.coroutine
    def _async_setup_platform(self, platform_type, platform_config,
                              discovery_info=None, tries=0):
        """Set up a platform for this component.

        This method must be run in the event loop.
        """
        platform = yield from async_prepare_setup_platform(
            self.hass, self.config, self.domain, platform_type)

        if platform is None:
            return

        # Config > Platform > Component
        scan_interval = (
            platform_config.get(CONF_SCAN_INTERVAL) or
            getattr(platform, 'SCAN_INTERVAL', None) or self.scan_interval)
        parallel_updates = getattr(
            platform, 'PARALLEL_UPDATES',
            int(not hasattr(platform, 'async_setup_platform')))

        entity_namespace = platform_config.get(CONF_ENTITY_NAMESPACE)

        key = (platform_type, scan_interval, entity_namespace)

        if key not in self._platforms:
            entity_platform = self._platforms[key] = EntityPlatform(
                self, platform_type, scan_interval, parallel_updates,
                entity_namespace)
        else:
            entity_platform = self._platforms[key]

        self.logger.info("Setting up %s.%s", self.domain, platform_type)
        warn_task = self.hass.loop.call_later(
            SLOW_SETUP_WARNING, self.logger.warning,
            "Setup of platform %s is taking over %s seconds.", platform_type,
            SLOW_SETUP_WARNING)

        try:
            if getattr(platform, 'async_setup_platform', None):
                task = platform.async_setup_platform(
                    self.hass, platform_config,
                    entity_platform.async_schedule_add_entities, discovery_info
                )
            else:
                # This should not be replaced with hass.async_add_job because
                # we don't want to track this task in case it blocks startup.
                task = self.hass.loop.run_in_executor(
                    None, platform.setup_platform, self.hass, platform_config,
                    entity_platform.schedule_add_entities, discovery_info
                )
            yield from asyncio.wait_for(
                asyncio.shield(task, loop=self.hass.loop),
                SLOW_SETUP_MAX_WAIT, loop=self.hass.loop)
            yield from entity_platform.async_block_entities_done()
            self.hass.config.components.add(
                '{}.{}'.format(self.domain, platform_type))
        except PlatformNotReady:
            tries += 1
            wait_time = min(tries, 6) * 30
            self.logger.warning(
                'Platform %s not ready yet. Retrying in %d seconds.',
                platform_type, wait_time)
            async_track_point_in_time(
                self.hass, self._async_setup_platform(
                    platform_type, platform_config, discovery_info, tries),
                dt_util.utcnow() + timedelta(seconds=wait_time))
        except asyncio.TimeoutError:
            self.logger.error(
                "Setup of platform %s is taking longer than %s seconds."
                " Startup will proceed without waiting any longer.",
                platform_type, SLOW_SETUP_MAX_WAIT)
        except Exception:  # pylint: disable=broad-except
            self.logger.exception(
                "Error while setting up platform %s", platform_type)
        finally:
            warn_task.cancel()

    @callback
    def async_update_group(self):
        """Set up and/or update component group.

        This method must be run in the event loop.
        """
        if self.group_name is None:
            return

        ids = [entity.entity_id for entity in
               sorted(self.entities,
                      key=lambda entity: entity.name or entity.entity_id)]

        self.hass.components.group.async_set_group(
            slugify(self.group_name), name=self.group_name,
            visible=False, entity_ids=ids
        )

    def reset(self):
        """Remove entities and reset the entity component to initial values."""
        run_coroutine_threadsafe(self.async_reset(), self.hass.loop).result()

    @asyncio.coroutine
    def async_reset(self):
        """Remove entities and reset the entity component to initial values.

        This method must be run in the event loop.
        """
        tasks = [platform.async_reset() for platform
                 in self._platforms.values()]

        if tasks:
            yield from asyncio.wait(tasks, loop=self.hass.loop)

        self._platforms = {
            'core': self._platforms['core']
        }
        self.config = None

        if self.group_name is not None:
            self.hass.components.group.async_remove(slugify(self.group_name))

    @asyncio.coroutine
    def async_remove_entity(self, entity_id):
        """Remove an entity managed by one of the platforms."""
        for platform in self._platforms.values():
            if entity_id in platform.entities:
                yield from platform.async_remove_entity(entity_id)

    def prepare_reload(self):
        """Prepare reloading this entity component."""
        return run_coroutine_threadsafe(
            self.async_prepare_reload(), loop=self.hass.loop).result()

    @asyncio.coroutine
    def async_prepare_reload(self):
        """Prepare reloading this entity component.

        This method must be run in the event loop.
        """
        try:
            conf = yield from \
                conf_util.async_hass_config_yaml(self.hass)
        except HomeAssistantError as err:
            self.logger.error(err)
            return None

        conf = conf_util.async_process_component_config(
            self.hass, conf, self.domain)

        if conf is None:
            return None

        yield from self.async_reset()
        return conf


class EntityPlatform(object):
    """Manage the entities for a single platform."""

    def __init__(self, component, platform, scan_interval, parallel_updates,
                 entity_namespace):
        """Initialize the entity platform."""
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

        component_entities = set(entity.entity_id for entity
                                 in self.component.entities)

        tasks = [
            self._async_add_entity(entity, update_before_add,
                                   component_entities)
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
    def _async_add_entity(self, entity, update_before_add, component_entities):
        """Helper method to add an entity to the platform."""
        if entity is None:
            raise ValueError('Entity cannot be None')

        # Do nothing if entity has already been added based on unique id.
        if entity in self.component.entities:
            return

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

        # Write entity_id to entity
        if getattr(entity, 'entity_id', None) is None:
            object_id = entity.name or DEVICE_DEFAULT_NAME

            if self.entity_namespace is not None:
                object_id = '{} {}'.format(self.entity_namespace,
                                           object_id)

            entity.entity_id = async_generate_entity_id(
                self.component.entity_id_format, object_id,
                component_entities)

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
