import logging
from datetime import datetime, timedelta

from phue import Bridge

from app.observer.WeatherWatcher import STATE_CATEGORY_SUN, SUN_STATE_BELOW_HORIZON, SUN_STATE_ABOVE_HORIZON
from app.StateMachine import track_state_change
from app.DeviceTracker import STATE_CATEGORY_ALL_DEVICES, STATE_DEVICE_HOME, STATE_DEVICE_NOT_HOME
from app.observer.Timer import track_time_change

LIGHTS_TURNING_ON_BEFORE_SUN_SET_PERIOD = timedelta(minutes=30)

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
        if statemachine.get_state(STATE_CATEGORY_SUN) == SUN_STATE_ABOVE_HORIZON:
            self.handle_sun_rising(None, None, None)


    def get_lights_status(self):
        lights_are_on = sum([1 for light in self.lights if light.on]) > 0

        light_needed = not lights_are_on and self.statemachine.get_state(STATE_CATEGORY_SUN).state == SUN_STATE_BELOW_HORIZON

        return lights_are_on, light_needed


    def turn_lights_on(self, transitiontime=None):
        command = {'on': True, 'xy': [0.5119, 0.4147], 'bri':164}

        if transitiontime is not None:
            command['transitiontime'] = transitiontime

        self.bridge.set_light([1, 2, 3], command)


    def turn_lights_off(self, transitiontime=None):
        command = {'on': False}

        if transitiontime is not None:
            command['transitiontime'] = transitiontime

        self.bridge.set_light([1, 2, 3], command)


    def handle_sun_rising(self, category, old_state, new_state):
        # Schedule an event X minutes prior to sun setting
        track_time_change(self.eventbus, self.handle_sun_setting, point_in_time=self.weather.next_sun_setting()-LIGHTS_TURNING_ON_BEFORE_SUN_SET_PERIOD)


    # Gets called when darkness starts falling in, slowly turn on the lights
    def handle_sun_setting(self, now):
        lights_are_on, light_needed = self.get_lights_status()

        if not lights_are_on and self.statemachine.get_state(STATE_CATEGORY_ALL_DEVICES).state == STATE_DEVICE_HOME:
            self.logger.info("Sun setting and devices home. Turning on lights.")

            # We will start the lights now and by the time the sun sets
            # the lights will be at full brightness
            transitiontime = (self.weather.next_sun_setting() - datetime.now()).seconds * 10

            self.turn_lights_on(transitiontime)


    def handle_device_state_change(self, category, old_state, new_state):
        lights_are_on, light_needed = self.get_lights_status()

        # Specific device came home ?
        if category != STATE_CATEGORY_ALL_DEVICES and new_state.state == STATE_DEVICE_HOME and light_needed:
            self.logger.info("Home coming event for {}. Turning lights on".format(category))
            self.turn_lights_on()

        # Did all devices leave the house?
        elif category == STATE_CATEGORY_ALL_DEVICES and new_state.state == STATE_DEVICE_NOT_HOME and lights_are_on:
            self.logger.info("Everyone has left. Turning lights off")
            self.turn_lights_off()
