"""
Tellstick Component.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/Tellstick/
"""
import logging
import threading
import voluptuous as vol

from homeassistant import bootstrap
from homeassistant.const import (
    ATTR_DISCOVERED, ATTR_SERVICE,
    EVENT_PLATFORM_DISCOVERED, EVENT_HOMEASSISTANT_STOP)
from homeassistant.loader import get_component
from homeassistant.helpers.entity import Entity

DOMAIN = "tellstick"

REQUIREMENTS = ['tellcore-py==1.1.2']

_LOGGER = logging.getLogger(__name__)

ATTR_SIGNAL_REPETITIONS = "signal_repetitions"
DEFAULT_SIGNAL_REPETITIONS = 1

DISCOVER_SWITCHES = "tellstick.switches"
DISCOVER_LIGHTS = "tellstick.lights"
DISCOVERY_TYPES = {"switch": DISCOVER_SWITCHES,
                   "light": DISCOVER_LIGHTS}

ATTR_DISCOVER_DEVICES = "devices"
ATTR_DISCOVER_CONFIG = "config"

# Use a global tellstick domain lock to handle
# tellcore errors then calling to concurrently
TELLSTICK_LOCK = threading.Lock()

# Keep a reference the the callback registry
# Used from entities that register callback listeners
TELLCORE_REGISTRY = None

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(ATTR_SIGNAL_REPETITIONS,
                     default=DEFAULT_SIGNAL_REPETITIONS):
        vol.Coerce(int),
    }),
}, extra=vol.ALLOW_EXTRA)


def _discover(hass, config, found_devices, component_name):
    """Setup and send the discovery event."""
    if not len(found_devices):
        return

    _LOGGER.info("discovered %d new %s devices",
                 len(found_devices), component_name)

    component = get_component(component_name)
    bootstrap.setup_component(hass, component.DOMAIN,
                              config)

    signal_repetitions = config[DOMAIN].get(ATTR_SIGNAL_REPETITIONS)

    hass.bus.fire(EVENT_PLATFORM_DISCOVERED,
                  {ATTR_SERVICE: DISCOVERY_TYPES[component_name],
                   ATTR_DISCOVERED: {ATTR_DISCOVER_DEVICES: found_devices,
                                     ATTR_DISCOVER_CONFIG:
                                         signal_repetitions}})


def setup(hass, config):
    """Setup the Tellstick component."""
    # pylint: disable=global-statement, import-error
    global TELLCORE_REGISTRY

    import tellcore.telldus as telldus
    import tellcore.constants as tellcore_constants
    from tellcore.library import DirectCallbackDispatcher

    core = telldus.TelldusCore(callback_dispatcher=DirectCallbackDispatcher())

    TELLCORE_REGISTRY = TellstickRegistry(hass, core)

    devices = core.devices()

    # Register devices
    TELLCORE_REGISTRY.register_devices(devices)

    # Discover the switches
    _discover(hass, config, [switch.id for switch in
                             devices if not switch.methods(
                                 tellcore_constants.TELLSTICK_DIM)],
              "switch")

    # Discover the lights
    _discover(hass, config, [light.id for light in
                             devices if light.methods(
                                 tellcore_constants.TELLSTICK_DIM)],
              "light")

    return True


class TellstickRegistry:
    """Handle everything around tellstick callbacks.

    Keeps a map device ids to home-assistant entities.
    Also responsible for registering / cleanup of callbacks.

    All device specific logic should be elsewhere (Entities).

    """

    def __init__(self, hass, tellcore_lib):
        """Init the tellstick mappings and callbacks."""
        self._core_lib = tellcore_lib
        # used when map callback device id to ha entities.
        self._id_to_entity_map = {}
        self._id_to_device_map = {}
        self._setup_device_callback(hass, tellcore_lib)

    def _device_callback(self, tellstick_id, method, data, cid):
        """Handle the actual callback from tellcore."""
        entity = self._id_to_entity_map.get(tellstick_id, None)
        if entity is not None:
            entity.set_tellstick_state(method, data)
            entity.update_ha_state()

    def _setup_device_callback(self, hass, tellcore_lib):
        """Register the callback handler."""
        callback_id = tellcore_lib.register_device_event(
            self._device_callback)

        def clean_up_callback(event):
            """Unregister the callback bindings."""
            if callback_id is not None:
                tellcore_lib.unregister_callback(callback_id)

        hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, clean_up_callback)

    def register_entity(self, tellcore_id, entity):
        """Register a new entity to receive callback updates."""
        self._id_to_entity_map[tellcore_id] = entity

    def register_devices(self, devices):
        """Register a list of devices."""
        self._id_to_device_map.update({device.id:
                                       device for device in devices})

    def get_device(self, tellcore_id):
        """Return a device by tellcore_id."""
        return self._id_to_device_map.get(tellcore_id, None)


class TellstickDevice(Entity):
    """Represents a Tellstick device.

    Contains the common logic for all Tellstick devices.

    """

    def __init__(self, tellstick_device, signal_repetitions):
        """Init the tellstick device."""
        self.signal_repetitions = signal_repetitions
        self._state = None
        self.tellstick_device = tellstick_device
        # add to id to entity mapping
        TELLCORE_REGISTRY.register_entity(tellstick_device.id, self)
        # Query tellcore for the current state
        self.update()

    @property
    def should_poll(self):
        """Tell Home Assistant not to poll this entity."""
        return False

    @property
    def assumed_state(self):
        """Tellstick devices are always assumed state."""
        return True

    @property
    def name(self):
        """Return the name of the switch if any."""
        return self.tellstick_device.name

    def set_tellstick_state(self, last_command_sent, last_data_sent):
        """Set the private switch state."""
        raise NotImplementedError(
            "set_tellstick_state needs to be implemented.")

    def _send_tellstick_command(self, command, data):
        """Do the actual call to the tellstick device."""
        raise NotImplementedError(
            "_call_tellstick needs to be implemented.")

    def call_tellstick(self, command, data=None):
        """Send a command to the device."""
        from tellcore.library import TelldusError
        with TELLSTICK_LOCK:
            try:
                for _ in range(self.signal_repetitions):
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
            last_command = self.tellstick_device.last_sent_command(
                tellcore_constants.TELLSTICK_TURNON |
                tellcore_constants.TELLSTICK_TURNOFF |
                tellcore_constants.TELLSTICK_DIM
            )
            last_value = self.tellstick_device.last_sent_value()
            self.set_tellstick_state(last_command, last_value)
        except TelldusError:
            _LOGGER.error(TelldusError)
