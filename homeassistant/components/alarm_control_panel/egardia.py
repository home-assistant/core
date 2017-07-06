"""
Interfaces with Egardia / Woonveilig alarm control panel.

For more details about this platform, please refer to the $
https://home-assistant.io/components/alarm_control_panel.egardia
"""

import logging

import voluptuous as vol

import homeassistant.components.alarm_control_panel as alarm
from homeassistant.components.alarm_control_panel import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_PORT,CONF_HOST, CONF_PASSWORD, CONF_USERNAME, STATE_UNKNOWN, CONF_CODE, CONF_NAME,
    STATE_ALARM_DISARMED, STATE_ALARM_ARMED_HOME, STATE_ALARM_ARMED_AWAY,
    EVENT_HOMEASSISTANT_STOP)
import homeassistant.helpers.config_validation as cv
import homeassistant.loader as loader

#REQUIREMENTS = ['egardia-python==1.0.0']
REQUIREMENTS = ['requests']
#PYTHON IMPORTS (should be 3rd party!)

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Egardia'
DEFAULT_PORT = '80'
DOMAIN = 'egardia'
NOTIFICATION_ID = 'egardia_notification'
NOTIFICATION_TITLE = 'Egardia'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
vol.Optional(CONF_NAME,default=DEFAULT_NAME):cv.string,
vol.Required(CONF_PASSWORD): cv.string,
vol.Required(CONF_USERNAME): cv.string,
vol.Required(CONF_HOST): cv.string,
vol.Optional(CONF_PORT,default=DEFAULT_PORT):cv.string,
})

def setup_platform(hass, config, add_devices, discovery_info=None):
	"""Set up the Egardia platform."""
	name = config.get(CONF_NAME)
	username = config.get(CONF_USERNAME)
	password = config.get(CONF_PASSWORD)
	host = config.get(CONF_HOST)
	port = config.get(CONF_PORT)
	add_devices([EgardiaAlarm(name,host,port,username,password)])

class EgardiaAlarm(alarm.AlarmControlPanel):
	"""Representation of a Egardia alarm."""
	def __init__(self, name,host,port,username,password):
		self._host = host
		self._port = port
		self._name = name
		self._username = username
		self._password = password

	@property
	def name(self):
		"""Return the name of the device."""
		return self._name

	@property
	def state(self):
		"""Return the state of the device."""
		self.update()
		if self._status == 'ARM':
			state = STATE_ALARM_ARMED_AWAY
		elif self._status == 'HOME':
			state = STATE_ALARM_ARMED_HOME
		elif self._status == 'DAY HOME':
			state = STATE_ALARM_ARMED_HOME
		elif self._status == 'NIGHT HOME':
			state = STATE_ALARM_ARMED_HOME
		elif self._status == 'DISARM':
			state = STATE_ALARM_DISARMED
		else:
			state = STATE_UNKNOWN
		return state

	def getState(self):
		import requests
		#Get status
		r = self.doRequest('get', 'panelCondGet')
		statustext = r.text
		ind1 = statustext.find('mode_a1 : "')
		statustext = statustext[ind1+11:]
		ind2 = statustext.find('"')
		status = statustext[:ind2]
		_LOGGER.info("Egardia alarm status: "+status)
		return status.upper()

	def doRequest(self,requestType,action, payload = None):
		import requests
		requestType = requestType.upper()
		_LOGGER.info("Egardia doRequest, type: "+requestType+", url: "+self.buildURL()+action+", payload: "+str(payload)+", auth=("+self._username+","+self._password+")")
		if requestType =='GET':
			return requests.get(self.buildURL()+action,auth=(self._username,self._password))
		elif requestType == 'POST':
			return requests.post(self.buildURL()+action,data=payload, auth=(self._username,self._password))
		else:
			return None
	def buildURL(self):
		return 'http://'+self._host+':'+self._port+'/action/'

	def update(self):
		"""Update the alarm status."""
		self._status = self.getState()
 
	def alarm_disarm(self, code=None):
		"""Send disarm command."""
		r = self.sendCondition(4)
		_LOGGER.info("Egardia alarm disarming, result: "+r)

	def alarm_arm_home(self, code=None):
		"""Send arm home command."""
		r = self.sendCondition(1)
		_LOGGER.info("Egardia alarm arming home, result: "+r)

	def alarm_arm_away(self, code=None):
		"""Send arm away command."""
		#ARM the alarm
		r = self.sendCondition(0)
		_LOGGER.info("Egardia alarm arming away, result: "+r)

	def sendCondition(self,p):
		import requests
		#Send payload to panelCondPost
		payload = {'area': '1', 'mode': p}
		r = self.doRequest('POST', 'panelCondPost', payload)
		statustext = r.text
		ind1 = statustext.find('result : ')
		statustext = statustext[ind1+9:]
		ind2 = statustext.find(',')
		statustext = statustext[:ind2]
		return statustext
