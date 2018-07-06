"""
Support for Tuya switch.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.tuya/
"""
import asyncio

from homeassistant.components.switch import SwitchDevice
from homeassistant.components.tuya import DOMAIN, DATA_TUYA, TuyaDevice

DEPENDENCIES = ['tuya']

DEVICE_TYPE = 'switch'


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up Tuya Switch device."""
    tuya = hass.data[DATA_TUYA]
    devices = tuya.get_devices_by_type(DEVICE_TYPE)

    if DEVICE_TYPE not in hass.data[DOMAIN]['entities']:
        hass.data[DOMAIN]['entities'][DEVICE_TYPE] = []

    for device in devices:
        if device.object_id() not in hass.data[DOMAIN]['dev_ids']:
            add_devices([TuyaSwitch(device, hass)])
            hass.data[DOMAIN]['dev_ids'].append(device.object_id())


class TuyaSwitch(TuyaDevice, SwitchDevice):
    """Tuya Switch Device."""

    def __init__(self, tuya, hass):
        """Init Tuya switch device."""
        super(TuyaSwitch, self).__init__(tuya, hass)
        self.entity_id = DEVICE_TYPE + '.' + tuya.object_id()

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Call when entity is added to hass."""
        self.hass.data[DOMAIN]['entities'][DEVICE_TYPE].append(self)

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self.tuya.state()

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        self.tuya.turn_on()

    def turn_off(self, **kwargs):
        """Turn the device off."""
        self.tuya.turn_off()
