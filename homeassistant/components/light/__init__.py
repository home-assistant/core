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

from homeassistant.loader import get_component
import homeassistant.util as util
from homeassistant.const import (
    STATE_ON, SERVICE_TURN_ON, SERVICE_TURN_OFF, ATTR_ENTITY_ID)
from homeassistant.helpers import (
    generate_entity_id, extract_entity_ids, config_per_platform)
from homeassistant.components import group, discovery, wink


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

# If the light should flash, can be FLASH_SHORT or FLASH_LONG
ATTR_FLASH = "flash"
FLASH_SHORT = "short"
FLASH_LONG = "long"

LIGHT_PROFILES_FILE = "light_profiles.csv"

# Maps discovered services to their platforms
DISCOVERY_PLATFORMS = {
    wink.DISCOVER_LIGHTS: 'wink',
    discovery.services.PHILIPS_HUE: 'hue',
}

_LOGGER = logging.getLogger(__name__)


def is_on(hass, entity_id=None):
    """ Returns if the lights are on based on the statemachine. """
    entity_id = entity_id or ENTITY_ID_ALL_LIGHTS

    return hass.states.is_state(entity_id, STATE_ON)


# pylint: disable=too-many-arguments
def turn_on(hass, entity_id=None, transition=None, brightness=None,
            rgb_color=None, xy_color=None, profile=None, flash=None):
    """ Turns all or specified light on. """
    data = {
        key: value for key, value in [
            (ATTR_ENTITY_ID, entity_id),
            (ATTR_PROFILE, profile),
            (ATTR_TRANSITION, transition),
            (ATTR_BRIGHTNESS, brightness),
            (ATTR_RGB_COLOR, rgb_color),
            (ATTR_XY_COLOR, xy_color),
            (ATTR_FLASH, flash),
        ] if value is not None
    }

    hass.services.call(DOMAIN, SERVICE_TURN_ON, data)


def turn_off(hass, entity_id=None, transition=None):
    """ Turns all or specified light off. """
    data = {
        key: value for key, value in [
            (ATTR_ENTITY_ID, entity_id),
            (ATTR_TRANSITION, transition),
        ] if value is not None
    }

    hass.services.call(DOMAIN, SERVICE_TURN_OFF, data)


# pylint: disable=too-many-branches, too-many-locals
def setup(hass, config):
    """ Exposes light control via statemachine and services. """

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

    # Dict to track entity_id -> lights
    lights = {}

    # Track all lights in a group
    light_group = group.Group(hass, GROUP_NAME_ALL_LIGHTS, user_defined=False)

    def add_lights(new_lights):
        """ Add lights to the component to track. """
        for light in new_lights:
            if light is not None and light not in lights.values():
                light.entity_id = generate_entity_id(
                    ENTITY_ID_FORMAT, light.name, lights.keys())

                lights[light.entity_id] = light

                light.update_ha_state(hass)

        light_group.update_tracked_entity_ids(lights.keys())

    for p_type, p_config in config_per_platform(config, DOMAIN, _LOGGER):
        platform = get_component(ENTITY_ID_FORMAT.format(p_type))

        if platform is None:
            _LOGGER.error("Unknown type specified: %s", p_type)

        platform.setup_platform(hass, p_config, add_lights)

    # pylint: disable=unused-argument
    def update_lights_state(now):
        """ Update the states of all the lights. """
        if lights:
            _LOGGER.info("Updating light states")

            for light in lights.values():
                light.update_ha_state(hass, True)

    update_lights_state(None)

    def light_discovered(service, info):
        """ Called when a light is discovered. """
        platform = get_component(
            ENTITY_ID_FORMAT.format(DISCOVERY_PLATFORMS[service]))

        platform.setup_platform(hass, {}, add_lights, info)

    discovery.listen(hass, DISCOVERY_PLATFORMS.keys(), light_discovered)

    def handle_light_service(service):
        """ Hande a turn light on or off service call. """
        # Get and validate data
        dat = service.data

        # Convert the entity ids to valid light ids
        target_lights = [lights[entity_id] for entity_id
                         in extract_entity_ids(hass, service)
                         if entity_id in lights]

        if not target_lights:
            target_lights = lights.values()

        params = {}

        transition = util.convert(dat.get(ATTR_TRANSITION), int)

        if transition is not None:
            params[ATTR_TRANSITION] = transition

        if service.service == SERVICE_TURN_OFF:
            for light in target_lights:
                # pylint: disable=star-args
                light.turn_off(**params)

        else:
            # Processing extra data for turn light on request

            # We process the profile first so that we get the desired
            # behavior that extra service data attributes overwrite
            # profile values
            profile = profiles.get(dat.get(ATTR_PROFILE))

            if profile:
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

            if ATTR_FLASH in dat:
                if dat[ATTR_FLASH] == FLASH_SHORT:
                    params[ATTR_FLASH] = FLASH_SHORT

                elif dat[ATTR_FLASH] == FLASH_LONG:
                    params[ATTR_FLASH] = FLASH_LONG

            for light in target_lights:
                # pylint: disable=star-args
                light.turn_on(**params)

        for light in target_lights:
            light.update_ha_state(hass, True)

    # Update light state every 30 seconds
    hass.track_time_change(update_lights_state, second=[0, 30])

    # Listen for light on and light off service calls
    hass.services.register(DOMAIN, SERVICE_TURN_ON,
                           handle_light_service)

    hass.services.register(DOMAIN, SERVICE_TURN_OFF,
                           handle_light_service)

    return True
