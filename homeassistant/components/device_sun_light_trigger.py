"""
Provides functionality to turn on lights based on the states.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/device_sun_light_trigger/
"""
import logging
from datetime import timedelta

import homeassistant.util.dt as dt_util
from homeassistant.const import STATE_HOME, STATE_NOT_HOME
from homeassistant.helpers.event import track_point_in_time
from homeassistant.helpers.event_decorators import track_state_change
from homeassistant.loader import get_component

DOMAIN = "device_sun_light_trigger"
DEPENDENCIES = ['light', 'device_tracker', 'group', 'sun']

LIGHT_TRANSITION_TIME = timedelta(minutes=15)

# Light profile to be used if none given
LIGHT_PROFILE = 'relax'

CONF_LIGHT_PROFILE = 'light_profile'
CONF_LIGHT_GROUP = 'light_group'
CONF_DEVICE_GROUP = 'device_group'


# pylint: disable=too-many-locals
def setup(hass, config):
    """The triggers to turn lights on or off based on device presence."""
    logger = logging.getLogger(__name__)
    device_tracker = get_component('device_tracker')
    group = get_component('group')
    light = get_component('light')
    sun = get_component('sun')

    disable_turn_off = 'disable_turn_off' in config[DOMAIN]
    light_group = config[DOMAIN].get(CONF_LIGHT_GROUP,
                                     light.ENTITY_ID_ALL_LIGHTS)
    light_profile = config[DOMAIN].get(CONF_LIGHT_PROFILE, LIGHT_PROFILE)
    device_group = config[DOMAIN].get(CONF_DEVICE_GROUP,
                                      device_tracker.ENTITY_ID_ALL_DEVICES)
    device_entity_ids = group.get_entity_ids(hass, device_group,
                                             device_tracker.DOMAIN)

    if not device_entity_ids:
        logger.error("No devices found to track")
        return False

    # Get the light IDs from the specified group
    light_ids = group.get_entity_ids(hass, light_group, light.DOMAIN)

    if not light_ids:
        logger.error("No lights found to turn on ")
        return False

    def calc_time_for_light_when_sunset():
        """Calculate the time when to start fading lights in when sun sets.

        Returns None if no next_setting data available.
        """
        next_setting = sun.next_setting(hass)
        if not next_setting:
            return None
        return next_setting - LIGHT_TRANSITION_TIME * len(light_ids)

    def turn_light_on_before_sunset(light_id):
        """Helper function to turn on lights.

        Speed is slow if there are devices home and the light is not on yet.
        """
        if not device_tracker.is_on(hass) or light.is_on(hass, light_id):
            return
        light.turn_on(hass, light_id,
                      transition=LIGHT_TRANSITION_TIME.seconds,
                      profile=light_profile)

    # Track every time sun rises so we can schedule a time-based
    # pre-sun set event
    @track_state_change(sun.ENTITY_ID, sun.STATE_BELOW_HORIZON,
                        sun.STATE_ABOVE_HORIZON)
    def schedule_lights_at_sun_set(hass, entity, old_state, new_state):
        """The moment sun sets we want to have all the lights on.

        We will schedule to have each light start after one another
        and slowly transition in.
        """
        start_point = calc_time_for_light_when_sunset()
        if not start_point:
            return

        def turn_on(light_id):
            """Lambda can keep track of function parameters.

            No local parameters. If we put the lambda directly in the below
            statement only the last light will be turned on.
            """
            return lambda now: turn_light_on_before_sunset(light_id)

        for index, light_id in enumerate(light_ids):
            track_point_in_time(hass, turn_on(light_id),
                                start_point + index * LIGHT_TRANSITION_TIME)

    # If the sun is already above horizon schedule the time-based pre-sun set
    # event.
    if sun.is_on(hass):
        schedule_lights_at_sun_set(hass, None, None, None)

    @track_state_change(device_entity_ids, STATE_NOT_HOME, STATE_HOME)
    def check_light_on_dev_state_change(hass, entity, old_state, new_state):
        """Handle tracked device state changes."""
        # pylint: disable=unused-variable
        lights_are_on = group.is_on(hass, light_group)

        light_needed = not (lights_are_on or sun.is_on(hass))

        # These variables are needed for the elif check
        now = dt_util.now()
        start_point = calc_time_for_light_when_sunset()

        # Do we need lights?
        if light_needed:
            logger.info("Home coming event for %s. Turning lights on", entity)
            light.turn_on(hass, light_ids, profile=light_profile)

        # Are we in the time span were we would turn on the lights
        # if someone would be home?
        # Check this by seeing if current time is later then the point
        # in time when we would start putting the lights on.
        elif (start_point and
              start_point < now < sun.next_setting(hass)):

            # Check for every light if it would be on if someone was home
            # when the fading in started and turn it on if so
            for index, light_id in enumerate(light_ids):
                if now > start_point + index * LIGHT_TRANSITION_TIME:
                    light.turn_on(hass, light_id)

                else:
                    # If this light didn't happen to be turned on yet so
                    # will all the following then, break.
                    break

    if not disable_turn_off:
        @track_state_change(device_group, STATE_HOME, STATE_NOT_HOME)
        def turn_off_lights_when_all_leave(hass, entity, old_state, new_state):
            """Handle device group state change."""
            # pylint: disable=unused-variable
            if not group.is_on(hass, light_group):
                return

            logger.info(
                "Everyone has left but there are lights on. Turning them off")
            light.turn_off(hass, light_ids)

    return True
