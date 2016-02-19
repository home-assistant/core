"""
homeassistant.components.automation.state
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Offers state listening automation rules.

For more details about this automation rule, please refer to the documentation
at https://home-assistant.io/components/automation/#state-trigger
"""
import logging
from datetime import timedelta

import homeassistant.util.dt as dt_util

from homeassistant.const import (
    EVENT_STATE_CHANGED, EVENT_TIME_CHANGED, MATCH_ALL)
from homeassistant.components.automation.time import (
    CONF_HOURS, CONF_MINUTES, CONF_SECONDS)
from homeassistant.helpers.event import track_state_change, track_point_in_time

CONF_ENTITY_ID = "entity_id"
CONF_FROM = "from"
CONF_TO = "to"
CONF_STATE = "state"
CONF_FOR = "for"


def trigger(hass, config, action):
    """ Listen for state changes based on `config`. """
    entity_id = config.get(CONF_ENTITY_ID)

    if entity_id is None:
        logging.getLogger(__name__).error(
            "Missing trigger configuration key %s", CONF_ENTITY_ID)
        return False

    from_state = config.get(CONF_FROM, MATCH_ALL)
    to_state = config.get(CONF_TO) or config.get(CONF_STATE) or MATCH_ALL

    if isinstance(from_state, bool) or isinstance(to_state, bool):
        logging.getLogger(__name__).error(
            'Config error. Surround to/from values with quotes.')
        return False

    if CONF_FOR in config:
        hours = config[CONF_FOR].get(CONF_HOURS)
        minutes = config[CONF_FOR].get(CONF_MINUTES)
        seconds = config[CONF_FOR].get(CONF_SECONDS)

        if hours is None and minutes is None and seconds is None:
            logging.getLogger(__name__).error(
                "Received invalid value for '%s': %s",
                config[CONF_FOR], CONF_FOR)
            return False

        if config.get(CONF_TO) is None and config.get(CONF_STATE) is None:
            logging.getLogger(__name__).error(
                "For: requires a to: value'%s': %s",
                config[CONF_FOR], CONF_FOR)
            return False

    def state_automation_listener(entity, from_s, to_s):
        """ Listens for state changes and calls action. """

        def state_for_listener(now):
            """ Fires on state changes after a delay and calls action. """
            hass.bus.remove_listener(
                EVENT_STATE_CHANGED, for_state_listener)
            action()

        def state_for_cancel_listener(entity, inner_from_s, inner_to_s):
            """ Fires on state changes and cancels
                for listener if state changed. """
            if inner_to_s == to_s:
                return
            hass.bus.remove_listener(EVENT_TIME_CHANGED, for_time_listener)
            hass.bus.remove_listener(
                EVENT_STATE_CHANGED, for_state_listener)

        if CONF_FOR in config:
            now = dt_util.now()
            target_tm = now + timedelta(
                hours=(hours or 0.0),
                minutes=(minutes or 0.0),
                seconds=(seconds or 0.0))
            for_time_listener = track_point_in_time(
                hass, state_for_listener, target_tm)
            for_state_listener = track_state_change(
                hass, entity_id, state_for_cancel_listener,
                MATCH_ALL, MATCH_ALL)
        else:
            action()

    track_state_change(
        hass, entity_id, state_automation_listener, from_state, to_state)

    return True


def if_action(hass, config):
    """ Wraps action method with state based condition. """
    entity_id = config.get(CONF_ENTITY_ID)
    state = config.get(CONF_STATE)

    if entity_id is None or state is None:
        logging.getLogger(__name__).error(
            "Missing if-condition configuration key %s or %s", CONF_ENTITY_ID,
            CONF_STATE)
        return None

    state = str(state)

    def if_state():
        """ Test if condition. """
        return hass.states.is_state(entity_id, state)

    return if_state
