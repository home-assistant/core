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
import os
import csv

import homeassistant as ha
from homeassistant.loader import get_component
import homeassistant.util as util
from homeassistant.components import (
    group, extract_entity_ids, STATE_ON,
    SERVICE_TURN_ON, SERVICE_TURN_OFF, ATTR_ENTITY_ID)


DOMAIN = "light"
DEPENDENCIES = []

GROUP_NAME_ALL_LIGHTS = 'all_lights'
ENTITY_ID_ALL_LIGHTS = group.ENTITY_ID_FORMAT.format(
    GROUP_NAME_ALL_LIGHTS)

ENTITY_ID_FORMAT = DOMAIN + ".{}"

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

_LOGGER = logging.getLogger(__name__)


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

    hass.services.call(DOMAIN, SERVICE_TURN_ON, data)


def turn_off(hass, entity_id=None, transition=None):
    """ Turns all or specified light off. """
    data = {}

    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    if transition is not None:
        data[ATTR_TRANSITION] = transition

    hass.services.call(DOMAIN, SERVICE_TURN_OFF, data)


# pylint: disable=too-many-branches, too-many-locals
def setup(hass, config):
    """ Exposes light control via statemachine and services. """

    if not util.validate_config(config, {DOMAIN: [ha.CONF_TYPE]}, _LOGGER):
        return False

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
                    _LOGGER.error(
                        "Error parsing light profiles from %s", profile_path)

                    return False

    # Load platform
    light_type = config[DOMAIN][ha.CONF_TYPE]

    light_init = get_component('light.{}'.format(light_type))

    if light_init is None:
        _LOGGER.error("Unknown light type specified: %s", light_type)

        return False

    lights = light_init.get_lights(hass, config[DOMAIN])

    if len(lights) == 0:
        _LOGGER.error("No lights found")
        return False

    ent_to_light = {}

    no_name_count = 1

    for light in lights:
        name = light.get_name()

        if name is None:
            name = "Light #{}".format(no_name_count)
            no_name_count += 1

        entity_id = util.ensure_unique_string(
            ENTITY_ID_FORMAT.format(util.slugify(name)),
            list(ent_to_light.keys()))

        light.entity_id = entity_id
        ent_to_light[entity_id] = light

    # pylint: disable=unused-argument
    def update_lights_state(now):
        """ Update the states of all the lights. """
        for light in lights:
            light.update_ha_state(hass)

    update_lights_state(None)

    # Track all lights in a group
    group.setup_group(
        hass, GROUP_NAME_ALL_LIGHTS, ent_to_light.keys(), False)

    def handle_light_service(service):
        """ Hande a turn light on or off service call. """
        # Get and validate data
        dat = service.data

        # Convert the entity ids to valid light ids
        lights = [ent_to_light[entity_id] for entity_id
                  in extract_entity_ids(hass, service)
                  if entity_id in ent_to_light]

        if not lights:
            lights = list(ent_to_light.values())

        params = {}

        transition = util.convert(dat.get(ATTR_TRANSITION), int)

        if transition is not None:
            params[ATTR_TRANSITION] = transition

        if service.service == SERVICE_TURN_OFF:
            for light in lights:
                # pylint: disable=star-args
                light.turn_off(**params)

        else:
            # Processing extra data for turn light on request

            # We process the profile first so that we get the desired
            # behavior that extra service data attributes overwrite
            # profile values
            profile = profiles.get(dat.get(ATTR_PROFILE))

            if profile:
                # *color, bright = profile
                *params[ATTR_XY_COLOR], params[ATTR_BRIGHTNESS] = profile

            if ATTR_BRIGHTNESS in dat:
                # We pass in the old value as the default parameter if parsing
                # of the new one goes wrong.
                params[ATTR_BRIGHTNESS] = util.convert(
                    dat.get(ATTR_BRIGHTNESS), int, params.get(ATTR_BRIGHTNESS))

            if ATTR_XY_COLOR in dat:
                try:
                    # xy_color should be a list containing 2 floats
                    xycolor = dat.get(ATTR_XY_COLOR)

                    # Without this check, a xycolor with value '99' would work
                    if not isinstance(xycolor, str):
                        params[ATTR_XY_COLOR] = [float(val) for val in xycolor]

                except (TypeError, ValueError):
                    # TypeError if xy_color is not iterable
                    # ValueError if value could not be converted to float
                    pass

            if ATTR_RGB_COLOR in dat:
                try:
                    # rgb_color should be a list containing 3 ints
                    rgb_color = dat.get(ATTR_RGB_COLOR)

                    if len(rgb_color) == 3:
                        params[ATTR_XY_COLOR] = \
                            util.color_RGB_to_xy(int(rgb_color[0]),
                                                 int(rgb_color[1]),
                                                 int(rgb_color[2]))

                except (TypeError, ValueError):
                    # TypeError if rgb_color is not iterable
                    # ValueError if not all values can be converted to int
                    pass

            for light in lights:
                # pylint: disable=star-args
                light.turn_on(**params)

        for light in lights:
            light.update_ha_state(hass, True)

    # Update light state every 30 seconds
    hass.track_time_change(update_lights_state, second=[0, 30])

    # Listen for light on and light off service calls
    hass.services.register(DOMAIN, SERVICE_TURN_ON,
                           handle_light_service)

    hass.services.register(DOMAIN, SERVICE_TURN_OFF,
                           handle_light_service)

    return True
