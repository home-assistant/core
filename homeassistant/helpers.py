"""
Helper methods for components within Home Assistant.
"""
from datetime import datetime

from homeassistant import NoEntitySpecifiedError

from homeassistant.loader import get_component
from homeassistant.const import (
    ATTR_ENTITY_ID, STATE_ON, STATE_OFF, CONF_PLATFORM, CONF_TYPE,
    DEVICE_DEFAULT_NAME)
from homeassistant.util import ensure_unique_string, slugify


def generate_entity_id(entity_id_format, name, current_ids=None, hass=None):
    if current_ids is None:
        if hass is None:
            raise RuntimeError("Missing required parameter currentids or hass")

        current_ids = hass.states.entity_ids()

    return ensure_unique_string(
        entity_id_format.format(slugify(name)), current_ids)


def extract_entity_ids(hass, service):
    """
    Helper method to extract a list of entity ids from a service call.
    Will convert group entity ids to the entity ids it represents.
    """
    entity_ids = []

    if service.data and ATTR_ENTITY_ID in service.data:
        group = get_component('group')

        # Entity ID attr can be a list or a string
        service_ent_id = service.data[ATTR_ENTITY_ID]
        if isinstance(service_ent_id, list):
            ent_ids = service_ent_id
        else:
            ent_ids = [service_ent_id]

        entity_ids.extend(
            ent_id for ent_id
            in group.expand_entity_ids(hass, ent_ids)
            if ent_id not in entity_ids)

    return entity_ids


# pylint: disable=too-few-public-methods, attribute-defined-outside-init
class TrackStates(object):
    """
    Records the time when the with-block is entered. Will add all states
    that have changed since the start time to the return list when with-block
    is exited.
    """
    def __init__(self, hass):
        self.hass = hass
        self.states = []

    def __enter__(self):
        self.now = datetime.now()
        return self.states

    def __exit__(self, exc_type, exc_value, traceback):
        self.states.extend(self.hass.states.get_since(self.now))


def validate_config(config, items, logger):
    """
    Validates if all items are available in the configuration.

    config is the general dictionary with all the configurations.
    items is a dict with per domain which attributes we require.
    logger is the logger from the caller to log the errors to.

    Returns True if all required items were found.
    """
    errors_found = False
    for domain in items.keys():
        config.setdefault(domain, {})

        errors = [item for item in items[domain] if item not in config[domain]]

        if errors:
            logger.error(
                "Missing required configuration items in {}: {}".format(
                    domain, ", ".join(errors)))

            errors_found = True

    return not errors_found


def config_per_platform(config, domain, logger):
    """
    Generator to break a component config into different platforms.
    For example, will find 'switch', 'switch 2', 'switch 3', .. etc
    """
    config_key = domain
    found = 1

    while config_key in config:
        platform_config = config[config_key]

        platform_type = platform_config.get(CONF_PLATFORM)

        # DEPRECATED, still supported for now.
        if platform_type is None:
            platform_type = platform_config.get(CONF_TYPE)

            if platform_type is not None:
                logger.warning((
                    'Please update your config for {}.{} to use "platform" '
                    'instead of "type"').format(domain, platform_type))

        if platform_type is None:
            logger.warning('No platform specified for %s', config_key)
            break

        yield platform_type, platform_config

        found += 1
        config_key = "{} {}".format(domain, found)


def platform_devices_from_config(config, domain, hass,
                                 entity_id_format, logger):

    """ Parses the config for specified domain.
        Loads different platforms and retrieve domains. """
    devices = []

    for p_type, p_config in config_per_platform(config, domain, logger):
        platform = get_component('{}.{}'.format(domain, p_type))

        if platform is None:
            logger.error("Unknown %s type specified: %s", domain, p_type)

        else:
            try:
                p_devices = platform.get_devices(hass, p_config)
            except AttributeError:
                # DEPRECATED, still supported for now
                logger.warning(
                    'Platform %s should migrate to use the method get_devices',
                    p_type)

                if domain == 'light':
                    p_devices = platform.get_lights(hass, p_config)
                elif domain == 'switch':
                    p_devices = platform.get_switches(hass, p_config)
                else:
                    raise

            logger.info("Found %d %s %ss", len(p_devices), p_type, domain)

            devices.extend(p_devices)

    # Setup entity IDs for each device
    device_dict = {}

    no_name_count = 0

    for device in devices:
        # Get the name or set to default if none given
        name = device.name or DEVICE_DEFAULT_NAME

        if name == DEVICE_DEFAULT_NAME:
            no_name_count += 1
            name = "{} {}".format(domain, no_name_count)

        entity_id = generate_entity_id(
            entity_id_format, name, device_dict.keys())

        device.entity_id = entity_id
        device_dict[entity_id] = device

    return device_dict


class Device(object):
    """ ABC for Home Assistant devices. """
    # pylint: disable=no-self-use

    entity_id = None

    @property
    def unique_id(self):
        """ Returns a unique id. """
        return "{}.{}".format(self.__class__, id(self))

    @property
    def name(self):
        """ Returns the name of the device. """
        return self.get_name()

    @property
    def state(self):
        """ Returns the state of the device. """
        return self.get_state()

    @property
    def state_attributes(self):
        """ Returns the state attributes. """
        return {}

    # DEPRECATION NOTICE:
    # Device is moving from getters to properties.
    # For now the new properties will call the old functions
    # This will be removed in the future.

    def get_name(self):
        """ Returns the name of the device if any. """
        return DEVICE_DEFAULT_NAME

    def get_state(self):
        """ Returns state of the device. """
        return "Unknown"

    def get_state_attributes(self):
        """ Returns optional state attributes. """
        return {}

    def update(self):
        """ Retrieve latest state from the real device. """
        pass

    def update_ha_state(self, hass, force_refresh=False):
        """
        Updates Home Assistant with current state of device.
        If force_refresh == True will update device before setting state.
        """
        if self.entity_id is None:
            raise NoEntitySpecifiedError(
                "No entity specified for device {}".format(self.name))

        if force_refresh:
            self.update()

        return hass.states.set(self.entity_id, self.state,
                               self.state_attributes)

    def __eq__(self, other):
        return (isinstance(other, Device) and
                other.unique_id == self.unique_id)


class ToggleDevice(Device):
    """ ABC for devices that can be turned on and off. """
    # pylint: disable=no-self-use

    @property
    def state(self):
        """ Returns the state. """
        return STATE_ON if self.is_on else STATE_OFF

    @property
    def is_on(self):
        """ True if device is on. """
        return False

    def turn_on(self, **kwargs):
        """ Turn the device on. """
        pass

    def turn_off(self, **kwargs):
        """ Turn the device off. """
        pass
