"""Helpers for components that manage entities."""
import asyncio
from datetime import timedelta
from itertools import chain

from homeassistant import config as conf_util
from homeassistant.setup import async_prepare_setup_platform
from homeassistant.const import (
    ATTR_ENTITY_ID, CONF_SCAN_INTERVAL, CONF_ENTITY_NAMESPACE)
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError, PlatformNotReady
from homeassistant.helpers import config_per_platform, discovery
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.helpers.service import extract_entity_ids
from homeassistant.util import slugify
from homeassistant.util.async import (
    run_callback_threadsafe, run_coroutine_threadsafe)
import homeassistant.util.dt as dt_util
from .entity_platform import EntityPlatform

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
