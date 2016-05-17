"""
Flux for Home-Assistant.

The RGB to XY function was taken from https://github.com/KpaBap/hue-flux/

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/flux/
"""
from datetime import timedelta
import logging
import voluptuous as vol

from homeassistant.helpers.event import track_time_change
from homeassistant.components.light import is_on, turn_on, turn_off
from homeassistant.components.sun import next_setting, next_rising
from homeassistant.util.color import color_temperature_to_rgb
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

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_LIGHTS): [cv.string],
        vol.Optional(CONF_WAKETIME, default=None): cv.time,
        vol.Optional(CONF_BEDTIME, default="22:00"): cv.time,
        vol.Optional(CONF_TURNOFF, default=False): cv.boolean,
        vol.Optional(CONF_AUTO, default=False): cv.boolean,
        vol.Optional(CONF_DAY_CT, default=4000):
            vol.All(vol.Coerce(int), vol.Range(min=1000, max=40000)),
        vol.Optional(CONF_SUNSET_CT, default=3000):
            vol.All(vol.Coerce(int), vol.Range(min=1000, max=40000)),
        vol.Optional(CONF_BEDTIME_CT, default=1900):
            vol.All(vol.Coerce(int), vol.Range(min=1000, max=40000)),
        vol.Optional(CONF_BRIGHTNESS, default=90):
            vol.All(vol.Coerce(int), vol.Range(min=0, max=255))
    })
}, extra=vol.ALLOW_EXTRA)


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


def set_lights_xy(hass, lights, x_value, y_value, brightness):
    """Set color of array of lights."""
    for light in lights:
        if is_on(hass, light):
            turn_on(hass, light,
                    xy_color=[x_value, y_value],
                    brightness=brightness)


def setup(hass, config):
    """Flux setup."""
    flux = Flux(hass, config.get(DOMAIN))

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
        self.lights = config[CONF_LIGHTS]
        self.hass = hass
        self.waketime = config[CONF_WAKETIME]
        self.bedtime = config[CONF_BEDTIME]
        self.turn_off = config[CONF_TURNOFF]
        self.day_colortemp = config[CONF_DAY_CT]
        self.sunset_colortemp = config[CONF_SUNSET_CT]
        self.bedtime_colortemp = config[CONF_BEDTIME_CT]
        self.brightness = config[CONF_BRIGHTNESS]
        if config[CONF_AUTO]:
            sunrise = self.sunrise()
            track_time_change(hass, self.update,
                              second=[0, 10, 20, 30, 40, 50],
                              minute=list(range(sunrise.minute, 59)),
                              hour=sunrise.hour)
            bedtime_hour = 1 + self.bedtime.hour
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
        bedtime = dt_util.now().replace(hour=int(self.bedtime.hour),
                                        minute=int(self.bedtime.minute),
                                        second=0)
        if sunrise < now < sunset:
            # Daytime
            temp_range = abs(self.day_colortemp - self.sunset_colortemp)
            day_length = int(sunset.timestamp() - sunrise.timestamp())
            now_secs = int(now.timestamp() - sunrise.timestamp())
            percentage_of_day_complete = now_secs / day_length
            temp_offset = temp_range * percentage_of_day_complete
            temp = self.day_colortemp - temp_offset
            x_value, y_value = rgb_to_xy(*color_temperature_to_rgb(temp))
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
            x_value, y_value = rgb_to_xy(*color_temperature_to_rgb(temp))
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
