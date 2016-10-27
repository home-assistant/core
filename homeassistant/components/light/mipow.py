"""
Support for mipow lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.mipow/
"""

import logging
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ATTR_FLASH,
    ATTR_RGB_COLOR,
    EFFECT_COLORLOOP,
    EFFECT_RAINBOW,
    EFFECT_CANDLE,
    FLASH_LONG,
    FLASH_SHORT,
    SUPPORT_BRIGHTNESS,
    SUPPORT_EFFECT, SUPPORT_FLASH, SUPPORT_RGB_COLOR,
    Light,
)
_LOGGER = logging.getLogger(__name__)
CHARNAME = "0000fffc-0000-1000-8000-00805f9b34fb"
REQUIREMENTS = ['pygatt[GATTTOOL]==3.0.0']
# pylint: disable=unused-argument
SUPPORT_MIPOW = (SUPPORT_BRIGHTNESS | SUPPORT_EFFECT | SUPPORT_FLASH |
                 SUPPORT_RGB_COLOR)


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Add device specified by serial number."""
    serial = config['serial']
    name = config.get('name')
    bulb = Mipow(serial, name)

    add_devices_callback([bulb])


class Mipow(Light):
    """Main class."""

    def __init__(self, serial, name=None):
        """Initialize the light."""
        from pygatt.exceptions import NotificationTimeout
        if name is not None:
            self._name = name
        else:
            self._name = serial

        self._serial = serial
        self._adapter = None
        self._connection = None
        try:
            self.update()
        except NotificationTimeout:
            self._rgb_color = [0, 0, 0]
            self._rgb_bright = [0]

    def update(self):
        """Read device state."""
        self._connection = self.connect()

        device_state = list(self._connection.char_read(CHARNAME))

        self._rgb_bright = device_state[:-3]
        self._rgb_color = device_state[1:]

    def _start_adapter(self):
        """Start the adapter."""
        import pygatt
        if self._adapter is not None:
            self._adapter.stop()

        adapter = pygatt.backends.GATTToolBackend()
        adapter.start()

        self._adapter = adapter

        return adapter

    def _stop_adapter(self):
        """Stop the adapter."""
        self._adapter.stop()

    def connect(self):
        """Connect to lamp."""
        import pygatt
        if self._connection is not None:
            if self._connection._connected:
                return self._connection
        else:
            if self._adapter is not None:
                self._adapter.stop()

            adapter = pygatt.backends.GATTToolBackend()
            adapter.start()

            self._adapter = adapter
            self._connection = self._adapter.connect(self._serial)
            return self._connection

    @property
    def should_poll(self):
        """Polling needed."""
        return True

    @property
    def name(self):
        """Return the name of the light."""
        return self._name

    @property
    def rgb_color(self):
        """Read rgb color."""

        return self._rgb_color

    @property
    def rgb_bright(self):
        """Read brightness."""

        return self._rgb_bright

    @property
    def brightness(self):
        """Return brightness."""
        return self._rgb_bright

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_MIPOW

    @property
    def is_on(self):
        """Check whether any of the LEDs colors are non-zero."""
        return sum(self._rgb_color)+sum(self._rgb_bright) > 0

    def turn_on(self, **kwargs):
        """Turn the device on."""
        self._connection = self.connect()
        cm = ([0x00, 0x00, 0x14, 0x01])
        cmd = ([0x00, 0x00, 0x14, 0x02])
        if (ATTR_RGB_COLOR in kwargs):
                self._rgb_color = [x for x in kwargs[ATTR_RGB_COLOR]]
                brgb = [0]
                brgb.append(self._rgb_color[0])
                brgb.append(self._rgb_color[1])
                brgb.append(self._rgb_color[2])
        elif ATTR_BRIGHTNESS in kwargs:
                brgb = ([kwargs[ATTR_BRIGHTNESS], 0, 0, 0])
        effect = kwargs.get(ATTR_EFFECT)
        if ATTR_EFFECT in kwargs:
            if effect == EFFECT_COLORLOOP:
                mode = 0x03
            elif effect == EFFECT_RAINBOW:
                mode = 0x02
            elif effect == EFFECT_CANDLE:
                mode = 0x04
            outp = ([0xff, 0x00, 0x00, 0x00, mode, 0x00, 0x14, 0x00])
            self._connection.char_write_handle(0x0023, outp)
        if ATTR_FLASH in kwargs:
            flash = kwargs.get(ATTR_FLASH)
            if flash == FLASH_LONG:
                outp = brgb + cmd
                self._connection.char_write_handle(0x0023, outp)
            if flash == FLASH_SHORT:
                outp = brgb + cm
                self._connection.char_write_handle(0x0023, outp)
        elif not self.is_on:
            self._connection.char_write_handle(0x0025, [255, 0, 0, 0])

    def turn_off(self, **kwargs):
        """Turn the device off."""
        self._connection = self.connect()
        self._connection.char_write_handle(0x0025, [00, 00, 00, 00])
