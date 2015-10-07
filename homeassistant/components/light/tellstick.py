"""
homeassistant.components.light.tellstick
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Support for Tellstick lights.
"""
import logging
# pylint: disable=no-name-in-module, import-error
from homeassistant.components.light import Light, ATTR_BRIGHTNESS
from homeassistant.const import (EVENT_HOMEASSISTANT_STOP,
                                 ATTR_FRIENDLY_NAME)
import tellcore.constants as tellcore_constants
from tellcore.library import DirectCallbackDispatcher
REQUIREMENTS = ['tellcore-py==1.1.2']


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """ Find and return Tellstick lights. """

    try:
        import tellcore.telldus as telldus
    except ImportError:
        logging.getLogger(__name__).exception(
            "Failed to import tellcore")
        return []

    core = telldus.TelldusCore(callback_dispatcher=DirectCallbackDispatcher())

    switches_and_lights = core.devices()
    lights = []

    for switch in switches_and_lights:
        if switch.methods(tellcore_constants.TELLSTICK_DIM):
            lights.append(TellstickLight(switch))

    def _device_event_callback(id_, method, data, cid):
        """ Called from the TelldusCore library to update one device """
        for light_device in lights:
            if light_device.tellstick_device.id == id_:
                # Execute the update in another thread
                light_device.update_ha_state(True)
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
    last_sent_command_mask = (tellcore_constants.TELLSTICK_TURNON |
                              tellcore_constants.TELLSTICK_TURNOFF |
                              tellcore_constants.TELLSTICK_DIM |
                              tellcore_constants.TELLSTICK_UP |
                              tellcore_constants.TELLSTICK_DOWN)

    def __init__(self, tellstick_device):
        self.tellstick_device = tellstick_device
        self.state_attr = {ATTR_FRIENDLY_NAME: tellstick_device.name}
        self._brightness = 0

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
        self.tellstick_device.turn_off()
        self._brightness = 0
        self.update_ha_state()

    def turn_on(self, **kwargs):
        """ Turns the switch on. """
        brightness = kwargs.get(ATTR_BRIGHTNESS)

        if brightness is None:
            self._brightness = 255
        else:
            self._brightness = brightness

        self.tellstick_device.dim(self._brightness)
        self.update_ha_state()

    def update(self):
        """ Update state of the light. """
        last_command = self.tellstick_device.last_sent_command(
            self.last_sent_command_mask)

        if last_command == tellcore_constants.TELLSTICK_TURNON:
            self._brightness = 255
        elif last_command == tellcore_constants.TELLSTICK_TURNOFF:
            self._brightness = 0
        elif (last_command == tellcore_constants.TELLSTICK_DIM or
              last_command == tellcore_constants.TELLSTICK_UP or
              last_command == tellcore_constants.TELLSTICK_DOWN):
            last_sent_value = self.tellstick_device.last_sent_value()
            if last_sent_value is not None:
                self._brightness = last_sent_value

    @property
    def should_poll(self):
        """ Tells Home Assistant not to poll this entity. """
        return False
