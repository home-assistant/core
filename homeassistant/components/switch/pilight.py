"""

Support for Pilight Switches.
"""
import logging
import socket
import json

from homeassistant.components.switch import SwitchDevice

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = []


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
	""" Sets up a pilight socket client """
	#_LOGGER.info(config)
	host = config['ip']
	port = config['port']
	for device in config['switches']:
		name = config['switches'][device]['name']
		_LOGGER.info("Register Device " + name + ".")
		aDevice = Pilight_Switch(host, port, name, device)
		if aDevice.setup():
			add_devices_callback([aDevice])
		else:
			return False
	return True



class Pilight_Switch(SwitchDevice):
	""" Represents a Pilight Switch """

	def __init__(self, host, port, name, dev_name):
		self._host = host
		self._port = port
		self._name = name
		self._dev_name = dev_name
		self._state = ""
		self._is_available = True
		
	@property
	def name(self):
		""" Return the hostname of the server. """
		return self._name

	@property
	def dev_name(self):
		""" Return the piligh intern device name of the server. """
		return self._dev_name

	@property
	def state(self):
		""" Return state of the device. """
		return self._state

	def is_on(self):
		""" True if the device is online. """
		return self._is_on

	def turn_on(self, **kwargs):
		""" Turn the switch on. """
		self.json_request({"action":"control","code":{"device": self._dev_name,"state": "on"}})

	def turn_off(self, **kwargs):
		""" Turn the switch off. """
		self.json_request({"action":"control","code":{"device": self._dev_name,"state": "off"}})

	def update(self):
		""" Ping the remote. """
		# just see if the remote port is open
		self._is_available = self.json_request({"action":"request values"})
		for device in  self._is_available['values']:
			if self._dev_name in device['devices']:
				if self._state != device['values']['state']:
					self._state = device['values']['state']
					if self._state == "off": 
						self._is_on = False
					elif self._state == "on":
						self._is_on = True
					_LOGGER.info("State of the Device " + self._name + " changed to " + device['values']['state'])
		#_LOGGER.info(self._is_available)

	def setup(self):
		""" Get the hostname of the remote. """
		response = self.json_request()
		if response:
			return True

		return False

	def json_request(self, request=None, wait_for_response=False):
		""" Communicate with the json server. """
		sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		sock.settimeout(5)

		try:
			sock.connect((self._host, int(self._port)))
			sock.send(bytearray(json.dumps({"action":"identify"}) + "\n", "utf-8"))
			buf = sock.recv(1024).decode("utf-8")
			if '\n\n' in buf[-2:]:
				response = buf[:-2]
			if response == '{"status":"success"}':
				#_LOGGER.info("identify complete")
				pass
			
		except OSError:
			sock.close()
			return False

		if not request:
			# no communication needed, simple presence detection returns True
			sock.close()
			return True
			
		#_LOGGER.info("Request:" + json.dumps(request) + "\n")
		sock.send(bytearray(json.dumps(request) + "\n", "utf-8"))
		
		try:
			buf = sock.recv(1024).decode("utf-8")
		except socket.timeout:
			# something is wrong, assume it's offline
			_LOGGER.info("Error: Timeout for Pilight Socket")
			sock.close()
			return False

		# read until a newline or timeout
		buffering = True
		while buffering:
			if "\n" in buf:
				response = buf.split("\n")[0]
				buffering = False
			else:
				try:
					more = sock.recv(1024).decode("utf-8")
				except socket.timeout:
					more = None
				if not more:
					buffering = False
					response = buf
				else:
					buf += more

		sock.close()
		return json.loads(response)
