"""
Allow to setup simple automation rules via the config file.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/automation/
"""
from functools import partial
import logging
import os

import voluptuous as vol

from homeassistant.bootstrap import prepare_setup_platform
from homeassistant import config as conf_util
from homeassistant.const import (
    ATTR_ENTITY_ID, CONF_PLATFORM, STATE_ON, SERVICE_TURN_ON, SERVICE_TURN_OFF,
    SERVICE_TOGGLE)
from homeassistant.components import logbook
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import extract_domain_configs, script, condition
from homeassistant.helpers.entity import ToggleEntity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.loader import get_platform
from homeassistant.util.dt import utcnow
import homeassistant.helpers.config_validation as cv

DOMAIN = 'automation'
ENTITY_ID_FORMAT = DOMAIN + '.{}'

DEPENDENCIES = ['group']

CONF_ALIAS = 'alias'
CONF_HIDE_ENTITY = 'hide_entity'

CONF_CONDITION = 'condition'
CONF_ACTION = 'action'
CONF_TRIGGER = 'trigger'
CONF_CONDITION_TYPE = 'condition_type'

CONDITION_USE_TRIGGER_VALUES = 'use_trigger_values'
CONDITION_TYPE_AND = 'and'
CONDITION_TYPE_OR = 'or'

DEFAULT_CONDITION_TYPE = CONDITION_TYPE_AND
DEFAULT_HIDE_ENTITY = False

METHOD_TRIGGER = 'trigger'
METHOD_IF_ACTION = 'if_action'

ATTR_LAST_TRIGGERED = 'last_triggered'
ATTR_VARIABLES = 'variables'
SERVICE_TRIGGER = 'trigger'
SERVICE_RELOAD = 'reload'

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
    vol.Optional(CONF_HIDE_ENTITY, default=DEFAULT_HIDE_ENTITY): cv.boolean,
    vol.Required(CONF_TRIGGER): _TRIGGER_SCHEMA,
    vol.Required(CONF_CONDITION_TYPE, default=DEFAULT_CONDITION_TYPE):
        vol.All(vol.Lower, vol.Any(CONDITION_TYPE_AND, CONDITION_TYPE_OR)),
    vol.Optional(CONF_CONDITION): _CONDITION_SCHEMA,
    vol.Required(CONF_ACTION): cv.SCRIPT_SCHEMA,
})

SERVICE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
})

TRIGGER_SERVICE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Optional(ATTR_VARIABLES, default={}): dict,
})

RELOAD_SERVICE_SCHEMA = vol.Schema({})


def is_on(hass, entity_id=None):
    """
    Return true if specified automation entity_id is on.

    Check all automation if no entity_id specified.
    """
    entity_ids = [entity_id] if entity_id else hass.states.entity_ids(DOMAIN)
    return any(hass.states.is_state(entity_id, STATE_ON)
               for entity_id in entity_ids)


def turn_on(hass, entity_id=None):
    """Turn on specified automation or all."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    hass.services.call(DOMAIN, SERVICE_TURN_ON, data)


def turn_off(hass, entity_id=None):
    """Turn off specified automation or all."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    hass.services.call(DOMAIN, SERVICE_TURN_OFF, data)


def toggle(hass, entity_id=None):
    """Toggle specified automation or all."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    hass.services.call(DOMAIN, SERVICE_TOGGLE, data)


def trigger(hass, entity_id=None):
    """Trigger specified automation or all."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    hass.services.call(DOMAIN, SERVICE_TRIGGER, data)


def reload(hass):
    """Reload the automation from config."""
    hass.services.call(DOMAIN, SERVICE_RELOAD)


def setup(hass, config):
    """Setup the automation."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)

    success = _process_config(hass, config, component)

    if not success:
        return False

    descriptions = conf_util.load_yaml_config_file(
        os.path.join(os.path.dirname(__file__), 'services.yaml'))

    def trigger_service_handler(service_call):
        """Handle automation triggers."""
        for entity in component.extract_from_service(service_call):
            entity.trigger(service_call.data.get(ATTR_VARIABLES))

    def service_handler(service_call):
        """Handle automation service calls."""
        for entity in component.extract_from_service(service_call):
            getattr(entity, service_call.service)()

    def reload_service_handler(service_call):
        """Remove all automations and load new ones from config."""
        conf = component.prepare_reload()
        if conf is None:
            return
        _process_config(hass, conf, component)

    hass.services.register(DOMAIN, SERVICE_TRIGGER, trigger_service_handler,
                           descriptions.get(SERVICE_TRIGGER),
                           schema=TRIGGER_SERVICE_SCHEMA)

    hass.services.register(DOMAIN, SERVICE_RELOAD, reload_service_handler,
                           descriptions.get(SERVICE_RELOAD),
                           schema=RELOAD_SERVICE_SCHEMA)

    for service in (SERVICE_TURN_ON, SERVICE_TURN_OFF, SERVICE_TOGGLE):
        hass.services.register(DOMAIN, service, service_handler,
                               descriptions.get(service),
                               schema=SERVICE_SCHEMA)

    return True


class AutomationEntity(ToggleEntity):
    """Entity to show status of entity."""

    # pylint: disable=too-many-arguments, too-many-instance-attributes
    def __init__(self, name, attach_triggers, cond_func, action, hidden):
        """Initialize an automation entity."""
        self._name = name
        self._attach_triggers = attach_triggers
        self._detach_triggers = attach_triggers(self.trigger)
        self._cond_func = cond_func
        self._action = action
        self._enabled = True
        self._last_triggered = None
        self._hidden = hidden

    @property
    def name(self):
        """Name of the automation."""
        return self._name

    @property
    def should_poll(self):
        """No polling needed for automation entities."""
        return False

    @property
    def state_attributes(self):
        """Return the entity state attributes."""
        return {
            ATTR_LAST_TRIGGERED: self._last_triggered
        }

    @property
    def hidden(self) -> bool:
        """Return True if the automation entity should be hidden from UIs."""
        return self._hidden

    @property
    def is_on(self) -> bool:
        """Return True if entity is on."""
        return self._enabled

    def turn_on(self, **kwargs) -> None:
        """Turn the entity on."""
        if self._enabled:
            return

        self._detach_triggers = self._attach_triggers(self.trigger)
        self._enabled = True
        self.update_ha_state()

    def turn_off(self, **kwargs) -> None:
        """Turn the entity off."""
        if not self._enabled:
            return

        self._detach_triggers()
        self._detach_triggers = None
        self._enabled = False
        self.update_ha_state()

    def trigger(self, variables):
        """Trigger automation."""
        if self._cond_func(variables):
            self._action(variables)
            self._last_triggered = utcnow()
            self.update_ha_state()

    def remove(self):
        """Remove automation from HASS."""
        self.turn_off()
        super().remove()


def _process_config(hass, config, component):
    """Process config and add automations."""
    success = False

    for config_key in extract_domain_configs(config, DOMAIN):
        conf = config[config_key]

        for list_no, config_block in enumerate(conf):
            name = config_block.get(CONF_ALIAS) or "{} {}".format(config_key,
                                                                  list_no)

            hidden = config_block[CONF_HIDE_ENTITY]

            action = _get_action(hass, config_block.get(CONF_ACTION, {}), name)

            if CONF_CONDITION in config_block:
                cond_func = _process_if(hass, config, config_block)

                if cond_func is None:
                    continue
            else:
                def cond_func(variables):
                    """Condition will always pass."""
                    return True

            attach_triggers = partial(_process_trigger, hass, config,
                                      config_block.get(CONF_TRIGGER, []), name)
            entity = AutomationEntity(name, attach_triggers, cond_func, action,
                                      hidden)
            component.add_entities((entity,))
            success = True

    return success


def _get_action(hass, config, name):
    """Return an action based on a configuration."""
    script_obj = script.Script(hass, config, name)

    def action(variables=None):
        """Action to be executed."""
        _LOGGER.info('Executing %s', name)
        logbook.log_entry(hass, name, 'has been triggered', DOMAIN)
        script_obj.run(variables)

    return action


def _process_if(hass, config, p_config):
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
            return all(check(hass, variables) for check in checks)
    else:
        def if_action(variables=None):
            """OR all conditions."""
            return any(check(hass, variables) for check in checks)

    return if_action


def _process_trigger(hass, config, trigger_configs, name, action):
    """Setup the triggers."""
    removes = []

    for conf in trigger_configs:
        platform = _resolve_platform(METHOD_TRIGGER, hass, config,
                                     conf.get(CONF_PLATFORM))
        if platform is None:
            continue

        remove = platform.trigger(hass, conf, action)

        if not remove:
            _LOGGER.error("Error setting up rule %s", name)
            continue

        _LOGGER.info("Initialized rule %s", name)
        removes.append(remove)

    if not removes:
        return None

    def remove_triggers():
        """Remove attached triggers."""
        for remove in removes:
            remove()

    return remove_triggers


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
