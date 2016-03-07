"""
Provides functionality to interact with lights.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/light/
"""
import logging
import os
import csv

from homeassistant.components import (
    group, discovery, wemo, wink, isy994, zwave, insteon_hub, mysensors)
from homeassistant.config import load_yaml_config_file
from homeassistant.const import (
    STATE_ON, SERVICE_TURN_ON, SERVICE_TURN_OFF, SERVICE_TOGGLE,
    ATTR_ENTITY_ID)
from homeassistant.helpers.entity import ToggleEntity
from homeassistant.helpers.entity_component import EntityComponent
import homeassistant.util as util
import homeassistant.util.color as color_util


DOMAIN = "light"
SCAN_INTERVAL = 30

GROUP_NAME_ALL_LIGHTS = 'all lights'
ENTITY_ID_ALL_LIGHTS = group.ENTITY_ID_FORMAT.format('all_lights')

ENTITY_ID_FORMAT = DOMAIN + ".{}"

# Integer that represents transition time in seconds to make change.
ATTR_TRANSITION = "transition"

# Lists holding color values
ATTR_RGB_COLOR = "rgb_color"
ATTR_XY_COLOR = "xy_color"
ATTR_COLOR_TEMP = "color_temp"

# int with value 0 .. 255 representing brightness of the light.
ATTR_BRIGHTNESS = "brightness"

# String representing a profile (built-in ones or external defined).
ATTR_PROFILE = "profile"

# If the light should flash, can be FLASH_SHORT or FLASH_LONG.
ATTR_FLASH = "flash"
FLASH_SHORT = "short"
FLASH_LONG = "long"

# Apply an effect to the light, can be EFFECT_COLORLOOP.
ATTR_EFFECT = "effect"
EFFECT_COLORLOOP = "colorloop"
EFFECT_RANDOM = "random"
EFFECT_WHITE = "white"

LIGHT_PROFILES_FILE = "light_profiles.csv"

# Maps discovered services to their platforms.
DISCOVERY_PLATFORMS = {
    wemo.DISCOVER_LIGHTS: 'wemo',
    wink.DISCOVER_LIGHTS: 'wink',
    insteon_hub.DISCOVER_LIGHTS: 'insteon_hub',
    isy994.DISCOVER_LIGHTS: 'isy994',
    discovery.SERVICE_HUE: 'hue',
    zwave.DISCOVER_LIGHTS: 'zwave',
    mysensors.DISCOVER_LIGHTS: 'mysensors',
}

PROP_TO_ATTR = {
    'brightness': ATTR_BRIGHTNESS,
    'color_temp': ATTR_COLOR_TEMP,
    'rgb_color': ATTR_RGB_COLOR,
    'xy_color': ATTR_XY_COLOR,
}

_LOGGER = logging.getLogger(__name__)


def is_on(hass, entity_id=None):
    """Return if the lights are on based on the statemachine."""
    entity_id = entity_id or ENTITY_ID_ALL_LIGHTS
    return hass.states.is_state(entity_id, STATE_ON)


# pylint: disable=too-many-arguments
def turn_on(hass, entity_id=None, transition=None, brightness=None,
            rgb_color=None, xy_color=None, color_temp=None, profile=None,
            flash=None, effect=None):
    """Turn all or specified light on."""
    data = {
        key: value for key, value in [
            (ATTR_ENTITY_ID, entity_id),
            (ATTR_PROFILE, profile),
            (ATTR_TRANSITION, transition),
            (ATTR_BRIGHTNESS, brightness),
            (ATTR_RGB_COLOR, rgb_color),
            (ATTR_XY_COLOR, xy_color),
            (ATTR_COLOR_TEMP, color_temp),
            (ATTR_FLASH, flash),
            (ATTR_EFFECT, effect),
        ] if value is not None
    }

    hass.services.call(DOMAIN, SERVICE_TURN_ON, data)


def turn_off(hass, entity_id=None, transition=None):
    """Turn all or specified light off."""
    data = {
        key: value for key, value in [
            (ATTR_ENTITY_ID, entity_id),
            (ATTR_TRANSITION, transition),
        ] if value is not None
    }

    hass.services.call(DOMAIN, SERVICE_TURN_OFF, data)


def toggle(hass, entity_id=None, transition=None):
    """Toggle all or specified light."""
    data = {
        key: value for key, value in [
            (ATTR_ENTITY_ID, entity_id),
            (ATTR_TRANSITION, transition),
        ] if value is not None
    }

    hass.services.call(DOMAIN, SERVICE_TOGGLE, data)


# pylint: disable=too-many-branches, too-many-locals, too-many-statements
def setup(hass, config):
    """Expose light control via statemachine and services."""
    component = EntityComponent(
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL, DISCOVERY_PLATFORMS,
        GROUP_NAME_ALL_LIGHTS)
    component.setup(config)

    # Load built-in profiles and custom profiles
    profile_paths = [os.path.join(os.path.dirname(__file__),
                                  LIGHT_PROFILES_FILE),
                     hass.config.path(LIGHT_PROFILES_FILE)]
    profiles = {}

    for profile_path in profile_paths:
        if not os.path.isfile(profile_path):
            continue
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

    def handle_light_service(service):
        """Hande a turn light on or off service call."""
        # Get and validate data
        dat = service.data

        # Convert the entity ids to valid light ids
        target_lights = component.extract_from_service(service)

        params = {}

        transition = util.convert(dat.get(ATTR_TRANSITION), int)

        if transition is not None:
            params[ATTR_TRANSITION] = transition

        service_fun = None
        if service.service == SERVICE_TURN_OFF:
            service_fun = 'turn_off'
        elif service.service == SERVICE_TOGGLE:
            service_fun = 'toggle'

        if service_fun:
            for light in target_lights:
                getattr(light, service_fun)(**params)

            for light in target_lights:
                if light.should_poll:
                    light.update_ha_state(True)
            return

        # Processing extra data for turn light on request.

        # We process the profile first so that we get the desired
        # behavior that extra service data attributes overwrite
        # profile values.
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
                # xy_color should be a list containing 2 floats.
                xycolor = dat.get(ATTR_XY_COLOR)

                # Without this check, a xycolor with value '99' would work.
                if not isinstance(xycolor, str):
                    params[ATTR_XY_COLOR] = [float(val) for val in xycolor]

            except (TypeError, ValueError):
                # TypeError if xy_color is not iterable
                # ValueError if value could not be converted to float
                pass

        if ATTR_COLOR_TEMP in dat:
            # color_temp should be an int of mirads value
            colortemp = dat.get(ATTR_COLOR_TEMP)

            # Without this check, a ctcolor with value '99' would work
            # These values are based on Philips Hue, may need ajustment later
            if isinstance(colortemp, int) and 154 <= colortemp <= 500:
                params[ATTR_COLOR_TEMP] = colortemp

        if ATTR_RGB_COLOR in dat:
            try:
                # rgb_color should be a list containing 3 ints
                rgb_color = dat.get(ATTR_RGB_COLOR)

                if len(rgb_color) == 3:
                    params[ATTR_RGB_COLOR] = [int(val) for val in rgb_color]

            except (TypeError, ValueError):
                # TypeError if rgb_color is not iterable
                # ValueError if not all values can be converted to int
                pass

        if dat.get(ATTR_FLASH) in (FLASH_SHORT, FLASH_LONG):
            params[ATTR_FLASH] = dat[ATTR_FLASH]

        if dat.get(ATTR_EFFECT) in (EFFECT_COLORLOOP, EFFECT_WHITE,
                                    EFFECT_RANDOM):
            params[ATTR_EFFECT] = dat[ATTR_EFFECT]

        for light in target_lights:
            light.turn_on(**params)

        for light in target_lights:
            if light.should_poll:
                light.update_ha_state(True)

    # Listen for light on and light off service calls.
    descriptions = load_yaml_config_file(
        os.path.join(os.path.dirname(__file__), 'services.yaml'))
    hass.services.register(DOMAIN, SERVICE_TURN_ON, handle_light_service,
                           descriptions.get(SERVICE_TURN_ON))

    hass.services.register(DOMAIN, SERVICE_TURN_OFF, handle_light_service,
                           descriptions.get(SERVICE_TURN_OFF))

    hass.services.register(DOMAIN, SERVICE_TOGGLE, handle_light_service,
                           descriptions.get(SERVICE_TOGGLE))

    return True


class Light(ToggleEntity):
    """Representation of a light."""

    # pylint: disable=no-self-use
    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return None

    @property
    def xy_color(self):
        """Return the XY color value [float, float]."""
        return None

    @property
    def rgb_color(self):
        """Return the RGB color value [int, int, int]."""
        return None

    @property
    def color_temp(self):
        """Return the CT color value in mirads."""
        return None

    @property
    def state_attributes(self):
        """Return optional state attributes."""
        data = {}

        if self.is_on:
            for prop, attr in PROP_TO_ATTR.items():
                value = getattr(self, prop)
                if value:
                    data[attr] = value

            if ATTR_RGB_COLOR not in data and ATTR_XY_COLOR in data and \
               ATTR_BRIGHTNESS in data:
                data[ATTR_RGB_COLOR] = color_util.color_xy_brightness_to_RGB(
                    data[ATTR_XY_COLOR][0], data[ATTR_XY_COLOR][1],
                    data[ATTR_BRIGHTNESS])

        return data
