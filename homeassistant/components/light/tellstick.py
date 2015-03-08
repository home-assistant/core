""" Support for Tellstick lights. """
import logging
# pylint: disable=no-name-in-module, import-error
from homeassistant.components.light import ATTR_BRIGHTNESS
from homeassistant.const import ATTR_FRIENDLY_NAME
from homeassistant.helpers.device import ToggleDevice
import tellcore.constants as tellcore_constants


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """ Find and return tellstick lights. """

    try:
        import tellcore.telldus as telldus
    except ImportError:
        logging.getLogger(__name__).exception(
            "Failed to import tellcore")
        return []

    core = telldus.TelldusCore()
    switches_and_lights = core.devices()
    lights = []

    for switch in switches_and_lights:
        if switch.methods(tellcore_constants.TELLSTICK_DIM):
            lights.append(TellstickLight(switch))
    add_devices_callback(lights)


class TellstickLight(ToggleDevice):
    """ Represents a tellstick light """
    last_sent_command_mask = (tellcore_constants.TELLSTICK_TURNON |
                              tellcore_constants.TELLSTICK_TURNOFF |
                              tellcore_constants.TELLSTICK_DIM |
                              tellcore_constants.TELLSTICK_UP |
                              tellcore_constants.TELLSTICK_DOWN)

    def __init__(self, tellstick):
        self.tellstick = tellstick
        self.state_attr = {ATTR_FRIENDLY_NAME: tellstick.name}
        self.brightness = 0

    @property
    def name(self):
        """ Returns the name of the switch if any. """
        return self.tellstick.name

    @property
    def is_on(self):
        """ True if switch is on. """
        return self.brightness > 0

    def turn_off(self, **kwargs):
        """ Turns the switch off. """
        self.tellstick.turn_off()
        self.brightness = 0

    def turn_on(self, **kwargs):
        """ Turns the switch on. """
        brightness = kwargs.get(ATTR_BRIGHTNESS)

        if brightness is None:
            self.brightness = 255
        else:
            self.brightness = brightness

        self.tellstick.dim(self.brightness)

    @property
    def state_attributes(self):
        """ Returns optional state attributes. """
        attr = {
            ATTR_FRIENDLY_NAME: self.name
        }

        attr[ATTR_BRIGHTNESS] = int(self.brightness)

        return attr

    def update(self):
        """ Update state of the light. """
        last_command = self.tellstick.last_sent_command(
            self.last_sent_command_mask)

        if last_command == tellcore_constants.TELLSTICK_TURNON:
            self.brightness = 255
        elif last_command == tellcore_constants.TELLSTICK_TURNOFF:
            self.brightness = 0
        elif (last_command == tellcore_constants.TELLSTICK_DIM or
              last_command == tellcore_constants.TELLSTICK_UP or
              last_command == tellcore_constants.TELLSTICK_DOWN):
            last_sent_value = self.tellstick.last_sent_value()
            if last_sent_value is not None:
                self.brightness = last_sent_value
