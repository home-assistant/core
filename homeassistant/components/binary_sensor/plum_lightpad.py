"""
Support for Plum Lightpad switches.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/light.plum_lightpad
"""
from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.components.plum_lightpad import PLUM_DATA
from homeassistant.helpers.event import async_call_later
from homeassistant.util import dt as dt_util

DEPENDENCIES = ['plum_lightpad']

MOTION_DEVICE_CLASS = 'motion'


async def async_setup_platform(hass, config, add_devices,
                               discovery_info=None):
    """Set up the motion sensors for the Plum Lightpad  platform."""
    if discovery_info is None:
        return

    plum = hass.data[PLUM_DATA]

    if 'lpid' in discovery_info:
        lightpad = plum.get_lightpad(discovery_info['lpid'])
        add_devices([
            PlumMotionSensor(lightpad=lightpad, hass=hass)
        ])


class PlumMotionSensor(BinarySensorDevice):
    """Representation of a Lightpad's motion detection."""

    def __init__(self, hass, lightpad):
        """Init Plum Motion Sensor."""
        self._hass = hass
        self._lightpad = lightpad
        self.off_delay = 10
        self._signal = None
        self._latest_motion = None

    async def async_added_to_hass(self):
        """Subscribe to pirSignal events."""
        self._lightpad.add_event_listener('pirSignal', self.motion_detected)

    def motion_detected(self, event):
        """Motion Detected handler."""
        self._signal = event['signal']
        self._latest_motion = dt_util.utcnow()
        self.schedule_update_ha_state()

        def off_handler(now):
            """Switch sensor off after a delay."""
            if (now - self._latest_motion).seconds >= self.off_delay:
                self._signal = None
                self.schedule_update_ha_state()

        async_call_later(hass=self.hass,
                         delay=self.off_delay, action=off_handler)

    @property
    def lpid(self):
        """Return the LightPad ID (lpid) which is attached to the sensor."""
        return self._lightpad.lpid

    @property
    def name(self):
        """Return the friendly name associated with the lightpad."""
        return self._lightpad.friendly_name

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._signal is not None

    @property
    def device_class(self):
        """Return the Motion device class."""
        return MOTION_DEVICE_CLASS
