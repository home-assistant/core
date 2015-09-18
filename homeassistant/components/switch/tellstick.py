"""
homeassistant.components.switch.tellstick
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Support for Tellstick switches.

Because the tellstick sends its actions via radio and from most
receivers it's impossible to know if the signal was received or not.
Therefore you can configure the switch to try to send each signal repeatedly
with the config parameter signal_repetitions (default is 1).
signal_repetitions: 3
"""
import logging


from homeassistant.const import ATTR_FRIENDLY_NAME
from homeassistant.helpers.entity import ToggleEntity
import tellcore.constants as tellcore_constants

SINGAL_REPETITIONS = 1

REQUIREMENTS = ['tellcore-py==1.0.4']


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """ Find and return Tellstick switches. """
    try:
        import tellcore.telldus as telldus
    except ImportError:
        logging.getLogger(__name__).exception(
            "Failed to import tellcore")
        return

    signal_repetitions = config.get('signal_repetitions', SINGAL_REPETITIONS)

    core = telldus.TelldusCore()
    switches_and_lights = core.devices()

    switches = []

    for switch in switches_and_lights:
        if not switch.methods(tellcore_constants.TELLSTICK_DIM):
            switches.append(TellstickSwitchDevice(switch, signal_repetitions))

    add_devices_callback(switches)


class TellstickSwitchDevice(ToggleEntity):
    """ Represents a Tellstick switch. """
    last_sent_command_mask = (tellcore_constants.TELLSTICK_TURNON |
                              tellcore_constants.TELLSTICK_TURNOFF)

    def __init__(self, tellstick, signal_repetitions):
        self.tellstick = tellstick
        self.state_attr = {ATTR_FRIENDLY_NAME: tellstick.name}
        self.signal_repetitions = signal_repetitions

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
        for _ in range(self.signal_repetitions):
            self.tellstick.turn_on()

    def turn_off(self, **kwargs):
        """ Turns the switch off. """
        for _ in range(self.signal_repetitions):
            self.tellstick.turn_off()
