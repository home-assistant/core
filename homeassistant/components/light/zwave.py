"""
Support for Z-Wave lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.zwave/
"""
# Because we do not compile openzwave on CI
# pylint: disable=import-error
from threading import Timer
import logging
from homeassistant.components.light import ATTR_BRIGHTNESS, DOMAIN, Light
from homeassistant.components import zwave
from homeassistant.const import STATE_OFF, STATE_ON

FIBARO = 0x010F
FIBARO_FGRM_222 = 0x1000
FIBARO_FGRM_222_ROLLERSHUTTER = (FIBARO, FIBARO_FGRM_222)

WORKAROUND_IGNORE = 'ignore'

DEVICE_MAPPINGS = {
    FIBARO_FGRM_222_ROLLERSHUTTER: WORKAROUND_IGNORE
}

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Find and add Z-Wave lights."""
    if discovery_info is None or zwave.NETWORK is None:
        return

    node = zwave.NETWORK.nodes[discovery_info[zwave.ATTR_NODE_ID]]
    value = node.values[discovery_info[zwave.ATTR_VALUE_ID]]
    # Make sure that we have values for the key before converting to int
    if (value.node.manufacturer_id.strip() and
            value.node.product_id.strip()):
        specific_sensor_key = (int(value.node.manufacturer_id, 16),
                               int(value.node.product_id, 16))
        if specific_sensor_key in DEVICE_MAPPINGS:
            if DEVICE_MAPPINGS[specific_sensor_key] == WORKAROUND_IGNORE:
                _LOGGER.debug("Fibaro FGRM-222 Rollershutter, ignoring")
                return

    if value.command_class != zwave.COMMAND_CLASS_SWITCH_MULTILEVEL:
        return
    if value.type != zwave.TYPE_BYTE:
        return
    if value.genre != zwave.GENRE_USER:
        return

    value.set_change_verified(False)
    add_devices([ZwaveDimmer(value)])


def brightness_state(value):
    """Return the brightness and state."""
    if value.data > 0:
        return (value.data / 99) * 255, STATE_ON
    else:
        return 255, STATE_OFF


class ZwaveDimmer(zwave.ZWaveDeviceEntity, Light):
    """Representation of a Z-Wave dimmer."""

    # pylint: disable=too-many-arguments
    def __init__(self, value):
        """Initialize the light."""
        from openzwave.network import ZWaveNetwork
        from pydispatch import dispatcher

        zwave.ZWaveDeviceEntity.__init__(self, value, DOMAIN)

        self._brightness, self._state = brightness_state(value)

        # Used for value change event handling
        self._refreshing = False
        self._timer = None

        dispatcher.connect(
            self._value_changed, ZWaveNetwork.SIGNAL_VALUE_CHANGED)

    def _value_changed(self, value):
        """Called when a value has changed on the network."""
        if self._value.value_id != value.value_id:
            return

        if self._refreshing:
            self._refreshing = False
            self._brightness, self._state = brightness_state(value)
        else:
            def _refresh_value():
                """Used timer callback for delayed value refresh."""
                self._refreshing = True
                self._value.refresh()

            if self._timer is not None and self._timer.isAlive():
                self._timer.cancel()

            self._timer = Timer(2, _refresh_value)
            self._timer.start()

        self.update_ha_state()

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._brightness

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state == STATE_ON

    def turn_on(self, **kwargs):
        """Turn the device on."""
        if ATTR_BRIGHTNESS in kwargs:
            self._brightness = kwargs[ATTR_BRIGHTNESS]

        # Zwave multilevel switches use a range of [0, 99] to control
        # brightness.
        brightness = int((self._brightness / 255) * 99)

        if self._value.node.set_dimmer(self._value.value_id, brightness):
            self._state = STATE_ON

    def turn_off(self, **kwargs):
        """Turn the device off."""
        if self._value.node.set_dimmer(self._value.value_id, 0):
            self._state = STATE_OFF
