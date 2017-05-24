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
from homeassistant.components.switch import DOMAIN, SwitchDevice
from homeassistant.const import CONF_NAME, CONF_PLATFORM
from homeassistant.helpers.event import track_time_change
from homeassistant.helpers.sun import get_astral_event_date
from homeassistant.util.color import (
    color_temperature_to_rgb, color_RGB_to_xy,
    color_temperature_kelvin_to_mired)
from homeassistant.util.dt import now as dt_now
import homeassistant.helpers.config_validation as cv

DEPENDENCIES = ['light']

_LOGGER = logging.getLogger(__name__)

CONF_LIGHTS = 'lights'
CONF_START_TIME = 'start_time'
CONF_STOP_TIME = 'stop_time'
CONF_START_CT = 'start_colortemp'
CONF_SUNSET_CT = 'sunset_colortemp'
CONF_STOP_CT = 'stop_colortemp'
CONF_BRIGHTNESS = 'brightness'
CONF_DISABLE_BRIGTNESS_ADJUST = 'disable_brightness_adjust'
CONF_MODE = 'mode'

MODE_XY = 'xy'
MODE_MIRED = 'mired'
DEFAULT_MODE = MODE_XY

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
        vol.All(vol.Coerce(int), vol.Range(min=0, max=255)),
    vol.Optional(CONF_DISABLE_BRIGTNESS_ADJUST): cv.boolean,
    vol.Optional(CONF_MODE, default=DEFAULT_MODE):
        vol.Any(MODE_XY, MODE_MIRED)
})


def set_lights_xy(hass, lights, x_val, y_val, brightness):
    """Set color of array of lights."""
    for light in lights:
        if is_on(hass, light):
            turn_on(hass, light,
                    xy_color=[x_val, y_val],
                    brightness=brightness,
                    transition=30)


def set_lights_temp(hass, lights, mired, brightness):
    """Set color of array of lights."""
    for light in lights:
        if is_on(hass, light):
            turn_on(hass, light,
                    color_temp=int(mired),
                    brightness=brightness,
                    transition=30)


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Flux switches."""
    name = config.get(CONF_NAME)
    lights = config.get(CONF_LIGHTS)
    start_time = config.get(CONF_START_TIME)
    stop_time = config.get(CONF_STOP_TIME)
    start_colortemp = config.get(CONF_START_CT)
    sunset_colortemp = config.get(CONF_SUNSET_CT)
    stop_colortemp = config.get(CONF_STOP_CT)
    brightness = config.get(CONF_BRIGHTNESS)
    disable_brightness_adjust = config.get(CONF_DISABLE_BRIGTNESS_ADJUST)
    mode = config.get(CONF_MODE)
    flux = FluxSwitch(name, hass, False, lights, start_time, stop_time,
                      start_colortemp, sunset_colortemp, stop_colortemp,
                      brightness, disable_brightness_adjust, mode)
    add_devices([flux])

    def update(call=None):
        """Update lights."""
        flux.flux_update()

    hass.services.register(DOMAIN, name + '_update', update)


class FluxSwitch(SwitchDevice):
    """Representation of a Flux switch."""

    def __init__(self, name, hass, state, lights, start_time, stop_time,
                 start_colortemp, sunset_colortemp, stop_colortemp,
                 brightness, disable_brightness_adjust, mode):
        """Initialize the Flux switch."""
        self._name = name
        self.hass = hass
        self._lights = lights
        self._start_time = start_time
        self._stop_time = stop_time
        self._start_colortemp = start_colortemp
        self._sunset_colortemp = sunset_colortemp
        self._stop_colortemp = stop_colortemp
        self._brightness = brightness
        self._disable_brightness_adjust = disable_brightness_adjust
        self._mode = mode
        self.unsub_tracker = None

    @property
    def name(self):
        """Return the name of the device if any."""
        return self._name

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self.unsub_tracker is not None

    def turn_on(self, **kwargs):
        """Turn on flux."""
        if self.is_on:
            return

        # Make initial update
        self.flux_update()

        self.unsub_tracker = track_time_change(
            self.hass, self.flux_update, second=[0, 30])

        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Turn off flux."""
        if self.unsub_tracker is not None:
            self.unsub_tracker()
            self.unsub_tracker = None

        self.schedule_update_ha_state()

    def flux_update(self, now=None):
        """Update all the lights using flux."""
        if now is None:
            now = dt_now()
        sunset = get_astral_event_date(self.hass, 'sunset', now.date())
        start_time = self.find_start_time(now)
        stop_time = now.replace(
            hour=self._stop_time.hour, minute=self._stop_time.minute,
            second=0)

        if start_time < now < sunset:
            # Daytime
            time_state = 'day'
            temp_range = abs(self._start_colortemp - self._sunset_colortemp)
            day_length = int(sunset.timestamp() - start_time.timestamp())
            seconds_from_start = int(now.timestamp() - start_time.timestamp())
            percentage_complete = seconds_from_start / day_length
            temp_offset = temp_range * percentage_complete
            if self._start_colortemp > self._sunset_colortemp:
                temp = self._start_colortemp - temp_offset
            else:
                temp = self._start_colortemp + temp_offset
        else:
            # Nightime
            time_state = 'night'
            if now < stop_time and now > start_time:
                now_time = now
            else:
                now_time = stop_time
            temp_range = abs(self._sunset_colortemp - self._stop_colortemp)
            night_length = int(stop_time.timestamp() - sunset.timestamp())
            seconds_from_sunset = int(now_time.timestamp() -
                                      sunset.timestamp())
            percentage_complete = seconds_from_sunset / night_length
            temp_offset = temp_range * percentage_complete
            if self._sunset_colortemp > self._stop_colortemp:
                temp = self._sunset_colortemp - temp_offset
            else:
                temp = self._sunset_colortemp + temp_offset
        x_val, y_val, b_val = color_RGB_to_xy(*color_temperature_to_rgb(temp))
        brightness = self._brightness if self._brightness else b_val
        if self._disable_brightness_adjust:
            brightness = None
        if self._mode == MODE_XY:
            set_lights_xy(self.hass, self._lights, x_val,
                          y_val, brightness)
            _LOGGER.info("Lights updated to x:%s y:%s brightness:%s, %s%% "
                         "of %s cycle complete at %s", x_val, y_val,
                         brightness, round(
                             percentage_complete * 100), time_state, now)
        else:
            # Convert to mired and clamp to allowed values
            mired = color_temperature_kelvin_to_mired(temp)
            set_lights_temp(self.hass, self._lights, mired, brightness)
            _LOGGER.info("Lights updated to mired:%s brightness:%s, %s%% "
                         "of %s cycle complete at %s", mired, brightness,
                         round(percentage_complete * 100), time_state, now)

    def find_start_time(self, now):
        """Return sunrise or start_time if given."""
        if self._start_time:
            sunrise = now.replace(
                hour=self._start_time.hour, minute=self._start_time.minute,
                second=0)
        else:
            sunrise = get_astral_event_date(self.hass, 'sunrise', now.date())
        return sunrise
