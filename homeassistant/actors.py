"""
homeassistant.actors
~~~~~~~~~~~~~~~~~~~~

This module provides actors that will react to events happening within homeassistant.

"""

import logging
from datetime import datetime, timedelta

import dateutil.parser
from phue import Bridge

from . import track_state_change

from .observers import (STATE_CATEGORY_SUN, SUN_STATE_BELOW_HORIZON, SUN_STATE_ABOVE_HORIZON,
                        STATE_CATEGORY_ALL_DEVICES, DEVICE_STATE_HOME, DEVICE_STATE_NOT_HOME,
                        STATE_CATEGORY_NEXT_SUN_SETTING, track_time_change)

LIGHT_TRANSITION_TIME = timedelta(minutes=15)

HUE_MAX_TRANSITION_TIME = 9000


def _hue_process_transition_time(transition_seconds):
    """ Transition time is in 1/10th seconds and cannot exceed MAX_TRANSITION_TIME. """
    return min(HUE_MAX_TRANSITION_TIME, transition_seconds * 10)


class LightTrigger(object):
    """ Class to turn on lights based on available devices and state of the sun. """

    def __init__(self, eventbus, statemachine, device_tracker, light_control):
        self.eventbus = eventbus
        self.statemachine = statemachine
        self.light_control = light_control

        self.logger = logging.getLogger(__name__)

        # Track home coming of each seperate device
        for category in device_tracker.device_state_categories():
            track_state_change(eventbus, category, DEVICE_STATE_NOT_HOME, DEVICE_STATE_HOME, self._handle_device_state_change)

        # Track when all devices are gone to shut down lights
        track_state_change(eventbus, STATE_CATEGORY_ALL_DEVICES, DEVICE_STATE_HOME, DEVICE_STATE_NOT_HOME, self._handle_device_state_change)

        # Track every time sun rises so we can schedule a time-based pre-sun set event
        track_state_change(eventbus, STATE_CATEGORY_SUN, SUN_STATE_BELOW_HORIZON, SUN_STATE_ABOVE_HORIZON, self._handle_sun_rising)

        # If the sun is already above horizon schedule the time-based pre-sun set event
        if statemachine.is_state(STATE_CATEGORY_SUN, SUN_STATE_ABOVE_HORIZON):
            self._handle_sun_rising(None, None, None)


    def _handle_sun_rising(self, category, old_state, new_state):
        """The moment sun sets we want to have all the lights on.
           We will schedule to have each light start after one another
           and slowly transition in."""

        start_point = self._start_point_turn_light_before_sun_set()

        def turn_on(light_id):
            """ Lambda can keep track of function parameters, not from local parameters
                If we put the lambda directly in the below statement only the last light
                would be turned on.. """
            return lambda now: self._turn_light_on_before_sunset(light_id)

        for index, light_id in enumerate(self.light_control.light_ids):
            track_time_change(self.eventbus, turn_on(light_id),
                              point_in_time=start_point + index * LIGHT_TRANSITION_TIME)


    def _turn_light_on_before_sunset(self, light_id=None):
        """ Helper function to turn on lights slowly if there are devices home and the light is not on yet. """
        if self.statemachine.is_state(STATE_CATEGORY_ALL_DEVICES, DEVICE_STATE_HOME) and not self.light_control.is_light_on(light_id):
            self.light_control.turn_light_on(light_id, LIGHT_TRANSITION_TIME.seconds)


    def _handle_device_state_change(self, category, old_state, new_state):
        """ Function to handle tracked device state changes. """
        lights_are_on = self.light_control.is_light_on()

        light_needed = not lights_are_on and self.statemachine.is_state(STATE_CATEGORY_SUN, SUN_STATE_BELOW_HORIZON)

        # Specific device came home ?
        if category != STATE_CATEGORY_ALL_DEVICES and new_state.state == DEVICE_STATE_HOME:
            # These variables are needed for the elif check
            now = datetime.now()
            start_point = self._start_point_turn_light_before_sun_set()

            # Do we need lights?
            if light_needed:
                self.logger.info("Home coming event for {}. Turning lights on".format(category))
                self.light_control.turn_light_on()

            # Are we in the time span were we would turn on the lights if someone would be home?
            # Check this by seeing if current time is later then the start point
            elif now > start_point and now < self._next_sun_setting():

                # If this is the case check for every light if it would be on
                # if someone was home when the fading in started and turn it on
                for index, light_id in enumerate(self.light_control.light_ids):

                    if now > start_point + index * LIGHT_TRANSITION_TIME:
                        self.light_control.turn_light_on(light_id)

                    else:
                        # If this one was not the case then the following IFs are not True
                        # as their points are even further in time, break
                        break


        # Did all devices leave the house?
        elif category == STATE_CATEGORY_ALL_DEVICES and new_state.state == DEVICE_STATE_NOT_HOME and lights_are_on:
            self.logger.info("Everyone has left but lights are on. Turning lights off")
            self.light_control.turn_light_off()

    def _next_sun_setting(self):
        """ Returns the datetime object representing the next sun setting. """
        return dateutil.parser.parse(self.statemachine.get_state(STATE_CATEGORY_NEXT_SUN_SETTING).state)

    def _start_point_turn_light_before_sun_set(self):
        """ Helper method to calculate the point in time we have to start fading in lights
            so that all the lights are on the moment the sun sets. """
        return self._next_sun_setting() - LIGHT_TRANSITION_TIME * len(self.light_control.light_ids)


class HueLightControl(object):
    """ Class to interface with the Hue light system. """

    def __init__(self, host=None):
        self.bridge = Bridge(host)
        self.lights = self.bridge.get_light_objects()
        self.light_ids = [light.light_id for light in self.lights]


    def is_light_on(self, light_id=None):
        """ Returns if specified or all light are on. """
        if light_id is None:
            return sum([1 for light in self.lights if light.on]) > 0

        else:
            return self.bridge.get_light(light_id, 'on')


    def turn_light_on(self, light_id=None, transition_seconds=None):
        """ Turn the specified or all lights on. """
        if light_id is None:
            light_id = self.light_ids

        command = {'on': True, 'xy': [0.5119, 0.4147], 'bri':164}

        if transition_seconds is not None:
            command['transitiontime'] = _hue_process_transition_time(transition_seconds)

        self.bridge.set_light(light_id, command)


    def turn_light_off(self, light_id=None, transition_seconds=None):
        """ Turn the specified or all lights off. """
        if light_id is None:
            light_id = self.light_ids

        command = {'on': False}

        if transition_seconds is not None:
            command['transitiontime'] = _hue_process_transition_time(transition_seconds)

        self.bridge.set_light(light_id, command)
