"""
Flux for Home-Assistant.

The primary functions in this component were taken from
https://github.com/KpaBap/hue-flux/

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/flux/
"""
from datetime import timedelta
import logging
import math
import voluptuous as vol

from homeassistant.helpers.event import track_time_change
from homeassistant.components.light import is_on, turn_on, turn_off
from homeassistant.components.sun import next_setting, next_rising
import homeassistant.helpers.config_validation as cv
import homeassistant.util.dt as dt_util

DEPENDENCIES = ['sun', 'light']
DOMAIN = "flux"
SUN = "sun.sun"
_LOGGER = logging.getLogger(__name__)

CONF_LIGHTS = 'lights'
CONF_WAKETIME = 'waketime'
CONF_BEDTIME = 'bedtime'
CONF_TURNOFF = 'turn_off'
CONF_AUTO = 'auto'
CONF_DAY_CT = 'day_colortemp'
CONF_SUNSET_CT = 'sunset_colortemp'
CONF_BEDTIME_CT = 'bedtime_colortemp'
CONF_BRIGHTNESS = 'brightness'

PLATFORM_SCHEMA = vol.Schema({
    vol.Required(CONF_LIGHTS): [cv.string],
    vol.Optional(CONF_WAKETIME): vol.Coerce(str),
    vol.Optional(CONF_BEDTIME, default="22:00"): vol.Coerce(str),
    vol.Optional(CONF_TURNOFF, default=False): vol.Coerce(bool),
    vol.Optional(CONF_AUTO, default=False): vol.Coerce(bool),
    vol.Optional(CONF_DAY_CT, default=4000): vol.Coerce(int),
    vol.Optional(CONF_SUNSET_CT, default=3000): vol.Coerce(int),
    vol.Optional(CONF_BEDTIME_CT, default=1900): vol.Coerce(int),
    vol.Optional(CONF_BRIGHTNESS, default=90): vol.Coerce(int)
})


def set_lights_xy(hass, lights, x_value, y_value, brightness):
    """Set color of array of lights."""
    for light in lights:
        turn_on(hass, light,
                xy_color=[x_value, y_value],
                brightness=brightness)


# https://github.com/KpaBap/hue-flux/blob/master/hue-flux.py
def rgb_to_xy(red, green, blue):
    """Convert RGB to xy."""
    red = red / 255
    blue = blue / 255
    green = green / 255

    # Gamma correction
    red = pow((red + 0.055) / (1.0 + 0.055),
              2.4) if (red > 0.04045) else (red / 12.92)
    green = pow((green + 0.055) / (1.0 + 0.055),
                2.4) if (green > 0.04045) else (green / 12.92)
    blue = pow((blue + 0.055) / (1.0 + 0.055),
               2.4) if (blue > 0.04045) else (blue / 12.92)

    tmp_x = red * 0.664511 + green * 0.154324 + blue * 0.162028
    tmp_y = red * 0.313881 + green * 0.668433 + blue * 0.047685
    tmp_z = red * 0.000088 + green * 0.072310 + blue * 0.986039

    try:
        x_value = tmp_x / (tmp_x + tmp_y + tmp_z)
        y_value = tmp_y / (tmp_x + tmp_y + tmp_z)
    except ZeroDivisionError:
        x_value, y_value = 0, 0

    if x_value > 0.675:
        x_value = 0.675
    if x_value < 0.167:
        x_value = 0.167

    if y_value > 0.518:
        y_value = 0.518
    if y_value < 0.04:
        y_value = 0.04

    return round(x_value, 3), round(y_value, 3)


# https://github.com/KpaBap/hue-flux/blob/master/hue-flux.py
def colortemp_k_to_rgb(temp):
    """Convert temp to RGB."""
    temp = temp / 100

    if temp <= 66:
        red = 255
    else:
        red = temp - 60
        red = 329.698727446 * (red ** -0.1332047592)
        red = 0 if red < 0 else red
        red = 255 if red > 255 else red

    if temp <= 66:
        green = temp
        green = 99.4708025861 * math.log(green) - 161.1195681661
        green = 0 if green < 0 else green
        green = 255 if green > 255 else green
    else:
        green = temp - 60
        green = 288.1221695283 * (green ** -0.0755148492)
        green = 0 if green < 0 else green
        green = 255 if green > 255 else green

    if temp >= 66:
        blue = 255
    else:
        if temp <= 19:
            blue = 0
        else:
            blue = temp - 10
            blue = 138.5177312231 * math.log(blue) - 305.0447927307
            blue = 0 if blue < 0 else blue
            blue = 255 if blue > 255 else blue

    return red, green, blue


def setup(hass, config):
    """Flux setup."""
    flux = Flux(hass, config)

    def update(call=None):
        """Update lights."""
        flux.update()

    hass.services.register(DOMAIN, 'update', update)
    return True


# pylint: disable=too-few-public-methods,too-many-instance-attributes
class Flux(object):
    """Class for Flux."""

    def __init__(self, hass, config):
        """Initialize Flux class."""
        self.lights = config[DOMAIN][0].get(CONF_LIGHTS)
        self.hass = hass
        self.waketime = config[DOMAIN][0].get(CONF_WAKETIME)
        self.bedtime = config[DOMAIN][0].get(CONF_BEDTIME)
        self.turn_off = config[DOMAIN][0].get(CONF_TURNOFF)
        self.day_colortemp = config[DOMAIN][0].get(CONF_DAY_CT)
        self.sunset_colortemp = config[DOMAIN][0].get(CONF_SUNSET_CT)
        self.bedtime_colortemp = config[DOMAIN][0].get(CONF_BEDTIME_CT)
        self.brightness = config[DOMAIN][0].get(CONF_BRIGHTNESS)
        if config[DOMAIN][0].get(CONF_AUTO):
            sunrise = self.sunrise()
            track_time_change(hass, self.update,
                              second=[0, 10, 20, 30, 40, 50],
                              minute=list(range(sunrise.minute, 59)),
                              hour=sunrise.hour)
            bedtime_hour = 1 + int(self.bedtime.split(":")[0])
            track_time_change(hass, self.update,
                              second=[0, 10, 20, 30, 40, 50],
                              hour=list(range(sunrise.hour + 1, bedtime_hour)))
            self.update(dt_util.now())

    # pylint: disable=too-many-locals
    def update(self, now=dt_util.now()):
        """Update all the lights."""
        sunset = next_setting(self.hass, SUN)
        sunrise = self.sunrise()
        if sunset.day > now.day:
            sunset = sunset - timedelta(days=1)
        bedtime = dt_util.now().replace(hour=int(self.bedtime.split(":")[0]),
                                        minute=int(self.bedtime.split(":")[1]),
                                        second=0)
        if sunrise < now < sunset:
            # Daytime
            temp_range = abs(self.day_colortemp - self.sunset_colortemp)
            day_length = int(sunset.timestamp() - sunrise.timestamp())
            now_secs = int(now.timestamp() - sunrise.timestamp())
            percentage_of_day_complete = now_secs / day_length
            temp_offset = temp_range * percentage_of_day_complete
            temp = self.day_colortemp - temp_offset
            x_value, y_value = rgb_to_xy(*colortemp_k_to_rgb(temp))
            set_lights_xy(self.hass, self.lights, x_value,
                          y_value, self.brightness)
            _LOGGER.info("Lights updated during the day, x:%s y:%s",
                         x_value, y_value)
        elif sunset < now < bedtime:
            # Nightime
            temp_range = abs(self.sunset_colortemp - self.bedtime_colortemp)
            night_length = int(bedtime.timestamp() - sunset.timestamp())
            now_secs = int(now.timestamp() - sunset.timestamp())
            percentage_of_day_complete = now_secs / night_length
            temp_offset = temp_range * percentage_of_day_complete
            temp = self.sunset_colortemp - temp_offset
            x_value, y_value = rgb_to_xy(*colortemp_k_to_rgb(temp))
            set_lights_xy(self.hass, self.lights, x_value,
                          y_value, self.brightness)
            _LOGGER.info("Lights updated at night, x:%s y:%s",
                         x_value, y_value)
        else:
            # Asleep
            if self.turn_off:
                for light in self.lights:
                    if is_on(self.hass, light):
                        _LOGGER.info("Lights off")
                        turn_off(self.hass, light, transition=10)

    def sunrise(self):
        """Return sunrise or waketime if given."""
        now = dt_util.now()
        if self.waketime:
            sunrise = now.replace(hour=int(self.waketime.split(":")[0]),
                                  minute=int(self.waketime.split(":")[1]),
                                  second=0)
        else:
            sunrise = next_rising(self.hass, SUN)
        if sunrise.day > now.day:
            sunrise = sunrise - timedelta(days=1)
        return sunrise
