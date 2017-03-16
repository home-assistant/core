"""Support for Lutron Caseta lights."""
import logging

from homeassistant.components.light import (
    ATTR_BRIGHTNESS, SUPPORT_BRIGHTNESS, Light)
from homeassistant.components.light.lutron import to_hass_level
from homeassistant.components.light.lutron import to_lutron_level

REQUIREMENTS = ['https://github.com/gurumitts/'
                'pylutron-caseta/archive/v0.2.0.zip#'
                'pylutron-caseta==v0.2.0', 'paramiko==2.1.2']

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup Lutron walldimmers and switches as lights."""
    from pylutron_caseta import smartbridge

    bridge = smartbridge.Smartbridge(
        hostname=config['host'],
        username=config['user'],
        password=config['password'])

    supported_types = ['WallDimmer']

    caseta_devices = bridge.get_devices()
    devs = []
    _LOGGER.debug(caseta_devices)
    for device in caseta_devices:
        if caseta_devices[device]["type"] in supported_types:
            dev = LutronCasetaLight(hass, caseta_devices[device], bridge)
            devs.append(dev)
    add_devices(devs, True)

    return True


class LutronCasetaLight(Light):
    """Representation of a Lutron Light, including dimmable."""

    def __init__(self, hass, device_info, bridge):
        """Initialize the light."""
        self._prev_brightness = None
        self._device_id = device_info["device_id"]
        self._device_type = device_info["type"]
        self._device_name = device_info["name"]
        self._state = None
        self._smartbridge = bridge
        self._smartbridge.add_subscriber(self._device_id,
                                         self._update_callback)
        self.update()

    def _update_callback(self):
        self.schedule_update_ha_state()

    @property
    def name(self):
        """Return the name of the device."""
        return self._device_name

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_BRIGHTNESS

    @property
    def brightness(self):
        """Return the brightness of the light."""
        return to_hass_level(self._state["current_state"])

    def turn_on(self, **kwargs):
        """Turn the light on."""
        if ATTR_BRIGHTNESS in kwargs and self._device_type == "WallDimmer":
            brightness = kwargs[ATTR_BRIGHTNESS]
        else:
            brightness = 100
        self._smartbridge.set_value(self._device_id,
                                    to_lutron_level(brightness))

    def turn_off(self, **kwargs):
        """Turn the light off."""
        self._smartbridge.set_value(self._device_id, 0)

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attr = {}
        attr['Lutron Integration ID'] = self._device_id
        return attr

    @property
    def is_on(self):
        """Return true if device is on."""
        _LOGGER.debug(self._state)
        return self._state["current_state"] > 0

    def update(self):
        """Called when forcing a refresh of the device."""
        self._state = self._smartbridge.get_device_by_id(self._device_id)

    @property
    def should_poll(self):
        """No polling needed."""
        return False
