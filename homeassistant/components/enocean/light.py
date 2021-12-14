"""Support for EnOcean light sources."""
import math

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    SUPPORT_BRIGHTNESS,
    LightEntity,
)

from .device import EnOceanEntity

SUPPORT_ENOCEAN = SUPPORT_BRIGHTNESS


class EnOceanLight(EnOceanEntity, LightEntity):
    """Representation of an EnOcean light source."""

    def __init__(self, sender_id, dev_id, dev_name):
        """Initialize the EnOcean light source."""
        super().__init__(dev_id, dev_name)
        self._on_state = False
        self._brightness = 50
        self._sender_id = sender_id

    @property
    def name(self):
        """Return the name of the device if any."""
        return self.dev_name

    @property
    def brightness(self):
        """Brightness of the light.

        This method is optional. Removing it indicates to Home Assistant
        that brightness is not supported for this light.
        """
        return self._brightness

    @property
    def is_on(self):
        """If light is on."""
        return self._on_state

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_ENOCEAN

    def turn_on(self, **kwargs):
        """Turn the light source on or sets a specific dimmer value."""
        if (brightness := kwargs.get(ATTR_BRIGHTNESS)) is not None:
            self._brightness = brightness

        bval = math.floor(self._brightness / 256.0 * 100.0)
        if bval == 0:
            bval = 1
        command = [0xA5, 0x02, bval, 0x01, 0x09]
        command.extend(self._sender_id)
        command.extend([0x00])
        self.send_command(command, [], 0x01)
        self._on_state = True

    def turn_off(self, **kwargs):
        """Turn the light source off."""
        command = [0xA5, 0x02, 0x00, 0x01, 0x09]
        command.extend(self._sender_id)
        command.extend([0x00])
        self.send_command(command, [], 0x01)
        self._on_state = False

    def value_changed(self, packet):
        """Update the internal state of this device.

        Dimmer devices like Eltako FUD61 send telegram in different RORGs.
        We only care about the 4BS (0xA5).
        """
        if packet.data[0] == 0xA5 and packet.data[1] == 0x02:
            val = packet.data[2]
            self._brightness = math.floor(val / 100.0 * 256.0)
            self._on_state = bool(val != 0)
            self.schedule_update_ha_state()
