"""
Support for Plum Lightpad switches.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/light.plum_lightpad
"""
from datetime import timedelta
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.components.light import PLATFORM_SCHEMA
from homeassistant.helpers import event as evt
from homeassistant.util import dt as dt_util
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD

DEPENDENCIES = ['plum_lightpad']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
})


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    plum = hass.data['plum']

    def new_lightpad(lightpad):
        add_devices_callback([
            PlumMotionSensor(lightpad=lightpad, hass=hass),
        ])

    for lightpad in plum.lightpads.values():
        new_lightpad(lightpad)

    plum.add_lightpad_listener(new_lightpad)


class PlumMotionSensor(BinarySensorDevice):

    def __init__(self, hass, lightpad):
        self._hass = hass
        self._lightpad = lightpad
        self.off_delay = 8  # TODO establish by config
        self._signal = None
        self._latest_motion = None

        lightpad.add_event_listener('pirSignal', self.motion_detected)

    def motion_detected(self, event):
        self._signal = event['signal']
        self._latest_motion = dt_util.utcnow()
        self.schedule_update_ha_state()

        def off_delay_handler(now):
            """Switch sensor off after a delay."""
            if (now - self._latest_motion).seconds >= self.off_delay:
                self._signal = None
                self.schedule_update_ha_state()

        motion_timeout = dt_util.utcnow() + timedelta(seconds=self.off_delay)
        evt.track_point_in_time(self._hass, off_delay_handler, motion_timeout)

    @property
    def lpid(self):
        return self._lightpad.lpid

    @property
    def name(self):
        return self._lightpad.friendly_name

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._signal is not None
