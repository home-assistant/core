"""
Support for Tellstick switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.tellstick/
"""
import logging

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.helpers.entity import ToggleEntity

SIGNAL_REPETITIONS = 1
REQUIREMENTS = ['tellcore-py==1.1.2']
_LOGGER = logging.getLogger(__name__)


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Setup Tellstick switches."""
    import tellcore.telldus as telldus
    import tellcore.constants as tellcore_constants
    from tellcore.library import DirectCallbackDispatcher

    core = telldus.TelldusCore(callback_dispatcher=DirectCallbackDispatcher())
    signal_repetitions = config.get('signal_repetitions', SIGNAL_REPETITIONS)
    switches_and_lights = core.devices()

    switches = []
    for switch in switches_and_lights:
        if not switch.methods(tellcore_constants.TELLSTICK_DIM):
            switches.append(
                TellstickSwitchDevice(switch, signal_repetitions))

    def _device_event_callback(id_, method, data, cid):
        """Called from the TelldusCore library to update one device."""
        for switch_device in switches:
            if switch_device.tellstick_device.id == id_:
                switch_device.update_ha_state()
                break

    callback_id = core.register_device_event(_device_event_callback)

    def unload_telldus_lib(event):
        """Un-register the callback bindings."""
        if callback_id is not None:
            core.unregister_callback(callback_id)

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, unload_telldus_lib)

    add_devices_callback(switches)


class TellstickSwitchDevice(ToggleEntity):
    """Representation of a Tellstick switch."""

    def __init__(self, tellstick_device, signal_repetitions):
        """Initialize the Tellstick switch."""
        import tellcore.constants as tellcore_constants

        self.tellstick_device = tellstick_device
        self.signal_repetitions = signal_repetitions

        self.last_sent_command_mask = (tellcore_constants.TELLSTICK_TURNON |
                                       tellcore_constants.TELLSTICK_TURNOFF)

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def assumed_state(self):
        """The Tellstick devices are always assumed state."""
        return True

    @property
    def name(self):
        """Return the name of the switch if any."""
        return self.tellstick_device.name

    @property
    def is_on(self):
        """Return true if switch is on."""
        import tellcore.constants as tellcore_constants

        last_command = self.tellstick_device.last_sent_command(
            self.last_sent_command_mask)

        return last_command == tellcore_constants.TELLSTICK_TURNON

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        for _ in range(self.signal_repetitions):
            self.tellstick_device.turn_on()
        self.update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the switch off."""
        for _ in range(self.signal_repetitions):
            self.tellstick_device.turn_off()
        self.update_ha_state()
