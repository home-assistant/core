"""Helpers for components that manage entities."""
from threading import Lock

from homeassistant.bootstrap import prepare_setup_platform
from homeassistant.components import discovery, group
from homeassistant.const import (
    ATTR_ENTITY_ID, CONF_SCAN_INTERVAL, CONF_ENTITY_NAMESPACE,
    DEVICE_DEFAULT_NAME)
from homeassistant.helpers import config_per_platform
from homeassistant.helpers.entity import generate_entity_id
from homeassistant.helpers.event import track_utc_time_change
from homeassistant.helpers.service import extract_entity_ids

DEFAULT_SCAN_INTERVAL = 15


class EntityComponent(object):
    """Helper class that will help a component manage its entities."""

    # pylint: disable=too-many-instance-attributes
    # pylint: disable=too-many-arguments
    def __init__(self, logger, domain, hass,
                 scan_interval=DEFAULT_SCAN_INTERVAL,
                 discovery_platforms=None, group_name=None):
        """Initialize an entity component."""
        self.logger = logger
        self.hass = hass

        self.domain = domain
        self.entity_id_format = domain + '.{}'
        self.scan_interval = scan_interval
        self.discovery_platforms = discovery_platforms
        self.group_name = group_name

        self.entities = {}
        self.group = None
        self.is_polling = False

        self.config = None
        self.lock = Lock()

        self.add_entities = EntityPlatform(self, self.scan_interval,
                                           None).add_entities

    def setup(self, config):
        """Set up a full entity component.

        Loads the platforms from the config and will listen for supported
        discovered platforms.
        """
        self.config = config

        # Look in config for Domain, Domain 2, Domain 3 etc and load them
        for p_type, p_config in config_per_platform(config, self.domain):
            self._setup_platform(p_type, p_config)

        if self.discovery_platforms:
            # Discovery listener for all items in discovery_platforms array
            # passed from a component's setup method (e.g. light/__init__.py)
            discovery.listen(
                self.hass, self.discovery_platforms.keys(),
                lambda service, info:
                self._setup_platform(self.discovery_platforms[service], {},
                                     info))

        # Generic discovery listener for loading platform dynamically
        # Refer to: homeassistant.components.discovery.load_platform()
        def load_platform_callback(service, info):
            """Callback to load a platform."""
            platform = info.pop(discovery.LOAD_PLATFORM)
            self._setup_platform(platform, {}, info if info else None)
        discovery.listen(self.hass, discovery.LOAD_PLATFORM + '.' +
                         self.domain, load_platform_callback)

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
        scan_interval = platform_config.get(
            CONF_SCAN_INTERVAL,
            getattr(platform, 'SCAN_INTERVAL', self.scan_interval))
        entity_namespace = platform_config.get(CONF_ENTITY_NAMESPACE)

        try:
            platform.setup_platform(
                self.hass, platform_config,
                EntityPlatform(self, scan_interval,
                               entity_namespace).add_entities,
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
            self.group = group.Group(self.hass, self.group_name,
                                     user_defined=False)

        if self.group is not None:
            self.group.update_tracked_entity_ids(self.entities.keys())


class EntityPlatform(object):
    """Keep track of entities for a single platform."""

    # pylint: disable=too-few-public-methods
    def __init__(self, component, scan_interval, entity_namespace):
        """Initalize the entity platform."""
        self.component = component
        self.scan_interval = scan_interval
        self.entity_namespace = entity_namespace
        self.platform_entities = []
        self.is_polling = False

    def add_entities(self, new_entities):
        """Add entities for a single platform."""
        with self.component.lock:
            for entity in new_entities:
                if self.component.add_entity(entity, self):
                    self.platform_entities.append(entity)

            self.component.update_group()

            if self.is_polling or \
               not any(entity.should_poll for entity
                       in self.platform_entities):
                return

            self.is_polling = True

            track_utc_time_change(
                self.component.hass, self._update_entity_states,
                second=range(0, 60, self.scan_interval))

    def _update_entity_states(self, now):
        """Update the states of all the polling entities."""
        with self.component.lock:
            # We copy the entities because new entities might be detected
            # during state update causing deadlocks.
            entities = list(entity for entity in self.platform_entities
                            if entity.should_poll)

        for entity in entities:
            entity.update_ha_state(True)
