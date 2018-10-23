"""
Support for the Fibaro devices.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/hive/
"""
import logging
from collections import defaultdict
import voluptuous as vol
from fiblary.client import Client
from homeassistant.const import (ATTR_ARMED, ATTR_BATTERY_LEVEL,
                                 ATTR_LAST_TRIP_TIME, ATTR_TRIPPED,
                                 EVENT_HOMEASSISTANT_STOP, CONF_PASSWORD, CONF_URL, CONF_USERNAME)
import homeassistant.helpers.config_validation as cv
from homeassistant.util import convert, slugify
from homeassistant.helpers import discovery
from homeassistant.helpers.entity import Entity

#REQUIREMENTS = ['pyhiveapi==0.2.14']

_LOGGER = logging.getLogger(__name__)
DOMAIN = 'fibaro'
FIBARO_DEVICES = 'fibaro_devices'
FIBARO_SCENES = 'fibaro_scenes'
FIBARO_CONTROLLER = 'fibaro_controller'
FIBARO_ID_FORMAT = '{}_{}'
ATTR_CURRENT_POWER_W = "current_power_w"
ATTR_CURRENT_ENERGY_KWH = "current_energy_kwh"

FIBARO_COMPONENTS = [
    'binary_sensor',
    'sensor',
    'light',
    'switch',
    # 'lock',
    # 'climate',
    'cover',
    # 'scene'
]


CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_URL): cv.string
    })
}, extra=vol.ALLOW_EXTRA)


class FibaroController:
    """Initiate Fibaro Controller Class."""

    entities = []
    fibaro_hc = None
    info = None
    rooms = None
    devices = None
    roomlist = None
    fibaro_devices = None

    def get_device_name(self, device):
        """Get room decorated name for Fibaro device."""
        if device.roomID == 0:
            room_name = 'Unknown'
        else:
            room_name = self.rooms[device.roomID].name
        device_name = room_name + '_' + device.name
        return device_name

    def _read_rooms(self):
        rooms = self.fibaro_hc.rooms.list()
        self.rooms = {}
        for room in rooms:
            self.rooms[room.id] = room
        return True

    def _read_devices(self):
        devices = self.fibaro_hc.devices.list()
        self.devices = {}
        for device in devices:
            self.devices[device.id] = device
        typemapping = {'com.fibaro.temperatureSensor' : 'sensor',
                       'com.fibaro.multilevelSensor' : "sensor",
                       'com.fibaro.humiditySensor' : 'sensor',
                       'com.fibaro.binarySwitch' : 'switch',
                       'com.fibaro.FGRGBW441M' : 'light',
                       'com.fibaro.multilevelSwitch' : 'switch',
                       'com.fibaro.FGD212' : 'light',
                       'com.fibaro.FGRM222' : 'cover',
                       'com.fibaro.FGR' : 'cover',
                       'com.fibaro.doorSensor' : 'binary_sensor',
                       'com.fibaro.FGMS001v2' : 'binary_sensor',
                       'com.fibaro.lightSensor' : 'sensor',
                       'com.fibaro.seismometer' : 'sensor',
                       'com.fibaro.accelerometer' : 'sensor',
                       'com.fibaro.FGSS001' : 'sensor',
                       'com.fibaro.remoteSwitch' : 'switch',
                       'com.fibaro.sensor': 'sensor',
                       'com.fibaro.colorController': 'sensor'
                       }
        if self.fibaro_devices is None:
            self.fibaro_devices = defaultdict(list)
        for _, device in self.devices.items():
            if (device.enabled is True) and (device.visible is True):
                if device.type in typemapping:
                    device_type = typemapping[device.type]
                elif device.baseType in typemapping:
                    device_type = typemapping[device.type]
                else:
                    continue
                if device_type is 'switch' and 'isLight' in device.properties and device.properties.isLight == 'true':
                    device_type = 'light'
                self.fibaro_devices[device_type].append(device)
        return True

    def init(self, hass, username, password, url):
        """Initialize the communication with the Fibaro controller."""
        try:
            self.fibaro_hc = Client('v4', url, username, password)
            self.info = self.fibaro_hc.info.get()
        except:
            self.fibaro_hc = None

        if self.fibaro_hc is None:
            _LOGGER.error("Failed to connect to Fibaro HC")
            return False

        login = self.fibaro_hc.login.get()
        if login is None or login.status is False:
            _LOGGER.error("Invaid login for Fibaro HC. Please check username and password.")
            return False

        self._read_rooms()
        self._read_devices()
        hass.data[FIBARO_CONTROLLER] = self
        hass.data[FIBARO_DEVICES] = self.fibaro_devices
        return True

def setup(hass, config):
    """Set up the Fibaro Component."""

    controller = FibaroController()
    username = config[DOMAIN][CONF_USERNAME]
    password = config[DOMAIN][CONF_PASSWORD]
    url = config[DOMAIN][CONF_URL]
    controller.init(hass, username, password, url)

    for component in FIBARO_COMPONENTS:
        discovery.load_platform(hass, component, DOMAIN, {}, config)

    return True

class FibaroDevice(Entity):
    """Representation of a Fibaro device entity."""

    def __init__(self, fibaro_device, controller):
        """Initialize the device."""
        self.fibaro_device = fibaro_device
        self.controller = controller

        self._name = controller.get_device_name(fibaro_device)
        # Append device id to prevent name clashes in HA.
        self.fibaro_id = FIBARO_ID_FORMAT.format(
            slugify(self._name), fibaro_device.id)

#        self.controller.register(fibaro_device, self._update_callback)

    def _update_callback(self, _device):
        """Update the state."""
        self.schedule_update_ha_state(True)

    def get_level(self):
        """Get the level of Fibaro device."""
        if 'value' in self.fibaro_device.properties:
            return self.fibaro_device.properties.value
        return None

    def set_level(self, level):
        """Set the level of Fibaro device."""
        pass

    def get_level2(self):
        """Get the tilt level of Fibaro device."""
        if 'value2' in self.fibaro_device.properties:
            return self.fibaro_device.properties.value2
        return None

    def set_level2(self, level):
        """Set the tilt level of Fibaro device."""
        pass

    def open(self):
        """Execute open command on Fibaro device."""
        pass

    def close(self):
        """Execute close command on Fibaro device."""
        pass

    def stop(self):
        """Execute stop command on Fibaro device."""
        pass

    def switch_on(self):
        """Switch on Fibaro device."""
        pass

    def switch_off(self):
        """Switch off Fibaro device."""
        pass

    @property
    def current_power_w(self):
        """Return the current power usage in W."""
        if 'power' in self.fibaro_device.properties:
            power = self.fibaro_device.properties.power
            if power:
                return convert(power, float, 0.0)
        else:
            return 0

    @property
    def current_binary_state(self):
        """Return the current binary state."""
        if self.fibaro_device.properties.value == 'false':
            return False
        if self.fibaro_device.properties.value == 'true':
            return True
        if int(self.fibaro_device.properties.value) > 0:
            return True
        return False

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def should_poll(self):
        """Get polling requirement from fibaro device."""
#        return self.fibaro_device.should_poll
        return True

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        attr = {}

        try:
            if 'battery' in self.fibaro_device.interfaces:
                attr[ATTR_BATTERY_LEVEL] = self.fibaro_device.properties.batteryLevel
        except:
            pass
        try:
            if 'fibaroAlarmArm' in self.fibaro_device.interfaces:
                armed = self.fibaro_device.properties.armed
                attr[ATTR_ARMED] = 'True' if armed else 'False'
        except:
            pass
        #
        # if self.fibaro_device.is_trippable:
        #     last_tripped = self.fibaro_device.last_trip
        #     if last_tripped is not None:
        #         utc_time = utc_from_timestamp(int(last_tripped))
        #         attr[ATTR_LAST_TRIP_TIME] = utc_time.isoformat()
        #     else:
        #         attr[ATTR_LAST_TRIP_TIME] = None
        #     tripped = self.fibaro_device.is_tripped
        #     attr[ATTR_TRIPPED] = 'True' if tripped else 'False'
        #
        try:
            if 'power' in self.fibaro_device.interfaces:
                power = float(self.fibaro_device.properties.power)
                if power:
                    attr[ATTR_CURRENT_POWER_W] = convert(power, float, 0.0)
        except:
            pass
        try:
            if 'energy' in self.fibaro_device.interfaces:
                energy = float(self.fibaro_device.properties.energy)
                if energy:
                    attr[ATTR_CURRENT_ENERGY_KWH] = convert(energy, float, 0.0)
        except:
            pass

        attr['Fibaro Device Id'] = self.fibaro_device.id

        return attr
