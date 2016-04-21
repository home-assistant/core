"""
Offer state listening automation rules.

For more details about this automation rule, please refer to the documentation
at https://home-assistant.io/components/automation/#state-trigger
"""
from datetime import timedelta

import voluptuous as vol

import homeassistant.util.dt as dt_util
from homeassistant.const import (
    EVENT_STATE_CHANGED, EVENT_TIME_CHANGED, MATCH_ALL, CONF_PLATFORM)
from homeassistant.components.automation.time import (
    CONF_HOURS, CONF_MINUTES, CONF_SECONDS)
from homeassistant.helpers.event import track_state_change, track_point_in_time
import homeassistant.helpers.config_validation as cv

CONF_ENTITY_ID = "entity_id"
CONF_FROM = "from"
CONF_TO = "to"
CONF_STATE = "state"
CONF_FOR = "for"

BASE_SCHEMA = vol.Schema({
    vol.Required(CONF_PLATFORM): 'state',
    vol.Required(CONF_ENTITY_ID): cv.entity_id,
    # These are str on purpose. Want to catch YAML conversions
    CONF_STATE: str,
    CONF_FOR: vol.All(vol.Schema({
        CONF_HOURS: vol.Coerce(int),
        CONF_MINUTES: vol.Coerce(int),
        CONF_SECONDS: vol.Coerce(int),
    }), cv.has_at_least_one_key(CONF_HOURS, CONF_MINUTES, CONF_SECONDS)),
})

TRIGGER_SCHEMA = vol.Schema(vol.All(
    BASE_SCHEMA.extend({
        # These are str on purpose. Want to catch YAML conversions
        CONF_FROM: str,
        CONF_TO: str,
    }),
    vol.Any(cv.key_dependency(CONF_FOR, CONF_TO),
            cv.key_dependency(CONF_FOR, CONF_STATE))
))

IF_ACTION_SCHEMA = vol.Schema(vol.All(
    BASE_SCHEMA,
    cv.key_dependency(CONF_FOR, CONF_STATE)
))


def get_time_config(config):
    """Helper function to extract the time specified in the configuration."""
    if CONF_FOR not in config:
        return None

    hours = config[CONF_FOR].get(CONF_HOURS)
    minutes = config[CONF_FOR].get(CONF_MINUTES)
    seconds = config[CONF_FOR].get(CONF_SECONDS)

    return timedelta(hours=(hours or 0.0),
                     minutes=(minutes or 0.0),
                     seconds=(seconds or 0.0))


def trigger(hass, config, action):
    """Listen for state changes based on configuration."""
    entity_id = config.get(CONF_ENTITY_ID)
    from_state = config.get(CONF_FROM, MATCH_ALL)
    to_state = config.get(CONF_TO) or config.get(CONF_STATE) or MATCH_ALL
    time_delta = get_time_config(config)

    def state_automation_listener(entity, from_s, to_s):
        """Listen for state changes and calls action."""
        def call_action():
            """Call action with right context."""
            action({
                'trigger': {
                    'platform': 'state',
                    'entity_id': entity,
                    'from_state': from_s,
                    'to_state': to_s,
                    'for': time_delta,
                }
            })

        if time_delta is None:
            call_action()
            return

        def state_for_listener(now):
            """Fire on state changes after a delay and calls action."""
            hass.bus.remove_listener(
                EVENT_STATE_CHANGED, attached_state_for_cancel)
            call_action()

        def state_for_cancel_listener(entity, inner_from_s, inner_to_s):
            """Fire on changes and cancel for listener if changed."""
            if inner_to_s == to_s:
                return
            hass.bus.remove_listener(EVENT_TIME_CHANGED,
                                     attached_state_for_listener)
            hass.bus.remove_listener(EVENT_STATE_CHANGED,
                                     attached_state_for_cancel)

        attached_state_for_listener = track_point_in_time(
            hass, state_for_listener, dt_util.utcnow() + time_delta)

        attached_state_for_cancel = track_state_change(
            hass, entity_id, state_for_cancel_listener)

    track_state_change(
        hass, entity_id, state_automation_listener, from_state, to_state)

    return True


def if_action(hass, config):
    """Wrap action method with state based condition."""
    entity_id = config.get(CONF_ENTITY_ID)
    state = config.get(CONF_STATE)
    time_delta = get_time_config(config)

    def if_state(variables):
        """Test if condition."""
        is_state = hass.states.is_state(entity_id, state)
        return (time_delta is None and is_state or
                time_delta is not None and
                dt_util.utcnow() - time_delta >
                hass.states.get(entity_id).last_changed)

    return if_state
