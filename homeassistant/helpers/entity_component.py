"""Helpers for components that manage entities."""
from threading import Lock

from homeassistant import config as conf_util
from homeassistant.bootstrap import (prepare_setup_platform,
                                     prepare_setup_component)
from homeassistant.const import (
    ATTR_ENTITY_ID, CONF_SCAN_INTERVAL, CONF_ENTITY_NAMESPACE,
    DEVICE_DEFAULT_NAME)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.loader import get_component
from homeassistant.helpers import config_per_platform, discovery
from homeassistant.helpers.entity import generate_entity_id
from homeassistant.helpers.event import track_utc_time_change
from homeassistant.helpers.service import extract_entity_ids

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
        self.lock = Lock()

        self._platforms = {
            'core': EntityPlatform(self, self.scan_interval, None),
        }
        self.add_entities = self._platforms['core'].add_entities

    def setup(self, config):
        """Set up a full entity component.

        Loads the platforms from the config and will listen for supported
        discovered platforms.
        """
        self.config = config

        # Look in config for Domain, Domain 2, Domain 3 etc and load them
        for p_type, p_config in config_per_platform(config, self.domain):
            self._setup_platform(p_type, p_config)

        # Generic discovery listener for loading platform dynamically
        # Refer to: homeassistant.components.discovery.load_platform()
        def component_platform_discovered(platform, info):
            """Callback to load a platform."""
            self._setup_platform(platform, {}, info)

        discovery.listen_platform(self.hass, self.domain,
                                  component_platform_discovered)

    def extract_from_service(self, service):
        """Extract all known entities from a service call.

        Will return all entities if no entities specified in call.
        Will return an empty list if entities specified but unknown.
        """
        with self.lock:
            if ATTR_ENTITY_ID not in service.data:
                return list(self.entities.values())

            return [self.entities[entity_id] for entity_id
                    in extract_entity_ids(self.hass, service)
                    if entity_id in self.entities]

    def _setup_platform(self, platform_type, platform_config,
                        discovery_info=None):
        """Setup a platform for this component."""
        platform = prepare_setup_platform(
            self.hass, self.config, self.domain, platform_type)

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
            platform.setup_platform(self.hass, platform_config,
                                    entity_platform.add_entities,
                                    discovery_info)

            self.hass.config.components.append(
                '{}.{}'.format(self.domain, platform_type))
        except Exception:  # pylint: disable=broad-except
            self.logger.exception(
                'Error while setting up platform %s', platform_type)

    def add_entity(self, entity, platform=None):
        """Add entity to component."""
        if entity is None or entity in self.entities.values():
            return False

        entity.hass = self.hass

        if getattr(entity, 'entity_id', None) is None:
            object_id = entity.name or DEVICE_DEFAULT_NAME

            if platform is not None and platform.entity_namespace is not None:
                object_id = '{} {}'.format(platform.entity_namespace,
                                           object_id)

            entity.entity_id = generate_entity_id(
                self.entity_id_format, object_id,
                self.entities.keys())

        self.entities[entity.entity_id] = entity
        entity.update_ha_state()

        return True

    def update_group(self):
        """Set up and/or update component group."""
        if self.group is None and self.group_name is not None:
            group = get_component('group')
            self.group = group.Group(self.hass, self.group_name,
                                     user_defined=False)

        if self.group is not None:
            self.group.update_tracked_entity_ids(self.entities.keys())

    def reset(self):
        """Remove entities and reset the entity component to initial values."""
        with self.lock:
            for platform in self._platforms.values():
                platform.reset()

            self._platforms = {
                'core': self._platforms['core']
            }
            self.entities = {}
            self.config = None

            if self.group is not None:
                self.group.stop()
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


class EntityPlatform(object):
    """Keep track of entities for a single platform."""

    # pylint: disable=too-few-public-methods
    def __init__(self, component, scan_interval, entity_namespace):
        """Initalize the entity platform."""
        self.component = component
        self.scan_interval = scan_interval
        self.entity_namespace = entity_namespace
        self.platform_entities = []
        self._unsub_polling = None

    def add_entities(self, new_entities):
        """Add entities for a single platform."""
        with self.component.lock:
            for entity in new_entities:
                if self.component.add_entity(entity, self):
                    self.platform_entities.append(entity)

            self.component.update_group()

            if self._unsub_polling is not None or \
               not any(entity.should_poll for entity
                       in self.platform_entities):
                return

            self._unsub_polling = track_utc_time_change(
                self.component.hass, self._update_entity_states,
                second=range(0, 60, self.scan_interval))

    def reset(self):
        """Remove all entities and reset data."""
        for entity in self.platform_entities:
            entity.remove()
        if self._unsub_polling is not None:
            self._unsub_polling()
            self._unsub_polling = None

    def _update_entity_states(self, now):
        """Update the states of all the polling entities."""
        with self.component.lock:
            # We copy the entities because new entities might be detected
            # during state update causing deadlocks.
            entities = list(entity for entity in self.platform_entities
                            if entity.should_poll)

        for entity in entities:
            entity.update_ha_state(True)
