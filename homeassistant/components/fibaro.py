"""
Support for the Fibaro devices.

To enable, add the following section to configuration.yaml:
[fibaro]
    url: "http://yourfibarohc/api/"
    username: "your@superuseremail.com"
    password: "YourPassword1"

For more detailed debugging, you can enable it in the [logger] section of you
configuration.yaml, like this:
[logger]
    logs:
        homeassistant.components.fibaro: debug
"""

import logging
from collections import defaultdict
import voluptuous as vol
from homeassistant.const import (ATTR_ARMED, ATTR_BATTERY_LEVEL,
                                 CONF_PASSWORD, CONF_URL, CONF_USERNAME)
import homeassistant.helpers.config_validation as cv
from homeassistant.util import convert, slugify
from homeassistant.helpers import discovery
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['fiblary3==0.1.7']

_LOGGER = logging.getLogger(__name__)
DOMAIN = 'fibaro'
FIBARO_DEVICES = 'fibaro_devices'
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

FIBARO_TYPEMAP = {
    'com.fibaro.multilevelSensor': "sensor",
    'com.fibaro.binarySwitch': 'switch',
    'com.fibaro.FGRGBW441M': 'light',
    'com.fibaro.multilevelSwitch': 'switch',
    'com.fibaro.FGD212': 'light',
    'com.fibaro.FGR': 'cover',
    'com.fibaro.doorSensor': 'binary_sensor',
    'com.fibaro.FGMS001v2': 'binary_sensor',
    'com.fibaro.lightSensor': 'sensor',
    'com.fibaro.seismometer': 'sensor',
    'com.fibaro.accelerometer': 'sensor',
    'com.fibaro.FGSS001': 'sensor',
    'com.fibaro.remoteSwitch': 'switch',
    'com.fibaro.sensor': 'sensor',
    'com.fibaro.colorController': 'sensor'
}

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_URL): cv.string
    })
}, extra=vol.ALLOW_EXTRA)


class FibaroController():
    """Initiate Fibaro Controller Class."""

    my_rooms = None             # Dict for mapping roomId to room object
    my_devices = None           # Dict for mapping deviceId to device object
    my_fibaro_devices = None    # List of devices by type
    callbacks = {}              # Dict of update value callbacks by deviceId
    client = None               # Fiblary's Client object for communication
    state_handler = None        # Fiblary's StateHandler object

    def __init__(self, username, password, url):
        """Initialize the communication with the Fibaro controller."""
        from fiblary3.client.v4.client import Client as FibaroClient
        self.client = FibaroClient(url, username, password)

        login = self.client.login.get()
        if login is None or login.status is False:
            _LOGGER.error("Invalid login for Fibaro HC. "
                          "Please check username and password.")
            self.client = None
            return
        self._read_rooms()
        self._read_devices()

    def __del__(self):
        """Deinitialize the Fibaro Controller"""
        if self.state_handler:
            self.disable_state_handler()

    def enable_state_handler(self):
        """Start StateHandler thread for monitoring updates"""
        from fiblary3.client.v4.client import StateHandler
        self.state_handler = StateHandler(self.client, self._on_state_change)

    def disable_state_handler(self):
        """Stop StateHandler thread used for monitoring updates"""
        self.state_handler.stop()
        self.state_handler = None

    def _on_state_change(self, state):
        """Handle change report received from the HomeCenter."""
        for change in state.get('changes', []):
            device_id = change.pop('id')
            for property_name, value in list(change.items()):
                if property_name == "log" and value and value != "transfer OK":
                    _LOGGER.info("LOG %s: %s",
                                 self.my_devices[device_id].friendly_name,
                                 value)
                    continue
                if property_name in self.my_devices[device_id].properties:
                    self.my_devices[device_id].properties[property_name] = \
                        value
                else:
                    _LOGGER.warning("Error updating %s data of %s, not found",
                                    property_name,
                                    self.my_devices[device_id].friendly_name)
                if self.callbacks.get(device_id, None):
                    self.callbacks[device_id]()

    def register(self, device_id, callback):
        """Register device with a callback for updates."""
        self.callbacks[device_id] = callback

    def _read_rooms(self):
        """Read and process the room list."""
        rooms = self.client.rooms.list()
        self.my_rooms = {}
        for room in rooms:
            self.my_rooms[room.id] = room
        return True

    def _read_devices(self):
        """Read and process the device list."""
        devices = self.client.devices.list()
        self.my_devices = {}
        for device in devices:
            if device.roomID == 0:
                room_name = 'Unknown'
            else:
                room_name = self.my_rooms[device.roomID].name
            device.friendly_name = room_name + '_' + device.name
            self.my_devices[device.id] = device
        self.my_fibaro_devices = defaultdict(list)
        for _, device in self.my_devices.items():
            if (device.enabled is True) and (device.visible is True):
                device_type = FIBARO_TYPEMAP.get(
                    device.type,
                    FIBARO_TYPEMAP.get(device.baseType, None))
                if device_type == 'switch' and \
                        'isLight' in device.properties and \
                        device.properties.isLight == 'true':
                    device_type = 'light'
                device.mapped_type = device_type
                if device_type:
                    self.my_fibaro_devices[device_type].append(device)
        return True


def setup(hass, config):
    """Set up the Fibaro Component."""
    username = config[DOMAIN][CONF_USERNAME]
    password = config[DOMAIN][CONF_PASSWORD]
    url = config[DOMAIN][CONF_URL]
    controller = FibaroController(username, password, url)
    hass.data[FIBARO_CONTROLLER] = controller
    hass.data[FIBARO_DEVICES] = controller.my_fibaro_devices

    for component in FIBARO_COMPONENTS:
        discovery.load_platform(hass, component, DOMAIN, {}, config)

    controller.enable_state_handler()

    return True


class FibaroDevice(Entity):
    """Representation of a Fibaro device entity."""

    def __init__(self, fibaro_device, controller):
        """Initialize the device."""
        self.fibaro_device = fibaro_device
        self.controller = controller

        self._name = fibaro_device.friendly_name
        # Append device id to prevent name clashes in HA.
        self.ha_id = FIBARO_ID_FORMAT.format(
            slugify(self._name), fibaro_device.id)
        self.fibaro_device.ha_id = self.ha_id
        self.controller.register(fibaro_device.id, self._update_callback)

    def _update_callback(self):
        """Update the state."""
        self.schedule_update_ha_state(True)

    def get_level(self):
        """Get the level of Fibaro device."""
        if 'value' in self.fibaro_device.properties:
            return self.fibaro_device.properties.value
        return None

    def get_level2(self):
        """Get the tilt level of Fibaro device."""
        if 'value2' in self.fibaro_device.properties:
            return self.fibaro_device.properties.value2
        return None

    def dont_know_message(self, action):
        """Make a warning in case we don't know how to perform an action."""
        _LOGGER.warning("Not sure how to setValue: %s "
                        "(available actions: %s)", str(self.ha_id),
                        str(self.fibaro_device.actions))

    def set_level(self, level):
        """Set the level of Fibaro device."""
        self.action("setValue", level)

    def set_color(self, color, white):
        """Set the tilt level of Fibaro device."""
        color_str = "{},{},{},{}".format(color[0], color[1],
                                         color[2], white)
        self.fibaro_device.properties.color = color_str
        self.action("setColor", str(color[0]), str(color[1]),
                    str(color[2]), str(white))

    def action(self, cmd, *args):
        """Perform an action on the Fibaro HC."""
        if cmd in self.fibaro_device.actions:
            getattr(self.fibaro_device, cmd)(*args)
        else:
            self.dont_know_message(cmd)

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
        if self.fibaro_device.properties.value == 'true' or \
                int(self.fibaro_device.properties.value) > 0:
            return True
        return False

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def should_poll(self):
        """Get polling requirement from fibaro device."""
        return False

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        attr = {}

        try:
            if 'battery' in self.fibaro_device.interfaces:
                attr[ATTR_BATTERY_LEVEL] = \
                    int(self.fibaro_device.properties.batteryLevel)
            if 'fibaroAlarmArm' in self.fibaro_device.interfaces:
                attr[ATTR_ARMED] = True if \
                    self.fibaro_device.properties.armed else False
            if 'power' in self.fibaro_device.interfaces:
                attr[ATTR_CURRENT_POWER_W] = convert(
                    self.fibaro_device.properties.power, float, 0.0)
            if 'energy' in self.fibaro_device.interfaces:
                attr[ATTR_CURRENT_ENERGY_KWH] = convert(
                    self.fibaro_device.properties.energy, float, 0.0)
        except (ValueError, KeyError):
            _LOGGER.error('Error while udpating attributes for %s',
                          self.ha_id)

        attr['Id'] = self.ha_id
        return attr
