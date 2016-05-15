"""
Flux for Home-Assistant.

The primary functions in this component were taken from:
    https://github.com/KpaBap/hue-flux/blob/master/hue-flux.py

This component will change the temperature of your lights similar to
the way flux works on your computer.

You might give a list of light entities to control in the
configuration.yaml.  You should also provide a 'bedtime', or the last
time of day the lights will be on.  You can use the 'turn_off' param
to tell flux whether or not to turn off the lights at night.

The 'auto' param will make this component turn on the lights in the morning,
and change them accordingly every 10 seconds throughout the day.

If you don't wish to run the auto program, you can create your own
automation rules that call the service flux.update whenever you want
the lights updated.

example configuration.yaml:

flux:
  lights:
    - light.desk
    - light.lamp
  bedtime: "22:00"          # optional, default 22:00
  turn_off: True            # optional, default False
  auto: True                # optional, default False
  day_colortemp: 4000       # optional, default 4000
  sunset_colortemp: 3000    # optional, default 3000
  bedtime_colortemp: 1900   # optional, default 1900
"""
from datetime import timedelta
import logging
import math

from homeassistant.helpers.event import track_time_change
from homeassistant.components.light import is_on, turn_on, turn_off
from homeassistant.components.sun import next_setting, next_rising
import homeassistant.util.dt as dt_util

DEPENDENCIES = ['sun', 'light']
DOMAIN = "flux"
SUN = "sun.sun"
_LOGGER = logging.getLogger(__name__)


def set_lights_xy(hass, lights, x_value, y_value):
    """Set color of array of lights."""
    for light in lights:
        turn_on(hass, light, xy_color=[x_value, y_value])


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


class Flux(object):
    """Class for Flux."""

    def __init__(self, hass, config):
        """Initialize Flux class."""
        self.lights = config[DOMAIN].get('lights')
        self.hass = hass
        self.bedtime = config[DOMAIN].get('bedtime', '22:00')
        self.turn_off = config[DOMAIN].get('turn_off', False)
        self.day_colortemp = config[DOMAIN].get('day_colortemp', 4000)
        self.sunset_colortemp = config[DOMAIN].get('sunset_colortemp', 3000)
        self.bedtime_colortemp = config[DOMAIN].get('bedtime_colortemp', 1900)
        if config[DOMAIN].get('auto', False):
            track_time_change(hass, self.update,
                              second=[0, 10, 20, 30, 40, 50])
            self.update(dt_util.now())

    def update(self, now=dt_util.now()):
        """Update all the lights."""
        current = now
        sunset = next_setting(self.hass, SUN)
        sunrise = next_rising(self.hass, SUN)
        if sunset.day > current.day:
            sunset = sunset - timedelta(days=1)
        if sunrise.day > current.day:
            sunrise = sunrise - timedelta(days=1)
        bedtime = dt_util.now().replace(hour=int(self.bedtime.split(":")[0]),
                                        minute=int(self.bedtime.split(":")[1]))
        if sunrise < current < sunset:
            # Daytime
            temp_range = abs(self.day_colortemp - self.sunset_colortemp)
            day_length = int(sunset.timestamp() - sunrise.timestamp())
            current_secs = int(current.timestamp() - sunrise.timestamp())
            percentage_of_day_complete = current_secs / day_length
            temp_offset = temp_range * percentage_of_day_complete
            temp = self.day_colortemp - temp_offset
            x_value, y_value = rgb_to_xy(*colortemp_k_to_rgb(temp))
            set_lights_xy(self.hass, self.lights, x_value, y_value)
            _LOGGER.info("Flux: Daytime lights updated! x:%s y:%s",
                         x_value, y_value)
        elif sunset < current < bedtime:
            # Nightime
            temp_range = abs(self.sunset_colortemp - self.bedtime_colortemp)
            night_length = int(bedtime.timestamp() - sunset.timestamp())
            current_secs = int(current.timestamp() - sunset.timestamp())
            percentage_of_day_complete = current_secs / night_length
            temp_offset = temp_range * percentage_of_day_complete
            temp = self.sunset_colortemp - temp_offset
            x_value, y_value = rgb_to_xy(*colortemp_k_to_rgb(temp))
            set_lights_xy(self.hass, self.lights, x_value, y_value)
            _LOGGER.info("Flux: Nighttime lights updated! x:%s y:%s",
                         x_value, y_value)
        else:
            # Asleep
            if self.turn_off:
                for light in self.lights:
                    if is_on(self.hass, light):
                        _LOGGER.info("Flux: Lights off!")
                        turn_off(self.hass, light, transition=10)
