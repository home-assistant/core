"""
homeassistant.components.automation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Allows to setup simple automation rules via the config file.
"""
import logging

from homeassistant.bootstrap import prepare_setup_platform
from homeassistant.util import split_entity_id
from homeassistant.const import ATTR_ENTITY_ID, CONF_PLATFORM
from homeassistant.components import logbook

DOMAIN = "automation"

DEPENDENCIES = ["group"]

CONF_ALIAS = "alias"
CONF_SERVICE = "execute_service"
CONF_SERVICE_ENTITY_ID = "service_entity_id"
CONF_SERVICE_DATA = "service_data"

CONF_CONDITION = "condition"
CONF_ACTION = 'action'
CONF_TRIGGER = "trigger"
CONF_CONDITION_TYPE = "condition_type"

CONDITION_TYPE_AND = "and"
CONDITION_TYPE_OR = "or"
DEFAULT_CONDITION_TYPE = CONDITION_TYPE_AND

_LOGGER = logging.getLogger(__name__)


def setup(hass, config):
    """ Sets up automation. """
    config_key = DOMAIN
    found = 1

    while config_key in config:
        p_config = _migrate_old_config(config[config_key])
        found += 1
        config_key = "{} {}".format(DOMAIN, found)

        name = p_config.get(CONF_ALIAS, config_key)
        action = _get_action(hass, p_config.get(CONF_ACTION, {}), name)

        if action is None:
            continue

        if CONF_CONDITION in p_config:
            cond_type = p_config.get(CONF_CONDITION_TYPE,
                                     DEFAULT_CONDITION_TYPE).lower()
            action = _process_if(hass, config, p_config[CONF_CONDITION],
                                 action, cond_type)

            if action is None:
                continue

        _process_trigger(hass, config, p_config.get(CONF_TRIGGER, []), name,
                         action)

    return True


def _get_action(hass, config, name):
    """ Return an action based on a config. """

    if CONF_SERVICE not in config:
        _LOGGER.error('Error setting up %s, no action specified.', name)
        return None

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


def _migrate_old_config(config):
    """ Migrate old config to new. """
    if CONF_PLATFORM not in config:
        return config

    _LOGGER.warning(
        'You are using an old configuration format. Please upgrade: '
        'https://home-assistant.io/components/automation.html')

    new_conf = {
        CONF_TRIGGER: dict(config),
        CONF_CONDITION: config.get('if', []),
        CONF_ACTION: dict(config),
    }

    for cat, key, new_key in (('trigger', 'mqtt_topic', 'topic'),
                              ('trigger', 'mqtt_payload', 'payload'),
                              ('trigger', 'state_entity_id', 'entity_id'),
                              ('trigger', 'state_before', 'before'),
                              ('trigger', 'state_after', 'after'),
                              ('trigger', 'state_to', 'to'),
                              ('trigger', 'state_from', 'from'),
                              ('trigger', 'state_hours', 'hours'),
                              ('trigger', 'state_minutes', 'minutes'),
                              ('trigger', 'state_seconds', 'seconds')):
        if key in new_conf[cat]:
            new_conf[cat][new_key] = new_conf[cat].pop(key)

    return new_conf


def _process_if(hass, config, if_configs, action, cond_type):
    """ Processes if checks. """

    if isinstance(if_configs, dict):
        if_configs = [if_configs]

    checks = []
    for if_config in if_configs:
        platform = _resolve_platform('condition', hass, config,
                                     if_config.get(CONF_PLATFORM))
        if platform is None:
            continue

        check = platform.if_action(hass, if_config)

        if check is None:
            return None

        checks.append(check)

    if cond_type == CONDITION_TYPE_AND:
        def if_action():
            """ AND all conditions. """
            if all(check() for check in checks):
                action()
    else:
        def if_action():
            """ OR all conditions. """
            if any(check() for check in checks):
                action()

    return if_action


def _process_trigger(hass, config, trigger_configs, name, action):
    """ Setup triggers. """
    if isinstance(trigger_configs, dict):
        trigger_configs = [trigger_configs]

    for conf in trigger_configs:
        platform = _resolve_platform('trigger', hass, config,
                                     conf.get(CONF_PLATFORM))
        if platform is None:
            continue

        if platform.trigger(hass, conf, action):
            _LOGGER.info("Initialized rule %s", name)
        else:
            _LOGGER.error("Error setting up rule %s", name)


def _resolve_platform(requester, hass, config, platform):
    """ Find automation platform. """
    if platform is None:
        return None
    platform = prepare_setup_platform(hass, config, DOMAIN, platform)

    if platform is None:
        _LOGGER.error("Unknown automation platform specified for %s: %s",
                      requester, platform)
        return None

    return platform
