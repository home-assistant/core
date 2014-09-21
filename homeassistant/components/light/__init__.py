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
DEPENDENCIES = []

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

PHUE_CONFIG_FILE = "phue.conf"
LIGHT_PROFILES_FILE = "light_profiles.csv"


def is_on(hass, entity_id=None):
    """ Returns if the lights are on based on the statemachine. """
    entity_id = entity_id or ENTITY_ID_ALL_LIGHTS

    return hass.states.is_state(entity_id, STATE_ON)


# pylint: disable=too-many-arguments
def turn_on(hass, entity_id=None, transition=None, brightness=None,
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

    hass.call_service(DOMAIN, SERVICE_TURN_ON, data)


def turn_off(hass, entity_id=None, transition=None):
    """ Turns all or specified light off. """
    data = {}

    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    if transition is not None:
        data[ATTR_TRANSITION] = transition

    hass.call_service(DOMAIN, SERVICE_TURN_OFF, data)


# pylint: disable=too-many-branches, too-many-locals
def setup(hass, config):
    """ Exposes light control via statemachine and services. """

    logger = logging.getLogger(__name__)

    if not util.validate_config(config, {DOMAIN: [ha.CONF_TYPE]}, logger):
        return False

    light_type = config[DOMAIN][ha.CONF_TYPE]

    if light_type == 'hue':
        light_init = HueLightControl

    else:
        logger.error("Found unknown light type: {}".format(light_type))

        return False

    light_control = light_init(hass, config[DOMAIN])

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

        hass.states.set(entity_id, state, state_attr)

    def update_light_state(light_id):
        """ Update the state of specified light. """
        _update_light_state(light_id, light_control.get(light_id))

    # pylint: disable=unused-argument
    def update_lights_state(time, force_reload=False):
        """ Update the state of all the lights. """

        # First time this method gets called, force_reload should be True
        if force_reload or \
           datetime.now() - update_lights_state.last_updated > \
           MIN_TIME_BETWEEN_SCANS:

            logger.info("Updating light status")
            update_lights_state.last_updated = datetime.now()

            for light_id, light_state in light_control.gets().items():
                _update_light_state(light_id, light_state)

    # Update light state and discover lights for tracking the group
    update_lights_state(None, True)

    if len(ent_to_light) == 0:
        logger.error("No lights found")
        return False

    # Track all lights in a group
    group.setup_group(hass, GROUP_NAME_ALL_LIGHTS, light_to_ent.values())

    # Load built-in profiles and custom profiles
    profile_paths = [os.path.join(os.path.dirname(__file__),
                                  LIGHT_PROFILES_FILE),
                     hass.get_config_path(LIGHT_PROFILES_FILE)]
    profiles = {}

    for profile_path in profile_paths:

        if os.path.isfile(profile_path):
            with open(profile_path) as inp:
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
                            profile_path))

                    return False

    def handle_light_service(service):
        """ Hande a turn light on or off service call. """
        # Get and validate data
        dat = service.data

        # Convert the entity ids to valid light ids
        light_ids = [ent_to_light[entity_id] for entity_id
                     in extract_entity_ids(hass, service)
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
                *color, bright = profile
            else:
                color, bright = None, None

            if ATTR_BRIGHTNESS in dat:
                bright = util.convert(dat.get(ATTR_BRIGHTNESS), int)

            if ATTR_XY_COLOR in dat:
                try:
                    # xy_color should be a list containing 2 floats
                    xy_color = dat.get(ATTR_XY_COLOR)

                    if len(xy_color) == 2:
                        color = [float(val) for val in xy_color]

                except (TypeError, ValueError):
                    # TypeError if xy_color is not iterable
                    # ValueError if value could not be converted to float
                    pass

            if ATTR_RGB_COLOR in dat:
                try:
                    # rgb_color should be a list containing 3 ints
                    rgb_color = dat.get(ATTR_RGB_COLOR)

                    if len(rgb_color) == 3:
                        color = util.color_RGB_to_xy(int(rgb_color[0]),
                                                     int(rgb_color[1]),
                                                     int(rgb_color[2]))

                except (TypeError, ValueError):
                    # TypeError if rgb_color is not iterable
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
    hass.track_time_change(update_lights_state, second=[0, 30])

    # Listen for light on and light off service calls
    hass.services.register(DOMAIN, SERVICE_TURN_ON,
                           handle_light_service)

    hass.services.register(DOMAIN, SERVICE_TURN_OFF,
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

    def __init__(self, hass, config):
        logger = logging.getLogger(__name__)

        host = config.get(ha.CONF_HOST, None)

        try:
            import phue
        except ImportError:
            logger.exception(
                "HueLightControl:Error while importing dependency phue.")

            self.success_init = False

            return

        try:
            self._bridge = phue.Bridge(host,
                                       config_file_path=hass.get_config_path(
                                           PHUE_CONFIG_FILE))
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

    def get(self, light_id):
        """ Return a LightState representing light light_id. """
        try:
            info = self._bridge.get_light(light_id)

            return _hue_to_light_state(info)

        except socket.error:
            # socket.error when we cannot reach Hue
            return None

    def gets(self):
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
