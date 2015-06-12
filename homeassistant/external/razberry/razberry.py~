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

		self.categories = {'Binary Power Switch'}

		self.device_id_map = {}

		devs = j.get('devices')
		for dev in devs:
			dev['categoryName'] = 'Binary Power Switch'
			self.device_id_map[dev.get('id')] = dev

	#get list of connected devices, the categoryFilter param can be either a string or array of strings
	def get_devices(self, categoryFilter=''):

		# the Razberry rest API is a bit rough so we need to make 2 calls to get all the info e need
		self.get_simple_devices_info()

		arequestUrl = self.BASE_URL + "/ZWaveAPI/Data/*"
		j = requests.get(arequestUrl).json()

		self.devices = []
		items = j.get('devices')

		for item in items:
			item['deviceInfo'] = self.device_id_map.get(item.get('id'))
			self.devices.append(RazberrySwitch(item, self))

		return self.devices


class RazberryDevice(object):

	def __init__(self, aJSonObj, razberryController):
		self.jsonState = aJSonObj
		self.deviceId = self.jsonState.get('id')
		self.razberryController = razberryController
		self.name = ''
		if self.jsonState.get('data'):
			self.category = self.jsonState.get('data').get('deviceTypeString').value
			self.name = self.jsonState.get('data').get('givenName').value
		else:
			self.category = ''

		if not self.name:
			if self.category:
				self.name = 'RaZberry ' + self.category + ' ' + str(self.deviceId)
			else:
				self.name = 'RaZberry Device ' + str(self.deviceId)


	def set_value(self, value):
		for item in self.jsonState.get('id'):
			requestUrl = self.razberryController.BASE_URL + "/ZWaveAPI/Run/devices[" + self.deviceId "].instances[0].SwitchBinary.Set(" + value + ")"
			r = requests.get(requestUrl)
			item['value'] = value

	def get_value(self):
		for item in self.jsonState.get('id'):
			return item.get('value')
		return None

	def refresh_value(self):
		for item in self.jsonState.get('id'):
			requestUrl = self.razberryController.BASE_URL + "/ZWaveAPI/Run/devices[" + self.deviceId "].instances[0].data.level.value"
			r = requests.get(requestUrl)
			item['value'] = r.text
			return item.get('value')
		return None

	@property
	def razberry_device_id(self):
		return self.deviceId


class RazberrySwitch(RazberryDevice):

	def __init__(self, aJSonObj, razberryController):
		super().__init__(aJSonObj, razberryController)

	def switch_on(self):
		self.set_value('Target', 255)

	def switch_off(self):
		self.set_value('Target', 0)

	def is_switched_on(self):
		self.refresh_value()
		val = self.get_value()
		if val == 'True':
			return True
		else:
			return False
