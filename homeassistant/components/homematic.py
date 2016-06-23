"""
Support for Homematic Devices.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/homematic/

Configuration:

homematic:
  loacal_ip: "<IP of device running Home Assistant>"
  local_port: <Port for connection with Home Assistant>
  remote_ip: "<IP of Homegear / CCU>"
  remote_port: <Port of Homegear / CCU XML-RPC Server>
"""

import logging
from collections import OrderedDict
from homeassistant.const import EVENT_HOMEASSISTANT_STOP,\
                                EVENT_PLATFORM_DISCOVERED,\
                                ATTR_SERVICE,\
                                ATTR_DISCOVERED,\
                                STATE_UNKNOWN
from homeassistant.loader import get_component
from homeassistant.helpers.entity import Entity
import homeassistant.bootstrap

DOMAIN = 'homematic'
REQUIREMENTS = ['pyhomematic==0.1.6']

HOMEMATIC = None
HOMEMATIC_DEVICES = {}
HOMEMATIC_AUTODETECT = False

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
                              "Motion", "MotionV2", "RemoteMotion"],
    DISCOVER_ROLLERSHUTTER: ["Blind"]
}

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

_HM_DISCOVER_HASS = None
_LOGGER = logging.getLogger(__name__)


# pylint: disable=unused-argument
def setup(hass, config):
    """Setup the Homematic component."""
    global HOMEMATIC, HOMEMATIC_AUTODETECT, _HM_DISCOVER_HASS

    from pyhomematic import HMConnection

    local_ip = config[DOMAIN].get("local_ip", None)
    local_port = config[DOMAIN].get("local_port", 8943)
    remote_ip = config[DOMAIN].get("remote_ip", None)
    remote_port = config[DOMAIN].get("remote_port", 2001)
    autodetect = config[DOMAIN].get("autodetect", False)

    if remote_ip is None or local_ip is None:
        _LOGGER.error("Missing remote CCU/Homegear or local address")
        return False

    # Create server thread
    HOMEMATIC_AUTODETECT = autodetect
    _HM_DISCOVER_HASS = hass
    HOMEMATIC = HMConnection(local=local_ip,
                             localport=local_port,
                             remote=remote_ip,
                             remoteport=remote_port,
                             systemcallback=system_callback_handler,
                             interface_id="homeassistant")

    # Start server thread, connect to homegear, initialize to receive events
    HOMEMATIC.start()

    # Stops server when Homeassistant is shuting down
    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, HOMEMATIC.stop)
    hass.config.components.append(DOMAIN)

    return True


# pylint: disable=too-many-branches
def system_callback_handler(src, *args):
    """Callback handler."""
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
            try:
                if dev in HOMEMATIC_DEVICES:
                    for hm_element in HOMEMATIC_DEVICES[dev]:
                        hm_element.link_homematic()
                else:
                    devices_not_created.append(dev)
            # pylint: disable=broad-except
            except Exception as err:
                _LOGGER.error("Failed to setup device %s: %s", str(dev),
                              str(err))
        # If configuration allows auto detection of devices,
        # all devices not configured are added.
        if HOMEMATIC_AUTODETECT and devices_not_created:
            for component_name, func_get_devices, discovery_type in (
                    ('switch', _get_switches, DISCOVER_SWITCHES),
                    ('light', _get_lights, DISCOVER_LIGHTS),
                    ('rollershutter', _get_rollershutters,
                     DISCOVER_ROLLERSHUTTER),
                    ('binary_sensor', _get_binary_sensors,
                     DISCOVER_BINARY_SENSORS),
                    ('sensor', _get_sensors, DISCOVER_SENSORS),
                    ('thermostat', _get_thermostats, DISCOVER_THERMOSTATS)):
                # Get all devices of a specific type
                found_devices = func_get_devices(devices_not_created)

                # When devices of this type are found
                # they are setup in HA and a event is fired
                if found_devices:
                    component = get_component(component_name)
                    config = {component.DOMAIN: found_devices}

                    # Ensure component is loaded
                    homeassistant.bootstrap.setup_component(
                        _HM_DISCOVER_HASS,
                        component.DOMAIN,
                        config)

                    # Fire discovery event
                    _HM_DISCOVER_HASS.bus.fire(
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
                        hm_element.link_homematic()


def _get_switches(keys=None):
    """Get switches."""
    return _get_devices(DISCOVER_SWITCHES, keys)


def _get_lights(keys=None):
    """Get lights."""
    return _get_devices(DISCOVER_LIGHTS, keys)


def _get_rollershutters(keys=None):
    """Get rollershutters."""
    return _get_devices(DISCOVER_ROLLERSHUTTER, keys)


def _get_binary_sensors(keys=None):
    """Get binary sensors."""
    return _get_devices(DISCOVER_BINARY_SENSORS, keys)


def _get_sensors(keys=None):
    """Get sensors."""
    return _get_devices(DISCOVER_SENSORS, keys)


def _get_thermostats(keys=None):
    """Get thermostats."""
    return _get_devices(DISCOVER_THERMOSTATS, keys)


def _get_devices(device_type, keys):
    """Get devices."""
    device_arr = []
    if not keys:
        keys = HOMEMATIC.devices
    for key in keys:
        device = HOMEMATIC.devices[key]
        if device.__class__.__name__ in HM_DEVICE_TYPES[device_type]:
            elements = device.ELEMENT + 1
            metadata = {}

            # load metadata if needed for generate a param list
            if device_type is DISCOVER_SENSORS:
                metadata.update(device.SENSORNODE)
            elif device_type is DISCOVER_BINARY_SENSORS:
                metadata.update(device.BINARYNODE)
            params = _create_params_list(HOMEMATIC.devices[key], metadata)

            # generate options for 1..n elements with 1..n params
            for channel in range(1, elements):
                for param in params[channel]:
                    name = _create_ha_name(name=HOMEMATIC.devices[key].NAME,
                                           channel=channel,
                                           param=param)
                    ordered_device_dict = OrderedDict()
                    ordered_device_dict["platform"] = "homematic"
                    ordered_device_dict["key"] = key
                    ordered_device_dict["name"] = name
                    ordered_device_dict["button"] = channel
                    if param is not None:
                        ordered_device_dict["param"] = param

                    # add new device
                    device_arr.append(ordered_device_dict)
    return device_arr


def _create_params_list(hmdevice, metadata):
    """ Create a list from HMDevice witch all posible param in config """
    params = {}
    elements = hmdevice.ELEMENT + 1

    # search in Sensor and Binary metadata per elements
    for channel in range(1, elements):
        param_chan = []
        for node, channel in metadata.items():
            if channel == 'c' or channel is None:
                # only channel linked data
                param_chan.append(node)
            elif channel == 1:
                # first channel can have other data channel
                param_chan.append(node)

        # default parameter
        if len(param_chan) == 0:
            param_chan.append(None)
        # add to channel
        params.update({channel: param_chan})

    return params


def _create_ha_name(name, channel, param):
    """ Generate a union object name  """
    # hm device is a simple device
    if channel == 1 and param is None:
        return name

    # have multible elements/channels
    if channel > 1 and param is None:
        return name + "_" + channel

    # with multible param first elements
    if channel == 1 and param is not None:
        return name + "_" + param

    # multible param on object with multible elements
    if channel > 1 and param is not None:
        return name + "_" + channel + "_" + param


def setup_hmdevice_entity_helper(hmdevicetype, config, add_callback_devices):
    """Helper to setup Homematic devices."""
    if HOMEMATIC is None:
        _LOGGER.error('Error setting up hmevice: Server not configured.')
        return False

    address = config.get('address', None)
    if address is None:
        _LOGGER.error("Error setting up Device '%s': " +
                      "'address' missing in configuration.", address)
        return False

    # create a new HA homematic object
    new_device = hmdevicetype(config)
    if address not in HOMEMATIC_DEVICES:
        HOMEMATIC_DEVICES[address] = []
    HOMEMATIC_DEVICES[address].append(new_device)

    # add to HA
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

        # set param to uppercase
        if self._state:
            self._state = self._state.upper()

        # generate name
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
        """Return True if unable to access real state of the light."""
        return not self._available

    @property
    def available(self):
        """Return True if light is available."""
        return self._available

    @property
    def hidden(self):
        """Return True if the entity should be hidden from UIs."""
        return self._hidden

    @property
    def device_state_attributes(self):
        """Return device specific state attributes."""
        attr = {}

        # generate a attributes list
        for node, data in HM_ATTRIBUTE_SUPPORT.items():
            # is a attributes and exists for this object
            if node in self._data:
                value = data[1].get(self._data[node], self._data[node])
                attr[data[0]] = value

        return attr

    def link_homematic(self):
        """Connect to homematic."""
        # exists a HM device from pyhomematic?
        if self._address in HOMEMATIC.devices:
            # init
            self._hmdevice = HOMEMATIC.devices[self._address]
            self._connected = True

            # check is HM class okay for HA class
            _LOGGER.info("Start linking %s to %s", self._address, self._name)
            if self._check_hm_to_ha_object():
                # init datapoints of this object
                self._init_data_struct()
                self._load_init_data_from_hm()
                _LOGGER.debug("%s datastruct: %s", self._name, str(self._data))

                # link events from pyhomatic
                self._subscribe_homematic_events()
                self._available = not self._hmdevice.UNREACH
            else:
                _LOGGER.critical("Delink %s object from HM!", self._name)
                self._connected = False
                self._available = False

            # update HA
            _LOGGER.debug("%s linking down, send update_ha_state", self._name)
            self.update_ha_state()

    def _hm_event_callback(self, device, caller, attribute, value):
        """ Handle all pyhomematic device events """
        _LOGGER.debug("%s receive event '%s' value: %s", self._name,
                      attribute, value)
        have_change = False

        # is data needed for this instance?
        if attribute in self._data:
            # data have change?
            if self._data[attribute] != value:
                self._data[attribute] = value
                have_change = True

        # if available have change
        if attribute is "UNREACH":
            self._available = bool(value)
            have_change = True

        # if it change data, update HA
        if have_change:
            _LOGGER.debug("%s update_ha_state after '%s'", self._name,
                          attribute)
            self.update_ha_state()

    def _subscribe_homematic_events(self):
        """ Subscribe all requered events to handle his job """
        channels_to_sub = {}

        # fill data to channels_to_sub from hmdevice metadata
        for metadata in (self._hmdevice.SENSORNODE, self._hmdevice.BINARYNODE,
                         self._hmdevice.ATTRIBUTENODE,
                         self._hmdevice.WRITENODE, self._hmdevice.EVENTNODE,
                         self._hmdevice.ACTIONNODE):
            for node, channel in metadata.items():
                # data are needed for this instance
                if node in self._data:
                    # chan is current channel
                    if channel == 'c' or channel is None:
                        channel = self._channel
                    # prepare for subscription
                    try:
                        if int(channel) > 0:
                            channels_to_sub.update({int(channel): True})
                    except (ValueError, TypeError):
                        _LOGGER("Invalid channel in metadata from %s",
                                self._name)

        # set callbacks
        for channel in channels_to_sub:
            _LOGGER.debug("Subscribe channel %s from %s",
                          str(channel), self._name)
            self._hmdevice.setEventCallback(callback=self._hm_event_callback,
                                            bequeath=False,
                                            channel=channel)

    def _load_init_data_from_hm(self):
        """ Load first value from pyhomematic """
        if not self._connected:
            return False

        # Read data from pyhomematic direct
        for metadata, funct in (
                (self._hmdevice.ATTRIBUTENODE,
                 self._hmdevice.getAttributeData),
                (self._hmdevice.WRITENODE, self._hmdevice.getWriteData),
                (self._hmdevice.SENSORNODE, self._hmdevice.getSensorData),
                (self._hmdevice.BINARYNODE, self._hmdevice.getBinaryData)):
            for node in metadata:
                if node in self._data:
                    self._data[node] = funct(name=node, channel=self._channel)

        return True

    def _hm_set_state(self, value):
        if self._state in self._data:
            self._data[self._state] = value

    def _hm_get_state(self):
        if self._state in self._data:
            return self._data[self._state]
        return None

    def _check_hm_to_ha_object(self):
        """
        Check if possible to use the HM Object as this HA type
        NEED overwrite by inheret!
        """
        if not self._connected or self._hmdevice is None:
            _LOGGER.error("HA object is not linked to homematic.")
            return False

        # check if button option is correct set for this object
        if self._channel > self._hmdevice.ELEMENT:
            _LOGGER.critical("Button option is not correct for this object!")
            return False

        return True

    def _init_data_struct(self):
        """
        Generate a data struct (self._data) from hm metadata
        NEED overwrite by inheret!
        """
        # add all attribute to data struct
        for data_note in self._hmdevice.ATTRIBUTENODE:
            self._data.update({data_note: STATE_UNKNOWN})
