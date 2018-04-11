"""
Support for Plum Lightpad switches.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/light.plum_lightpad
"""
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.components.light import PLATFORM_SCHEMA
from homeassistant.helpers import event as evt
from homeassistant.util import dt as dt_util
from datetime import timedelta
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD

DEPENDENCIES = ['plum_lightpad']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
})


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    plum = hass.data['plum']

    for lpid, lightpad in plum.lightpads.items():
        add_devices_callback([
            PlumMotionSensor(plum=plum, lpid=lpid, lightpad=lightpad, hass=hass),
        ])

class PlumMotionSensor(BinarySensorDevice):

    def __init__(self, plum, hass, lpid, lightpad):
        self._plum = plum
        self._hass = hass
        self._lpid = lpid
        self._name = lightpad.name
        self.off_delay = 5
        self._signal = None
        self._latest_motion = None

        plum.add_pir_listener(self._lpid, self.motion_detected)

    def motion_detected(self, signal):
        self._signal = signal
        self._latest_motion = dt_util.utcnow()
        self.schedule_update_ha_state()

        def off_delay_handler(now):
            """Switch sensor off after a delay."""
            if ((now - self._latest_motion).seconds >= self.off_delay):
                self._signal = None
                self.schedule_update_ha_state()

        evt.track_point_in_time(self._hass, off_delay_handler, dt_util.utcnow() + timedelta(seconds=self.off_delay))

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._signal != None

