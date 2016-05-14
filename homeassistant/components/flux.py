"""
example configuration.yaml:

flux:
  lights:
    - light.desk
    - light.lamp
  bedtime: "22:00"
  turn_off: True
"""
from homeassistant.helpers.event import track_state_change, track_time_change
from homeassistant.components.light import is_on, turn_on, turn_off
from homeassistant.components.sun import next_setting, next_rising
import homeassistant.util.dt as dt_util

from datetime import timedelta
import logging
import math



DEPENDENCIES = ['sun', 'light']
DOMAIN = "flux"
SUN = "sun.sun"
_LOGGER = logging.getLogger(__name__)

DAY_COLORTEMP = 4000
SUNSET_COLORTEMP = 3000
BEDTIME_COLORTEMP = 1900


def set_lights_xy(hass, lights, x, y):
    for light in lights:
        turn_on(hass, light, xy_color=[x,y])

# https://github.com/KpaBap/hue-flux/blob/master/hue-flux.py
def RGB_to_xy(red, green, blue):

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

    x = red * 0.664511 + green * 0.154324 + blue * 0.162028
    y = red * 0.313881 + green * 0.668433 + blue * 0.047685
    z = red * 0.000088 + green * 0.072310 + blue * 0.986039

    try:
        cx = x / (x + y + z)
        cy = y / (x + y + z)
    except:
        cx, cy = 0, 0

    if cx > 0.675:
        cx = 0.675
    if cx < 0.167:
        cx = 0.167

    if cy > 0.518:
        cy = 0.518
    if cy < 0.04:
        cy = 0.04

    return round(cx, 3), round(cy, 3)

# https://github.com/KpaBap/hue-flux/blob/master/hue-flux.py
def colortemp_k_to_RGB(temp):
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
    Flux(hass, config)

class Flux(object):

    def __init__(self, hass, config):
        self.lights = config[DOMAIN]['lights']
        self.hass = hass
        self.bedtime = config[DOMAIN]['bedtime']
        self.turn_off = config[DOMAIN]['turn_off']
        track_time_change(hass, self.update, second=[0,10,20,30,40,50])
        self.update(dt_util.now())

    def update(self, now):
        current_time = now
        sunset_time = next_setting(self.hass, SUN)
        sunrise_time = next_rising(self.hass, SUN)
        if sunset_time.day > current_time.day:
          sunset_time = sunset_time - timedelta(days=1)
        if sunrise_time.day > current_time.day:
          sunrise_time = sunrise_time - timedelta(days=1)
        bedtime = dt_util.now().replace(hour=int(self.bedtime.split(":")[0]), minute=int(self.bedtime.split(":")[1]))
        if sunrise_time < current_time < sunset_time:
            ### Daytime
            temp_range = abs(DAY_COLORTEMP - SUNSET_COLORTEMP)
            day_length = int(sunset_time.timestamp() - sunrise_time.timestamp()) # in seconds
            current_time_secs = int(current_time.timestamp() - sunrise_time.timestamp()) # seconds from sunrise
            percentage_of_day_complete = current_time_secs / day_length        
            temp_offset = temp_range * percentage_of_day_complete
            temp = DAY_COLORTEMP - temp_offset
            x,y = RGB_to_xy(*colortemp_k_to_RGB(temp))
            set_lights_xy(self.hass, self.lights, x, y)
            _LOGGER.info("Flux: Daytime lights updated! x:%s y:%s",x,y)
        elif sunset_time < current_time < bedtime:
            ### Nightime
            temp_range = abs(SUNSET_COLORTEMP - BEDTIME_COLORTEMP)
            night_length = int(bedtime.timestamp() - sunset_time.timestamp()) # in seconds
            current_time_secs = int(current_time.timestamp() - sunset_time.timestamp()) # seconds from sunrise
            percentage_of_day_complete = current_time_secs / night_length        
            temp_offset = temp_range * percentage_of_day_complete
            temp = SUNSET_COLORTEMP - temp_offset
            x,y = RGB_to_xy(*colortemp_k_to_RGB(temp))
            set_lights_xy(self.hass, self.lights, x, y)
            _LOGGER.info("Flux: Nighttime lights updated! x:%s y:%s",x,y)
        else:
            if self.turn_off:
              for light in self.lights:
                  if is_on(self.hass, light):
                      _LOGGER.info("Flux: Lights off!")
                      turn_off(self.hass, light, transition=10)
