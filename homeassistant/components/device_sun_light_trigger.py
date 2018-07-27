"""
Provides functionality to turn on lights based on the states.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/device_sun_light_trigger/
"""
import asyncio
import logging
from datetime import timedelta

import voluptuous as vol

from homeassistant.core import callback
import homeassistant.util.dt as dt_util
from homeassistant.const import STATE_HOME, STATE_NOT_HOME
from homeassistant.helpers.event import (
    async_track_point_in_utc_time, async_track_state_change)
from homeassistant.helpers.sun import is_up, get_astral_event_next
import homeassistant.helpers.config_validation as cv

DOMAIN = 'device_sun_light_trigger'
DEPENDENCIES = ['light', 'device_tracker', 'group']

CONF_DEVICE_GROUP = 'device_group'
CONF_DISABLE_TURN_OFF = 'disable_turn_off'
CONF_LIGHT_GROUP = 'light_group'
CONF_LIGHT_PROFILE = 'light_profile'

DEFAULT_DISABLE_TURN_OFF = False
DEFAULT_LIGHT_PROFILE = 'relax'

LIGHT_TRANSITION_TIME = timedelta(minutes=15)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_DEVICE_GROUP): cv.entity_id,
        vol.Optional(CONF_DISABLE_TURN_OFF, default=DEFAULT_DISABLE_TURN_OFF):
            cv.boolean,
        vol.Optional(CONF_LIGHT_GROUP): cv.string,
        vol.Optional(CONF_LIGHT_PROFILE, default=DEFAULT_LIGHT_PROFILE):
            cv.string,
    }),
}, extra=vol.ALLOW_EXTRA)


@asyncio.coroutine
def async_setup(hass, config):
    """Set up the triggers to control lights based on device presence."""
    logger = logging.getLogger(__name__)
    device_tracker = hass.components.device_tracker
    group = hass.components.group
    light = hass.components.light
    conf = config[DOMAIN]
    disable_turn_off = conf.get(CONF_DISABLE_TURN_OFF)
    light_group = conf.get(CONF_LIGHT_GROUP, light.ENTITY_ID_ALL_LIGHTS)
    light_profile = conf.get(CONF_LIGHT_PROFILE)
    device_group = conf.get(
        CONF_DEVICE_GROUP, device_tracker.ENTITY_ID_ALL_DEVICES)
    device_entity_ids = group.get_entity_ids(
        device_group, device_tracker.DOMAIN)

    if not device_entity_ids:
        logger.error("No devices found to track")
        return False

    # Get the light IDs from the specified group
    light_ids = group.get_entity_ids(light_group, light.DOMAIN)

    if not light_ids:
        logger.error("No lights found to turn on")
        return False

    def calc_time_for_light_when_sunset():
        """Calculate the time when to start fading lights in when sun sets.

        Returns None if no next_setting data available.

        Async friendly.
        """
        next_setting = get_astral_event_next(hass, 'sunset')
        if not next_setting:
            return None
        return next_setting - LIGHT_TRANSITION_TIME * len(light_ids)

    def async_turn_on_before_sunset(light_id):
        """Turn on lights."""
        if not device_tracker.is_on() or light.is_on(light_id):
            return
        light.async_turn_on(light_id,
                            transition=LIGHT_TRANSITION_TIME.seconds,
                            profile=light_profile)

    def async_turn_on_factory(light_id):
        """Generate turn on callbacks as factory."""
        @callback
        def async_turn_on_light(now):
            """Turn on specific light."""
            async_turn_on_before_sunset(light_id)

        return async_turn_on_light

    # Track every time sun rises so we can schedule a time-based
    # pre-sun set event
    @callback
    def schedule_light_turn_on(now):
        """Turn on all the lights at the moment sun sets.

        We will schedule to have each light start after one another
        and slowly transition in.
        """
        start_point = calc_time_for_light_when_sunset()
        if not start_point:
            return

        for index, light_id in enumerate(light_ids):
            async_track_point_in_utc_time(
                hass, async_turn_on_factory(light_id),
                start_point + index * LIGHT_TRANSITION_TIME)

    async_track_point_in_utc_time(hass, schedule_light_turn_on,
                                  get_astral_event_next(hass, 'sunrise'))

    # If the sun is already above horizon schedule the time-based pre-sun set
    # event.
    if is_up(hass):
        schedule_light_turn_on(None)

    @callback
    def check_light_on_dev_state_change(entity, old_state, new_state):
        """Handle tracked device state changes."""
        lights_are_on = group.is_on(light_group)
        light_needed = not (lights_are_on or is_up(hass))

        # These variables are needed for the elif check
        now = dt_util.utcnow()
        start_point = calc_time_for_light_when_sunset()

        # Do we need lights?
        if light_needed:
            logger.info("Home coming event for %s. Turning lights on", entity)
            light.async_turn_on(light_ids, profile=light_profile)

        # Are we in the time span were we would turn on the lights
        # if someone would be home?
        # Check this by seeing if current time is later then the point
        # in time when we would start putting the lights on.
        elif (start_point and
              start_point < now < get_astral_event_next(hass, 'sunset')):

            # Check for every light if it would be on if someone was home
            # when the fading in started and turn it on if so
            for index, light_id in enumerate(light_ids):
                if now > start_point + index * LIGHT_TRANSITION_TIME:
                    light.async_turn_on(light_id)

                else:
                    # If this light didn't happen to be turned on yet so
                    # will all the following then, break.
                    break

    async_track_state_change(
        hass, device_entity_ids, check_light_on_dev_state_change,
        STATE_NOT_HOME, STATE_HOME)

    if disable_turn_off:
        return True

    @callback
    def turn_off_lights_when_all_leave(entity, old_state, new_state):
        """Handle device group state change."""
        if not group.is_on(light_group):
            return

        logger.info(
            "Everyone has left but there are lights on. Turning them off")
        light.async_turn_off(light_ids)

    async_track_state_change(
        hass, device_group, turn_off_lights_when_all_leave,
        STATE_HOME, STATE_NOT_HOME)

    return True
