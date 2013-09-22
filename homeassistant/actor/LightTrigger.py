import logging
from datetime import datetime, timedelta

from homeassistant.observer.WeatherWatcher import STATE_CATEGORY_SUN, SUN_STATE_BELOW_HORIZON, SUN_STATE_ABOVE_HORIZON
from homeassistant.observer.DeviceTracker import STATE_CATEGORY_ALL_DEVICES, STATE_DEVICE_HOME, STATE_DEVICE_NOT_HOME
from homeassistant.StateMachine import track_state_change
from homeassistant.observer.Timer import track_time_change

LIGHT_TRANSITION_TIME = timedelta(minutes=15)

class LightTrigger(object):
    """ Class to turn on lights based on available devices and state of the sun. """

    def __init__(self, eventbus, statemachine, device_tracker, weather, light_control):
        self.eventbus = eventbus
        self.statemachine = statemachine
        self.weather = weather
        self.light_control = light_control

        self.logger = logging.getLogger(__name__)

        # Track home coming of each seperate device
        for category in device_tracker.device_state_categories():
            track_state_change(eventbus, category, STATE_DEVICE_NOT_HOME, STATE_DEVICE_HOME, self._handle_device_state_change)

        # Track when all devices are gone to shut down lights
        track_state_change(eventbus, STATE_CATEGORY_ALL_DEVICES, STATE_DEVICE_HOME, STATE_DEVICE_NOT_HOME, self._handle_device_state_change)

        # Track every time sun rises so we can schedule a time-based pre-sun set event
        track_state_change(eventbus, STATE_CATEGORY_SUN, SUN_STATE_BELOW_HORIZON, SUN_STATE_ABOVE_HORIZON, self._handle_sun_rising)

        # If the sun is already above horizon schedule the time-based pre-sun set event
        if statemachine.is_state(STATE_CATEGORY_SUN, SUN_STATE_ABOVE_HORIZON):
            self._handle_sun_rising(None, None, None)


    def _handle_sun_rising(self, category, old_state, new_state):
        """The moment sun sets we want to have all the lights on.
           We will schedule to have each light start after one another
           and slowly transition in."""

        start_point = self.weather.next_sun_setting() - LIGHT_TRANSITION_TIME * len(self.light_control.light_ids)

        # Lambda can keep track of function parameters, not from local parameters
        # If we put the lambda directly in the below statement only the last light
        # would be turned on..
        def turn_on(light_id):
            return lambda now: self._turn_light_on_before_sunset(light_id)

        for index, light_id in enumerate(self.light_control.light_ids):
            track_time_change(self.eventbus, turn_on(light_id),
                              point_in_time=start_point + index * LIGHT_TRANSITION_TIME)


    def _turn_light_on_before_sunset(self, light_id=None):
        """ Helper function to turn on lights slowly if there are devices home and the light is not on yet. """
        if self.statemachine.is_state(STATE_CATEGORY_ALL_DEVICES, STATE_DEVICE_HOME) and not self.light_control.is_light_on(light_id):
            self.light_control.turn_light_on(light_id, LIGHT_TRANSITION_TIME.seconds)


    def _handle_device_state_change(self, category, old_state, new_state):
        """ Function to handle tracked device state changes. """
        lights_are_on = self.light_control.is_light_on()

        light_needed = not lights_are_on and self.statemachine.is_state(STATE_CATEGORY_SUN, SUN_STATE_BELOW_HORIZON)

        # Specific device came home ?
        if category != STATE_CATEGORY_ALL_DEVICES and new_state.state == STATE_DEVICE_HOME and light_needed:
            self.logger.info("Home coming event for {}. Turning lights on".format(category))
            self.light_control.turn_light_on()

        # Did all devices leave the house?
        elif category == STATE_CATEGORY_ALL_DEVICES and new_state.state == STATE_DEVICE_NOT_HOME and lights_are_on:
            self.logger.info("Everyone has left but lights are on. Turning lights off")
            self.light_control.turn_light_off()
