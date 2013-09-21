import logging
from datetime import timedelta

from phue import Bridge

from app.observer.WeatherWatcher import STATE_CATEGORY_SUN, SUN_STATE_BELOW_HORIZON, SUN_STATE_ABOVE_HORIZON
from app.StateMachine import track_state_change
from app.DeviceTracker import STATE_CATEGORY_ALL_DEVICES, STATE_DEVICE_HOME, STATE_DEVICE_NOT_HOME
from app.observer.Timer import track_time_change

LIGHTS_TURNING_ON_BEFORE_SUN_SET_PERIOD = timedelta(minutes=15)

LIGHT_TRANSITION_TIME_HUE = 9000 # 1/10th seconds
LIGHT_TRANSITION_TIME = timedelta(seconds=LIGHT_TRANSITION_TIME_HUE/10)

class HueTrigger(object):
    def __init__(self, config, eventbus, statemachine, device_tracker, weather):
        self.eventbus = eventbus
        self.statemachine = statemachine
        self.weather = weather

        self.bridge = Bridge(config.get("hue","host"))
        self.lights = self.bridge.get_light_objects()
        self.logger = logging.getLogger("HueTrigger")

        # Track home coming of each seperate device
        for category in device_tracker.device_state_categories():
            track_state_change(eventbus, category, STATE_DEVICE_NOT_HOME, STATE_DEVICE_HOME, self.handle_device_state_change)

        # Track when all devices are gone to shut down lights
        track_state_change(eventbus, STATE_CATEGORY_ALL_DEVICES, STATE_DEVICE_HOME, STATE_DEVICE_NOT_HOME, self.handle_device_state_change)

        # Track every time sun rises so we can schedule a time-based pre-sun set event
        track_state_change(eventbus, STATE_CATEGORY_SUN, SUN_STATE_BELOW_HORIZON, SUN_STATE_ABOVE_HORIZON, self.handle_sun_rising)

        # If the sun is already above horizon schedule the time-based pre-sun set event
        if statemachine.is_state(STATE_CATEGORY_SUN, SUN_STATE_ABOVE_HORIZON):
            self.handle_sun_rising(None, None, None)


    def get_lights_status(self):
        lights_are_on = sum([1 for light in self.lights if light.on]) > 0

        light_needed = not lights_are_on and self.statemachine.is_state(STATE_CATEGORY_SUN, SUN_STATE_BELOW_HORIZON)

        return lights_are_on, light_needed

    def turn_light_on(self, light_id=None, transitiontime=None):
        if light_id is None:
            light_id = [light.light_id for light in self.lights]

        command = {'on': True, 'xy': [0.5119, 0.4147], 'bri':164}

        if transitiontime is not None:
            command['transitiontime'] = transitiontime

        self.bridge.set_light(light_id, command)


    def turn_light_off(self, light_id=None, transitiontime=None):
        if light_id is None:
            light_id = [light.light_id for light in self.lights]

        command = {'on': False}

        if transitiontime is not None:
            command['transitiontime'] = transitiontime

        self.bridge.set_light(light_id, command)


    def handle_sun_rising(self, category, old_state, new_state):
        """The moment sun sets we want to have all the lights on.
           We will schedule to have each light start after one another
           and slowly transition in."""

        start_point = self.weather.next_sun_setting() - LIGHT_TRANSITION_TIME * len(self.lights)

        # Lambda can keep track of function parameters, not from local parameters
        # If we put the lambda directly in the below statement only the last light
        # would be turned on..
        def turn_on(light_id):
            return lambda now: self.turn_light_on_before_sunset(light_id)

        for index, light in enumerate(self.lights):
            track_time_change(self.eventbus, turn_on(light.light_id),
                              point_in_time=start_point + index * LIGHT_TRANSITION_TIME)


    def turn_light_on_before_sunset(self, light_id=None):
        """Helper function to turn on lights slowly if there are devices home and the light is not on yet."""
        if self.statemachine.is_state(STATE_CATEGORY_ALL_DEVICES, STATE_DEVICE_HOME) and not self.bridge.get_light(light_id, 'on'):
            self.turn_light_on(light_id, LIGHT_TRANSITION_TIME_HUE)


    def handle_device_state_change(self, category, old_state, new_state):
        lights_are_on, light_needed = self.get_lights_status()

        # Specific device came home ?
        if category != STATE_CATEGORY_ALL_DEVICES and new_state.state == STATE_DEVICE_HOME and light_needed:
            self.logger.info("Home coming event for {}. Turning lights on".format(category))
            self.turn_light_on()

        # Did all devices leave the house?
        elif category == STATE_CATEGORY_ALL_DEVICES and new_state.state == STATE_DEVICE_NOT_HOME and lights_are_on:
            self.logger.info("Everyone has left. Turning lights off")
            self.turn_light_off()
