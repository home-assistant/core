"""
Provides helpers for components that handle devices.
"""
from homeassistant.loader import get_component
from homeassistant.helpers import (
    generate_entity_id, config_per_platform, extract_entity_ids)
from homeassistant.components import group, discovery
from homeassistant.const import ATTR_ENTITY_ID


class DeviceComponent(object):
    # pylint: disable=too-many-instance-attributes
    # pylint: disable=too-many-arguments
    """
    Helper class that will help a device component manage its devices.
    """
    def __init__(self, logger, domain, hass, scan_interval,
                 discovery_platforms=None, group_name=None):
        self.logger = logger
        self.hass = hass

        self.domain = domain
        self.entity_id_format = domain + '.{}'
        self.scan_interval = scan_interval
        self.discovery_platforms = discovery_platforms
        self.group_name = group_name

        self.devices = {}
        self.group = None
        self.is_polling = False

    def setup(self, config):
        """
        Sets up a full device component:
         - Loads the platforms from the config
         - Will update devices on an interval
         - Will listen for supported discovered platforms
        """

        # only setup group if name is given
        if self.group_name is None:
            self.group = None
        else:
            self.group = group.Group(self.hass, self.group_name,
                                     user_defined=False)

        # Look in config for Domain, Domain 2, Domain 3 etc and load them
        for p_type, p_config in \
                config_per_platform(config, self.domain, self.logger):

            self._setup_platform(p_type, p_config)

        if self.discovery_platforms:
            discovery.listen(self.hass, self.discovery_platforms.keys(),
                             self._device_discovered)

    def extract_from_service(self, service):
        """
        Takes a service and extracts all known devices.
        Will return all if no entity IDs given in service.
        """
        if ATTR_ENTITY_ID not in service.data:
            return self.devices.values()
        else:
            return [self.devices[entity_id] for entity_id
                    in extract_entity_ids(self.hass, service)
                    if entity_id in self.devices]

    def _update_device_states(self, now):
        """ Update the states of all the lights. """
        self.logger.info("Updating %s states", self.domain)

        for device in self.devices.values():
            if device.should_poll:
                device.update_ha_state(True)

    def _device_discovered(self, service, info):
        """ Called when a device is discovered. """
        if service not in self.discovery_platforms:
            return

        self._setup_platform(self.discovery_platforms[service], {}, info)

    def _add_devices(self, new_devices):
        """
        Takes in a list of new devices. For each device will see if it already
        exists. If not, will add it, set it up and push the first state.
        """
        for device in new_devices:
            if device is not None and device not in self.devices.values():
                device.hass = self.hass

                device.entity_id = generate_entity_id(
                    self.entity_id_format, device.name, self.devices.keys())

                self.devices[device.entity_id] = device

                device.update_ha_state()

        if self.group is not None:
            self.group.update_tracked_entity_ids(self.devices.keys())

        self._start_polling()

    def _start_polling(self):
        """ Start polling device states if necessary. """
        if self.is_polling or \
           not any(device.should_poll for device in self.devices.values()):
            return

        self.is_polling = True

        self.hass.track_time_change(
            self._update_device_states,
            second=range(0, 60, self.scan_interval))

    def _setup_platform(self, platform_type, config, discovery_info=None):
        """ Tries to setup a platform for this component. """
        platform_name = '{}.{}'.format(self.domain, platform_type)
        platform = get_component(platform_name)

        if platform is None:
            self.logger.error('Unable to find platform %s', platform_type)
            return

        try:
            platform.setup_platform(
                self.hass, config, self._add_devices, discovery_info)
        except AttributeError:
            # Support old deprecated method for now - 3/1/2015
            if hasattr(platform, 'get_devices'):
                self.logger.warning(
                    "Please upgrade %s to return new devices using "
                    "setup_platform. See %s/demo.py for an example.",
                    platform_name, self.domain)
                self._add_devices(platform.get_devices(self.hass, config))

            else:
                # AttributeError if setup_platform does not exist
                self.logger.exception(
                    "Error setting up %s", platform_type)
