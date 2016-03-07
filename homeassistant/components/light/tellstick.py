"""
homeassistant.components.light.tellstick
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Support for Tellstick lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.tellstick/
"""
from datetime import timedelta
import logging
from homeassistant.components.light import ATTR_BRIGHTNESS, Light
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.util import Synchronized

REQUIREMENTS = ['tellcore-py==1.1.2']
SIGNAL_REPETITIONS = 1
MIN_TIME_BETWEEN_CALLS = timedelta(seconds=0.5)
_LOGGER = logging.getLogger(__name__)


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """ Find and return Tellstick lights. """

    import tellcore.telldus as telldus
    from tellcore.library import DirectCallbackDispatcher
    import tellcore.constants as tellcore_constants

    core = telldus.TelldusCore(callback_dispatcher=DirectCallbackDispatcher())
    signal_repetitions = config.get('signal_repetitions', SIGNAL_REPETITIONS)

    switches_and_lights = core.devices()
    lights = []

    for switch in switches_and_lights:
        if switch.methods(tellcore_constants.TELLSTICK_DIM):
            lights.append(TellstickLight(switch, signal_repetitions))

    def _device_event_callback(id_, method, data, cid):
        """ Called from the TelldusCore library to update one device """
        for light_device in lights:
            if light_device.tellstick_device.id == id_:
                # We got the current values so set state directly.
                light_device.set_state(method, data)
                light_device.update_ha_state()
                break

    callback_id = core.register_device_event(_device_event_callback)

    def unload_telldus_lib(event):
        """ Un-register the callback bindings """
        if callback_id is not None:
            core.unregister_callback(callback_id)

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, unload_telldus_lib)

    add_devices_callback(lights)


class TellstickLight(Light):
    """ Represents a Tellstick light. """

    def __init__(self, tellstick_device, signal_repetitions):
        import tellcore.constants as tellcore_constants

        self.tellstick_device = tellstick_device
        self.signal_repetitions = signal_repetitions
        self._brightness = 0

        self.last_sent_command_mask = (tellcore_constants.TELLSTICK_TURNON |
                                       tellcore_constants.TELLSTICK_TURNOFF |
                                       tellcore_constants.TELLSTICK_DIM)
        self.update()

    @property
    def name(self):
        """ Returns the name of the switch if any. """
        return self.tellstick_device.name

    @property
    def is_on(self):
        """ True if switch is on. """
        return self._brightness > 0

    @property
    def brightness(self):
        """ Brightness of this light between 0..255. """
        return self._brightness

    def turn_off(self, **kwargs):
        """ Turns the switch off. """
        self._call_light(0)

    def turn_on(self, **kwargs):
        """ Turns the switch on. """
        brightness = kwargs.get(ATTR_BRIGHTNESS)

        if brightness is None:
            self._brightness = 255
        else:
            self._brightness = brightness

        self._call_light(self._brightness)

    @Synchronized(True)
    def _call_light(self, brightness):
        from tellcore.library import TelldusError
        try:
            for _ in range(self.signal_repetitions):
                if brightness == 0:
                    self.tellstick_device.turn_off()
                else:
                    self.tellstick_device.dim(brightness)
            self._brightness = brightness
            self.update_ha_state()
        except TelldusError:
            _LOGGER.error(TelldusError)

    @Synchronized(True)
    def update(self):
        """ Update state of the light. """
        import tellcore.constants as tellcore_constants
        from tellcore.library import TelldusError

        try:
            last_command = self.tellstick_device.last_sent_command(
                self.last_sent_command_mask)
            last_sent_value = (None if last_command !=
                               tellcore_constants.TELLSTICK_DIM else
                               self.tellstick_device.last_sent_value())
            self.set_state(last_command, last_sent_value)
        except TelldusError:
            _LOGGER.error(TelldusError)

    def set_state(self, last_command, last_sent_value):
        """
        Sets the state depending on last command sent
        :param last_command:
        :param last_sent_value:
        :return:
        """
        import tellcore.constants as tellcore_constants
        if last_command == tellcore_constants.TELLSTICK_TURNON:
            self._brightness = 255
        elif last_command == tellcore_constants.TELLSTICK_TURNOFF:
            self._brightness = 0
        elif (last_sent_value is not None and
              last_command == tellcore_constants.TELLSTICK_DIM):
            self._brightness = last_sent_value

    @property
    def should_poll(self):
        """ Tells Home Assistant not to poll this entity. """
        return False

    @property
    def assumed_state(self):
        """  Tellstick devices are always assumed state """
        return True
