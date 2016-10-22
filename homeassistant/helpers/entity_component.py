"""Helpers for components that manage entities."""
import asyncio

from homeassistant import config as conf_util
from homeassistant.bootstrap import (prepare_setup_platform,
                                     prepare_setup_component)
from homeassistant.const import (
    ATTR_ENTITY_ID, CONF_SCAN_INTERVAL, CONF_ENTITY_NAMESPACE,
    DEVICE_DEFAULT_NAME)
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.loader import get_component
from homeassistant.helpers import config_per_platform, discovery
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.event import async_track_utc_time_change
from homeassistant.helpers.service import extract_entity_ids
from homeassistant.util.async import (
    run_callback_threadsafe, run_coroutine_threadsafe)

DEFAULT_SCAN_INTERVAL = 15


class EntityComponent(object):
    """Helper class that will help a component manage its entities."""

    # pylint: disable=too-many-instance-attributes
    # pylint: disable=too-many-arguments
    def __init__(self, logger, domain, hass,
                 scan_interval=DEFAULT_SCAN_INTERVAL, group_name=None):
        """Initialize an entity component."""
        self.logger = logger
        self.hass = hass

        self.domain = domain
        self.entity_id_format = domain + '.{}'
        self.scan_interval = scan_interval
        self.group_name = group_name

        self.entities = {}
        self.group = None

        self.config = None

        self._platforms = {
            'core': EntityPlatform(self, self.scan_interval, None),
        }
        self.async_add_entities = self._platforms['core'].async_add_entities
        self.add_entities = self._platforms['core'].add_entities

    def setup(self, config):
        """Set up a full entity component.

        Loads the platforms from the config and will listen for supported
        discovered platforms.
        """
        run_coroutine_threadsafe(
            self.async_setup(config), self.hass.loop
        ).result()

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

        yield from asyncio.gather(*tasks, loop=self.hass.loop)

        # Generic discovery listener for loading platform dynamically
        # Refer to: homeassistant.components.discovery.load_platform()
        @callback
        def component_platform_discovered(platform, info):
            """Callback to load a platform."""
            self.hass.loop.create_task(
                self._async_setup_platform(platform, {}, info))

        discovery.async_listen_platform(
            self.hass, self.domain, component_platform_discovered)

    def extract_from_service(self, service):
        """Extract all known entities from a service call.

        Will return all entities if no entities specified in call.
        Will return an empty list if entities specified but unknown.
        """
        return run_callback_threadsafe(
            self.hass.loop, self.async_extract_from_service, service
        ).result()

    def async_extract_from_service(self, service):
        """Extract all known entities from a service call.

        Will return all entities if no entities specified in call.
        Will return an empty list if entities specified but unknown.

        This method must be run in the event loop.
        """
        if ATTR_ENTITY_ID not in service.data:
            return list(self.entities.values())

        return [self.entities[entity_id] for entity_id
                in extract_entity_ids(self.hass, service)
                if entity_id in self.entities]

    @asyncio.coroutine
    def _async_setup_platform(self, platform_type, platform_config,
                              discovery_info=None):
        """Setup a platform for this component.

        This method must be run in the event loop.
        """
        platform = yield from self.hass.loop.run_in_executor(
            None, prepare_setup_platform, self.hass, self.config, self.domain,
            platform_type
        )

        if platform is None:
            return

        # Config > Platform > Component
        scan_interval = (platform_config.get(CONF_SCAN_INTERVAL) or
                         getattr(platform, 'SCAN_INTERVAL', None) or
                         self.scan_interval)
        entity_namespace = platform_config.get(CONF_ENTITY_NAMESPACE)

        key = (platform_type, scan_interval, entity_namespace)

        if key not in self._platforms:
            self._platforms[key] = EntityPlatform(self, scan_interval,
                                                  entity_namespace)
        entity_platform = self._platforms[key]

        try:
            if getattr(platform, 'async_setup_platform', None):
                yield from platform.async_setup_platform(
                    self.hass, platform_config,
                    entity_platform.async_add_entities, discovery_info
                )
            else:
                yield from self.hass.loop.run_in_executor(
                    None, platform.setup_platform, self.hass, platform_config,
                    entity_platform.add_entities, discovery_info
                )

            self.hass.config.components.append(
                '{}.{}'.format(self.domain, platform_type))
        except Exception:  # pylint: disable=broad-except
            self.logger.exception(
                'Error while setting up platform %s', platform_type)

    def add_entity(self, entity, platform=None):
        """Add entity to component."""
        return run_coroutine_threadsafe(
            self.async_add_entity(entity, platform), self.hass.loop
        ).result()

    @asyncio.coroutine
    def async_add_entity(self, entity, platform=None):
        """Add entity to component.

        This method must be run in the event loop.
        """
        if entity is None or entity in self.entities.values():
            return False

        entity.hass = self.hass

        if getattr(entity, 'entity_id', None) is None:
            object_id = entity.name or DEVICE_DEFAULT_NAME

            if platform is not None and platform.entity_namespace is not None:
                object_id = '{} {}'.format(platform.entity_namespace,
                                           object_id)

            entity.entity_id = async_generate_entity_id(
                self.entity_id_format, object_id,
                self.entities.keys())

        self.entities[entity.entity_id] = entity
        yield from entity.async_update_ha_state()

        return True

    def update_group(self):
        """Set up and/or update component group."""
        run_callback_threadsafe(
            self.hass.loop, self.async_update_group).result()

    @asyncio.coroutine
    def async_update_group(self):
        """Set up and/or update component group.

        This method must be run in the event loop.
        """
        if self.group is None and self.group_name is not None:
            group = get_component('group')
            self.group = yield from group.Group.async_create_group(
                self.hass, self.group_name, self.entities.keys(),
                user_defined=False
            )
        elif self.group is not None:
            yield from self.group.async_update_tracked_entity_ids(
                self.entities.keys())

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

        yield from asyncio.gather(*tasks, loop=self.hass.loop)

        self._platforms = {
            'core': self._platforms['core']
        }
        self.entities = {}
        self.config = None

        if self.group is not None:
            yield from self.group.async_stop()
            self.group = None

    def prepare_reload(self):
        """Prepare reloading this entity component."""
        try:
            path = conf_util.find_config_file(self.hass.config.config_dir)
            conf = conf_util.load_yaml_config_file(path)
        except HomeAssistantError as err:
            self.logger.error(err)
            return None

        conf = prepare_setup_component(self.hass, conf, self.domain)

        if conf is None:
            return None

        self.reset()
        return conf

    @asyncio.coroutine
    def async_prepare_reload(self):
        """Prepare reloading this entity component.

        This method must be run in the event loop.
        """
        conf = yield from self.hass.loop.run_in_executor(
            None, self.prepare_reload
        )
        return conf


class EntityPlatform(object):
    """Keep track of entities for a single platform and stay in loop."""

    # pylint: disable=too-few-public-methods
    def __init__(self, component, scan_interval, entity_namespace):
        """Initalize the entity platform."""
        self.component = component
        self.scan_interval = scan_interval
        self.entity_namespace = entity_namespace
        self.platform_entities = []
        self._async_unsub_polling = None

    def add_entities(self, new_entities):
        """Add entities for a single platform."""
        run_coroutine_threadsafe(
            self.async_add_entities(new_entities), self.component.hass.loop
        ).result()

    @asyncio.coroutine
    def async_add_entities(self, new_entities):
        """Add entities for a single platform async.

        This method must be run in the event loop.
        """
        tasks = [self._async_process_entity(entity) for entity in new_entities]

        yield from asyncio.gather(*tasks, loop=self.component.hass.loop)
        yield from self.component.async_update_group()

        if self._async_unsub_polling is not None or \
           not any(entity.should_poll for entity
                   in self.platform_entities):
            return

        self._async_unsub_polling = async_track_utc_time_change(
            self.component.hass, self._update_entity_states,
            second=range(0, 60, self.scan_interval))

    @asyncio.coroutine
    def _async_process_entity(self, new_entity):
        """Add entities to StateMachine."""
        ret = yield from self.component.async_add_entity(new_entity, self)
        if ret:
            self.platform_entities.append(new_entity)

    @asyncio.coroutine
    def async_reset(self):
        """Remove all entities and reset data.

        This method must be run in the event loop.
        """
        tasks = [entity.async_remove() for entity in self.platform_entities]

        yield from asyncio.gather(*tasks, loop=self.component.hass.loop)

        if self._async_unsub_polling is not None:
            self._async_unsub_polling()
            self._async_unsub_polling = None

    @callback
    def _update_entity_states(self, now):
        """Update the states of all the polling entities.

        This method must be run in the event loop.
        """
        for entity in self.platform_entities:
            if entity.should_poll:
                self.component.hass.loop.create_task(
                    entity.async_update_ha_state(True)
                )
