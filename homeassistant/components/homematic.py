"""
Support for HomeMatic devices.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/homematic/
"""
import asyncio
import os
import logging
from datetime import timedelta
from functools import partial

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    EVENT_HOMEASSISTANT_STOP, STATE_UNKNOWN, CONF_USERNAME, CONF_PASSWORD,
    CONF_PLATFORM, CONF_HOSTS, CONF_NAME, ATTR_ENTITY_ID)
from homeassistant.helpers import discovery
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import track_time_interval
from homeassistant.config import load_yaml_config_file

REQUIREMENTS = ['pyhomematic==0.1.33']

DOMAIN = 'homematic'

SCAN_INTERVAL_HUB = timedelta(seconds=300)
SCAN_INTERVAL_VARIABLES = timedelta(seconds=30)

DISCOVER_SWITCHES = 'homematic.switch'
DISCOVER_LIGHTS = 'homematic.light'
DISCOVER_SENSORS = 'homematic.sensor'
DISCOVER_BINARY_SENSORS = 'homematic.binary_sensor'
DISCOVER_COVER = 'homematic.cover'
DISCOVER_CLIMATE = 'homematic.climate'

ATTR_DISCOVER_DEVICES = 'devices'
ATTR_PARAM = 'param'
ATTR_CHANNEL = 'channel'
ATTR_NAME = 'name'
ATTR_ADDRESS = 'address'
ATTR_VALUE = 'value'
ATTR_PROXY = 'proxy'
ATTR_ERRORCODE = 'error'
ATTR_MESSAGE = 'message'

EVENT_KEYPRESS = 'homematic.keypress'
EVENT_IMPULSE = 'homematic.impulse'
EVENT_ERROR = 'homematic.error'

SERVICE_VIRTUALKEY = 'virtualkey'
SERVICE_RECONNECT = 'reconnect'
SERVICE_SET_VAR_VALUE = 'set_var_value'
SERVICE_SET_DEV_VALUE = 'set_dev_value'

HM_DEVICE_TYPES = {
    DISCOVER_SWITCHES: [
        'Switch', 'SwitchPowermeter', 'IOSwitch', 'IPSwitch',
        'IPSwitchPowermeter', 'KeyMatic', 'HMWIOSwitch', 'Rain', 'EcoLogic'],
    DISCOVER_LIGHTS: ['Dimmer', 'KeyDimmer', 'IPKeyDimmer'],
    DISCOVER_SENSORS: [
        'SwitchPowermeter', 'Motion', 'MotionV2', 'RemoteMotion', 'MotionIP',
        'ThermostatWall', 'AreaThermostat', 'RotaryHandleSensor',
        'WaterSensor', 'PowermeterGas', 'LuxSensor', 'WeatherSensor',
        'WeatherStation', 'ThermostatWall2', 'TemperatureDiffSensor',
        'TemperatureSensor', 'CO2Sensor', 'IPSwitchPowermeter', 'HMWIOSwitch',
        'FillingLevel', 'ValveDrive', 'EcoLogic', 'IPThermostatWall',
        'IPSmoke'],
    DISCOVER_CLIMATE: [
        'Thermostat', 'ThermostatWall', 'MAXThermostat', 'ThermostatWall2',
        'MAXWallThermostat', 'IPThermostat', 'IPThermostatWall',
        'ThermostatGroup'],
    DISCOVER_BINARY_SENSORS: [
        'ShutterContact', 'Smoke', 'SmokeV2', 'Motion', 'MotionV2',
        'RemoteMotion', 'WeatherSensor', 'TiltSensor', 'IPShutterContact',
        'HMWIOSwitch', 'MaxShutterContact', 'Rain', 'WiredSensor'],
    DISCOVER_COVER: ['Blind', 'KeyBlind']
}

HM_IGNORE_DISCOVERY_NODE = [
    'ACTUAL_TEMPERATURE',
    'ACTUAL_HUMIDITY'
]

HM_ATTRIBUTE_SUPPORT = {
    'LOWBAT': ['battery', {0: 'High', 1: 'Low'}],
    'ERROR': ['sabotage', {0: 'No', 1: 'Yes'}],
    'RSSI_DEVICE': ['rssi', {}],
    'VALVE_STATE': ['valve', {}],
    'BATTERY_STATE': ['battery', {}],
    'CONTROL_MODE': ['mode', {0: 'Auto',
                              1: 'Manual',
                              2: 'Away',
                              3: 'Boost',
                              4: 'Comfort',
                              5: 'Lowering'}],
    'POWER': ['power', {}],
    'CURRENT': ['current', {}],
    'VOLTAGE': ['voltage', {}],
    'WORKING': ['working', {0: 'No', 1: 'Yes'}],
}

HM_PRESS_EVENTS = [
    'PRESS_SHORT',
    'PRESS_LONG',
    'PRESS_CONT',
    'PRESS_LONG_RELEASE',
    'PRESS',
]

HM_IMPULSE_EVENTS = [
    'SEQUENCE_OK',
]

_LOGGER = logging.getLogger(__name__)

CONF_RESOLVENAMES_OPTIONS = [
    'metadata',
    'json',
    'xml',
    False
]

DATA_HOMEMATIC = 'homematic'
DATA_DEVINIT = 'homematic_devinit'
DATA_STORE = 'homematic_store'

CONF_LOCAL_IP = 'local_ip'
CONF_LOCAL_PORT = 'local_port'
CONF_IP = 'ip'
CONF_PORT = 'port'
CONF_PATH = 'path'
CONF_CALLBACK_IP = 'callback_ip'
CONF_CALLBACK_PORT = 'callback_port'
CONF_RESOLVENAMES = 'resolvenames'
CONF_VARIABLES = 'variables'
CONF_DEVICES = 'devices'
CONF_PRIMARY = 'primary'

DEFAULT_LOCAL_IP = '0.0.0.0'
DEFAULT_LOCAL_PORT = 0
DEFAULT_RESOLVENAMES = False
DEFAULT_PORT = 2001
DEFAULT_PATH = ''
DEFAULT_USERNAME = 'Admin'
DEFAULT_PASSWORD = ''
DEFAULT_VARIABLES = False
DEFAULT_DEVICES = True
DEFAULT_PRIMARY = False


DEVICE_SCHEMA = vol.Schema({
    vol.Required(CONF_PLATFORM): 'homematic',
    vol.Required(ATTR_NAME): cv.string,
    vol.Required(ATTR_ADDRESS): cv.string,
    vol.Required(ATTR_PROXY): cv.string,
    vol.Optional(ATTR_CHANNEL, default=1): vol.Coerce(int),
    vol.Optional(ATTR_PARAM): cv.string,
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_HOSTS): {cv.match_all: {
            vol.Required(CONF_IP): cv.string,
            vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
            vol.Optional(CONF_PATH, default=DEFAULT_PATH): cv.string,
            vol.Optional(CONF_USERNAME, default=DEFAULT_USERNAME): cv.string,
            vol.Optional(CONF_PASSWORD, default=DEFAULT_PASSWORD): cv.string,
            vol.Optional(CONF_VARIABLES, default=DEFAULT_VARIABLES):
                cv.boolean,
            vol.Optional(CONF_RESOLVENAMES, default=DEFAULT_RESOLVENAMES):
                vol.In(CONF_RESOLVENAMES_OPTIONS),
            vol.Optional(CONF_DEVICES, default=DEFAULT_DEVICES): cv.boolean,
            vol.Optional(CONF_PRIMARY, default=DEFAULT_PRIMARY): cv.boolean,
            vol.Optional(CONF_CALLBACK_IP): cv.string,
            vol.Optional(CONF_CALLBACK_PORT): cv.port,
        }},
        vol.Optional(CONF_LOCAL_IP, default=DEFAULT_LOCAL_IP): cv.string,
        vol.Optional(CONF_LOCAL_PORT, default=DEFAULT_LOCAL_PORT): cv.port,
    }),
}, extra=vol.ALLOW_EXTRA)

SCHEMA_SERVICE_VIRTUALKEY = vol.Schema({
    vol.Required(ATTR_ADDRESS): vol.All(cv.string, vol.Upper),
    vol.Required(ATTR_CHANNEL): vol.Coerce(int),
    vol.Required(ATTR_PARAM): cv.string,
    vol.Optional(ATTR_PROXY): cv.string,
})

SCHEMA_SERVICE_SET_VAR_VALUE = vol.Schema({
    vol.Required(ATTR_NAME): cv.string,
    vol.Required(ATTR_VALUE): cv.match_all,
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
})

SCHEMA_SERVICE_SET_DEV_VALUE = vol.Schema({
    vol.Required(ATTR_ADDRESS): vol.All(cv.string, vol.Upper),
    vol.Required(ATTR_CHANNEL): vol.Coerce(int),
    vol.Required(ATTR_PARAM): vol.All(cv.string, vol.Upper),
    vol.Required(ATTR_VALUE): cv.match_all,
    vol.Optional(ATTR_PROXY): cv.string,
})

SCHEMA_SERVICE_RECONNECT = vol.Schema({})


def virtualkey(hass, address, channel, param, proxy=None):
    """Send virtual keypress to homematic controlller."""
    data = {
        ATTR_ADDRESS: address,
        ATTR_CHANNEL: channel,
        ATTR_PARAM: param,
        ATTR_PROXY: proxy,
    }

    hass.services.call(DOMAIN, SERVICE_VIRTUALKEY, data)


def set_var_value(hass, entity_id, value):
    """Change value of a Homematic system variable."""
    data = {
        ATTR_ENTITY_ID: entity_id,
        ATTR_VALUE: value,
    }

    hass.services.call(DOMAIN, SERVICE_SET_VAR_VALUE, data)


def set_dev_value(hass, address, channel, param, value, proxy=None):
    """Call setValue XML-RPC method of supplied proxy."""
    data = {
        ATTR_ADDRESS: address,
        ATTR_CHANNEL: channel,
        ATTR_PARAM: param,
        ATTR_VALUE: value,
        ATTR_PROXY: proxy,
    }

    hass.services.call(DOMAIN, SERVICE_SET_DEV_VALUE, data)


def reconnect(hass):
    """Reconnect to CCU/Homegear."""
    hass.services.call(DOMAIN, SERVICE_RECONNECT, {})


def setup(hass, config):
    """Set up the Homematic component."""
    from pyhomematic import HMConnection

    hass.data[DATA_DEVINIT] = {}
    hass.data[DATA_STORE] = set()

    # Create hosts-dictionary for pyhomematic
    remotes = {}
    hosts = {}
    for rname, rconfig in config[DOMAIN][CONF_HOSTS].items():
        server = rconfig.get(CONF_IP)

        remotes[rname] = {}
        remotes[rname][CONF_IP] = server
        remotes[rname][CONF_PORT] = rconfig.get(CONF_PORT)
        remotes[rname][CONF_PATH] = rconfig.get(CONF_PATH)
        remotes[rname][CONF_RESOLVENAMES] = rconfig.get(CONF_RESOLVENAMES)
        remotes[rname][CONF_USERNAME] = rconfig.get(CONF_USERNAME)
        remotes[rname][CONF_PASSWORD] = rconfig.get(CONF_PASSWORD)
        remotes[rname]['callbackip'] = rconfig.get(CONF_CALLBACK_IP)
        remotes[rname]['callbackport'] = rconfig.get(CONF_CALLBACK_PORT)

        if server not in hosts or rconfig.get(CONF_PRIMARY):
            hosts[server] = {
                CONF_VARIABLES: rconfig.get(CONF_VARIABLES),
                CONF_NAME: rname,
            }
        hass.data[DATA_DEVINIT][rname] = rconfig.get(CONF_DEVICES)

    # Create server thread
    bound_system_callback = partial(_system_callback_handler, hass, config)
    hass.data[DATA_HOMEMATIC] = homematic = HMConnection(
        local=config[DOMAIN].get(CONF_LOCAL_IP),
        localport=config[DOMAIN].get(CONF_LOCAL_PORT),
        remotes=remotes,
        systemcallback=bound_system_callback,
        interface_id='homeassistant'
    )

    # Start server thread, connect to hosts, initialize to receive events
    homematic.start()

    # Stops server when HASS is shutting down
    hass.bus.listen_once(
        EVENT_HOMEASSISTANT_STOP, hass.data[DATA_HOMEMATIC].stop)

    # Init homematic hubs
    entity_hubs = []
    for _, hub_data in hosts.items():
        entity_hubs.append(HMHub(
            hass, homematic, hub_data[CONF_NAME], hub_data[CONF_VARIABLES]))

    # Register HomeMatic services
    descriptions = load_yaml_config_file(
        os.path.join(os.path.dirname(__file__), 'services.yaml'))

    def _hm_service_virtualkey(service):
        """Service to handle virtualkey servicecalls."""
        address = service.data.get(ATTR_ADDRESS)
        channel = service.data.get(ATTR_CHANNEL)
        param = service.data.get(ATTR_PARAM)

        # Device not found
        hmdevice = _device_from_servicecall(hass, service)
        if hmdevice is None:
            _LOGGER.error("%s not found for service virtualkey!", address)
            return

        # Parameter doesn't exist for device
        if param not in hmdevice.ACTIONNODE:
            _LOGGER.error("%s not datapoint in hm device %s", param, address)
            return

        # Channel doesn't exist for device
        if channel not in hmdevice.ACTIONNODE[param]:
            _LOGGER.error("%i is not a channel in hm device %s",
                          channel, address)
            return

        # Call parameter
        hmdevice.actionNodeData(param, True, channel)

    hass.services.register(
        DOMAIN, SERVICE_VIRTUALKEY, _hm_service_virtualkey,
        descriptions[DOMAIN][SERVICE_VIRTUALKEY],
        schema=SCHEMA_SERVICE_VIRTUALKEY)

    def _service_handle_value(service):
        """Service to call setValue method for HomeMatic system variable."""
        entity_ids = service.data.get(ATTR_ENTITY_ID)
        name = service.data[ATTR_NAME]
        value = service.data[ATTR_VALUE]

        if entity_ids:
            entities = [entity for entity in entity_hubs if
                        entity.entity_id in entity_ids]
        else:
            entities = entity_hubs

        if not entities:
            _LOGGER.error("No HomeMatic hubs available")
            return

        for hub in entities:
            hub.hm_set_variable(name, value)

    hass.services.register(
        DOMAIN, SERVICE_SET_VAR_VALUE, _service_handle_value,
        descriptions[DOMAIN][SERVICE_SET_VAR_VALUE],
        schema=SCHEMA_SERVICE_SET_VAR_VALUE)

    def _service_handle_reconnect(service):
        """Service to reconnect all HomeMatic hubs."""
        homematic.reconnect()

    hass.services.register(
        DOMAIN, SERVICE_RECONNECT, _service_handle_reconnect,
        descriptions[DOMAIN][SERVICE_RECONNECT],
        schema=SCHEMA_SERVICE_RECONNECT)

    def _service_handle_device(service):
        """Service to call setValue method for HomeMatic devices."""
        address = service.data.get(ATTR_ADDRESS)
        channel = service.data.get(ATTR_CHANNEL)
        param = service.data.get(ATTR_PARAM)
        value = service.data.get(ATTR_VALUE)

        # Device not found
        hmdevice = _device_from_servicecall(hass, service)
        if hmdevice is None:
            _LOGGER.error("%s not found!", address)
            return

        hmdevice.setValue(param, value, channel)

    hass.services.register(
        DOMAIN, SERVICE_SET_DEV_VALUE, _service_handle_device,
        descriptions[DOMAIN][SERVICE_SET_DEV_VALUE],
        schema=SCHEMA_SERVICE_SET_DEV_VALUE)

    return True


def _system_callback_handler(hass, config, src, *args):
    """System callback handler."""
    # New devices available at hub
    if src == 'newDevices':
        (interface_id, dev_descriptions) = args
        proxy = interface_id.split('-')[-1]

        # Device support active?
        if not hass.data[DATA_DEVINIT][proxy]:
            return

        addresses = []
        for dev in dev_descriptions:
            address = dev['ADDRESS'].split(':')[0]
            if address not in hass.data[DATA_STORE]:
                hass.data[DATA_STORE].add(address)
                addresses.append(address)

        # Register EVENTS
        # Search all devices with an EVENTNODE that includes data
        bound_event_callback = partial(_hm_event_handler, hass, proxy)
        for dev in addresses:
            hmdevice = hass.data[DATA_HOMEMATIC].devices[proxy].get(dev)

            if hmdevice.EVENTNODE:
                hmdevice.setEventCallback(
                    callback=bound_event_callback, bequeath=True)

        # Create HASS entities
        if addresses:
            for component_name, discovery_type in (
                    ('switch', DISCOVER_SWITCHES),
                    ('light', DISCOVER_LIGHTS),
                    ('cover', DISCOVER_COVER),
                    ('binary_sensor', DISCOVER_BINARY_SENSORS),
                    ('sensor', DISCOVER_SENSORS),
                    ('climate', DISCOVER_CLIMATE)):
                # Get all devices of a specific type
                found_devices = _get_devices(
                    hass, discovery_type, addresses, proxy)

                # When devices of this type are found
                # they are setup in HASS and an discovery event is fired
                if found_devices:
                    discovery.load_platform(hass, component_name, DOMAIN, {
                        ATTR_DISCOVER_DEVICES: found_devices
                    }, config)

    # Homegear error message
    elif src == 'error':
        _LOGGER.error("Error: %s", args)
        (interface_id, errorcode, message) = args
        hass.bus.fire(EVENT_ERROR, {
            ATTR_ERRORCODE: errorcode,
            ATTR_MESSAGE: message
        })


def _get_devices(hass, discovery_type, keys, proxy):
    """Get the HomeMatic devices for given discovery_type."""
    device_arr = []

    for key in keys:
        device = hass.data[DATA_HOMEMATIC].devices[proxy][key]
        class_name = device.__class__.__name__
        metadata = {}

        # Class not supported by discovery type
        if class_name not in HM_DEVICE_TYPES[discovery_type]:
            continue

        # Load metadata needed to generate a parameter list
        if discovery_type == DISCOVER_SENSORS:
            metadata.update(device.SENSORNODE)
        elif discovery_type == DISCOVER_BINARY_SENSORS:
            metadata.update(device.BINARYNODE)
        else:
            metadata.update({None: device.ELEMENT})

        # Generate options for 1...n elements with 1...n parameters
        for param, channels in metadata.items():
            if param in HM_IGNORE_DISCOVERY_NODE:
                continue

            # Add devices
            _LOGGER.debug("%s: Handling %s: %s: %s",
                          discovery_type, key, param, channels)
            for channel in channels:
                name = _create_ha_name(
                    name=device.NAME, channel=channel, param=param,
                    count=len(channels)
                )
                device_dict = {
                    CONF_PLATFORM: "homematic",
                    ATTR_ADDRESS: key,
                    ATTR_PROXY: proxy,
                    ATTR_NAME: name,
                    ATTR_CHANNEL: channel
                }
                if param is not None:
                    device_dict[ATTR_PARAM] = param

                # Add new device
                try:
                    DEVICE_SCHEMA(device_dict)
                    device_arr.append(device_dict)
                except vol.MultipleInvalid as err:
                    _LOGGER.error("Invalid device config: %s",
                                  str(err))
    return device_arr


def _create_ha_name(name, channel, param, count):
    """Generate a unique entity id."""
    # HMDevice is a simple device
    if count == 1 and param is None:
        return name

    # Has multiple elements/channels
    if count > 1 and param is None:
        return "{} {}".format(name, channel)

    # With multiple parameters on first channel
    if count == 1 and param is not None:
        return "{} {}".format(name, param)

    # Multiple parameters with multiple channels
    if count > 1 and param is not None:
        return "{} {} {}".format(name, channel, param)


def _hm_event_handler(hass, proxy, device, caller, attribute, value):
    """Handle all pyhomematic device events."""
    try:
        channel = int(device.split(":")[1])
        address = device.split(":")[0]
        hmdevice = hass.data[DATA_HOMEMATIC].devices[proxy].get(address)
    except (TypeError, ValueError):
        _LOGGER.error("Event handling channel convert error!")
        return

    # Return if not an event supported by device
    if attribute not in hmdevice.EVENTNODE:
        return

    _LOGGER.debug("Event %s for %s channel %i", attribute,
                  hmdevice.NAME, channel)

    # Keypress event
    if attribute in HM_PRESS_EVENTS:
        hass.bus.fire(EVENT_KEYPRESS, {
            ATTR_NAME: hmdevice.NAME,
            ATTR_PARAM: attribute,
            ATTR_CHANNEL: channel
        })
        return

    # Impulse event
    if attribute in HM_IMPULSE_EVENTS:
        hass.bus.fire(EVENT_IMPULSE, {
            ATTR_NAME: hmdevice.NAME,
            ATTR_CHANNEL: channel
        })
        return

    _LOGGER.warning("Event is unknown and not forwarded")


def _device_from_servicecall(hass, service):
    """Extract HomeMatic device from service call."""
    address = service.data.get(ATTR_ADDRESS)
    proxy = service.data.get(ATTR_PROXY)
    if address == 'BIDCOS-RF':
        address = 'BidCoS-RF'

    if proxy:
        return hass.data[DATA_HOMEMATIC].devices[proxy].get(address)

    for _, devices in hass.data[DATA_HOMEMATIC].devices.items():
        if address in devices:
            return devices[address]


class HMHub(Entity):
    """The HomeMatic hub. (CCU2/HomeGear)."""

    def __init__(self, hass, homematic, name, use_variables):
        """Initialize HomeMatic hub."""
        self.hass = hass
        self.entity_id = "{}.{}".format(DOMAIN, name.lower())
        self._homematic = homematic
        self._variables = {}
        self._name = name
        self._state = STATE_UNKNOWN
        self._use_variables = use_variables

        # Load data
        track_time_interval(
            self.hass, self._update_hub, SCAN_INTERVAL_HUB)
        self.hass.add_job(self._update_hub, None)

        if self._use_variables:
            track_time_interval(
                self.hass, self._update_variables, SCAN_INTERVAL_VARIABLES)
            self.hass.add_job(self._update_variables, None)

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def should_poll(self):
        """Return false. HomeMatic Hub object updates variables."""
        return False

    @property
    def state(self):
        """Return the state of the entity."""
        return self._state

    @property
    def state_attributes(self):
        """Return the state attributes."""
        attr = self._variables.copy()
        return attr

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return "mdi:gradient"

    def _update_hub(self, now):
        """Retrieve latest state."""
        service_message = self._homematic.getServiceMessages(self._name)
        state = None if service_message is None else len(service_message)

        # state have change?
        if self._state != state:
            self._state = state
            self.schedule_update_ha_state()

    def _update_variables(self, now):
        """Retrive all variable data and update hmvariable states."""
        variables = self._homematic.getAllSystemVariables(self._name)
        if variables is None:
            return

        state_change = False
        for key, value in variables.items():
            if key in self._variables and value == self._variables[key]:
                continue

            state_change = True
            self._variables.update({key: value})

        if state_change:
            self.schedule_update_ha_state()

    def hm_set_variable(self, name, value):
        """Set variable value on CCU/Homegear."""
        if name not in self._variables:
            _LOGGER.error("Variable %s not found on %s", name, self.name)
            return
        old_value = self._variables.get(name)
        if isinstance(old_value, bool):
            value = cv.boolean(value)
        else:
            value = float(value)
        self._homematic.setSystemVariable(self.name, name, value)

        self._variables.update({name: value})
        self.schedule_update_ha_state()


class HMDevice(Entity):
    """The HomeMatic device base object."""

    def __init__(self, config):
        """Initialize a generic HomeMatic device."""
        self._name = config.get(ATTR_NAME)
        self._address = config.get(ATTR_ADDRESS)
        self._proxy = config.get(ATTR_PROXY)
        self._channel = config.get(ATTR_CHANNEL)
        self._state = config.get(ATTR_PARAM)
        self._data = {}
        self._homematic = None
        self._hmdevice = None
        self._connected = False
        self._available = False

        # Set parameter to uppercase
        if self._state:
            self._state = self._state.upper()

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Load data init callbacks."""
        yield from self.hass.async_add_job(self.link_homematic)

    @property
    def should_poll(self):
        """Return false. HomeMatic states are pushed by the XML-RPC Server."""
        return False

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def assumed_state(self):
        """Return true if unable to access real state of the device."""
        return not self._available

    @property
    def available(self):
        """Return true if device is available."""
        return self._available

    @property
    def device_state_attributes(self):
        """Return device specific state attributes."""
        attr = {}

        # No data available
        if not self.available:
            return attr

        # Generate a dictionary with attributes
        for node, data in HM_ATTRIBUTE_SUPPORT.items():
            # Is an attribute and exists for this object
            if node in self._data:
                value = data[1].get(self._data[node], self._data[node])
                attr[data[0]] = value

        # Static attributes
        attr['id'] = self._hmdevice.ADDRESS
        attr['proxy'] = self._proxy

        return attr

    def link_homematic(self):
        """Connect to HomeMatic."""
        if self._connected:
            return True

        # Initialize
        self._homematic = self.hass.data[DATA_HOMEMATIC]
        self._hmdevice = self._homematic.devices[self._proxy][self._address]
        self._connected = True

        try:
            # Initialize datapoints of this object
            self._init_data()
            self._load_data_from_hm()

            # Link events from pyhomematic
            self._subscribe_homematic_events()
            self._available = not self._hmdevice.UNREACH
        # pylint: disable=broad-except
        except Exception as err:
            self._connected = False
            _LOGGER.error("Exception while linking %s: %s",
                          self._address, str(err))

    def _hm_event_callback(self, device, caller, attribute, value):
        """Handle all pyhomematic device events."""
        _LOGGER.debug("%s received event '%s' value: %s", self._name,
                      attribute, value)
        has_changed = False

        # Is data needed for this instance?
        if attribute in self._data:
            # Did data change?
            if self._data[attribute] != value:
                self._data[attribute] = value
                has_changed = True

        # Availability has changed
        if attribute == 'UNREACH':
            self._available = bool(value)
            has_changed = True

        # If it has changed data point, update HASS
        if has_changed:
            self.schedule_update_ha_state()

    def _subscribe_homematic_events(self):
        """Subscribe all required events to handle job."""
        channels_to_sub = set()
        channels_to_sub.add(0)  # Add channel 0 for UNREACH

        # Push data to channels_to_sub from hmdevice metadata
        for metadata in (self._hmdevice.SENSORNODE, self._hmdevice.BINARYNODE,
                         self._hmdevice.ATTRIBUTENODE,
                         self._hmdevice.WRITENODE, self._hmdevice.EVENTNODE,
                         self._hmdevice.ACTIONNODE):
            for node, channels in metadata.items():
                # Data is needed for this instance
                if node in self._data:
                    # chan is current channel
                    if len(channels) == 1:
                        channel = channels[0]
                    else:
                        channel = self._channel

                    # Prepare for subscription
                    try:
                        channels_to_sub.add(int(channel))
                    except (ValueError, TypeError):
                        _LOGGER.error("Invalid channel in metadata from %s",
                                      self._name)

        # Set callbacks
        for channel in channels_to_sub:
            _LOGGER.debug(
                "Subscribe channel %d from %s", channel, self._name)
            self._hmdevice.setEventCallback(
                callback=self._hm_event_callback, bequeath=False,
                channel=channel)

    def _load_data_from_hm(self):
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
                if metadata[node] and node in self._data:
                    self._data[node] = funct(name=node, channel=self._channel)

        return True

    def _hm_set_state(self, value):
        """Set data to main datapoint."""
        if self._state in self._data:
            self._data[self._state] = value

    def _hm_get_state(self):
        """Get data from main datapoint."""
        if self._state in self._data:
            return self._data[self._state]
        return None

    def _init_data(self):
        """Generate a data dict (self._data) from the HomeMatic metadata."""
        # Add all attributes to data dictionary
        for data_note in self._hmdevice.ATTRIBUTENODE:
            self._data.update({data_note: STATE_UNKNOWN})

        # Initialize device specific data
        self._init_data_struct()

    def _init_data_struct(self):
        """Generate a data dictionary from the HomeMatic device metadata."""
        raise NotImplementedError
