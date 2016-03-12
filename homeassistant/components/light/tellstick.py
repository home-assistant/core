"""
Support for Tellstick lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.tellstick/
"""
from homeassistant.components.light import ATTR_BRIGHTNESS, Light
from homeassistant.const import EVENT_HOMEASSISTANT_STOP

REQUIREMENTS = ['tellcore-py==1.1.2']
SIGNAL_REPETITIONS = 1


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Setup Tellstick lights."""
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
        """Called from the TelldusCore library to update one device."""
        for light_device in lights:
            if light_device.tellstick_device.id == id_:
                # Execute the update in another thread
                light_device.update_ha_state(True)
                break

    callback_id = core.register_device_event(_device_event_callback)

    def unload_telldus_lib(event):
        """Un-register the callback bindings."""
        if callback_id is not None:
            core.unregister_callback(callback_id)

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, unload_telldus_lib)

    add_devices_callback(lights)


class TellstickLight(Light):
    """Representation of a Tellstick light."""

    def __init__(self, tellstick_device, signal_repetitions):
        """Initialize the light."""
        import tellcore.constants as tellcore_constants

        self.tellstick_device = tellstick_device
        self.signal_repetitions = signal_repetitions
        self._brightness = 0

        self.last_sent_command_mask = (tellcore_constants.TELLSTICK_TURNON |
                                       tellcore_constants.TELLSTICK_TURNOFF |
                                       tellcore_constants.TELLSTICK_DIM |
                                       tellcore_constants.TELLSTICK_UP |
                                       tellcore_constants.TELLSTICK_DOWN)
        self.update()

    @property
    def name(self):
        """Return the name of the switch if any."""
        return self.tellstick_device.name

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._brightness > 0

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._brightness

    def turn_off(self, **kwargs):
        """Turn the switch off."""
        for _ in range(self.signal_repetitions):
            self.tellstick_device.turn_off()
        self._brightness = 0
        self.update_ha_state()

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        brightness = kwargs.get(ATTR_BRIGHTNESS)

        if brightness is None:
            self._brightness = 255
        else:
            self._brightness = brightness

        for _ in range(self.signal_repetitions):
            self.tellstick_device.dim(self._brightness)
        self.update_ha_state()

    def update(self):
        """Update state of the light."""
        import tellcore.constants as tellcore_constants

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
        """No polling needed."""
        return False

    @property
    def assumed_state(self):
        """Tellstick devices are always assumed state."""
        return True
