"""
homeassistant.components.automation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Allows to setup simple automation rules via the config file.
"""
import logging

from homeassistant.bootstrap import prepare_setup_platform
from homeassistant.helpers import config_per_platform
from homeassistant.util import split_entity_id
from homeassistant.const import ATTR_ENTITY_ID, CONF_PLATFORM
from homeassistant.components import logbook

DOMAIN = "automation"

DEPENDENCIES = ["group"]

CONF_ALIAS = "alias"
CONF_SERVICE = "execute_service"
CONF_SERVICE_ENTITY_ID = "service_entity_id"
CONF_SERVICE_DATA = "service_data"
CONF_IF = "if"

_LOGGER = logging.getLogger(__name__)


def setup(hass, config):
    """ Sets up automation. """
    success = False

    for p_type, p_config in config_per_platform(config, DOMAIN, _LOGGER):
        platform = prepare_setup_platform(hass, config, DOMAIN, p_type)

        if platform is None:
            _LOGGER.error("Unknown automation platform specified: %s", p_type)
            continue

        action = _get_action(hass, p_config)

        if action is None:
            return

        if CONF_IF in p_config:
            action = _process_if(hass, config, p_config[CONF_IF], action)

        if platform.trigger(hass, p_config, action):
            _LOGGER.info(
                "Initialized %s rule %s", p_type, p_config.get(CONF_ALIAS, ""))
            success = True
        else:
            _LOGGER.error(
                "Error setting up rule %s", p_config.get(CONF_ALIAS, ""))

    return success


def _get_action(hass, config):
    """ Return an action based on a config. """

    name = config.get(CONF_ALIAS, 'Unnamed automation')

    if CONF_SERVICE not in config:
        _LOGGER.error('Error setting up %s, no action specified.',
                      name)
        return

    def action():
        """ Action to be executed. """
        _LOGGER.info('Executing %s', name)
        logbook.log_entry(hass, name, 'has been triggered', DOMAIN)

        domain, service = split_entity_id(config[CONF_SERVICE])

        service_data = config.get(CONF_SERVICE_DATA, {})

        if not isinstance(service_data, dict):
            _LOGGER.error("%s should be a dictionary", CONF_SERVICE_DATA)
            service_data = {}

        if CONF_SERVICE_ENTITY_ID in config:
            try:
                service_data[ATTR_ENTITY_ID] = \
                    config[CONF_SERVICE_ENTITY_ID].split(",")
            except AttributeError:
                service_data[ATTR_ENTITY_ID] = \
                    config[CONF_SERVICE_ENTITY_ID]

        hass.services.call(domain, service, service_data)

    return action


def _process_if(hass, config, if_configs, action):
    """ Processes if checks. """

    if isinstance(if_configs, dict):
        if_configs = [if_configs]

    for if_config in if_configs:
        p_type = if_config.get(CONF_PLATFORM)
        if p_type is None:
            _LOGGER.error("No platform defined found for if-statement %s",
                          if_config)
            continue

        platform = prepare_setup_platform(hass, config, DOMAIN, p_type)

        if platform is None or not hasattr(platform, 'if_action'):
            _LOGGER.error("Unsupported if-statement platform specified: %s",
                          p_type)
            continue

        action = platform.if_action(hass, if_config, action)

    return action
