"""
homeassistant.components.sun
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Provides functionality to keep track of the sun.
"""
import logging
from datetime import datetime, timedelta

import homeassistant as ha
import homeassistant.util as util

DEPENDENCIES = []
DOMAIN = "sun"
ENTITY_ID = "sun.sun"

STATE_ABOVE_HORIZON = "above_horizon"
STATE_BELOW_HORIZON = "below_horizon"

STATE_ATTR_NEXT_RISING = "next_rising"
STATE_ATTR_NEXT_SETTING = "next_setting"


def is_on(hass, entity_id=None):
    """ Returns if the sun is currently up based on the statemachine. """
    entity_id = entity_id or ENTITY_ID

    return hass.states.is_state(entity_id, STATE_ABOVE_HORIZON)


def next_setting(hass, entity_id=None):
    """ Returns the datetime object representing the next sun setting. """
    entity_id = entity_id or ENTITY_ID

    state = hass.states.get(ENTITY_ID)

    try:
        return util.str_to_datetime(state.attributes[STATE_ATTR_NEXT_SETTING])
    except (AttributeError, KeyError):
        # AttributeError if state is None
        # KeyError if STATE_ATTR_NEXT_SETTING does not exist
        return None


def next_rising(hass, entity_id=None):
    """ Returns the datetime object representing the next sun rising. """
    entity_id = entity_id or ENTITY_ID

    state = hass.states.get(ENTITY_ID)

    try:
        return util.str_to_datetime(state.attributes[STATE_ATTR_NEXT_RISING])
    except (AttributeError, KeyError):
        # AttributeError if state is None
        # KeyError if STATE_ATTR_NEXT_RISING does not exist
        return None


def setup(hass, config):
    """ Tracks the state of the sun. """
    logger = logging.getLogger(__name__)

    if not util.validate_config(config,
                                {ha.DOMAIN: [ha.CONF_LATITUDE,
                                             ha.CONF_LONGITUDE]},
                                logger):
        return False

    try:
        import ephem
    except ImportError:
        logger.exception("Error while importing dependency ephem.")
        return False

    sun = ephem.Sun()  # pylint: disable=no-member

    latitude = config[ha.DOMAIN][ha.CONF_LATITUDE]
    longitude = config[ha.DOMAIN][ha.CONF_LONGITUDE]

    # Validate latitude and longitude
    observer = ephem.Observer()

    errors = []

    try:
        observer.lat = latitude  # pylint: disable=assigning-non-slot
    except ValueError:
        errors.append("invalid value for latitude given: {}".format(latitude))

    try:
        observer.long = longitude  # pylint: disable=assigning-non-slot
    except ValueError:
        errors.append("invalid value for latitude given: {}".format(latitude))

    if errors:
        logger.error("Error setting up: %s", ", ".join(errors))
        return False

    def update_sun_state(now):
        """ Method to update the current state of the sun and
            set time of next setting and rising. """
        utc_offset = datetime.utcnow() - datetime.now()
        utc_now = now + utc_offset

        observer = ephem.Observer()
        observer.lat = latitude  # pylint: disable=assigning-non-slot
        observer.long = longitude  # pylint: disable=assigning-non-slot

        next_rising_dt = ephem.localtime(
            observer.next_rising(sun, start=utc_now))
        next_setting_dt = ephem.localtime(
            observer.next_setting(sun, start=utc_now))

        if next_rising_dt > next_setting_dt:
            new_state = STATE_ABOVE_HORIZON
            next_change = next_setting_dt

        else:
            new_state = STATE_BELOW_HORIZON
            next_change = next_rising_dt

        logger.info("%s. Next change: %s",
                    new_state, next_change.strftime("%H:%M"))

        state_attributes = {
            STATE_ATTR_NEXT_RISING: util.datetime_to_str(next_rising_dt),
            STATE_ATTR_NEXT_SETTING: util.datetime_to_str(next_setting_dt)
        }

        hass.states.set(ENTITY_ID, new_state, state_attributes)

        # +1 second so Ephem will report it has set
        hass.track_point_in_time(update_sun_state,
                                 next_change + timedelta(seconds=1))

    update_sun_state(datetime.now())

    return True
