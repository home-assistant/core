"""
Support for Homematic Devices.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/homematic/

Configuration:

homematic:
  local_ip: "<IP of device running Home Assistant>"
  local_port: <Port for connection with Home Assistant>
  remote_ip: "<IP of Homegear / CCU>"
  remote_port: <Port of Homegear / CCU XML-RPC Server>
  autodetect: "<True/False>" (optional, experimental, detect all devices)
"""
import time
import logging
from functools import partial
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, \
    EVENT_PLATFORM_DISCOVERED, \
    ATTR_SERVICE, \
    ATTR_DISCOVERED, \
    STATE_UNKNOWN
from homeassistant.loader import get_component
from homeassistant.helpers.entity import Entity
import homeassistant.bootstrap

DOMAIN = 'homematic'
REQUIREMENTS = ['pyhomematic==0.1.6']

HOMEMATIC = None
HOMEMATIC_DEVICES = {}

DISCOVER_SWITCHES = "homematic.switch"
DISCOVER_LIGHTS = "homematic.light"
DISCOVER_SENSORS = "homematic.sensor"
DISCOVER_BINARY_SENSORS = "homematic.binary_sensor"
DISCOVER_ROLLERSHUTTER = "homematic.rollershutter"
DISCOVER_THERMOSTATS = "homematic.thermostat"

ATTR_DISCOVER_DEVICES = "devices"
ATTR_DISCOVER_CONFIG = "config"

HM_DEVICE_TYPES = {
    DISCOVER_SWITCHES: ["Switch", "SwitchPowermeter"],
    DISCOVER_LIGHTS: ["Dimmer"],
    DISCOVER_SENSORS: ["SwitchPowermeter", "Motion", "MotionV2",
                       "RemoteMotion", "ThermostatWall", "AreaThermostat",
                       "RotaryHandleSensor"],
    DISCOVER_THERMOSTATS: ["Thermostat", "ThermostatWall", "MAXThermostat"],
    DISCOVER_BINARY_SENSORS: ["Remote", "ShutterContact", "Smoke", "SmokeV2",
                              "Motion", "MotionV2", "RemoteMotion",
                              "GongSensor"],
    DISCOVER_ROLLERSHUTTER: ["Blind"]
}

HM_IGNORE_DISCOVERY_NODE = [
    "ACTUAL_TEMPERATURE"
]

HM_ATTRIBUTE_SUPPORT = {
    "LOWBAT": ["Battery", {0: "High", 1: "Low"}],
    "ERROR": ["Sabotage", {0: "No", 1: "Yes"}],
    "RSSI_DEVICE": ["RSSI", {}],
    "VALVE_STATE": ["Valve", {}],
    "BATTERY_STATE": ["Battery", {}],
    "CONTROL_MODE": ["Mode", {0: "Auto", 1: "Manual", 2: "Away", 3: "Boost"}],
    "POWER": ["Power", {}],
    "CURRENT": ["Current", {}],
    "VOLTAGE": ["Voltage", {}]
}

_LOGGER = logging.getLogger(__name__)


# pylint: disable=unused-argument
def setup(hass, config):
    """Setup the Homematic component."""
    global HOMEMATIC

    from pyhomematic import HMConnection

    local_ip = config[DOMAIN].get("local_ip", None)
    local_port = config[DOMAIN].get("local_port", 8943)
    remote_ip = config[DOMAIN].get("remote_ip", None)
    remote_port = config[DOMAIN].get("remote_port", 2001)

    if remote_ip is None or local_ip is None:
        _LOGGER.error("Missing remote CCU/Homegear or local address")
        return False

    # Create server thread
    bound_system_callback = partial(system_callback_handler, hass, config)
    HOMEMATIC = HMConnection(local=local_ip,
                             localport=local_port,
                             remote=remote_ip,
                             remoteport=remote_port,
                             systemcallback=bound_system_callback,
                             interface_id="homeassistant")

    # Start server thread, connect to peer, initialize to receive events
    HOMEMATIC.start()

    # Stops server when Homeassistant is shutting down
    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, HOMEMATIC.stop)
    hass.config.components.append(DOMAIN)

    return True


# pylint: disable=too-many-branches
def system_callback_handler(hass, config, src, *args):
    """Callback handler."""
    delay = config[DOMAIN].get("delay", 0.5)
    if src == 'newDevices':
        # pylint: disable=unused-variable
        (interface_id, dev_descriptions) = args
        key_dict = {}
        # Get list of all keys of the devices (ignoring channels)
        for dev in dev_descriptions:
            key_dict[dev['ADDRESS'].split(':')[0]] = True
        # Connect devices already created in HA to pyhomematic and
        # add remaining devices to list
        devices_not_created = []
        for dev in key_dict:
            if dev in HOMEMATIC_DEVICES:
                for hm_element in HOMEMATIC_DEVICES[dev]:
                    hm_element.link_homematic(delay=delay)
            else:
                devices_not_created.append(dev)

        # If configuration allows autodetection of devices,
        # all devices not configured are added.
        autodetect = config[DOMAIN].get("autodetect", False)
        if autodetect and devices_not_created:
            for component_name, discovery_type in (
                    ('switch', DISCOVER_SWITCHES),
                    ('light', DISCOVER_LIGHTS),
                    ('rollershutter', DISCOVER_ROLLERSHUTTER),
                    ('binary_sensor', DISCOVER_BINARY_SENSORS),
                    ('sensor', DISCOVER_SENSORS),
                    ('thermostat', DISCOVER_THERMOSTATS)):
                # Get all devices of a specific type
                found_devices = _get_devices(discovery_type,
                                             devices_not_created)

                # When devices of this type are found
                # they are setup in HA and an event is fired
                if found_devices:
                    component = get_component(component_name)
                    config = {component.DOMAIN: found_devices}

                    # Ensure component is loaded
                    homeassistant.bootstrap.setup_component(
                            hass,
                            component.DOMAIN,
                            config)

                    # Fire discovery event
                    hass.bus.fire(
                            EVENT_PLATFORM_DISCOVERED, {
                                ATTR_SERVICE: discovery_type,
                                ATTR_DISCOVERED: {
                                    ATTR_DISCOVER_DEVICES:
                                        found_devices,
                                    ATTR_DISCOVER_CONFIG: ''
                                }
                            }
                    )

            for dev in devices_not_created:
                if dev in HOMEMATIC_DEVICES:
                    for hm_element in HOMEMATIC_DEVICES[dev]:
                        hm_element.link_homematic(delay=delay)


def _get_devices(device_type, keys):
    """Get devices."""
    from homeassistant.components.binary_sensor.homematic import \
        SUPPORT_HM_EVENT_AS_BINMOD

    # run
    device_arr = []
    if not keys:
        keys = HOMEMATIC.devices
    for key in keys:
        device = HOMEMATIC.devices[key]
        if device.__class__.__name__ not in HM_DEVICE_TYPES[device_type]:
            continue
        metadata = {}

        # Load metadata if needed to generate a param list
        if device_type == DISCOVER_SENSORS:
            metadata.update(device.SENSORNODE)
        elif device_type == DISCOVER_BINARY_SENSORS:
            metadata.update(device.BINARYNODE)

            # Also add supported events as binary type
            for event, channel in device.EVENTNODE.items():
                if event in SUPPORT_HM_EVENT_AS_BINMOD:
                    metadata.update({event: channel})

        params = _create_params_list(device, metadata)
        if params:
            # Generate options for 1...n elements with 1...n params
            for channel in range(1, device.ELEMENT + 1):
                _LOGGER.debug("Handling %s:%i", key, channel)
                if channel in params:
                    for param in params[channel]:
                        name = _create_ha_name(name=device.NAME,
                                               channel=channel,
                                               param=param)
                        device_dict = dict(platform="homematic",
                                           address=key,
                                           name=name,
                                           button=channel)
                        if param is not None:
                            device_dict["param"] = param

                        # Add new device
                        device_arr.append(device_dict)
                else:
                    _LOGGER.debug("Channel %i not in params", channel)
        else:
            _LOGGER.debug("Got no params for %s", key)
    _LOGGER.debug("%s autodiscovery: %s",
                  device_type, str(device_arr))
    return device_arr


def _create_params_list(hmdevice, metadata):
    """Create a list from HMDevice with all possible parameters in config."""
    params = {}

    # Search in sensor and binary metadata per elements
    for channel in range(1, hmdevice.ELEMENT + 1):
        param_chan = []
        try:
            for node, meta_chan in metadata.items():
                # Is this attribute ignored?
                if node in HM_IGNORE_DISCOVERY_NODE:
                    continue
                if meta_chan == 'c' or meta_chan is None:
                    # Only channel linked data
                    param_chan.append(node)
                elif channel == 1:
                    # First channel can have other data channel
                    param_chan.append(node)
        # pylint: disable=broad-except
        except Exception as err:
            _LOGGER.error("Exception generating %s (%s): %s",
                          hmdevice.ADDRESS, str(metadata), str(err))
        # Default parameter
        if not param_chan:
            param_chan.append(None)
        # Add to channel
        params.update({channel: param_chan})

    _LOGGER.debug("Create param list for %s with: %s", hmdevice.ADDRESS,
                  str(params))
    return params


def _create_ha_name(name, channel, param):
    """Generate a unique object name."""
    # HMDevice is a simple device
    if channel == 1 and param is None:
        return name

    # Has multiple elements/channels
    if channel > 1 and param is None:
        return "{} {}".format(name, channel)

    # With multiple param first elements
    if channel == 1 and param is not None:
        return "{} {}".format(name, param)

    # Multiple param on object with multiple elements
    if channel > 1 and param is not None:
        return "{} {} {}".format(name, channel, param)


def setup_hmdevice_entity_helper(hmdevicetype, config, add_callback_devices):
    """Helper to setup Homematic devices."""
    if HOMEMATIC is None:
        _LOGGER.error('Error setting up HMDevice: Server not configured.')
        return False

    address = config.get('address', None)
    if address is None:
        _LOGGER.error("Error setting up device '%s': " +
                      "'address' missing in configuration.", address)
        return False

    # Create a new HA homematic object
    new_device = hmdevicetype(config)
    if address not in HOMEMATIC_DEVICES:
        HOMEMATIC_DEVICES[address] = []
    HOMEMATIC_DEVICES[address].append(new_device)

    # Add to HA
    add_callback_devices([new_device])
    return True


class HMDevice(Entity):
    """Homematic device base object."""

    # pylint: disable=too-many-instance-attributes
    def __init__(self, config):
        """Initialize generic HM device."""
        self._name = config.get("name", None)
        self._address = config.get("address", None)
        self._channel = config.get("button", 1)
        self._state = config.get("param", None)
        self._hidden = config.get("hidden", False)
        self._data = {}
        self._hmdevice = None
        self._connected = False
        self._available = False

        # Set param to uppercase
        if self._state:
            self._state = self._state.upper()

        # Generate name
        if not self._name:
            self._name = _create_ha_name(name=self._address,
                                         channel=self._channel,
                                         param=self._state)

    @property
    def should_poll(self):
        """Return False. Homematic states are pushed by the XML RPC Server."""
        return False

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def assumed_state(self):
        """Return True if unable to access real state of the device."""
        return not self._available

    @property
    def available(self):
        """Return True if device is available."""
        return self._available

    @property
    def hidden(self):
        """Return True if the entity should be hidden from UIs."""
        return self._hidden

    @property
    def device_state_attributes(self):
        """Return device specific state attributes."""
        attr = {}

        # Generate an attributes list
        for node, data in HM_ATTRIBUTE_SUPPORT.items():
            # Is an attributes and exists for this object
            if node in self._data:
                value = data[1].get(self._data[node], self._data[node])
                attr[data[0]] = value

        return attr

    def link_homematic(self, delay=0.5):
        """Connect to homematic."""
        # Does a HMDevice from pyhomematic exist?
        if self._address in HOMEMATIC.devices:
            # Init
            self._hmdevice = HOMEMATIC.devices[self._address]
            self._connected = True

            # Check if HM class is okay for HA class
            _LOGGER.info("Start linking %s to %s", self._address, self._name)
            if self._check_hm_to_ha_object():
                try:
                    # Init datapoints of this object
                    self._init_data_struct()
                    if delay:
                        # We delay / pause loading of data to avoid overloading
                        # of CCU / Homegear when doing auto detection
                        time.sleep(delay)
                    self._load_init_data_from_hm()
                    _LOGGER.debug("%s datastruct: %s",
                                  self._name, str(self._data))

                    # Link events from pyhomatic
                    self._subscribe_homematic_events()
                    self._available = not self._hmdevice.UNREACH
                # pylint: disable=broad-except
                except Exception as err:
                    self._connected = False
                    self._available = False
                    _LOGGER.error("Exception while linking %s: %s" %
                                  (self._address, str(err)))
            else:
                _LOGGER.critical("Delink %s object from HM!", self._name)
                self._connected = False
                self._available = False

            # Update HA
            _LOGGER.debug("%s linking down, send update_ha_state", self._name)
            self.update_ha_state()
        else:
            _LOGGER.debug("%s not found in HOMEMATIC.devices", self._address)

    def _hm_event_callback(self, device, caller, attribute, value):
        """Handle all pyhomematic device events."""
        _LOGGER.debug("%s receive event '%s' value: %s", self._name,
                      attribute, value)
        have_change = False

        # Is data needed for this instance?
        if attribute in self._data:
            # Did data change?
            if self._data[attribute] != value:
                self._data[attribute] = value
                have_change = True

        # If available it has changed
        if attribute is "UNREACH":
            self._available = bool(value)
            have_change = True

        # If it has changed, update HA
        if have_change:
            _LOGGER.debug("%s update_ha_state after '%s'", self._name,
                          attribute)
            self.update_ha_state()

            # Reset events
            if attribute in self._hmdevice.EVENTNODE:
                _LOGGER.debug("%s reset event", self._name)
                self._data[attribute] = False
                self.update_ha_state()

    def _subscribe_homematic_events(self):
        """Subscribe all required events to handle job."""
        channels_to_sub = {}

        # Push data to channels_to_sub from hmdevice metadata
        for metadata in (self._hmdevice.SENSORNODE, self._hmdevice.BINARYNODE,
                         self._hmdevice.ATTRIBUTENODE,
                         self._hmdevice.WRITENODE, self._hmdevice.EVENTNODE,
                         self._hmdevice.ACTIONNODE):
            for node, channel in metadata.items():
                # Data is needed for this instance
                if node in self._data:
                    # chan is current channel
                    if channel == 'c' or channel is None:
                        channel = self._channel
                    # Prepare for subscription
                    try:
                        if int(channel) > 0:
                            channels_to_sub.update({int(channel): True})
                    except (ValueError, TypeError):
                        _LOGGER("Invalid channel in metadata from %s",
                                self._name)

        # Set callbacks
        for channel in channels_to_sub:
            _LOGGER.debug("Subscribe channel %s from %s",
                          str(channel), self._name)
            self._hmdevice.setEventCallback(callback=self._hm_event_callback,
                                            bequeath=False,
                                            channel=channel)

    def _load_init_data_from_hm(self):
        """Load first value from pyhomematic."""
        if not self._connected:
            return False

        # Read data from pyhomematic
        for metadata, funct in (
                (self._hmdevice.ATTRIBUTENODE,
                 self._hmdevice.getAttributeData),
                (self._hmdevice.WRITENODE, self._hmdevice.getWriteData),
                (self._hmdevice.SENSORNODE, self._hmdevice.getSensorData),
                (self._hmdevice.BINARYNODE, self._hmdevice.getBinaryData)):
            for node in metadata:
                if node in self._data:
                    self._data[node] = funct(name=node, channel=self._channel)

        # Set events to False
        for node in self._hmdevice.EVENTNODE:
            if node in self._data:
                self._data[node] = False

        return True

    def _hm_set_state(self, value):
        if self._state in self._data:
            self._data[self._state] = value

    def _hm_get_state(self):
        if self._state in self._data:
            return self._data[self._state]
        return None

    def _check_hm_to_ha_object(self):
        """Check if it is possible to use the HM Object as this HA type.

        NEEDS overwrite by inherit!
        """
        if not self._connected or self._hmdevice is None:
            _LOGGER.error("HA object is not linked to homematic.")
            return False

        # Check if button option is correctly set for this object
        if self._channel > self._hmdevice.ELEMENT:
            _LOGGER.critical("Button option is not correct for this object!")
            return False

        return True

    def _init_data_struct(self):
        """Generate a data dict (self._data) from hm metadata.

        NEEDS overwrite by inherit!
        """
        # Add all attributes to data dict
        for data_note in self._hmdevice.ATTRIBUTENODE:
            self._data.update({data_note: STATE_UNKNOWN})
