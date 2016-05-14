"""

Support for Pilight Switches.
"""
import logging
import socket
import json

from homeassistant.components.switch import SwitchDevice
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = []


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
	""" Sets up a pilight socket client """
	#_LOGGER.info(config)
	host = config['ip']
	port = config['port']
	server = Pilight_Server(host, port)
	add_devices_callback([server])
	if server.setup():
		for device in config['switches']:
			if server.existSwitch(device):
				if config['switches'][device]:
					name = config['switches'][device]['name']
				else:
					name = device
				_LOGGER.info("Register Device " + name + ".")
				aDevice = Pilight_Switch(server, name, device)
				if aDevice.setup():
					add_devices_callback([aDevice])
			else: 
				_LOGGER.info("Pilight doesnt know a Switch " + device + ".")
		return True
	return False

class Pilight_Server(Entity):
	""" represents the pilight server and saves the states of the switches """
	
	def __init__(self, host, port):
		self._name = "Pilight"
		self._host = host
		self._port = port
		self._hidden = True
		self._states = {}
		self._is_available = True

	@property
	def name(self):
		""" Return the name of the Server. """
		return self._name

	@property
	def states(self):
		""" Return the states of the devices. """
		return self._states

	@property
	def host(self):
		""" Return the hostname of the server. """
		return self._host

	@property
	def port(self):
		""" Return the port of the server. """
		return self._port

	@property
	def hidden(self):
		""" Return the visibility in GUI. """
		return self._hidden

	def setup(self):
		""" Intruduce the device. """
		return self.update()

	def update(self):
		""" Grap the states from the pilight server. """
		self._states = self.json_request({"action":"request values"})
		if self._states:
			return True
		_LOGGER.info("Update failed. Maybe the Server isnt online.")
		return False

	def existSwitch(self, name):
		""" Checks if a switch with the name exist """
		for device in  self.states['values']:
			if name in device['devices']:
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

class Pilight_Switch(SwitchDevice,Pilight_Server):
	""" Represents a Pilight Switch """

	def __init__(self, server, name, dev_name):
		Pilight_Server.__init__(self, server.host, server.port)
		self._name = name
		self._dev_name = dev_name
		self._state = ""
		self._hidden = False
		self._server = server
		self._is_available = True
		
	@property
	def name(self):
		""" Return the name of the switch. """
		return self._name

	@property
	def dev_name(self):
		""" Return the piligh intern device name of the server. """
		return self._dev_name

	@property
	def state(self):
		""" Return state of the device. """
		return self._state

	@property
	def hidden(self):
		""" Return the visibility in GUI. """
		return self._hidden

	def setup(self):
		""" Get intruduce the switch an checks the exist. """
		return self.update()

	def turn_on(self, **kwargs):
		""" Turn the switch on. """
		res = self.json_request({"action":"control","code":{"device": self._dev_name,"state": "on"}})
		if res: 
			return True
		return False

	def turn_off(self, **kwargs):
		""" Turn the switch off. """
		res = self.json_request({"action":"control","code":{"device": self._dev_name,"state": "off"}})
		if res: 
			return True
		return False

	def update(self):
		""" Update the State of the Switch """
		for device in  self._server.states['values']:
			if self._dev_name in device['devices']:
				if self._state != device['values']['state']:
					self._state = device['values']['state']
					if self._state == "off": 
						self._is_on = False
					elif self._state == "on":
						self._is_on = True
					_LOGGER.info("State of the Device " + self._name + " changed to " + device['values']['state'])
				return True
		return False
		#_LOGGER.info(self._is_available)



