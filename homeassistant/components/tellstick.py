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


def _discover(hass, config, component_name, found_tellcore_devices):
    """Setup and send the discovery event."""
    if not len(found_tellcore_devices):
        return

    _LOGGER.info("Discovered %d new %s devices", len(found_tellcore_devices),
                 component_name)

    signal_repetitions = config[DOMAIN].get(ATTR_SIGNAL_REPETITIONS)

    discovery.load_platform(hass, component_name, DOMAIN, {
        ATTR_DISCOVER_DEVICES: found_tellcore_devices,
        ATTR_DISCOVER_CONFIG: signal_repetitions}, config)


def setup(hass, config):
    """Setup the Tellstick component."""
    from tellcore.constants import TELLSTICK_DIM
    from tellcore.library import DirectCallbackDispatcher
    from tellcore.telldus import TelldusCore

    try:
        tellcore_lib = TelldusCore(
            callback_dispatcher=DirectCallbackDispatcher())
    except OSError:
        _LOGGER.exception('Could not initialize Tellstick')
        return False

    # Get all devices, switches and lights alike
    all_tellcore_devices = tellcore_lib.devices()

    # Register devices
    tellcore_registry = TellstickRegistry(hass, tellcore_lib)
    tellcore_registry.register_tellcore_devices(all_tellcore_devices)
    hass.data['tellcore_registry'] = tellcore_registry

    # Discover the switches
    _discover(hass, config, 'switch',
              [tellcore_device.id for tellcore_device in all_tellcore_devices
               if not tellcore_device.methods(TELLSTICK_DIM)])

    # Discover the lights
    _discover(hass, config, 'light',
              [tellcore_device.id for tellcore_device in all_tellcore_devices
               if tellcore_device.methods(TELLSTICK_DIM)])

    return True


class TellstickRegistry(object):
    """Handle everything around Tellstick callbacks.

    Keeps a map device ids to the tellcore device object, and
    another to the HA device objects (entities).

    Also responsible for registering / cleanup of callbacks, and for
    dispatching the callbacks to the corresponding HA device object.

    All device specific logic should be elsewhere (Entities).
    """

    def __init__(self, hass, tellcore_lib):
        """Initialize the Tellstick mappings and callbacks."""
        # used when map callback device id to ha entities.
        self._id_to_ha_device_map = {}
        self._id_to_tellcore_device_map = {}
        self._setup_tellcore_callback(hass, tellcore_lib)

    def _tellcore_event_callback(self, tellcore_id, tellcore_command,
                                 tellcore_data, cid):
        """Handle the actual callback from Tellcore."""
        ha_device = self._id_to_ha_device_map.get(tellcore_id, None)
        if ha_device is not None:
            # Pass it on to the HA device object
            ha_device.update_from_tellcore(tellcore_command, tellcore_data)
            ha_device.schedule_update_ha_state()

    def _setup_tellcore_callback(self, hass, tellcore_lib):
        """Register the callback handler."""
        callback_id = tellcore_lib.register_device_event(
            self._tellcore_event_callback)

        def clean_up_callback(event):
            """Unregister the callback bindings."""
            if callback_id is not None:
                tellcore_lib.unregister_callback(callback_id)
                _LOGGER.debug("Tellstick callback unregistered")

        hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, clean_up_callback)

    def register_ha_device(self, tellcore_id, ha_device):
        """Register a new HA device to receive callback updates."""
        self._id_to_ha_device_map[tellcore_id] = ha_device

    def register_tellcore_devices(self, tellcore_devices):
        """Register a list of devices."""
        self._id_to_tellcore_device_map.update(
            {tellcore_device.id: tellcore_device for tellcore_device
             in tellcore_devices})

    def get_tellcore_device(self, tellcore_id):
        """Return a device by tellcore_id."""
        return self._id_to_tellcore_device_map.get(tellcore_id, None)


class TellstickDevice(Entity):
    """Representation of a Tellstick device.

    Contains the common logic for all Tellstick devices.
    """

    def __init__(self, tellcore_id, tellcore_registry, signal_repetitions):
        """Initalize the Tellstick device."""
        self._signal_repetitions = signal_repetitions
        self._state = None
        # Look up our corresponding tellcore device
        self._tellcore_device = tellcore_registry.get_tellcore_device(
            tellcore_id)
        # Query tellcore for the current state
        self.update()
        # Add ourselves to the mapping
        tellcore_registry.register_ha_device(tellcore_id, self)

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
        """Return the name of the device as reported by tellcore."""
        return self._tellcore_device.name

    @property
    def is_on(self):
        """Return true if the device is on."""
        return self._state

    def _parse_ha_data(self, kwargs):
        """Turn the value from HA into something useful."""
        raise NotImplementedError

    def _parse_tellcore_data(self, tellcore_data):
        """Turn the value recieved from tellcore into something useful."""
        raise NotImplementedError

    def _update_model(self, new_state, data):
        """Update the device entity state to match the arguments."""
        raise NotImplementedError

    def _send_tellstick_command(self):
        """Let tellcore update the device to match the current state."""
        raise NotImplementedError

    def _do_action(self, new_state, data):
        """The logic for actually turning on or off the device."""
        from tellcore.library import TelldusError

        with TELLSTICK_LOCK:
            # Update self with requested new state
            self._update_model(new_state, data)
            # ... and then send this new state to the Tellstick
            try:
                for _ in range(self._signal_repetitions):
                    self._send_tellstick_command()
            except TelldusError:
                _LOGGER.error(TelldusError)
        self.update_ha_state()

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        self._do_action(True, self._parse_ha_data(kwargs))

    def turn_off(self, **kwargs):
        """Turn the switch off."""
        self._do_action(False, None)

    def update_from_tellcore(self, tellcore_command, tellcore_data):
        """Handle updates from the tellcore callback."""
        from tellcore.constants import (TELLSTICK_TURNON, TELLSTICK_TURNOFF,
                                        TELLSTICK_DIM)

        if tellcore_command not in [TELLSTICK_TURNON, TELLSTICK_TURNOFF,
                                    TELLSTICK_DIM]:
            _LOGGER.debug("Unhandled tellstick command: %d",
                          tellcore_command)
            return

        self._update_model(tellcore_command != TELLSTICK_TURNOFF,
                           self._parse_tellcore_data(tellcore_data))

    def update(self):
        """Poll the current state of the device."""
        from tellcore.library import TelldusError
        from tellcore.constants import (TELLSTICK_TURNON, TELLSTICK_TURNOFF,
                                        TELLSTICK_DIM)

        try:
            last_tellcore_command = self._tellcore_device.last_sent_command(
                TELLSTICK_TURNON | TELLSTICK_TURNOFF | TELLSTICK_DIM
            )
            last_tellcore_data = self._tellcore_device.last_sent_value()

            self.update_from_tellcore(last_tellcore_command,
                                      last_tellcore_data)
        except TelldusError:
            _LOGGER.error(TelldusError)
