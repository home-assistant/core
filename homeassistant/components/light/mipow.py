"""
Support for mipow lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.mipow/
"""

import logging
from homeassistant.components.light import (
    ATTR_BRIGHTNESS, ATTR_RGB_COLOR, ATTR_EFFECT, EFFECT_RAINBOW, EFFECT_CANDLE, ATTR_FLASH, FLASH_LONG, FLASH_SHORT, Light)
from homeassistant.loader import get_component
_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['pygatt==3.0.0']

# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Add device specified by serial number."""
    import pygatt
    serial = config['serial']
    name = config.get('name')
    bulb = Mipow(serial, name)

    add_devices_callback([bulb])


class Mipow(Light):
    """Representation of a mipow light."""

    def __init__(self, serial, name=None):
        """Initialize the light."""
        if name is not None:
            self._name = name
        else:
            self._name = serial

        self._serial = serial
        self._adapter = None
        self._connection = None
        try:
            self.update()
        except:
            self._rgb_color = [0, 0, 0]
            self._rgb_bright = [0]

    def update(self):
        """Read back the device state."""
        self._rgb_color = self.rgb_color
        self._rgb_bright = self.rgb_bright

    def _start_adapter(self):
        if self._adapter is not None:
            self._adapter.stop()

        adapter = pygatt.backends.GATTToolBackend()
        adapter.start()

        self._adapter = adapter

        return adapter

    def _stop_adapter(self):
        self._adapter.stop()
        

    def isconnected(self):
        if device._connected == True:
            if adapter.address == self._serial:
                return True
        else:
            return False
    def connect(self):
        
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
# Get device status from gattools
        self._connection = self.connect()

        device_status = self._connection.char_read("0000fffc-0000-1000-8000-00805f9b34fb")

#Convert byte array into int list
        device_colors = [x for x in device_status]

# Remove first element as it's the brightness
        device_colors.pop(0)

# Assign to instance for later use
        self._rgb_color = device_colors


# Return list for ha use
        return self._rgb_color
    @property
    def rgb_bright(self):
# Get device status from gattools
        self._connection = self.connect()

        device_status = self._connection.char_read("0000fffc-0000-1000-8000-00805f9b34fb")

#Convert byte array into int list
        device_bright = [x for x in device_status]

# Remove first element as it's the brightness
        device_bright.pop()
        device_bright.pop()
        device_bright.pop()
# Assign to instance for later use
        self._rgb_bright = device_bright

# Return list for ha use
        return self._rgb_bright
    @property
    def brightness(self):
        return self._rgb_bright
    @property
    def is_on(self):
        """Check whether any of the LEDs colors are non-zero."""
        return sum(self._rgb_color)+sum(self._rgb_bright) > 0

    def turn_on(self, **kwargs):
        """Turn the device on."""
        self._connection = self.connect()

        if ATTR_BRIGHTNESS in kwargs and ATTR_RGB_COLOR in kwargs and not ATTR_FLASH in kwargs:
            self._rgb_color = [x for x in kwargs[ATTR_RGB_COLOR]]
            brgb = [kwargs[ATTR_BRIGHTNESS], self._rgb_color[0], self._rgb_color[1], self._rgb_color[2]]

            self._connection.char_write_handle(0x0025, brgb)
        elif ATTR_RGB_COLOR in kwargs and not ATTR_BRIGHTNESS in kwargs and not ATTR_FLASH in kwargs:
            self._rgb_color = [x for x in kwargs[ATTR_RGB_COLOR]]
            brgb = [0]
            brgb.append(self._rgb_color[0])
            brgb.append(self._rgb_color[1])
            brgb.append(self._rgb_color[2])

            self._connection.char_write_handle(0x0025, brgb)
        elif ATTR_BRIGHTNESS in kwargs and not ATTR_RGB_COLOR in kwargs and not ATTR_FLASH in kwargs:
            brgb = [kwargs[ATTR_BRIGHTNESS], 0, 0, 0]
            self._rgb_color = [255, 255, 255]
            self._connection.char_write_handle(0x0025, brgb)
        effect = kwargs.get(ATTR_EFFECT)
        if effect == EFFECT_RAINBOW:
                val = bytearray([0x00, 0x00, 0x00, 0x00, 0x02, 0x00, 0x14, 0x00])
                self._connection.char_write_handle(0x0023, val)
        if effect == EFFECT_CANDLE:
                val = bytearray([0x00, 0x00, 0x00, 0x00, 0x02, 0x00, 0x14, 0x00])
                self._connection.char_write_handle(0x0023, val)
        if ATTR_FLASH in kwargs and ATTR_RGB_COLOR in kwargs:
                self._rgb_color = [x for x in kwargs[ATTR_RGB_COLOR]]
                bri = 0
                red = self._rgb_color[0]
                green = self._rgb_color[1]
                blue = self._rgb_color[2]
                flash = kwargs.get(ATTR_FLASH)
                if flash == FLASH_LONG:
                    speed = 0x14
                if flash == FLASH_SHORT:
                    speed = 0x00
                mode = 00
                val = bytearray([bri, red, green, blue, mode, 0x00, speed, 0x00])
                self._connection.char_write_handle(0x0023, val)
        elif not self.is_on:

            self._connection.char_write_handle(0x0025, [255, 0, 0, 0])


    def turn_off(self, **kwargs):
        """Turn the device off."""
        self._connection = self.connect()
        self._connection.char_write_handle(0x0025, [00, 00, 00, 00])


