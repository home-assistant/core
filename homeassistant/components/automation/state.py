"""
Offer state listening automation rules.

For more details about this automation rule, please refer to the documentation
at https://home-assistant.io/components/automation/#state-trigger
"""
import voluptuous as vol

import homeassistant.util.dt as dt_util
from homeassistant.const import MATCH_ALL, CONF_PLATFORM
from homeassistant.helpers.event import track_state_change, track_point_in_time
import homeassistant.helpers.config_validation as cv

CONF_ENTITY_ID = "entity_id"
CONF_FROM = "from"
CONF_TO = "to"
CONF_STATE = "state"
CONF_FOR = "for"

TRIGGER_SCHEMA = vol.All(
    vol.Schema({
        vol.Required(CONF_PLATFORM): 'state',
        vol.Required(CONF_ENTITY_ID): cv.entity_ids,
        # These are str on purpose. Want to catch YAML conversions
        CONF_FROM: str,
        CONF_TO: str,
        CONF_STATE: str,
        CONF_FOR: vol.All(cv.time_period, cv.positive_timedelta),
    }),
    vol.Any(cv.key_dependency(CONF_FOR, CONF_TO),
            cv.key_dependency(CONF_FOR, CONF_STATE))
)


def trigger(hass, config, action):
    """Listen for state changes based on configuration."""
    entity_id = config.get(CONF_ENTITY_ID)
    from_state = config.get(CONF_FROM, MATCH_ALL)
    to_state = config.get(CONF_TO) or config.get(CONF_STATE) or MATCH_ALL
    time_delta = config.get(CONF_FOR)
    remove_state_for_cancel = None
    remove_state_for_listener = None

    def state_automation_listener(entity, from_s, to_s):
        """Listen for state changes and calls action."""
        nonlocal remove_state_for_cancel, remove_state_for_listener

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
            remove_state_for_cancel()
            call_action()

        def state_for_cancel_listener(entity, inner_from_s, inner_to_s):
            """Fire on changes and cancel for listener if changed."""
            if inner_to_s.state == to_s.state:
                return
            remove_state_for_listener()
            remove_state_for_cancel()

        remove_state_for_listener = track_point_in_time(
            hass, state_for_listener, dt_util.utcnow() + time_delta)

        remove_state_for_cancel = track_state_change(
            hass, entity, state_for_cancel_listener)

    unsub = track_state_change(hass, entity_id, state_automation_listener,
                               from_state, to_state)

    def remove():
        """Remove state listeners."""
        unsub()
        # pylint: disable=not-callable
        if remove_state_for_cancel is not None:
            remove_state_for_cancel()

        if remove_state_for_listener is not None:
            remove_state_for_listener()

    return remove
