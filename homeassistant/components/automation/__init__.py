"""
Allow to setup simple automation rules via the config file.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/automation/
"""
import logging

import voluptuous as vol

from homeassistant.bootstrap import prepare_setup_platform
from homeassistant.const import ATTR_ENTITY_ID, CONF_PLATFORM
from homeassistant.components import logbook
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import extract_domain_configs, script, condition
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
                    CONF_PLATFORM: str,
                    CONF_CONDITION: str,
                }, extra=vol.ALLOW_EXTRA),
                cv.has_at_least_one_key(CONF_PLATFORM, CONF_CONDITION),
            ),
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
    success = False
    for config_key in extract_domain_configs(config, DOMAIN):
        conf = config[config_key]

        for list_no, config_block in enumerate(conf):
            name = config_block.get(CONF_ALIAS, "{}, {}".format(config_key,
                                                                list_no))
            success = (_setup_automation(hass, config_block, name, config) or
                       success)

    return success


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

    # Deprecated since 0.19 - 5/5/2016
    if cond_type != DEFAULT_CONDITION_TYPE:
        _LOGGER.warning('Using condition_type: "or" is deprecated. Please use '
                        '"condition: or" instead.')

    if_configs = p_config.get(CONF_CONDITION)
    use_trigger = if_configs == CONDITION_USE_TRIGGER_VALUES

    if use_trigger:
        if_configs = p_config[CONF_TRIGGER]

    checks = []
    for if_config in if_configs:
        # Deprecated except for used by use_trigger_values
        # since 0.19 - 5/5/2016
        if CONF_PLATFORM in if_config:
            if not use_trigger:
                _LOGGER.warning("Please switch your condition configuration "
                                "to use 'condition' instead of 'platform'.")
            if_config = dict(if_config)
            if_config[CONF_CONDITION] = if_config.pop(CONF_PLATFORM)

            # To support use_trigger_values with state trigger accepting
            # multiple entity_ids to monitor.
            if_entity_id = if_config.get(ATTR_ENTITY_ID)
            if isinstance(if_entity_id, list) and len(if_entity_id) == 1:
                if_config[ATTR_ENTITY_ID] = if_entity_id[0]

        try:
            checks.append(condition.from_config(if_config))
        except HomeAssistantError as ex:
            # Invalid conditions are allowed if we base it on trigger
            if use_trigger:
                _LOGGER.warning('Ignoring invalid condition: %s', ex)
            else:
                _LOGGER.warning('Invalid condition: %s', ex)
                return None

    if cond_type == CONDITION_TYPE_AND:
        def if_action(variables=None):
            """AND all conditions."""
            if all(check(hass, variables) for check in checks):
                action(variables)
    else:
        def if_action(variables=None):
            """OR all conditions."""
            if any(check(hass, variables) for check in checks):
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
