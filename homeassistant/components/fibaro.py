"""
Support for the Fibaro devices.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/hive/
"""
import logging
import voluptuous as vol
from collections import defaultdict

from homeassistant.const import (ATTR_ARMED, ATTR_BATTERY_LEVEL, ATTR_LAST_TRIP_TIME, ATTR_TRIPPED,
								 EVENT_HOMEASSISTANT_STOP,CONF_PASSWORD, CONF_URL,CONF_USERNAME)
import homeassistant.helpers.config_validation as cv
from homeassistant.util import convert, slugify
from homeassistant.helpers import discovery
from homeassistant.helpers.entity import Entity

"""REQUIREMENTS = ['pyhiveapi==0.2.14']
"""

_LOGGER = logging.getLogger(__name__)
DOMAIN = 'fibaro'
DATA_FIBARO = 'data_fibaro'
FIBARO_DEVICES = 'fibaro_devices'
FIBARO_SCENES = 'fibaro_scenes'
FIBARO_CONTROLLER = 'fibaro_controller'
FIBARO_ID_FORMAT = '{}_{}'

FIBARO_COMPONENTS = [
	'binary_sensor',
	'sensor',
	'light',
#	'switch',
#   'lock',
#	'climate',
#	'cover',
#	'scene'
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
	hc = None
	login = None
	info = None
	rooms = None
	devices = None
	roomlist = None

	def getDeviceName(self, device):
		rl = self.rooms[device.roomID]
		rs = rl.name
		s = rs + "_" + device.name
		return s

def setup(hass, config):
	"""Set up the Fibaro Component."""
	from fiblary.client import Client

	session = FibaroController()

	username = config[DOMAIN][CONF_USERNAME]
	password = config[DOMAIN][CONF_PASSWORD]
	url = config[DOMAIN][CONF_URL]

	try:
		session.hc = Client ('v4', url, username, password)
		session.info = session.hc.info.get()
	except:
		session.hc = None

	if session.hc is None:
		_LOGGER.error("Failed to connect to Fibaro HC")
		return False

	session.login = session.hc.login.get()
	if session.login is None or session.login.status is False:
		_LOGGER.error("Invaid login for Fibaro HC. Please check username and password.")
		return False
	rooms = session.hc.rooms.list()
	class placeholder:
		pass
	runkn = placeholder
	runkn.id = 0
	runkn.name = 'Unknown'
	session.rooms = { 0 : runkn }
	for room in rooms:
		session.rooms[room.id]=room
	devices = session.hc.devices.list()
	session.devices = {}
	for device in devices:
		session.devices[device.id]=device
	hass.data[DATA_FIBARO] = session
#	unknowninterfaces= []
#	unknowntypes= []
#	unknownbasetypes= []
	typemapping = {'com.fibaro.temperatureSensor' : 'sensor',
				   'com.fibaro.multilevelSensor' : "sensor",
				   'com.fibaro.humiditySensor' : 'sensor',
				   'com.fibaro.binarySwitch' : 'switch',
				   'com.fibaro.FGRGBW441M' : 'light',
				   'com.fibaro.multilevelSwitch' : 'switch',
				   'com.fibaro.remoteController' : 'switch',
				   'com.fibaro.FGD212' : 'light',
				   'com.fibaro.FGRM222' : 'cover',
				   'com.fibaro.doorSensor' : 'binary_sensor',
				   'com.fibaro.FGMS001v2' : 'binary_sensor',
				   'com.fibaro.lightSensor' : 'sensor',
				   'com.fibaro.seismometer' : 'sensor',
				   'com.fibaro.accelerometer' : 'sensor',
				   'com.fibaro.FGSS001' : 'sensor',
				   'com.fibaro.remoteSwitch' : 'switch' }
	fibaro_devices = defaultdict(list)
	for idx, device in session.devices.items():
		if device.enabled is True:
			device_type = None
			if device.type in typemapping:
				device_type = typemapping[device.type]
			if device_type is None:
				continue
			fibaro_devices[device_type].append(device)
	hass.data[FIBARO_DEVICES] = fibaro_devices
	hass.data[FIBARO_CONTROLLER] = session
#	fibaro_scenes = []
#	for scene in all_scenes:
#		fibaro_scenes.append(scene)
#	hass.data[FIBARO_SCENES] = fibaro_scenes

	for component in FIBARO_COMPONENTS:
		discovery.load_platform(hass, component, DOMAIN, {}, config)

	return True

class FibaroDevice(Entity):
	"""Representation of a Fibaro device entity."""

	def __init__(self, fibaro_device, controller):
		"""Initialize the device."""
		self.fibaro_device = fibaro_device
		self.controller = controller

		self._name = controller.getDeviceName (fibaro_device)
		# Append device id to prevent name clashes in HA.
		self.fibaro_id = FIBARO_ID_FORMAT.format(
			slugify(self._name), fibaro_device.id)

#        self.controller.register(fibaro_device, self._update_callback)

	def _update_callback(self, _device):
		"""Update the state."""
		self.schedule_update_ha_state(True)

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
