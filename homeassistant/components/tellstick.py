"""
Tellstick Component.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/tellstick/
"""
import logging
import threading

import voluptuous as vol

from homeassistant.helpers import discovery
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.helpers.entity import Entity

DOMAIN = 'tellstick'

REQUIREMENTS = ['tellcore-py==1.1.2']

_LOGGER = logging.getLogger(__name__)

ATTR_SIGNAL_REPETITIONS = 'signal_repetitions'
DEFAULT_SIGNAL_REPETITIONS = 1

ATTR_DISCOVER_DEVICES = 'devices'
ATTR_DISCOVER_CONFIG = 'config'

# Use a global tellstick domain lock to avoid getting Tellcore errors when
# calling concurrently.
TELLSTICK_LOCK = threading.Lock()

# A TellstickRegistry that keeps a map from tellcore_id to the corresponding
# tellcore_device and HA device (entity).
TELLCORE_REGISTRY = None

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(ATTR_SIGNAL_REPETITIONS,
                     default=DEFAULT_SIGNAL_REPETITIONS): vol.Coerce(int),
    }),
}, extra=vol.ALLOW_EXTRA)


def _discover(hass, config, found_tellcore_devices, component_name):
    """Setup and send the discovery event."""
    if not len(found_tellcore_devices):
        return

    _LOGGER.info(
        "Discovered %d new %s devices", len(found_tellcore_devices), component_name)

    signal_repetitions = config[DOMAIN].get(ATTR_SIGNAL_REPETITIONS)

    discovery.load_platform(hass, component_name, DOMAIN, {
        ATTR_DISCOVER_DEVICES: found_tellcore_devices,
        ATTR_DISCOVER_CONFIG: signal_repetitions}, config)


def setup(hass, config):
    """Setup the Tellstick component."""
    # pylint: disable=global-statement, import-error
    global TELLCORE_REGISTRY

    import tellcore.telldus as telldus
    import tellcore.constants as tellcore_constants
    from tellcore.library import DirectCallbackDispatcher

    core = telldus.TelldusCore(callback_dispatcher=DirectCallbackDispatcher())

    TELLCORE_REGISTRY = TellstickRegistry(hass, core)

    tellcore_devices = core.devices()

    # Register devices
    TELLCORE_REGISTRY.register_tellcore_devices(tellcore_devices)

    # Discover the switches
    _discover(hass, config, [tellcore_switch.id for tellcore_switch in
                             tellcore_devices if not tellcore_switch.methods(
                                 tellcore_constants.TELLSTICK_DIM)],
              'switch')

    # Discover the lights
    _discover(hass, config, [tellcore_light.id for tellcore_light in
                             tellcore_devices if tellcore_light.methods(
                                 tellcore_constants.TELLSTICK_DIM)],
              'light')

    return True


class TellstickRegistry(object):
    """Handle everything around Tellstick callbacks.

    Keeps a map device ids to the tellcore device object, and
    another to the HA device objects (entities).

    Also responsible for registering / cleanup of callbacks.

    All device specific logic should be elsewhere (Entities).
    """

    def __init__(self, hass, tellcore_lib):
        """Initialize the Tellstick mappings and callbacks."""
        # used when map callback device id to ha entities.
        self._id_to_ha_device_map = {}
        self._id_to_tellcore_device_map = {}
        self._setup_tellcore_callback(hass, tellcore_lib)

    def _tellcore_event_callback(self, tellcore_id, tellcore_command, data, cid):
        """Handle the actual callback from Tellcore."""
        ha_device = self._id_to_ha_device_map.get(tellcore_id, None)
        if ha_device is not None:
            ha_device.set_tellstick_state(tellcore_command, data)
            ha_device.schedule_update_ha_state()

    def _setup_tellcore_callback(self, hass, tellcore_lib):
        """Register the callback handler."""
        callback_id = tellcore_lib.register_device_event(self._tellcore_event_callback)

        def clean_up_callback(event):
            """Unregister the callback bindings."""
            if callback_id is not None:
                tellcore_lib.unregister_callback(callback_id)

        hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, clean_up_callback)

    def register_ha_device(self, tellcore_id, ha_device):
        """Register a new HA device to receive callback updates."""
        self._id_to_ha_device_map[tellcore_id] = ha_device

    def register_tellcore_devices(self, tellcore_devices):
        """Register a list of devices."""
        self._id_to_tellcore_device_map.update(
            {tellcore_device.id: tellcore_device for tellcore_device in tellcore_devices})

    def get_tellcore_device(self, tellcore_id):
        """Return a device by tellcore_id."""
        return self._id_to_tellcore_device_map.get(tellcore_id, None)


class TellstickDevice(Entity):
    """Representation of a Tellstick device.

    Contains the common logic for all Tellstick devices.
    """

    def __init__(self, tellcore_device, signal_repetitions):
        """Initalize the Tellstick device."""
        self._signal_repetitions = signal_repetitions
        self._state = None
        self._tellcore_device = tellcore_device
        # Add to id to HA device mapping
        TELLCORE_REGISTRY.register_ha_device(tellcore_device.id, self)
        # Query tellcore for the current state
        self.update()

    @property
    def should_poll(self):
        """Tell Home Assistant not to poll this device."""
        return False

    @property
    def assumed_state(self):
        """Tellstick devices are always assumed state."""
        return True

    @property
    def name(self):
        """Return the name of the device if any."""
        return self._tellcore_device.name

    def set_tellstick_state(self, last_command_sent, last_data_sent):
        """Set the private device state."""
        raise NotImplementedError(
            "set_tellstick_state needs to be implemented.")

    def _send_tellstick_command(self, command, data):
        """Do the actual call to the tellstick device."""
        raise NotImplementedError(
            "_send_tellstick_command needs to be implemented.")

    def call_tellstick(self, command, data=None):
        """Send a command to the device."""
        from tellcore.library import TelldusError
        with TELLSTICK_LOCK:
            try:
                for _ in range(self._signal_repetitions):
                    self._send_tellstick_command(command, data)
                # Update the internal state
                self.set_tellstick_state(command, data)
                self.update_ha_state()
            except TelldusError:
                _LOGGER.error(TelldusError)

    def update(self):
        """Poll the current state of the device."""
        import tellcore.constants as tellcore_constants
        from tellcore.library import TelldusError
        try:
            last_command = self._tellcore_device.last_sent_command(
                tellcore_constants.TELLSTICK_TURNON |
                tellcore_constants.TELLSTICK_TURNOFF |
                tellcore_constants.TELLSTICK_DIM
            )
            last_value = self._tellcore_device.last_sent_value()
            self.set_tellstick_state(last_command, last_value)
        except TelldusError:
            _LOGGER.error(TelldusError)
