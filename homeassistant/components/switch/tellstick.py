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

from homeassistant.const import (EVENT_HOMEASSISTANT_STOP,
                                 ATTR_FRIENDLY_NAME)
from homeassistant.helpers.entity import ToggleEntity
import tellcore.constants as tellcore_constants
from tellcore.library import DirectCallbackDispatcher
SINGAL_REPETITIONS = 1

REQUIREMENTS = ['tellcore-py==1.1.2']


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """ Find and return Tellstick switches. """
    try:
        import tellcore.telldus as telldus
    except ImportError:
        logging.getLogger(__name__).exception(
            "Failed to import tellcore")
        return

    core = telldus.TelldusCore(callback_dispatcher=DirectCallbackDispatcher())

    signal_repetitions = config.get('signal_repetitions', SINGAL_REPETITIONS)

    switches_and_lights = core.devices()

    switches = []

    for switch in switches_and_lights:
        if not switch.methods(tellcore_constants.TELLSTICK_DIM):
            switches.append(
                TellstickSwitchDevice(switch, signal_repetitions))

    def _device_event_callback(id_, method, data, cid):
        """ Called from the TelldusCore library to update one device """
        for switch_device in switches:
            if switch_device.tellstick_device.id == id_:
                switch_device.update_ha_state()
                break

    callback_id = core.register_device_event(_device_event_callback)

    def unload_telldus_lib(event):
        """ Un-register the callback bindings """
        if callback_id is not None:
            core.unregister_callback(callback_id)

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, unload_telldus_lib)

    add_devices_callback(switches)


class TellstickSwitchDevice(ToggleEntity):
    """ Represents a Tellstick switch. """
    last_sent_command_mask = (tellcore_constants.TELLSTICK_TURNON |
                              tellcore_constants.TELLSTICK_TURNOFF)

    def __init__(self, tellstick_device, signal_repetitions):
        self.tellstick_device = tellstick_device
        self.state_attr = {ATTR_FRIENDLY_NAME: tellstick_device.name}
        self.signal_repetitions = signal_repetitions

    @property
    def should_poll(self):
        """ Tells Home Assistant not to poll this entity. """
        return False

    @property
    def name(self):
        """ Returns the name of the switch if any. """
        return self.tellstick_device.name

    @property
    def state_attributes(self):
        """ Returns optional state attributes. """
        return self.state_attr

    @property
    def is_on(self):
        """ True if switch is on. """
        last_command = self.tellstick_device.last_sent_command(
            self.last_sent_command_mask)

        return last_command == tellcore_constants.TELLSTICK_TURNON

    def turn_on(self, **kwargs):
        """ Turns the switch on. """
        for _ in range(self.signal_repetitions):
            self.tellstick_device.turn_on()
        self.update_ha_state()

    def turn_off(self, **kwargs):
        """ Turns the switch off. """
        for _ in range(self.signal_repetitions):
            self.tellstick_device.turn_off()
        self.update_ha_state()
