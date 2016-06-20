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
REQUIREMENTS = ['pyhomematic==0.1.4']


HOMEMATIC_DEVICES = {}

HOMEMATIC = None
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
    DISCOVER_SWITCHES: ['HMSwitch'],
    DISCOVER_LIGHTS: ['HMDimmer'],
    DISCOVER_SENSORS: ['HMCcu'],
    DISCOVER_THERMOSTATS: ['HMThermostat'],
    DISCOVER_BINARY_SENSORS: ['HMRemote', 'HMDoorContact'],
    DISCOVER_ROLLERSHUTTER: ['HMRollerShutter']
}

HM_ATTRIBUTE_SUPPORT = {
    "LOWBAT": "Battery",
    "ERROR": "Sabotage",
    "RSSI_DEVICE": "RSSI",
    "VALVE_STATE": "Valve",
    "BATTERY_STATE": "Battery"
}

_LOGGER = logging.getLogger(__name__)


# pylint: disable=unused-argument
def setup(hass, config):
    """Setup the Homematic component."""
    global HOMEMATIC, HOMEMATIC_AUTODETECT

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
    HOMEMATIC = HMConnection(local=local_ip,
                             localport=local_port,
                             remote=remote_ip,
                             remoteport=remote_port,
                             systemcallback=system_callback_handler,
                             interface_id='homeassistant')

    # Start server thread, connect to homegear, initialize to receive events
    HOMEMATIC.start()

    # Stops server when Homeassistant is shuting down
    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, HOMEMATIC.stop)
    hass.config.components.append(DOMAIN)

    return True


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
                    # pylint: disable=logging-not-lazy
                    _LOGGER.error("Failed to setup device %s: %s" % (
                        (str(dev), str(err))))
            # If configuration allows auto detection of devices,
            # all devices not configured are added.
            if HOMEMATIC_AUTODETECT and devices_not_created:
                for component_name, func_get_devices, discovery_type in (
                        ('switch', get_switches, DISCOVER_SWITCHES),
                        ('light', get_lights, DISCOVER_LIGHTS),
                        ('rollershutter', get_rollershutters,
                         DISCOVER_ROLLERSHUTTER),
                        ('binary_sensor', get_binary_sensors,
                         DISCOVER_BINARY_SENSORS),
                        ('sensor', get_sensors, DISCOVER_SENSORS),
                        ('thermostat', get_thermostats, DISCOVER_THERMOSTATS)):
                    # Get all devices of a specific type
                    found_devices = func_get_devices(devices_not_created)

                    # When devices of this type are found
                    # they are setup in HA and a event is fired
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
                            hm_element.link_homematic()


def get_switches(keys=None):
    """Get switches."""
    return get_devices(HM_DEVICE_TYPES[DISCOVER_SWITCHES], keys)


def get_lights(keys=None):
    """Get lights."""
    return get_devices(HM_DEVICE_TYPES[DISCOVER_LIGHTS], keys)


def get_rollershutters(keys=None):
    """Get rollershutters."""
    return get_devices(HM_DEVICE_TYPES[DISCOVER_ROLLERSHUTTER], keys)


def get_binary_sensors(keys=None):
    """Get binary sensors."""
    return get_devices(HM_DEVICE_TYPES[DISCOVER_BINARY_SENSORS], keys)


def get_sensors(keys=None):
    """Get sensors."""
    return get_devices(HM_DEVICE_TYPES[DISCOVER_SENSORS], keys)


def get_thermostats(keys=None):
    """Get thermostats."""
    return get_devices(HM_DEVICE_TYPES[DISCOVER_THERMOSTATS], keys)


def get_devices(device_types, keys):
    """Get devices."""
    device_arr = []
    if not keys:
        keys = HOMEMATIC.devices
    for key in keys:
        if HOMEMATIC.devices[key].__class__.__name__ in device_types:
            ordered_device_dict = OrderedDict()
            ordered_device_dict['platform'] = 'homematic'
            ordered_device_dict['key'] = key
            ordered_device_dict['name'] = HOMEMATIC.devices[key].NAME
            device_arr.append(ordered_device_dict)
    return device_arr


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

        if not self._name:
            self._name = self._address

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
        for data_node, text in HM_ATTRIBUTE_SUPPORT.items():
            # is a attributes and exists for this object
            if data_node in self._data:
                attr[name] = self._data[data_node]

        return attr

    def link_homematic(self):
        """Connect to homematic."""
        # exists a HM device from pyhomematic?
        if self._address in HOMEMATIC.devices:
            # init
            self._hmdevice = HOMEMATIC.devices[self._address]
            self._connected = True
            self._available = not self._hmdevice.UNREACH

            # check is HM class okay for HA class
            if self._check_hm_to_ha_object() and \
               self._element <= self._hmdevice.ELEMENT:
                # init datapoints of this object
                self._init_data()
                self._subscribe_homematic_events()

            # update HA
            self.update_ha_state()

    def _hm_event_callback(self, device, caller, attribute, value):
        """ Handle all pyhomematic device events """
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
            self.update_ha_state()

    def _subscribe_homematic_events(self):
        """ Subscribe all requered events to handle his job """
        channels_to_sub = {}

        # fill data to channels_to_sub from hmdevice metadata
        for metadata in (self._hmdevice.SENSORNODE, self._hmdevice.BINARYNODE,
                         self._hmdevice.ATTRIBUTENODE,
                         self._hmdevice.WRITENODE):
            for node, channel in metadata.items():
                # data are needed for this instance
                if node in self._data:
                    # chan is current channel
                    if channel == 'n' or channel is None:
                        channel = self._channel
                    # prepare for subscription
                    channels_to_sub.update({channel: True})

        # set callbacks
        for channel in channels_to_sub:
            self._hmdevice.setEventCallback(callback=self._hm_event_callback,
                                            bequeath=false,
                                            channel=channel)

    def _check_hm_to_ha_object(self):
        """
        Check if possible to use the HM Object as this HA type
        NEED overwrite by inheret!
        """
        if not self._connected or self._hmdevice is None:
            _LOGGER.error("HA object is not linked to homematic.")
            return False

        # check if button option is correct set for this object
        if self._channel <= self._hmdevice.ELEMENT:
            _LOGGER.critical("Button option is not correct for this object!")
            return False

        return True

    def _init_data(self):
        """
        Generate a data struct (self._data) from hm metadata
        NEED overwrite by inheret!
        """
        # add all attribute to data struct
        for data_note in self._hmdevice.ATTRIBUTENODE:
            self._data[data_note] = STATE_UNKNOWN
