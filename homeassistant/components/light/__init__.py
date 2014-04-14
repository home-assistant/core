"""
homeassistant.components.light
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Provides functionality to interact with lights.

It offers the following services:

TURN_OFF - Turns one or multiple lights off.

Supports following parameters:
 - transition
   Integer that represents the time the light should take to transition to
   the new state.
 - entity_id
   String or list of strings that point at entity_ids of lights.

TURN_ON - Turns one or multiple lights on and change attributes.

Supports following parameters:
 - transition
   Integer that represents the time the light should take to transition to
   the new state.

 - entity_id
   String or list of strings that point at entity_ids of lights.

 - profile
   String with the name of one of the built-in profiles (relax, energize,
   concentrate, reading) or one of the custom profiles defined in
   light_profiles.csv in the current working directory.

   Light profiles define a xy color and a brightness.

   If a profile is given and a brightness or xy color then the profile values
   will be overwritten.

 - xy_color
   A list containing two floats representing the xy color you want the light
   to be.

 - rgb_color
   A list containing three integers representing the xy color you want the
   light to be.

 - brightness
   Integer between 0 and 255 representing how bright you want the light to be.

"""

import logging
import socket
from datetime import datetime, timedelta
from collections import namedtuple
import os
import csv

import homeassistant as ha
import homeassistant.util as util
from homeassistant.components import (group, extract_entity_ids,
                                      STATE_ON, STATE_OFF,
                                      SERVICE_TURN_ON, SERVICE_TURN_OFF,
                                      ATTR_ENTITY_ID, ATTR_FRIENDLY_NAME)


DOMAIN = "light"

GROUP_NAME_ALL_LIGHTS = 'all_lights'
ENTITY_ID_ALL_LIGHTS = group.ENTITY_ID_FORMAT.format(
    GROUP_NAME_ALL_LIGHTS)

ENTITY_ID_FORMAT = DOMAIN + ".{}"

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)

# integer that represents transition time in seconds to make change
ATTR_TRANSITION = "transition"

# lists holding color values
ATTR_RGB_COLOR = "rgb_color"
ATTR_XY_COLOR = "xy_color"

# int with value 0 .. 255 representing brightness of the light
ATTR_BRIGHTNESS = "brightness"

# String representing a profile (built-in ones or external defined)
ATTR_PROFILE = "profile"

LIGHT_PROFILES_FILE = "light_profiles.csv"


def is_on(statemachine, entity_id=None):
    """ Returns if the lights are on based on the statemachine. """
    entity_id = entity_id or ENTITY_ID_ALL_LIGHTS

    return statemachine.is_state(entity_id, STATE_ON)


# pylint: disable=too-many-arguments
def turn_on(bus, entity_id=None, transition=None, brightness=None,
            rgb_color=None, xy_color=None, profile=None):
    """ Turns all or specified light on. """
    data = {}

    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    if profile:
        data[ATTR_PROFILE] = profile

    if transition is not None:
        data[ATTR_TRANSITION] = transition

    if brightness is not None:
        data[ATTR_BRIGHTNESS] = brightness

    if rgb_color:
        data[ATTR_RGB_COLOR] = rgb_color

    if xy_color:
        data[ATTR_XY_COLOR] = xy_color

    bus.call_service(DOMAIN, SERVICE_TURN_ON, data)


def turn_off(bus, entity_id=None, transition=None):
    """ Turns all or specified light off. """
    data = {}

    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    if transition is not None:
        data[ATTR_TRANSITION] = transition

    bus.call_service(DOMAIN, SERVICE_TURN_OFF, data)


# pylint: disable=too-many-branches, too-many-locals
def setup(bus, statemachine, light_control):
    """ Exposes light control via statemachine and services. """

    logger = logging.getLogger(__name__)

    ent_to_light = {}
    light_to_ent = {}

    def _update_light_state(light_id, light_state):
        """ Update statemachine based on the LightState passed in. """
        name = light_control.get_name(light_id) or "Unknown Light"

        try:
            entity_id = light_to_ent[light_id]
        except KeyError:
            # We have not seen this light before, set it up

            # Create entity id
            logger.info("Found new light {}".format(name))

            entity_id = util.ensure_unique_string(
                ENTITY_ID_FORMAT.format(util.slugify(name)),
                list(ent_to_light.keys()))

            ent_to_light[entity_id] = light_id
            light_to_ent[light_id] = entity_id

        state_attr = {ATTR_FRIENDLY_NAME: name}

        if light_state.on:
            state = STATE_ON

            if light_state.brightness:
                state_attr[ATTR_BRIGHTNESS] = light_state.brightness

            if light_state.color:
                state_attr[ATTR_XY_COLOR] = light_state.color

        else:
            state = STATE_OFF

        statemachine.set_state(entity_id, state, state_attr)

    def update_light_state(light_id):
        """ Update the state of specified light. """
        _update_light_state(light_id, light_control.get_state(light_id))

    # pylint: disable=unused-argument
    def update_lights_state(time, force_reload=False):
        """ Update the state of all the lights. """

        # First time this method gets called, force_reload should be True
        if (force_reload or
           datetime.now() - update_lights_state.last_updated >
           MIN_TIME_BETWEEN_SCANS):

            logger.info("Updating light status")
            update_lights_state.last_updated = datetime.now()

            for light_id, light_state in light_control.get_states().items():
                _update_light_state(light_id, light_state)

    # Update light state and discover lights for tracking the group
    update_lights_state(None, True)

    if len(ent_to_light) == 0:
        logger.error("No lights found")
        return False

    # Track all lights in a group
    group.setup(bus, statemachine,
                GROUP_NAME_ALL_LIGHTS, light_to_ent.values())

    # Load built-in profiles and custom profiles
    profile_paths = [os.path.dirname(__file__), os.getcwd()]
    profiles = {}

    for dir_path in profile_paths:
        file_path = os.path.join(dir_path, LIGHT_PROFILES_FILE)

        if os.path.isfile(file_path):
            with open(file_path) as inp:
                reader = csv.reader(inp)

                # Skip the header
                next(reader, None)

                try:
                    for profile_id, color_x, color_y, brightness in reader:
                        profiles[profile_id] = (float(color_x), float(color_y),
                                                int(brightness))

                except ValueError:
                    # ValueError if not 4 values per row
                    # ValueError if convert to float/int failed
                    logger.error(
                        "Error parsing light profiles from {}".format(
                            file_path))

                    return False

    def handle_light_service(service):
        """ Hande a turn light on or off service call. """
        # Get and validate data
        dat = service.data

        # Convert the entity ids to valid light ids
        light_ids = [ent_to_light[entity_id] for entity_id
                     in extract_entity_ids(statemachine, service)
                     if entity_id in ent_to_light]

        if not light_ids:
            light_ids = list(ent_to_light.values())

        transition = util.convert(dat.get(ATTR_TRANSITION), int)

        if service.service == SERVICE_TURN_OFF:
            light_control.turn_light_off(light_ids, transition)

        else:
            # Processing extra data for turn light on request

            # We process the profile first so that we get the desired
            # behavior that extra service data attributes overwrite
            # profile values
            profile = profiles.get(dat.get(ATTR_PROFILE))

            if profile:
                color = profile[0:2]
                bright = profile[2]
            else:
                color = None
                bright = None

            if ATTR_BRIGHTNESS in dat:
                bright = util.convert(dat.get(ATTR_BRIGHTNESS), int)

            if ATTR_XY_COLOR in dat:
                try:
                    # xy_color should be a list containing 2 floats
                    xy_color = [float(val) for val in dat.get(ATTR_XY_COLOR)]

                    if len(xy_color) == 2:
                        color = xy_color

                except (TypeError, ValueError):
                    # TypeError if dat[ATTR_XY_COLOR] is not iterable
                    # ValueError if value could not be converted to float
                    pass

            if ATTR_RGB_COLOR in dat:
                try:
                    # rgb_color should be a list containing 3 ints
                    rgb_color = [int(val) for val in dat.get(ATTR_RGB_COLOR)]

                    if len(rgb_color) == 3:
                        color = util.color_RGB_to_xy(rgb_color[0],
                                                     rgb_color[1],
                                                     rgb_color[2])

                except (TypeError, ValueError):
                    # TypeError if dat[ATTR_RGB_COLOR] is not iterable
                    # ValueError if not all values can be converted to int
                    pass

            light_control.turn_light_on(light_ids, transition, bright, color)

        # Update state of lights touched. If there was only 1 light selected
        # then just update that light else update all
        if len(light_ids) == 1:
            update_light_state(light_ids[0])
        else:
            update_lights_state(None, True)

    # Update light state every 30 seconds
    ha.track_time_change(bus, update_lights_state, second=[0, 30])

    # Listen for light on and light off service calls
    bus.register_service(DOMAIN, SERVICE_TURN_ON,
                         handle_light_service)

    bus.register_service(DOMAIN, SERVICE_TURN_OFF,
                         handle_light_service)

    return True


LightState = namedtuple("LightState", ['on', 'brightness', 'color'])


def _hue_to_light_state(info):
    """ Helper method to convert a Hue state to a LightState. """
    try:
        return LightState(info['state']['reachable'] and info['state']['on'],
                          info['state']['bri'], info['state']['xy'])
    except KeyError:
        # KeyError if one of the keys didn't exist
        return None


class HueLightControl(object):
    """ Class to interface with the Hue light system. """

    def __init__(self, host=None):
        logger = logging.getLogger(__name__)

        try:
            import phue
        except ImportError:
            logger.exception(
                "HueLightControl:Error while importing dependency phue.")

            self.success_init = False

            return

        try:
            self._bridge = phue.Bridge(host)
        except socket.error:  # Error connecting using Phue
            logger.exception((
                "HueLightControl:Error while connecting to the bridge. "
                "Is phue registered?"))

            self.success_init = False

            return

        # Dict mapping light_id to name
        self._lights = {}
        self._update_lights()

        if len(self._lights) == 0:
            logger.error("HueLightControl:Could not find any lights. ")

            self.success_init = False
        else:
            self.success_init = True

    def _update_lights(self):
        """ Helper method to update the known names from Hue. """
        try:
            self._lights = {int(item[0]): item[1]['name'] for item
                            in self._bridge.get_light().items()}

        except (socket.error, KeyError):
            # socket.error because sometimes we cannot reach Hue
            # KeyError if we got unexpected data
            # We don't do anything, keep old values
            pass

    def get_name(self, light_id):
        """ Return name for specified light_id or None if no name known. """
        if not light_id in self._lights:
            self._update_lights()

        return self._lights.get(light_id)

    def get_state(self, light_id):
        """ Return a LightState representing light light_id. """
        try:
            info = self._bridge.get_light(light_id)

            return _hue_to_light_state(info)

        except socket.error:
            # socket.error when we cannot reach Hue
            return None

    def get_states(self):
        """ Return a dict with id mapped to LightState objects. """
        states = {}

        try:
            api = self._bridge.get_api()

        except socket.error:
            # socket.error when we cannot reach Hue
            return states

        api_states = api.get('lights')

        if not isinstance(api_states, dict):
            return states

        for light_id, info in api_states.items():
            state = _hue_to_light_state(info)

            if state:
                states[int(light_id)] = state

        return states

    def turn_light_on(self, light_ids, transition, brightness, xy_color):
        """ Turn the specified or all lights on. """
        command = {'on': True}

        if transition is not None:
            # Transition time is in 1/10th seconds and cannot exceed
            # 900 seconds.
            command['transitiontime'] = min(9000, transition * 10)

        if brightness is not None:
            command['bri'] = brightness

        if xy_color:
            command['xy'] = xy_color

        self._bridge.set_light(light_ids, command)

    def turn_light_off(self, light_ids, transition):
        """ Turn the specified or all lights off. """
        command = {'on': False}

        if transition is not None:
            # Transition time is in 1/10th seconds and cannot exceed
            # 900 seconds.
            command['transitiontime'] = min(9000, transition * 10)

        self._bridge.set_light(light_ids, command)
