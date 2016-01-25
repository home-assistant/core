"""
Helpers for listening to events
"""
import functools as ft
import logging

from datetime import timedelta, datetime
from croniter import croniter

from ..util import dt as dt_util
from ..const import (
    ATTR_NOW, EVENT_STATE_CHANGED, EVENT_TIME_CHANGED, MATCH_ALL)

_LOGGER = logging.getLogger(__name__)


def track_state_change(hass, entity_ids, action, from_state=None,
                       to_state=None):
    """
    Track specific state changes.
    entity_ids, from_state and to_state can be string or list.
    Use list to match multiple.

    Returns the listener that listens on the bus for EVENT_STATE_CHANGED.
    Pass the return value into hass.bus.remove_listener to remove it.
    """
    from_state = _process_match_param(from_state)
    to_state = _process_match_param(to_state)

    # Ensure it is a lowercase list with entity ids we want to match on
    if isinstance(entity_ids, str):
        entity_ids = (entity_ids.lower(),)
    else:
        entity_ids = tuple(entity_id.lower() for entity_id in entity_ids)

    @ft.wraps(action)
    def state_change_listener(event):
        """ The listener that listens for specific state changes. """
        if event.data['entity_id'] not in entity_ids:
            return

        if 'old_state' in event.data:
            old_state = event.data['old_state'].state
        else:
            old_state = None

        if _matcher(old_state, from_state) and \
           _matcher(event.data['new_state'].state, to_state):

            action(event.data['entity_id'],
                   event.data.get('old_state'),
                   event.data['new_state'])

    hass.bus.listen(EVENT_STATE_CHANGED, state_change_listener)

    return state_change_listener


def track_point_in_time(hass, action, point_in_time):
    """
    Adds a listener that fires once after a spefic point in time.
    """
    utc_point_in_time = dt_util.as_utc(point_in_time)

    @ft.wraps(action)
    def utc_converter(utc_now):
        """ Converts passed in UTC now to local now. """
        action(dt_util.as_local(utc_now))

    return track_point_in_utc_time(hass, utc_converter, utc_point_in_time)


def track_point_in_utc_time(hass, action, point_in_time):
    """
    Adds a listener that fires once after a specific point in UTC time.
    """
    # Ensure point_in_time is UTC
    point_in_time = dt_util.as_utc(point_in_time)

    @ft.wraps(action)
    def point_in_time_listener(event):
        """ Listens for matching time_changed events. """
        now = event.data[ATTR_NOW]

        if now >= point_in_time and \
           not hasattr(point_in_time_listener, 'run'):

            # Set variable so that we will never run twice.
            # Because the event bus might have to wait till a thread comes
            # available to execute this listener it might occur that the
            # listener gets lined up twice to be executed. This will make
            # sure the second time it does nothing.
            point_in_time_listener.run = True

            hass.bus.remove_listener(EVENT_TIME_CHANGED,
                                     point_in_time_listener)

            action(now)

    hass.bus.listen(EVENT_TIME_CHANGED, point_in_time_listener)
    return point_in_time_listener


def track_utc_time_change(hass, action, cron=None, second=None, local=None):
    """
    Adds a listener that will fire if time matches a pattern.
    @param hass:
    @param action:
    @param cron: given in '* * * * *' format
    @param second:
    @param local:
    @return:
    """
    # We do not have to wrap the function with time pattern matching logic
    # if no pattern given
    if not cron and not second:
        @ft.wraps(action)
        def time_change_listener(event):
            """ Fires every time event that comes in. """
            action(event.data[ATTR_NOW])

        hass.bus.listen(EVENT_TIME_CHANGED, time_change_listener)
        return time_change_listener

    if not cron:
        cron = "* * * * *"

    start_now = dt_util.now() if local else dt_util.utcnow()

    _LOGGER.info("%s %s", cron, second)
    iterator = croniter(cron, start_now)

    log_nxt = iterator.get_next(datetime)

    _LOGGER.info("Next event fires %s", log_nxt)

    set_second = second

    @ft.wraps(action)
    def pattern_time_change_listener(event):
        """ Listens for matching time_changed events. """

        current_fire = iterator.get_current(datetime)
        current_fire = current_fire.replace(second=set_second)

        now = event.data[ATTR_NOW]

        now = dt_util.as_local(now) if local else dt_util.as_utc(now)

        fire = current_fire - now
        _LOGGER.warning("%s <= %s", fire, timedelta(seconds=1))
        if fire <= timedelta(seconds=1):
            next_fire = iterator.get_next(datetime)
            _LOGGER.info("Next event fires %s", next_fire)

            action(now)

    hass.bus.listen(EVENT_TIME_CHANGED, pattern_time_change_listener)
    return pattern_time_change_listener


# pylint: disable=too-many-arguments
def track_time_change(hass, action, year=None, month=None, day=None,
                      hour=None, minute=None, second=None,
                      day_of_week=None, cron=None, local=True):
    """ Adds a listener that will fire if UTC time matches a pattern. """
    if not cron:
        cron = time_params_to_cron(year, month, day, hour, minute, second,
                                   day_of_week)

    track_utc_time_change(hass, action, cron, second, local)


def time_params_to_cron(year=None, month=None, day=None, hour=None,
                        minute=None, second=None, day_of_week=None):
    return "%s %s %s %s %s" % (
        minute or '*',
        hour or '*',
        day or '*',
        month or '*',
        day_of_week or '*'
    )


def _process_match_param(parameter):
    """ Wraps parameter in a tuple if it is not one and returns it. """
    if parameter is None or parameter == MATCH_ALL:
        return MATCH_ALL
    elif isinstance(parameter, str) or not hasattr(parameter, '__iter__'):
        return (parameter,)
    else:
        return tuple(parameter)


def _matcher(subject, pattern):
    """ Returns True if subject matches the pattern.
    Pattern is either a tuple of allowed subjects or a `MATCH_ALL`.
    """
    return MATCH_ALL == pattern or subject in pattern
