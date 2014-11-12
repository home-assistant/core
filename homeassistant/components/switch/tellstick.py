""" Support for Tellstick switches. """
import logging

from homeassistant.components import ToggleDevice, ATTR_FRIENDLY_NAME

try:
    import tellcore.constants as tc_constants
except ImportError:
    # Don't care for now. Warning will come when get_switches is called.
    pass


# pylint: disable=unused-argument
def get_switches(hass, config):
    """ Find and return Tellstick switches. """
    try:
        import tellcore.telldus as telldus
    except ImportError:
        logging.getLogger(__name__).exception(
            "Failed to import tellcore")
        return []

    core = telldus.TelldusCore()
    switches = core.devices()

    return [TellstickSwitch(switch) for switch in switches]


class TellstickSwitch(ToggleDevice):
    """ represents a Tellstick switch within home assistant. """
    last_sent_command_mask = (tc_constants.TELLSTICK_TURNON |
                              tc_constants.TELLSTICK_TURNOFF)

    def __init__(self, tellstick):
        self.tellstick = tellstick
        self.state_attr = {ATTR_FRIENDLY_NAME: tellstick.name}

    def get_name(self):
        """ Returns the name of the switch if any. """
        return self.tellstick.name

    # pylint: disable=unused-argument
    def turn_on(self, **kwargs):
        """ Turns the switch on. """
        self.tellstick.turn_on()

    # pylint: disable=unused-argument
    def turn_off(self, **kwargs):
        """ Turns the switch off. """
        self.tellstick.turn_off()

    def is_on(self):
        """ True if switch is on. """
        last_command = self.tellstick.last_sent_command(
            self.last_sent_command_mask)

        return last_command == tc_constants.TELLSTICK_TURNON

    def get_state_attributes(self):
        """ Returns optional state attributes. """
        return self.state_attr
