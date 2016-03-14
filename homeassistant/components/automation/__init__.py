"""
Allow to setup simple automation rules via the config file.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/automation/
"""
import logging

from homeassistant.bootstrap import prepare_setup_platform
from homeassistant.const import CONF_PLATFORM
from homeassistant.components import logbook
from homeassistant.helpers import extract_domain_configs
from homeassistant.helpers.service import (call_from_config,
                                           validate_service_call)


DOMAIN = 'automation'

DEPENDENCIES = ['group']

CONF_ALIAS = 'alias'

CONF_CONDITION = 'condition'
CONF_ACTION = 'action'
CONF_TRIGGER = 'trigger'
CONF_CONDITION_TYPE = 'condition_type'

CONDITION_USE_TRIGGER_VALUES = 'use_trigger_values'
CONDITION_TYPE_AND = 'and'
CONDITION_TYPE_OR = 'or'

DEFAULT_CONDITION_TYPE = CONDITION_TYPE_AND

_LOGGER = logging.getLogger(__name__)


def setup(hass, config):
    """Setup the automation."""
    for config_key in extract_domain_configs(config, DOMAIN):
        conf = config[config_key]

        if not isinstance(conf, list):
            conf = [conf]

        for list_no, config_block in enumerate(conf):
            name = config_block.get(CONF_ALIAS, "{}, {}".format(config_key,
                                                                list_no))
            _setup_automation(hass, config_block, name, config)

    return True


def _setup_automation(hass, config_block, name, config):
    """Setup one instance of automation."""
    action = _get_action(hass, config_block.get(CONF_ACTION, {}), name)

    if action is None:
        return False

    if CONF_CONDITION in config_block or CONF_CONDITION_TYPE in config_block:
        action = _process_if(hass, config, config_block, action)

        if action is None:
            return False

    _process_trigger(hass, config, config_block.get(CONF_TRIGGER, []), name,
                     action)
    return True


def _get_action(hass, config, name):
    """Return an action based on a configuration."""
    validation_error = validate_service_call(config)
    if validation_error:
        _LOGGER.error(validation_error)
        return None

    def action():
        """Action to be executed."""
        _LOGGER.info('Executing %s', name)
        logbook.log_entry(hass, name, 'has been triggered', DOMAIN)

        call_from_config(hass, config)

    return action


def _process_if(hass, config, p_config, action):
    """Process if checks."""
    cond_type = p_config.get(CONF_CONDITION_TYPE,
                             DEFAULT_CONDITION_TYPE).lower()

    if_configs = p_config.get(CONF_CONDITION)
    use_trigger = if_configs == CONDITION_USE_TRIGGER_VALUES

    if use_trigger:
        if_configs = p_config[CONF_TRIGGER]

    if isinstance(if_configs, dict):
        if_configs = [if_configs]

    checks = []
    for if_config in if_configs:
        platform = _resolve_platform('if_action', hass, config,
                                     if_config.get(CONF_PLATFORM))
        if platform is None:
            continue

        check = platform.if_action(hass, if_config)

        # Invalid conditions are allowed if we base it on trigger
        if check is None and not use_trigger:
            return None

        checks.append(check)

    if cond_type == CONDITION_TYPE_AND:
        def if_action():
            """AND all conditions."""
            if all(check() for check in checks):
                action()
    else:
        def if_action():
            """OR all conditions."""
            if any(check() for check in checks):
                action()

    return if_action


def _process_trigger(hass, config, trigger_configs, name, action):
    """Setup the triggers."""
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


def _resolve_platform(method, hass, config, platform):
    """Find the automation platform."""
    if platform is None:
        return None
    platform = prepare_setup_platform(hass, config, DOMAIN, platform)

    if platform is None or not hasattr(platform, method):
        _LOGGER.error("Unknown automation platform specified for %s: %s",
                      method, platform)
        return None

    return platform
