"""
Support for HomematicIP.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/homematicip/
"""

import asyncio
import logging

import voluptuous as vol
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.entity import Entity, async_generate_entity_id
from homeassistant.helpers.event import async_track_state_change
from datetime import datetime
from homeassistant.const import (ATTR_FRIENDLY_NAME, ATTR_UNIT_OF_MEASUREMENT, 
	EVENT_HOMEASSISTANT_START)

from datetime import timedelta

REQUIREMENTS = ['homematicip>=0.7.0']
from homematicip.home import Home

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'homematicip'

EVENT_HOME_CHANGED = 'homematicip_home_changed'
EVENT_DEVICE_CHANGED = 'homematicip_device_changed'
EVENT_GROUP_CHANGED = 'homematicip_group_changed'
EVENT_SECURITY_CHANGED = 'homematicip_security_changed'
EVENT_JOURNAL_CHANGED = 'homematicip_journal_changed'

CONF_NAME = 'name'
CONF_HUBID = 'hubid'
CONF_AUTHTOKEN = 'authtoken'
CONF_TIMEOUT = 'timeout'
CONF_RECONNECT = 'reconnect'

CONFIG_SCHEMA = vol.Schema({
	vol.Optional(DOMAIN): [ vol.Schema({
		vol.Optional(CONF_NAME, default='None'): cv.string,
		vol.Required(CONF_HUBID): cv.string,
		vol.Required(CONF_AUTHTOKEN): cv.string,
		vol.Optional(CONF_TIMEOUT, default=timedelta(seconds=20)): (
			vol.All(cv.time_period, cv.positive_timedelta)),
		vol.Optional(CONF_RECONNECT, default=timedelta(minutes=10)): (
		vol.All(cv.time_period, cv.positive_timedelta)),
#		vol.Optional(CONF_DISCOVERY, default=True): cv.boolean,
	}) ],
}, extra=vol.ALLOW_EXTRA)


class HomematicIP(Home):
	"""Representation of an HomeMaticIP."""
	label = None


	def __init__(self, hass, name, hubid, authtoken, timeout=20, reconnect=10):
		"""Set up connection and hook it into HA for reconnect/shutdown."""
		super().__init__()
		
		def events_hmip(events):
			"""Handle incoming HomeMaticIP events."""
			for event in events:
				eventType = event["eventType"]
				_LOGGER.debug("Fire event: {}, label: {}".format(eventType, event["data"].label))
				if eventType == 'DEVICE_CHANGED':
					hass.bus.async_fire(EVENT_DEVICE_CHANGED, event["data"].id)
				if eventType == 'GROUP_CHANGED':
					hass.bus.async_fire(EVENT_GROUP_CHANGED, event["data"].id)
				if eventType == 'HOME_CHANGED':
					hass.bus.async_fire(EVENT_HOME_CHANGED, event["data"].id)
				if eventType == 'JOURNAL_CHANGED':
					hass.bus.async_fire(EVENT_SECURITY_CHANGED, event["data"].id)
		
		try:
			self.init(hubid)
			self.set_auth_token(authtoken)
			self.get_current_state()
			self.onEvent += events_hmip
			self.enable_events()
			_LOGGER.info('Connected to HomematicIP server')
		except timeout as exc:
			hass.loop.call_later(connect, reconnect, exc)
			_LOGGER.warning("Connection to server could not be established")
		
		self.label = name	
	

@asyncio.coroutine
def async_setup(hass, config):
	"""Set up the HomematicIP component."""
	hass.data.setdefault(DOMAIN, {})
	homes = hass.data[DOMAIN]

	hubs = config.get(DOMAIN, [])
	for device in hubs:
		name = device.get(CONF_NAME)
		hubid = device.get(CONF_HUBID)
		authtoken = device.get(CONF_AUTHTOKEN)
		timeout = device.get(CONF_TIMEOUT)
		reconnect = device.get(CONF_RECONNECT)
		_LOGGER.info('Initiating HomematicIP hub {}, {}'.format(name, hubid))
		home = HomematicIP(hass, name, hubid, authtoken, timeout, reconnect)
		homes[home.id] = home
		_LOGGER.info('HUB name: {}, id: {}'.format(home.label, home.id))
		for component in 'sensor', 'climate':
			hass.async_add_job(async_load_platform(hass, component, DOMAIN, {'homeid': home.id}, config))

	return True


