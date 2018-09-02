"""
Support for HomeMatic devices.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/homematic/
"""
import asyncio
from datetime import timedelta
from functools import partial
import logging
import socket

import voluptuous as vol

from homeassistant.const import (
    ATTR_ENTITY_ID, ATTR_NAME, CONF_HOST, CONF_HOSTS, CONF_PASSWORD,
    CONF_PLATFORM, CONF_USERNAME, EVENT_HOMEASSISTANT_STOP, STATE_UNKNOWN)
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.loader import bind_hass

REQUIREMENTS = ['pyhomematic==0.1.47']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'homematic'

SCAN_INTERVAL_HUB = timedelta(seconds=300)
SCAN_INTERVAL_VARIABLES = timedelta(seconds=30)

DISCOVER_SWITCHES = 'homematic.switch'
DISCOVER_LIGHTS = 'homematic.light'
DISCOVER_SENSORS = 'homematic.sensor'
DISCOVER_BINARY_SENSORS = 'homematic.binary_sensor'
DISCOVER_COVER = 'homematic.cover'
DISCOVER_CLIMATE = 'homematic.climate'
DISCOVER_LOCKS = 'homematic.locks'

ATTR_DISCOVER_DEVICES = 'devices'
ATTR_PARAM = 'param'
ATTR_CHANNEL = 'channel'
ATTR_ADDRESS = 'address'
ATTR_VALUE = 'value'
ATTR_INTERFACE = 'interface'
ATTR_ERRORCODE = 'error'
ATTR_MESSAGE = 'message'
ATTR_MODE = 'mode'
ATTR_TIME = 'time'
ATTR_UNIQUE_ID = 'unique_id'
ATTR_PARAMSET_KEY = 'paramset_key'
ATTR_PARAMSET = 'paramset'

EVENT_KEYPRESS = 'homematic.keypress'
EVENT_IMPULSE = 'homematic.impulse'
EVENT_ERROR = 'homematic.error'

SERVICE_VIRTUALKEY = 'virtualkey'
SERVICE_RECONNECT = 'reconnect'
SERVICE_SET_VARIABLE_VALUE = 'set_variable_value'
SERVICE_SET_DEVICE_VALUE = 'set_device_value'
SERVICE_SET_INSTALL_MODE = 'set_install_mode'
SERVICE_PUT_PARAMSET = 'put_paramset'

HM_DEVICE_TYPES = {
    DISCOVER_SWITCHES: [
        'Switch', 'SwitchPowermeter', 'IOSwitch', 'IPSwitch', 'RFSiren',
        'IPSwitchPowermeter', 'HMWIOSwitch', 'Rain', 'EcoLogic',
        'IPKeySwitchPowermeter'],
    DISCOVER_LIGHTS: ['Dimmer', 'KeyDimmer', 'IPKeyDimmer'],
    DISCOVER_SENSORS: [
        'SwitchPowermeter', 'Motion', 'MotionV2', 'RemoteMotion', 'MotionIP',
        'ThermostatWall', 'AreaThermostat', 'RotaryHandleSensor',
        'WaterSensor', 'PowermeterGas', 'LuxSensor', 'WeatherSensor',
        'WeatherStation', 'ThermostatWall2', 'TemperatureDiffSensor',
        'TemperatureSensor', 'CO2Sensor', 'IPSwitchPowermeter', 'HMWIOSwitch',
        'FillingLevel', 'ValveDrive', 'EcoLogic', 'IPThermostatWall',
        'IPSmoke', 'RFSiren', 'PresenceIP', 'IPAreaThermostat',
        'IPWeatherSensor', 'RotaryHandleSensorIP', 'IPPassageSensor',
        'IPKeySwitchPowermeter', 'IPThermostatWall230V'],
    DISCOVER_CLIMATE: [
        'Thermostat', 'ThermostatWall', 'MAXThermostat', 'ThermostatWall2',
        'MAXWallThermostat', 'IPThermostat', 'IPThermostatWall',
        'ThermostatGroup', 'IPThermostatWall230V'],
    DISCOVER_BINARY_SENSORS: [
        'ShutterContact', 'Smoke', 'SmokeV2', 'Motion', 'MotionV2',
        'MotionIP', 'RemoteMotion', 'WeatherSensor', 'TiltSensor',
        'IPShutterContact', 'HMWIOSwitch', 'MaxShutterContact', 'Rain',
        'WiredSensor', 'PresenceIP', 'IPWeatherSensor', 'IPPassageSensor',
        'SmartwareMotion'],
    DISCOVER_COVER: ['Blind', 'KeyBlind', 'IPKeyBlind', 'IPKeyBlindTilt'],
    DISCOVER_LOCKS: ['KeyMatic']
}

HM_IGNORE_DISCOVERY_NODE = [
    'ACTUAL_TEMPERATURE',
    'ACTUAL_HUMIDITY'
]

HM_IGNORE_DISCOVERY_NODE_EXCEPTIONS = {
    'ACTUAL_TEMPERATURE': ['IPAreaThermostat', 'IPWeatherSensor'],
}

HM_ATTRIBUTE_SUPPORT = {
    'LOWBAT': ['battery', {0: 'High', 1: 'Low'}],
    'LOW_BAT': ['battery', {0: 'High', 1: 'Low'}],
    'ERROR': ['sabotage', {0: 'No', 1: 'Yes'}],
    'SABOTAGE': ['sabotage', {0: 'No', 1: 'Yes'}],
    'RSSI_PEER': ['rssi', {}],
    'VALVE_STATE': ['valve', {}],
    'BATTERY_STATE': ['battery', {}],
    'CONTROL_MODE': ['mode', {
        0: 'Auto',
        1: 'Manual',
        2: 'Away',
        3: 'Boost',
        4: 'Comfort',
        5: 'Lowering'
    }],
    'POWER': ['power', {}],
    'CURRENT': ['current', {}],
    'VOLTAGE': ['voltage', {}],
    'OPERATING_VOLTAGE': ['voltage', {}],
    'WORKING': ['working', {0: 'No', 1: 'Yes'}]
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

CONF_RESOLVENAMES_OPTIONS = [
    'metadata',
    'json',
    'xml',
    False
]

DATA_HOMEMATIC = 'homematic'
DATA_STORE = 'homematic_store'
DATA_CONF = 'homematic_conf'

CONF_INTERFACES = 'interfaces'
CONF_LOCAL_IP = 'local_ip'
CONF_LOCAL_PORT = 'local_port'
CONF_PORT = 'port'
CONF_PATH = 'path'
CONF_CALLBACK_IP = 'callback_ip'
CONF_CALLBACK_PORT = 'callback_port'
CONF_RESOLVENAMES = 'resolvenames'
CONF_JSONPORT = 'jsonport'
CONF_VARIABLES = 'variables'
CONF_DEVICES = 'devices'
CONF_PRIMARY = 'primary'

DEFAULT_LOCAL_IP = '0.0.0.0'
DEFAULT_LOCAL_PORT = 0
DEFAULT_RESOLVENAMES = False
DEFAULT_JSONPORT = 80
DEFAULT_PORT = 2001
DEFAULT_PATH = ''
DEFAULT_USERNAME = 'Admin'
DEFAULT_PASSWORD = ''


DEVICE_SCHEMA = vol.Schema({
    vol.Required(CONF_PLATFORM): 'homematic',
    vol.Required(ATTR_NAME): cv.string,
    vol.Required(ATTR_ADDRESS): cv.string,
    vol.Required(ATTR_INTERFACE): cv.string,
    vol.Optional(ATTR_CHANNEL, default=1): vol.Coerce(int),
    vol.Optional(ATTR_PARAM): cv.string,
    vol.Optional(ATTR_UNIQUE_ID): cv.string,
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_INTERFACES, default={}): {cv.match_all: {
            vol.Required(CONF_HOST): cv.string,
            vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
            vol.Optional(CONF_PATH, default=DEFAULT_PATH): cv.string,
            vol.Optional(CONF_RESOLVENAMES, default=DEFAULT_RESOLVENAMES):
                vol.In(CONF_RESOLVENAMES_OPTIONS),
            vol.Optional(CONF_JSONPORT, default=DEFAULT_JSONPORT): cv.port,
            vol.Optional(CONF_USERNAME, default=DEFAULT_USERNAME): cv.string,
            vol.Optional(CONF_PASSWORD, default=DEFAULT_PASSWORD): cv.string,
            vol.Optional(CONF_CALLBACK_IP): cv.string,
            vol.Optional(CONF_CALLBACK_PORT): cv.port,
        }},
        vol.Optional(CONF_HOSTS, default={}): {cv.match_all: {
            vol.Required(CONF_HOST): cv.string,
            vol.Optional(CONF_USERNAME, default=DEFAULT_USERNAME): cv.string,
            vol.Optional(CONF_PASSWORD, default=DEFAULT_PASSWORD): cv.string,
        }},
        vol.Optional(CONF_LOCAL_IP, default=DEFAULT_LOCAL_IP): cv.string,
        vol.Optional(CONF_LOCAL_PORT): cv.port,
    }),
}, extra=vol.ALLOW_EXTRA)

SCHEMA_SERVICE_VIRTUALKEY = vol.Schema({
    vol.Required(ATTR_ADDRESS): vol.All(cv.string, vol.Upper),
    vol.Required(ATTR_CHANNEL): vol.Coerce(int),
    vol.Required(ATTR_PARAM): cv.string,
    vol.Optional(ATTR_INTERFACE): cv.string,
})

SCHEMA_SERVICE_SET_VARIABLE_VALUE = vol.Schema({
    vol.Required(ATTR_NAME): cv.string,
    vol.Required(ATTR_VALUE): cv.match_all,
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
})

SCHEMA_SERVICE_SET_DEVICE_VALUE = vol.Schema({
    vol.Required(ATTR_ADDRESS): vol.All(cv.string, vol.Upper),
    vol.Required(ATTR_CHANNEL): vol.Coerce(int),
    vol.Required(ATTR_PARAM): vol.All(cv.string, vol.Upper),
    vol.Required(ATTR_VALUE): cv.match_all,
    vol.Optional(ATTR_INTERFACE): cv.string,
})

SCHEMA_SERVICE_RECONNECT = vol.Schema({})

SCHEMA_SERVICE_SET_INSTALL_MODE = vol.Schema({
    vol.Required(ATTR_INTERFACE): cv.string,
    vol.Optional(ATTR_TIME, default=60): cv.positive_int,
    vol.Optional(ATTR_MODE, default=1):
        vol.All(vol.Coerce(int), vol.In([1, 2])),
    vol.Optional(ATTR_ADDRESS): vol.All(cv.string, vol.Upper),
})

SCHEMA_SERVICE_PUT_PARAMSET = vol.Schema({
    vol.Required(ATTR_INTERFACE): cv.string,
    vol.Required(ATTR_ADDRESS): vol.All(cv.string, vol.Upper),
    vol.Required(ATTR_PARAMSET_KEY): vol.All(cv.string, vol.Upper),
    vol.Required(ATTR_PARAMSET): dict,
})


@bind_hass
def virtualkey(hass, address, channel, param, interface=None):
    """Send virtual keypress to homematic controller."""
    data = {
        ATTR_ADDRESS: address,
        ATTR_CHANNEL: channel,
        ATTR_PARAM: param,
        ATTR_INTERFACE: interface,
    }

    hass.services.call(DOMAIN, SERVICE_VIRTUALKEY, data)


@bind_hass
def set_variable_value(hass, entity_id, value):
    """Change value of a Homematic system variable."""
    data = {
        ATTR_ENTITY_ID: entity_id,
        ATTR_VALUE: value,
    }

    hass.services.call(DOMAIN, SERVICE_SET_VARIABLE_VALUE, data)


@bind_hass
def set_device_value(hass, address, channel, param, value, interface=None):
    """Call setValue XML-RPC method of supplied interface."""
    data = {
        ATTR_ADDRESS: address,
        ATTR_CHANNEL: channel,
        ATTR_PARAM: param,
        ATTR_VALUE: value,
        ATTR_INTERFACE: interface,
    }

    hass.services.call(DOMAIN, SERVICE_SET_DEVICE_VALUE, data)


@bind_hass
def put_paramset(hass, interface, address, paramset_key, paramset):
    """Call putParamset XML-RPC method of supplied interface."""
    data = {
        ATTR_INTERFACE: interface,
        ATTR_ADDRESS: address,
        ATTR_PARAMSET_KEY: paramset_key,
        ATTR_PARAMSET: paramset,
    }

    hass.services.call(DOMAIN, SERVICE_PUT_PARAMSET, data)


@bind_hass
def set_install_mode(hass, interface, mode=None, time=None, address=None):
    """Call setInstallMode XML-RPC method of supplied interface."""
    data = {
        key: value for key, value in (
            (ATTR_INTERFACE, interface),
            (ATTR_MODE, mode),
            (ATTR_TIME, time),
            (ATTR_ADDRESS, address)
        ) if value
    }

    hass.services.call(DOMAIN, SERVICE_SET_INSTALL_MODE, data)


@bind_hass
def reconnect(hass):
    """Reconnect to CCU/Homegear."""
    hass.services.call(DOMAIN, SERVICE_RECONNECT, {})


def setup(hass, config):
    """Set up the Homematic component."""
    from pyhomematic import HMConnection

    conf = config[DOMAIN]
    hass.data[DATA_CONF] = remotes = {}
    hass.data[DATA_STORE] = set()

    # Create hosts-dictionary for pyhomematic
    for rname, rconfig in conf[CONF_INTERFACES].items():
        remotes[rname] = {
            'ip': socket.gethostbyname(rconfig.get(CONF_HOST)),
            'port': rconfig.get(CONF_PORT),
            'path': rconfig.get(CONF_PATH),
            'resolvenames': rconfig.get(CONF_RESOLVENAMES),
            'jsonport': rconfig.get(CONF_JSONPORT),
            'username': rconfig.get(CONF_USERNAME),
            'password': rconfig.get(CONF_PASSWORD),
            'callbackip': rconfig.get(CONF_CALLBACK_IP),
            'callbackport': rconfig.get(CONF_CALLBACK_PORT),
            'connect': True,
        }

    for sname, sconfig in conf[CONF_HOSTS].items():
        remotes[sname] = {
            'ip': socket.gethostbyname(sconfig.get(CONF_HOST)),
            'port': DEFAULT_PORT,
            'username': sconfig.get(CONF_USERNAME),
            'password': sconfig.get(CONF_PASSWORD),
            'connect': False,
        }

    # Create server thread
    bound_system_callback = partial(_system_callback_handler, hass, config)
    hass.data[DATA_HOMEMATIC] = homematic = HMConnection(
        local=config[DOMAIN].get(CONF_LOCAL_IP),
        localport=config[DOMAIN].get(CONF_LOCAL_PORT, DEFAULT_LOCAL_PORT),
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
    for hub_name in conf[CONF_HOSTS].keys():
        entity_hubs.append(HMHub(hass, homematic, hub_name))

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
        DOMAIN, SERVICE_SET_VARIABLE_VALUE, _service_handle_value,
        schema=SCHEMA_SERVICE_SET_VARIABLE_VALUE)

    def _service_handle_reconnect(service):
        """Service to reconnect all HomeMatic hubs."""
        homematic.reconnect()

    hass.services.register(
        DOMAIN, SERVICE_RECONNECT, _service_handle_reconnect,
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
        DOMAIN, SERVICE_SET_DEVICE_VALUE, _service_handle_device,
        schema=SCHEMA_SERVICE_SET_DEVICE_VALUE)

    def _service_handle_install_mode(service):
        """Service to set interface into install mode."""
        interface = service.data.get(ATTR_INTERFACE)
        mode = service.data.get(ATTR_MODE)
        time = service.data.get(ATTR_TIME)
        address = service.data.get(ATTR_ADDRESS)

        homematic.setInstallMode(interface, t=time, mode=mode, address=address)

    hass.services.register(
        DOMAIN, SERVICE_SET_INSTALL_MODE, _service_handle_install_mode,
        schema=SCHEMA_SERVICE_SET_INSTALL_MODE)

    def _service_put_paramset(service):
        """Service to call the putParamset method on a HomeMatic connection."""
        interface = service.data.get(ATTR_INTERFACE)
        address = service.data.get(ATTR_ADDRESS)
        paramset_key = service.data.get(ATTR_PARAMSET_KEY)
        # When passing in the paramset from a YAML file we get an OrderedDict
        # here instead of a dict, so add this explicit cast.
        # The service schema makes sure that this cast works.
        paramset = dict(service.data.get(ATTR_PARAMSET))

        _LOGGER.debug(
            "Calling putParamset: %s, %s, %s, %s",
            interface, address, paramset_key, paramset
        )
        homematic.putParamset(interface, address, paramset_key, paramset)

    hass.services.register(
        DOMAIN, SERVICE_PUT_PARAMSET, _service_put_paramset,
        schema=SCHEMA_SERVICE_PUT_PARAMSET)

    return True


def _system_callback_handler(hass, config, src, *args):
    """System callback handler."""
    # New devices available at hub
    if src == 'newDevices':
        (interface_id, dev_descriptions) = args
        interface = interface_id.split('-')[-1]

        # Device support active?
        if not hass.data[DATA_CONF][interface]['connect']:
            return

        addresses = []
        for dev in dev_descriptions:
            address = dev['ADDRESS'].split(':')[0]
            if address not in hass.data[DATA_STORE]:
                hass.data[DATA_STORE].add(address)
                addresses.append(address)

        # Register EVENTS
        # Search all devices with an EVENTNODE that includes data
        bound_event_callback = partial(_hm_event_handler, hass, interface)
        for dev in addresses:
            hmdevice = hass.data[DATA_HOMEMATIC].devices[interface].get(dev)

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
                    ('climate', DISCOVER_CLIMATE),
                    ('lock', DISCOVER_LOCKS)):
                # Get all devices of a specific type
                found_devices = _get_devices(
                    hass, discovery_type, addresses, interface)

                # When devices of this type are found
                # they are setup in HASS and a discovery event is fired
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


def _get_devices(hass, discovery_type, keys, interface):
    """Get the HomeMatic devices for given discovery_type."""
    device_arr = []

    for key in keys:
        device = hass.data[DATA_HOMEMATIC].devices[interface][key]
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
            if param in HM_IGNORE_DISCOVERY_NODE and class_name not in \
             HM_IGNORE_DISCOVERY_NODE_EXCEPTIONS.get(param, []):
                continue

            # Add devices
            _LOGGER.debug("%s: Handling %s: %s: %s",
                          discovery_type, key, param, channels)
            for channel in channels:
                name = _create_ha_id(
                    name=device.NAME, channel=channel, param=param,
                    count=len(channels)
                )
                unique_id = _create_ha_id(
                    name=key, channel=channel, param=param,
                    count=len(channels)
                )
                device_dict = {
                    CONF_PLATFORM: "homematic",
                    ATTR_ADDRESS: key,
                    ATTR_INTERFACE: interface,
                    ATTR_NAME: name,
                    ATTR_CHANNEL: channel,
                    ATTR_UNIQUE_ID: unique_id
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


def _create_ha_id(name, channel, param, count):
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


def _hm_event_handler(hass, interface, device, caller, attribute, value):
    """Handle all pyhomematic device events."""
    try:
        channel = int(device.split(":")[1])
        address = device.split(":")[0]
        hmdevice = hass.data[DATA_HOMEMATIC].devices[interface].get(address)
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
    interface = service.data.get(ATTR_INTERFACE)
    if address == 'BIDCOS-RF':
        address = 'BidCoS-RF'

    if interface:
        return hass.data[DATA_HOMEMATIC].devices[interface].get(address)

    for devices in hass.data[DATA_HOMEMATIC].devices.values():
        if address in devices:
            return devices[address]


class HMHub(Entity):
    """The HomeMatic hub. (CCU2/HomeGear)."""

    def __init__(self, hass, homematic, name):
        """Initialize HomeMatic hub."""
        self.hass = hass
        self.entity_id = "{}.{}".format(DOMAIN, name.lower())
        self._homematic = homematic
        self._variables = {}
        self._name = name
        self._state = None

        # Load data
        self.hass.helpers.event.track_time_interval(
            self._update_hub, SCAN_INTERVAL_HUB)
        self.hass.add_job(self._update_hub, None)

        self.hass.helpers.event.track_time_interval(
            self._update_variables, SCAN_INTERVAL_VARIABLES)
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
        """Retrieve all variable data and update hmvariable states."""
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
        self._interface = config.get(ATTR_INTERFACE)
        self._channel = config.get(ATTR_CHANNEL)
        self._state = config.get(ATTR_PARAM)
        self._unique_id = config.get(ATTR_UNIQUE_ID)
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
    def unique_id(self):
        """Return unique ID. HomeMatic entity IDs are unique by default."""
        return self._unique_id.replace(" ", "_")

    @property
    def should_poll(self):
        """Return false. HomeMatic states are pushed by the XML-RPC Server."""
        return False

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def available(self):
        """Return true if device is available."""
        return self._available

    @property
    def device_state_attributes(self):
        """Return device specific state attributes."""
        attr = {}

        # Generate a dictionary with attributes
        for node, data in HM_ATTRIBUTE_SUPPORT.items():
            # Is an attribute and exists for this object
            if node in self._data:
                value = data[1].get(self._data[node], self._data[node])
                attr[data[0]] = value

        # Static attributes
        attr['id'] = self._hmdevice.ADDRESS
        attr['interface'] = self._interface

        return attr

    def link_homematic(self):
        """Connect to HomeMatic."""
        if self._connected:
            return True

        # Initialize
        self._homematic = self.hass.data[DATA_HOMEMATIC]
        self._hmdevice = \
            self._homematic.devices[self._interface][self._address]
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
            self._available = not bool(value)
            has_changed = True
        elif not self.available:
            self._available = False
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
