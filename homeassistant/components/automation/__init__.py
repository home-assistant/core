"""
Allow to setup simple automation rules via the config file.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/automation/
"""
import logging

import voluptuous as vol

from homeassistant.bootstrap import prepare_setup_platform
from homeassistant.const import CONF_PLATFORM
from homeassistant.components import logbook
from homeassistant.helpers import extract_domain_configs, script
from homeassistant.loader import get_platform
import homeassistant.helpers.config_validation as cv

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

METHOD_TRIGGER = 'trigger'
METHOD_IF_ACTION = 'if_action'

_LOGGER = logging.getLogger(__name__)


def _platform_validator(method, schema):
    """Generate platform validator for different steps."""
    def validator(config):
        """Validate it is a valid  platform."""
        platform = get_platform(DOMAIN, config[CONF_PLATFORM])

        if not hasattr(platform, method):
            raise vol.Invalid('invalid method platform')

        if not hasattr(platform, schema):
            return config

        return getattr(platform, schema)(config)

    return validator

_TRIGGER_SCHEMA = vol.All(
    cv.ensure_list,
    [
        vol.All(
            vol.Schema({
                vol.Required(CONF_PLATFORM): cv.platform_validator(DOMAIN)
            }, extra=vol.ALLOW_EXTRA),
            _platform_validator(METHOD_TRIGGER, 'TRIGGER_SCHEMA')
        ),
    ]
)

_CONDITION_SCHEMA = vol.Any(
    CONDITION_USE_TRIGGER_VALUES,
    vol.All(
        cv.ensure_list,
        [
            vol.All(
                vol.Schema({
                    vol.Required(CONF_PLATFORM): cv.platform_validator(DOMAIN),
                }, extra=vol.ALLOW_EXTRA),
                _platform_validator(METHOD_IF_ACTION, 'IF_ACTION_SCHEMA'),
            )
        ]
    )
)

PLATFORM_SCHEMA = vol.Schema({
    CONF_ALIAS: cv.string,
    vol.Required(CONF_TRIGGER): _TRIGGER_SCHEMA,
    vol.Required(CONF_CONDITION_TYPE, default=DEFAULT_CONDITION_TYPE):
        vol.All(vol.Lower, vol.Any(CONDITION_TYPE_AND, CONDITION_TYPE_OR)),
    CONF_CONDITION: _CONDITION_SCHEMA,
    vol.Required(CONF_ACTION): cv.SCRIPT_SCHEMA,
})


def setup(hass, config):
    """Setup the automation."""
    for config_key in extract_domain_configs(config, DOMAIN):
        conf = config[config_key]

        for list_no, config_block in enumerate(conf):
            name = config_block.get(CONF_ALIAS, "{}, {}".format(config_key,
                                                                list_no))
            _setup_automation(hass, config_block, name, config)

    return True


def _setup_automation(hass, config_block, name, config):
    """Setup one instance of automation."""
    action = _get_action(hass, config_block.get(CONF_ACTION, {}), name)

    if CONF_CONDITION in config_block:
        action = _process_if(hass, config, config_block, action)

        if action is None:
            return False

    _process_trigger(hass, config, config_block.get(CONF_TRIGGER, []), name,
                     action)
    return True


def _get_action(hass, config, name):
    """Return an action based on a configuration."""
    script_obj = script.Script(hass, config, name)

    def action(variables=None):
        """Action to be executed."""
        _LOGGER.info('Executing %s', name)
        logbook.log_entry(hass, name, 'has been triggered', DOMAIN)
        script_obj.run(variables)

    return action


def _process_if(hass, config, p_config, action):
    """Process if checks."""
    cond_type = p_config.get(CONF_CONDITION_TYPE,
                             DEFAULT_CONDITION_TYPE).lower()

    if_configs = p_config.get(CONF_CONDITION)
    use_trigger = if_configs == CONDITION_USE_TRIGGER_VALUES

    if use_trigger:
        if_configs = p_config[CONF_TRIGGER]

    checks = []
    for if_config in if_configs:
        platform = _resolve_platform(METHOD_IF_ACTION, hass, config,
                                     if_config.get(CONF_PLATFORM))
        if platform is None:
            continue

        check = platform.if_action(hass, if_config)

        # Invalid conditions are allowed if we base it on trigger
        if check is None and not use_trigger:
            return None

        checks.append(check)

    if cond_type == CONDITION_TYPE_AND:
        def if_action(variables=None):
            """AND all conditions."""
            if all(check(variables) for check in checks):
                action(variables)
    else:
        def if_action(variables=None):
            """OR all conditions."""
            if any(check(variables) for check in checks):
                action(variables)

    return if_action


def _process_trigger(hass, config, trigger_configs, name, action):
    """Setup the triggers."""
    for conf in trigger_configs:
        platform = _resolve_platform(METHOD_TRIGGER, hass, config,
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
