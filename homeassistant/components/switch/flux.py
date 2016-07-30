"""
Flux for Home-Assistant.

The idea was taken from https://github.com/KpaBap/hue-flux/

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/switch.flux/
"""
from datetime import time
import logging
import voluptuous as vol

from homeassistant.components.light import is_on, turn_on
from homeassistant.components.sun import next_setting, next_rising
from homeassistant.components.switch import DOMAIN, SwitchDevice
from homeassistant.const import CONF_NAME, CONF_PLATFORM, EVENT_TIME_CHANGED
from homeassistant.helpers.event import track_utc_time_change
from homeassistant.util.color import color_temperature_to_rgb as temp_to_rgb
from homeassistant.util.color import color_RGB_to_xy
from homeassistant.util.dt import now as dt_now
from homeassistant.util.dt import as_local
import homeassistant.helpers.config_validation as cv

DEPENDENCIES = ['sun', 'light']
SUN = "sun.sun"
_LOGGER = logging.getLogger(__name__)

CONF_LIGHTS = 'lights'
CONF_START_TIME = 'start_time'
CONF_STOP_TIME = 'stop_time'
CONF_START_CT = 'start_colortemp'
CONF_SUNSET_CT = 'sunset_colortemp'
CONF_STOP_CT = 'stop_colortemp'
CONF_BRIGHTNESS = 'brightness'

PLATFORM_SCHEMA = vol.Schema({
    vol.Required(CONF_PLATFORM): 'flux',
    vol.Required(CONF_LIGHTS): cv.entity_ids,
    vol.Optional(CONF_NAME, default="Flux"): cv.string,
    vol.Optional(CONF_START_TIME): cv.time,
    vol.Optional(CONF_STOP_TIME, default=time(22, 0)): cv.time,
    vol.Optional(CONF_START_CT, default=4000):
        vol.All(vol.Coerce(int), vol.Range(min=1000, max=40000)),
    vol.Optional(CONF_SUNSET_CT, default=3000):
        vol.All(vol.Coerce(int), vol.Range(min=1000, max=40000)),
    vol.Optional(CONF_STOP_CT, default=1900):
        vol.All(vol.Coerce(int), vol.Range(min=1000, max=40000)),
    vol.Optional(CONF_BRIGHTNESS):
        vol.All(vol.Coerce(int), vol.Range(min=0, max=255))
})


def set_lights_xy(hass, lights, x_val, y_val, brightness):
    """Set color of array of lights."""
    for light in lights:
        if is_on(hass, light):
            turn_on(hass, light,
                    xy_color=[x_val, y_val],
                    brightness=brightness,
                    transition=30)


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Flux switches."""
    name = config.get(CONF_NAME)
    lights = config.get(CONF_LIGHTS)
    start_time = config.get(CONF_START_TIME)
    stop_time = config.get(CONF_STOP_TIME)
    start_colortemp = config.get(CONF_START_CT)
    sunset_colortemp = config.get(CONF_SUNSET_CT)
    stop_colortemp = config.get(CONF_STOP_CT)
    brightness = config.get(CONF_BRIGHTNESS)
    flux = FluxSwitch(name, hass, False, lights, start_time, stop_time,
                      start_colortemp, sunset_colortemp, stop_colortemp,
                      brightness)
    add_devices([flux])

    def update(call=None):
        """Update lights."""
        flux.flux_update()

    hass.services.register(DOMAIN, 'flux_update', update)


# pylint: disable=too-many-instance-attributes
class FluxSwitch(SwitchDevice):
    """Representation of a Flux switch."""

    # pylint: disable=too-many-arguments
    def __init__(self, name, hass, state, lights, start_time, stop_time,
                 start_colortemp, sunset_colortemp, stop_colortemp,
                 brightness):
        """Initialize the Flux switch."""
        self._name = name
        self.hass = hass
        self._state = state
        self._lights = lights
        self._start_time = start_time
        self._stop_time = stop_time
        self._start_colortemp = start_colortemp
        self._sunset_colortemp = sunset_colortemp
        self._stop_colortemp = stop_colortemp
        self._brightness = brightness
        self.tracker = None

    @property
    def name(self):
        """Return the name of the device if any."""
        return self._name

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._state

    def turn_on(self, **kwargs):
        """Turn on flux."""
        self._state = True
        self.tracker = track_utc_time_change(self.hass,
                                             self.flux_update,
                                             second=[0, 30])
        self.update_ha_state()

    def turn_off(self, **kwargs):
        """Turn off flux."""
        self._state = False
        self.hass.bus.remove_listener(EVENT_TIME_CHANGED, self.tracker)
        self.update_ha_state()

    # pylint: disable=too-many-locals
    def flux_update(self, now=dt_now()):
        """Update all the lights using flux."""
        sunset = next_setting(self.hass, SUN).replace(day=now.day,
                                                      month=now.month,
                                                      year=now.year)
        start_time = self.find_start_time(now)
        stop_time = now.replace(hour=self._stop_time.hour,
                                minute=self._stop_time.minute,
                                second=0)

        if start_time < now < sunset:
            # Daytime
            temp_range = abs(self._start_colortemp - self._sunset_colortemp)
            day_length = int(sunset.timestamp() - start_time.timestamp())
            seconds_from_start = int(now.timestamp() - start_time.timestamp())
            percentage_of_day_complete = seconds_from_start / day_length
            temp_offset = temp_range * percentage_of_day_complete
            if self._start_colortemp > self._sunset_colortemp:
                temp = self._start_colortemp - temp_offset
            else:
                temp = self._start_colortemp + temp_offset
            x_val, y_val, b_val = color_RGB_to_xy(*temp_to_rgb(temp))
            brightness = self._brightness if self._brightness else b_val
            set_lights_xy(self.hass, self._lights, x_val,
                          y_val, brightness)
            _LOGGER.info("Lights updated to x:%s y:%s brightness:%s, %s%%"
                         " of day cycle complete at %s", x_val, y_val,
                         brightness, round(percentage_of_day_complete*100),
                         as_local(now))
        else:
            # Nightime
            if now < stop_time and now > start_time:
                now_time = now
            else:
                now_time = stop_time
            temp_range = abs(self._sunset_colortemp - self._stop_colortemp)
            night_length = int(stop_time.timestamp() - sunset.timestamp())
            seconds_from_sunset = int(now_time.timestamp() -
                                      sunset.timestamp())
            percentage_of_night_complete = seconds_from_sunset / night_length
            temp_offset = temp_range * percentage_of_night_complete
            if self._sunset_colortemp > self._stop_colortemp:
                temp = self._sunset_colortemp - temp_offset
            else:
                temp = self._sunset_colortemp + temp_offset
            x_val, y_val, b_val = color_RGB_to_xy(*temp_to_rgb(temp))
            brightness = self._brightness if self._brightness else b_val
            set_lights_xy(self.hass, self._lights, x_val,
                          y_val, brightness)
            _LOGGER.info("Lights updated to x:%s y:%s brightness:%s, %s%%"
                         " of night cycle complete at %s", x_val, y_val,
                         brightness, round(percentage_of_night_complete*100),
                         as_local(now))

    def find_start_time(self, now):
        """Return sunrise or start_time if given."""
        if self._start_time:
            sunrise = now.replace(hour=self._start_time.hour,
                                  minute=self._start_time.minute,
                                  second=0)
        else:
            sunrise = next_rising(self.hass, SUN).replace(day=now.day,
                                                          month=now.month,
                                                          year=now.year)
        return sunrise
