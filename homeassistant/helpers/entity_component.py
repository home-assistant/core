"""
homeassistant.helpers.entity_component
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Provides helpers for components that manage entities.
"""
from homeassistant.bootstrap import prepare_setup_platform
from homeassistant.helpers import (
    generate_entity_id, config_per_platform, extract_entity_ids)
from homeassistant.helpers.event import track_utc_time_change
from homeassistant.components import group, discovery
from homeassistant.const import ATTR_ENTITY_ID

DEFAULT_SCAN_INTERVAL = 15


class EntityComponent(object):
    # pylint: disable=too-many-instance-attributes
    # pylint: disable=too-many-arguments
    """
    Helper class that will help a component manage its entities.
    """
    def __init__(self, logger, domain, hass,
                 scan_interval=DEFAULT_SCAN_INTERVAL,
                 discovery_platforms=None, group_name=None):
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

    def setup(self, config):
        """
        Sets up a full entity component:
         - Loads the platforms from the config
         - Will listen for supported discovered platforms
        """
        self.config = config

        # Look in config for Domain, Domain 2, Domain 3 etc and load them
        for p_type, p_config in \
                config_per_platform(config, self.domain, self.logger):

            self._setup_platform(p_type, p_config)

        if self.discovery_platforms:
            discovery.listen(self.hass, self.discovery_platforms.keys(),
                             self._entity_discovered)

    def add_entities(self, new_entities):
        """
        Takes in a list of new entities. For each entity will see if it already
        exists. If not, will add it, set it up and push the first state.
        """
        for entity in new_entities:
            if entity is not None and entity not in self.entities.values():
                entity.hass = self.hass

                entity.entity_id = generate_entity_id(
                    self.entity_id_format, entity.name, self.entities.keys())

                self.entities[entity.entity_id] = entity

                entity.update_ha_state()

        if self.group is None and self.group_name is not None:
            self.group = group.Group(self.hass, self.group_name,
                                     user_defined=False)

        if self.group is not None:
            self.group.update_tracked_entity_ids(self.entities.keys())

        self._start_polling()

    def extract_from_service(self, service):
        """
        Takes a service and extracts all known entities.
        Will return all if no entity IDs given in service.
        """
        if ATTR_ENTITY_ID not in service.data:
            return self.entities.values()
        else:
            return [self.entities[entity_id] for entity_id
                    in extract_entity_ids(self.hass, service)
                    if entity_id in self.entities]

    def _update_entity_states(self, now):
        """ Update the states of all the entities. """
        self.logger.info("Updating %s entities", self.domain)

        for entity in self.entities.values():
            if entity.should_poll:
                entity.update_ha_state(True)

    def _entity_discovered(self, service, info):
        """ Called when a entity is discovered. """
        if service not in self.discovery_platforms:
            return

        self._setup_platform(self.discovery_platforms[service], {}, info)

    def _start_polling(self):
        """ Start polling entities if necessary. """
        if self.is_polling or \
           not any(entity.should_poll for entity in self.entities.values()):
            return

        self.is_polling = True

        track_utc_time_change(
            self.hass, self._update_entity_states,
            second=range(0, 60, self.scan_interval))

    def _setup_platform(self, platform_type, platform_config,
                        discovery_info=None):
        """ Tries to setup a platform for this component. """
        platform = prepare_setup_platform(
            self.hass, self.config, self.domain, platform_type)

        if platform is None:
            return

        platform_name = '{}.{}'.format(self.domain, platform_type)

        try:
            platform.setup_platform(
                self.hass, platform_config, self.add_entities, discovery_info)

            self.hass.config.components.append(platform_name)
        except Exception:  # pylint: disable=broad-except
            self.logger.exception(
                'Error while setting up platform %s', platform_type)
