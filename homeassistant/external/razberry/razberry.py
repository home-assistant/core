__author__ = 'marcinpilarczyk'

import json
import time

import requests

"""
RaZberry Controller Python API
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This lib is designed to simplify communication with RaZberry Z-Wave controllers
"""

class RazberryController(object):

	def __init__(self, baseUrl):
		self.BASE_URL = baseUrl
		self.devices = []

	def get_simple_devices_info(self):
		simpleRequestUrl = self.BASE_URL + "/ZWaveAPI/Data/*"
		j = requests.get(simpleRequestUrl).json()

		#self.categories = {'Binary Power Switch'}

		self.device_id_map = {}

		devs = j.get('devices')
		for dev in devs:
			self.device_id_map[dev] = dev


	#get list of connected devices, the categoryFilter param can be either a string or array of strings
	def get_devices(self, categoryFilter=''):

		# the Razberry rest API is a bit rough so we need to make 2 calls to get all the info e need
		self.get_simple_devices_info()

		arequestUrl = self.BASE_URL + "/ZWaveAPI/Data/*"
		j = requests.get(arequestUrl).json()

		self.devices = []
		devices = j.get('devices')

		for keyDev in devices:
			for keyInst in devices[keyDev].get('instances'):
				#item['deviceInfo'] = self.device_id_map.get(item)
				self.devices.append(RazberrySwitch(devices[keyDev], keyDev, keyInst, self))

		return self.devices


class RazberryDevice(object):

	def __init__(self, aJSonObj, aDeviceId, aInstanceId, razberryController):
		self.jsonState = aJSonObj
		self.deviceId = aDeviceId
		self.instanceId = aInstanceId
		self.razberryController = razberryController
		self.value = True
		self.name = ''
		if self.jsonState.get('data'):
			self.category = self.jsonState['data']['deviceTypeString']['value']
			self.name = self.jsonState['data']['givenName']['value']
		else:
			self.category = ''

		if not self.name:
			if self.category:
				self.name = 'RaZberry ' + self.category + ' ' + str(self.deviceId)
			else:
				self.name = 'RaZberry Device ' + str(self.deviceId)


	def set_value(self, value):
		requestUrl = self.razberryController.BASE_URL + "/ZWaveAPI/Run/devices[" + str(self.deviceId) + "].instances[" + str(self.instanceId) + "].SwitchBinary.Set(" + str(value) + ")"
		r = requests.get(requestUrl)
		self.value = r.text

	def get_value(self):
		return self.value

	def refresh_value(self):		
		requestUrl = self.razberryController.BASE_URL + "/ZWaveAPI/Run/devices[" + str(self.deviceId) + "].instances[" + str(self.instanceId) + "].SwitchBinary.data.level.value"
		r = requests.get(requestUrl)
		self.value = r.text
		return self.get_value()

	@property
	def razberry_device_id(self):
		return self.deviceId


class RazberrySwitch(RazberryDevice):

	def __init__(self, aJSonObj, aDeviceId, aInstanceId, razberryController):
		super().__init__(aJSonObj, aDeviceId, aInstanceId, razberryController)

	def switch_on(self):
		self.set_value(255)

	def switch_off(self):
		self.set_value(0)

	def is_switched_on(self):
		self.refresh_value()
		val = self.get_value()
		if val == 'true':
			return True
		else:
			return False
