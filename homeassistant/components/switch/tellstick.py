""" Support for Tellstick switches. """
import logging


from homeassistant.const import ATTR_FRIENDLY_NAME
from homeassistant.helpers.device import ToggleDevice
import tellcore.constants as tellcore_constants


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """ Find and return tellstick switches. """
    try:
        import tellcore.telldus as telldus
    except ImportError:
        logging.getLogger(__name__).exception(
            "Failed to import tellcore")
        return

    core = telldus.TelldusCore()
    switches_and_lights = core.devices()

    switches = []

    for switch in switches_and_lights:
        if not switch.methods(tellcore_constants.TELLSTICK_DIM):
            switches.append(TellstickSwitchDevice(switch))

    add_devices_callback(switches)


class TellstickSwitchDevice(ToggleDevice):
    """ represents a Tellstick switch within home assistant. """
    last_sent_command_mask = (tellcore_constants.TELLSTICK_TURNON |
                              tellcore_constants.TELLSTICK_TURNOFF)

    def __init__(self, tellstick):
        self.tellstick = tellstick
        self.state_attr = {ATTR_FRIENDLY_NAME: tellstick.name}

    @property
    def name(self):
        """ Returns the name of the switch if any. """
        return self.tellstick.name

    @property
    def state_attributes(self):
        """ Returns optional state attributes. """
        return self.state_attr

    @property
    def is_on(self):
        """ True if switch is on. """
        last_command = self.tellstick.last_sent_command(
            self.last_sent_command_mask)

        return last_command == tellcore_constants.TELLSTICK_TURNON

    def turn_on(self, **kwargs):
        """ Turns the switch on. """
        self.tellstick.turn_on()

    def turn_off(self, **kwargs):
        """ Turns the switch off. """
        self.tellstick.turn_off()
