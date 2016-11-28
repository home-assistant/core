"""
CEC component.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/hdmi_cec/
"""
import logging

import yaml

import struct

import voluptuous as vol

from homeassistant.const import (EVENT_HOMEASSISTANT_START, CONF_DEVICES)
import homeassistant.helpers.config_validation as cv

import cec

_CEC = None
_LOGGER = logging.getLogger(__name__)

ATTR_DEVICE = 'device'
ATTR_COMMAND = 'command'
ATTR_KEY = 'key'
ATTR_DURATION = 'duration'
ATTR_SRC = 'src'
ATTR_DST = 'dst'
ATTR_CMD = 'cmd'
ATTR_ATT = 'att'
ATTR_RAW = 'raw'

EVENT_CEC_COMMAND_RECEIVED = 'cec_command_received'
EVENT_CEC_KEYPRESS_RECEIVED = 'cec_keypress_received'

DOMAIN = 'hdmi_cec'

MAX_DEPTH = 4

SERVICE_POWER_ON = 'power_on'
SERVICE_SELECT_DEVICE = 'select_device'
SERVICE_SEND_COMMAND = 'send_command'
SERVICE_STANDBY = 'standby'
SERVICE_SELF = 'self'

# pylint: disable=unnecessary-lambda
DEVICE_SCHEMA = vol.Schema({
	vol.All(cv.positive_int): vol.Any(lambda devices: DEVICE_SCHEMA(devices), cv.string)
})

CONFIG_SCHEMA = vol.Schema({
	DOMAIN: vol.Schema({
		vol.Required(CONF_DEVICES): DEVICE_SCHEMA
	})
}, extra=vol.ALLOW_EXTRA)


def parse_mapping(mapping, parents=None):
	"""Parse configuration device mapping."""
	if parents is None:
		parents = []
	for addr, val in mapping.items():
		cur = parents + [str(addr)]
		if isinstance(val, dict):
			yield from parse_mapping(val, cur)
		elif isinstance(val, str):
			yield (val, cur)

def pad_physical_address(addr):
	"""Right-pad a physical address."""
	return addr + ['0'] * (MAX_DEPTH - len(addr))

def setup(hass, config):
	"""Setup CEC capability."""
	global _CEC

	_LOGGER.debug("CEC setup")

	# logging callback
	def log_callback(level, time, message):
	  return _CEC.LogCallback(level, time, message)
	
	# key press callback
	def key_press_callback(key, duration):
	  return _CEC.KeyPressCallback(key, duration)
	
	# command callback
	def command_callback(cmd):
	  return _CEC.CommandCallback(cmd)
	
	# Parse configuration into a dict of device name to physical address
	# represented as a list of four elements.
	flat = {}
	for pair in parse_mapping(config[DOMAIN].get(CONF_DEVICES, {})):
		flat[pair[0]] = pad_physical_address(pair[1])

	_CEC = pyCecClient(hass)
	_CEC.SetLogCallback(log_callback)
	_CEC.SetKeyPressCallback(key_press_callback)
	_CEC.SetCommandCallback(command_callback)

	def _power_on(call):
		"""Power on all devices."""
		_CEC.ProcessCommandPowerOn()

	def _standby(call):
		"""Standby all devices."""
		_CEC.ProcessCommandStandby()

	def _self_command(call):
		"""Standby all devices."""
		result = _CEC.ProcessCommandSelf()
		_LOGGER.info(type(result))
		_LOGGER.info("%s", yaml.dump(result, indent=2))
		return result

	def _select_device(call):
		"""Select the active device."""
		path = flat.get(call.data[ATTR_DEVICE])
		if not path:
			_LOGGER.error("Device not found: %s", call.data[ATTR_DEVICE])
		cmds = []
		for i in range(1, MAX_DEPTH - 1):
			addr = pad_physical_address(path[:i])
			cmds.append('1f:82:{}{}:{}{}'.format(*addr))
			cmds.append('1f:86:{}{}:{}{}'.format(*addr))
		for cmd in cmds:
			_CEC.ProcessCommandTx(cmd)

	def _send_command(call):
		"""Send CEC command."""
		if call.data is list:
			data = call.data
		else:
			data = [ call.data ]
		_LOGGER.info("data %s", data)
		for d in data:
			if ATTR_RAW in d:
				command = d[ATTR_RAW]
			else:
				if ATTR_SRC in d:
					src = d[ATTR_SRC]
				else:
					src = str(_CEC.GetMyAddress())
					_LOGGER.info("src %s", src)
				if ATTR_DST in d:
					dst = d[ATTR_DST]
				else:
					dst = "f"
				if ATTR_CMD in d:
					cmd = d[ATTR_CMD]
				else:
					_LOGGER.error("Attribute 'cmd' is missing")
					return False
				if ATTR_ATT in d:
					att = ":%s" % d[ATTR_ATT]
				else:
					att = ""
				command = "%s%s:%s%s" % ( src, dst, cmd, att )
			_LOGGER.info("Sending %s", command)
			_CEC.ProcessCommandTx(command)

	def _start_cec(event):
		"""Open CEC adapter."""
		# initialise libCEC and enter the main loop
		if _CEC.InitLibCec():
			hass.services.register(DOMAIN, SERVICE_POWER_ON, _power_on)
			hass.services.register(DOMAIN, SERVICE_STANDBY, _standby)
			hass.services.register(DOMAIN, SERVICE_SELECT_DEVICE, _select_device)
			hass.services.register(DOMAIN, SERVICE_SEND_COMMAND, _send_command)
			hass.services.register(DOMAIN, SERVICE_SELF, _self_command)
			return True
		else:
			return False

	hass.bus.listen_once(EVENT_HOMEASSISTANT_START, _start_cec)
	return True

class pyCecClient:
	cecconfig = {}
	lib = {}
	hass = {}

	def SetLogCallback(self, callback):
		_LOGGER.info("Setting log callback...")
		self.cecconfig.SetLogCallback(callback)
		_LOGGER.info("log callback set")

	def SetKeyPressCallback(self, callback):
		_LOGGER.info("Setting keypress callback...")
		self.cecconfig.SetKeyPressCallback(callback)
		_LOGGER.info(" keypress callback set")

	def SetCommandCallback(self, callback):
		_LOGGER.info("Setting command callback...")
		self.cecconfig.SetCommandCallback(callback)
		_LOGGER.info("command callback set")

	# detect an adapter and return the com port path
	def DetectAdapter(self):
		retval = None
		adapters = self.lib.DetectAdapters()
		for adapter in adapters:
			_LOGGER.info("found a CEC adapter:")
			_LOGGER.info("port:     " + adapter.strComName)
			_LOGGER.info("vendor:   " + hex(adapter.iVendorId))
			_LOGGER.info("product:  " + hex(adapter.iProductId))
			retval = adapter.strComName
		return retval

	# initialise libCEC
	def InitLibCec(self):
		self.lib = cec.ICECAdapter.Create(self.cecconfig)
		# print libCEC version and compilation information
		_LOGGER.info("libCEC version " + self.lib.VersionToString(self.cecconfig.serverVersion) + " loaded: " + self.lib.GetLibInfo())

		# search for adapters
		adapter = self.DetectAdapter()
		if adapter == None:
			_LOGGER.info("No adapters found")
			return False
		else:
			if self.lib.Open(adapter):
				self.lib.GetCurrentConfiguration(self.cecconfig)
				_LOGGER.info("connection opened")
				return True
			else:
				_LOGGER.info("failed to open a connection to the CEC adapter")
				return False

	def GetMyAddress(self):
		return self.cecconfig.logicalAddresses.primary

	# display the addresses controlled by libCEC
	def ProcessCommandSelf(self):
		addresses = self.lib.GetLogicalAddresses()
		strOut = "Addresses controlled by libCEC: "
		x = 0
		notFirst = False
		while x < 15:
			if addresses.IsSet(x):
				if notFirst:
					strOut += ", "
				strOut += self.lib.LogicalAddressToString(x)
				if self.lib.IsActiveSource(x):
					strOut += " (*)"
				notFirst = True
			x += 1
		_LOGGER.info(strOut)

	# send an active source message
	def ProcessCommandActiveSource(self):
		self.lib.SetActiveSource()

	# send a standby command
	def ProcessCommandStandby(self):
		_LOGGER.info("Standby all devices ")
		self.lib.StandbyDevices(cec.CECDEVICE_BROADCAST)

	def ProcessCommandPowerOn(self):
		_LOGGER.info("Power on all devices ")
		self.lib.PowerOnDevices(cec.CECDEVICE_BROADCAST)

	# send a custom command
	def ProcessCommandTx(self, data):
		cmd = self.lib.CommandFromString(data)
		_LOGGER.info("transmit " + data)
		if self.lib.Transmit(cmd):
			_LOGGER.info("command sent")
		else:
			_LOGGER.error("failed to send command")

	# scan the bus and display devices that were found
	def ProcessCommandScan(self):
		_LOGGER.info("requesting CEC bus information ...")
		strLog = "CEC bus information\n===================\n"
		addresses = self.lib.GetActiveDevices()
		activeSource = self.lib.GetActiveSource()
		x = 0
		while x < 15:
			if addresses.IsSet(x):
				vendorId        = self.lib.GetDeviceVendorId(x)
				physicalAddress = self.lib.GetDevicePhysicalAddress(x)
				active          = self.lib.IsActiveSource(x)
				cecVersion      = self.lib.GetDeviceCecVersion(x)
				power           = self.lib.GetDevicePowerStatus(x)
				osdName         = self.lib.GetDeviceOSDName(x)
				strLog += "device #" + str(x) +": " + self.lib.LogicalAddressToString(x)  + "\n"
				strLog += "address:       " + str(physicalAddress) + "\n"
				strLog += "active source: " + str(active) + "\n"
				strLog += "vendor:        " + self.lib.VendorIdToString(vendorId) + "\n"
				strLog += "CEC version:   " + self.lib.CecVersionToString(cecVersion) + "\n"
				strLog += "OSD name:      " + osdName + "\n"
				strLog += "power status:  " + self.lib.PowerStatusToString(power) + "\n\n\n"
			x += 1
		_LOGGER.info(strLog)

	# logging callback
	def LogCallback(self, level, time, message):

		if level == cec.CEC_LOG_ERROR:
			levelstr = "ERROR:   "
			_LOGGER.error(levelstr + "[" + str(time) + "]     " + message)
		elif level == cec.CEC_LOG_WARNING:
			levelstr = "WARNING: "
			_LOGGER.warning(levelstr + "[" + str(time) + "]     " + message)
		elif level == cec.CEC_LOG_NOTICE:
			levelstr = "NOTICE:  "
			_LOGGER.info(levelstr + "[" + str(time) + "]     " + message)
		elif level == cec.CEC_LOG_TRAFFIC:
			levelstr = "TRAFFIC: "
			_LOGGER.info(levelstr + "[" + str(time) + "]     " + message)
		elif level == cec.CEC_LOG_DEBUG:
			levelstr = "DEBUG:   "
			_LOGGER.debug(levelstr + "[" + str(time) + "]     " + message)
		else:
			levelstr = "UNKNOWN:   "
			_LOGGER.error(levelstr + "[" + str(time) + "]     " + message)

		return 0

	# key press callback
	def KeyPressCallback(self, key, duration):
		_LOGGER.info("[key pressed] " + str(key))
		self.hass.bus.fire(EVENT_CEC_KEYPRESS_RECEIVED, {ATTR_KEY: key, ATTR_DURATION: duration})
		return 0

	# command received callback
	def CommandCallback(self, cmd):
		_LOGGER.info("[command received] " + cmd)
		self.hass.bus.fire(EVENT_CEC_COMMAND_RECEIVED, {ATTR_COMMAND: cmd})
		return 0

	def __init__(self, hass):
		self.cecconfig = cec.libcec_configuration()
		self.cecconfig.strDeviceName   = "pyLibCec"
		self.cecconfig.bActivateSource = 0
		self.cecconfig.bMonitorOnly = 0
		self.cecconfig.deviceTypes.Add(cec.CEC_DEVICE_TYPE_RECORDING_DEVICE)
		self.cecconfig.clientVersion = cec.LIBCEC_VERSION_CURRENT
		self.hass = hass

