"""
Support for HomematicIP sensors.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/homematicip/
"""

import asyncio
import logging


from homeassistant.core import callback
from homeassistant.const import (
	ATTR_FRIENDLY_NAME, ATTR_UNIT_OF_MEASUREMENT, CONF_VALUE_TEMPLATE,
	CONF_ICON_TEMPLATE, ATTR_ENTITY_ID,
	CONF_SENSORS)
from homeassistant.helpers.entity import Entity, async_generate_entity_id
from homeassistant.components.homematicip import ( DOMAIN,
	EVENT_HOME_CHANGED, EVENT_DEVICE_CHANGED)
#from datetime import timedelta

import homematicip

_LOGGER = logging.getLogger(__name__)

ATTR_ID = 'device_id'
ATTR_HOME_ID = 'home_id'
ATTR_LABEL = 'label'
ATTR_LASTSTATUS_UPDATE = 'last_status_update'
ATTR_FIRMWARE = 'status_firmware'
ATTR_ACTUAL_FIRMWARE = 'actual_firmware'
ATTR_AVAILABLE_FIRMWARE = 'available_firmware'
ATTR_LOW_BATTERY = 'low_battery'
ATTR_UNREACHABLE = 'not_reachable'
ATTR_SABOTAGE = 'sabotage'
ATTR_UPTODATE = 'up_to_date'
ATTR_WINDOW = 'window'
ATTR_ON = 'on'
ATTR_VALVE_POSITION = 'valve_position'
ATTR_TEMPERATURE_OFFSET = 'temperature_offset'

ATTR_CONNECTED = 'connected'
ATTR_DUTYCYCLE = 'dutycycle'
ATTR_CURRENT_APVERSION = 'current_apversion'
ATTR_AVAILABLE_APVERSION = 'available_apversion'
ATTR_TIMEZONE_ID = 'timezone_id'
ATTR_PIN_ASSIGNED = 'pin_assigned'
ATTR_UPDATE_STATE = 'update_state'
ATTR_APEXCHANGE_CLIENTID = 'apexchange_clientid'
ATTR_APEXCHANGE_STATE = 'apexchange_state'
ATTR_HUB_ID = 'hub_id'


@asyncio.coroutine
# pylint: disable=unused-argument
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
	"""Set up the HomematicIP sensors devices."""
	_LOGGER.info('Setting up HomeMaticIP AccesPoint & Generic')
	homeid = discovery_info['homeid']
	home = hass.data[DOMAIN][homeid]

	async_add_devices([HomeMaticIP_AccessPoint(hass, home)])
	for device in home.devices:
		async_add_devices([HomeMaticIP_GenericDevice(hass, home, device)])
	return True


class HomeMaticIP_AccessPoint(Entity):
	"""Representation of an HomeMaticIP access point."""

	def __init__(self, hass, home):
		"""Initialize the access point sensor."""
		self.hass = hass
		self._home = home

		@callback
		def event_accesspoint(event):
			"""Handle device state changes."""
			_LOGGER.debug('Event Access Point: {}'.format(self._home.label))
			self.async_schedule_update_ha_state(True)

		hass.bus.async_listen(EVENT_HOME_CHANGED, event_accesspoint)

	@property
	def name(self):
		"""Return the name of the access point device."""
		if self._home.label == 'None':
			return 'Access Point Status'
		else:
			return '{} Access Point Status'.format(self._home.label)

	@property
	def icon(self):
		return 'mdi:access-point-network'

	@property
	def state(self):
		"""Return the state of the access point."""
		return self._home.dutyCycle

	@property
	def force_update(self):
		"""Force update."""
		return True

	@property
	def device_state_attributes(self):
		"""Return the state attributes of the access point."""
		return {
			ATTR_CONNECTED: self._home.connected,
			ATTR_DUTYCYCLE: self._home.dutyCycle,
			ATTR_CURRENT_APVERSION: self._home.currentAPVersion,
			ATTR_AVAILABLE_APVERSION: self._home.availableAPVersion,
			ATTR_TIMEZONE_ID: self._home.timeZoneId,
			ATTR_PIN_ASSIGNED: self._home.pinAssigned,
			ATTR_UPDATE_STATE: self._home.updateState,
			ATTR_APEXCHANGE_CLIENTID: self._home.apExchangeClientId,
			ATTR_APEXCHANGE_STATE: self._home.apExchangeState,
			ATTR_ID: self._home.id,
			ATTR_LABEL: self._home.label,
			}



class HomeMaticIP_GenericDevice(Entity):
	"""Representation of an HomeMaticIP generic device."""

	def __init__(self, hass, home, device, signal=None):
		"""Initialize the generic device."""
		self.hass = hass
		self._home = home
		self._device = device
		_LOGGER.debug('Setting up generic sensor device: {}'.format(device.label))

		@callback
		def event_sensor(event):
			"""Receive notification that new data exists."""
			if event.data == self._device.id:
				_LOGGER.debug('Event GenericDevice: {}'.format(self._device.label))
				self.async_schedule_update_ha_state(True)

		if signal is None:
			hass.bus.async_listen(EVENT_DEVICE_CHANGED, event_sensor)
		else:
			hass.bus.async_listen(signal, event_sensor)

	@property
	def name(self):
		"""Return the name of the generic device."""
		if self._home.label != 'None':
			return '{} {}'.format(self._home.label, self._device.label)
		return self._device.label

	@property
	def icon(self):
		"""Return the icon of the generic device."""
		if self._device.unreach: return 'mdi:wifi-off'
		if self._device.lowBat: return 'mdi:battery-outline'
		if self._device.updateState.lower() != ATTR_UPTODATE: return 'mdi:refresh'
		return 'mdi:check'

	@property
	def state(self):
		"""Return the state of the generic device."""
		if self._device.unreach: return ATTR_UNREACHABLE
		if self._device.lowBat: return ATTR_LOW_BATTERY
		if self._device.updateState.lower() != ATTR_UPTODATE: return self._device.updateState.lower()
		return 'ok'

	@property
	def force_update(self):
		"""Force update."""
		return True

	@property
	def should_poll(self):
		"""No polling needed."""
		return False

	@property
	def available(self):
		return not self._device.unreach

	@asyncio.coroutine
	def async_update(self):
		return True

	def _generic_state_attributes(self):
		"""Return the state attributes of the generic device."""
		attr = {}
		if hasattr(self._device, 'id'):
			attr.update({ATTR_ID: self._device.id.lower()})
		if hasattr(self._device, 'homeId'):
			attr.update({ATTR_HOME_ID: self._device.homeId})
		if hasattr(self._device, 'lastStatusUpdate') and  self._device.lastStatusUpdate != None:
			attr.update({ATTR_LASTSTATUS_UPDATE: self._device.lastStatusUpdate.strftime('%d-%m-%Y %H:%M:%S')})
		if hasattr(self._device, 'updateState') and self._device.updateState != None:
			attr.update({ATTR_FIRMWARE: self._device.updateState.lower()})
		if hasattr(self._device, 'firmwareVersion'):
			attr.update({ATTR_ACTUAL_FIRMWARE: self._device.firmwareVersion})
		if hasattr(self._device, 'availableFirmwareVersion'):
			attr.update({ATTR_AVAILABLE_FIRMWARE: self._device.availableFirmwareVersion})
		if hasattr(self._device, 'lowBat') and self._device.lowBat != None:
			attr.update({ATTR_LOW_BATTERY: self._device.lowBat})
		if hasattr(self._device, 'unreach') and self._device.unreach != None:
			attr.update({ATTR_UNREACHABLE: self._device.unreach})
		if hasattr(self._device, 'sabotage') and self._device.sabotage != None:
			attr.update({ATTR_SABOTAGE: self._device.sabotage})

		if hasattr(self._device, 'windowState') and self._device.windowState != None:
			attr.update({ATTR_WINDOW: self._device.windowState.lower()})
		if hasattr(self._device, 'on') and self._device.on != None:
			attr.update({ATTR_ON: self._device.on})

		if hasattr(self._device, 'valvePosition') and self._device.valvePosition != None:
			attr.update({ATTR_VALVE_POSITION: self._device.valvePosition})
		if hasattr(self._device, 'temperatureOffset') and self._device.temperatureOffset != None:
			attr.update({ATTR_TEMPERATURE_OFFSET: self._device.temperatureOffset})

		if hasattr(self._device, 'currentPowerConsumption') and self._device.currentPowerConsumption != None:
			attr.update({'currentPowerConsumption': self._device.currentPowerConsumption})

		return attr

	@property
	def device_state_attributes(self):
		"""Return the state attributes of the generic device."""
		return self._generic_state_attributes()



