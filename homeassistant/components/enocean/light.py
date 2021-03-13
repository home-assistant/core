"""Support for EnOcean light sources."""
import math

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.light import (ATTR_BRIGHTNESS, PLATFORM_SCHEMA,
                                            SUPPORT_BRIGHTNESS, LightEntity)
from homeassistant.const import CONF_ID, CONF_NAME

from .device import EnOceanEntity

CONF_SENDER_ID = "sender_id"
CONF_TEACH_IN = "teach_in"

DEFAULT_NAME = "EnOcean Light"
DEFAULT_TEACH_IN = "False"
SUPPORT_ENOCEAN = SUPPORT_BRIGHTNESS

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_ID, default=[]): vol.All(cv.ensure_list, [vol.Coerce(int)]),
        vol.Required(CONF_SENDER_ID): vol.All(cv.ensure_list, [vol.Coerce(int)]),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_TEACH_IN, default=DEFAULT_TEACH_IN): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the EnOcean light platform."""
    sender_id = config.get(CONF_SENDER_ID)
    dev_name = config.get(CONF_NAME)
    dev_id = config.get(CONF_ID)
    teach_in = config.get(CONF_TEACH_IN)

    add_entities([EnOceanLight(sender_id, dev_id, dev_name, teach_in)])


class EnOceanLight(EnOceanEntity, LightEntity):
    """Representation of an EnOcean light source."""

    def __init__(self, sender_id, dev_id, dev_name, teach_in):
        """Initialize the EnOcean light source."""
        super().__init__(dev_id, dev_name)
        self._on_state = False
        self._brightness = 256
        self._sender_id = sender_id
        self._teach_in = teach_in
        self._external_value_changed = False

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
        if self._external_value_changed:
            self._on_state = True
            self._external_value_changed = False
            return
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        if brightness is not None:
            self._brightness = brightness

        bval = math.ceil(self._brightness / 256.0 * 100.0)

        if self._teach_in == "True":
            command = [0xA5, 0xE0, 0x40, 0x0D, 0x80]
        else:
            command = [0xA5, 0x02, bval, 0x01, 0x09]
        command.extend(self._sender_id)
        command.extend([0x00])
        self.send_command(command, [], 0x01)
        self._on_state = True

    def turn_off(self, **kwargs):
        """Turn the light source off."""
        if self._external_value_changed:
            self._on_state = False
            self._external_value_changed = False
            return
        command = [0xA5, 0x02, 0x00, 0x01, 0x08]
        command.extend(self._sender_id)
        command.extend([0x00])
        self.send_command(command, [], 0x01)
        self._on_state = False

    def value_changed(self, packet):
        """Update the internal state of this device.

        Dimmer devices like Eltako FUD61 send telegram in different RORGs.
        We only care about the 4BS (0xA5).

        Eltako series 14 send telegram RPS (0xF6) if its a  simple on/off actuator,
        dimming actuators send in 4BS (0xA5).
        On/Off actuators are handled in the automation.yaml as a binary sensor.
        Without self._external_value_changed you will get an infinite loop between
        FAM14 and Home Assistant.
        """
        if packet.data[0] == 0xF6:
            self._external_value_changed = True
        if packet.data[0] == 0xA5 and packet.data[1] == 0x02:
            val = packet.data[2]
            self._brightness = math.floor(val / 100.0 * 256.0)
            self._on_state = bool(val != 0)
            self.schedule_update_ha_state()
