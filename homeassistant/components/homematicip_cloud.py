"""
Support for HomematicIP components.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/homematicip_cloud/
"""

import logging
from socket import timeout

import voluptuous as vol

from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import (dispatcher_send,
                                              async_dispatcher_connect)
from homeassistant.helpers.discovery import load_platform
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['homematicip==0.8']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'homematicip_cloud'

CONF_NAME = 'name'
CONF_ACCESSPOINT = 'accesspoint'
CONF_AUTHTOKEN = 'authtoken'

CONFIG_SCHEMA = vol.Schema({
    vol.Optional(DOMAIN): [vol.Schema({
        vol.Optional(CONF_NAME, default=''): cv.string,
        vol.Required(CONF_ACCESSPOINT): cv.string,
        vol.Required(CONF_AUTHTOKEN): cv.string,
    })],
}, extra=vol.ALLOW_EXTRA)

EVENT_HOME_CHANGED = 'homematicip_home_changed'
EVENT_DEVICE_CHANGED = 'homematicip_device_changed'
EVENT_GROUP_CHANGED = 'homematicip_group_changed'
EVENT_SECURITY_CHANGED = 'homematicip_security_changed'
EVENT_JOURNAL_CHANGED = 'homematicip_journal_changed'

ATTR_HOME_ID = 'home_id'
ATTR_HOME_LABEL = 'home_label'
ATTR_DEVICE_ID = 'device_id'
ATTR_DEVICE_LABEL = 'device_label'
ATTR_STATUS_UPDATE = 'status_update'
ATTR_FIRMWARE_STATE = 'firmware_state'
ATTR_LOW_BATTERY = 'low_battery'
ATTR_SABOTAGE = 'sabotage'
ATTR_RSSI = 'rssi'
ATTR_TYPE = 'type'


def setup(hass, config):
    """Set up the HomematicIP component."""
    # pylint: disable=import-error, no-name-in-module
    from homematicip.home import Home

    hass.data.setdefault(DOMAIN, {})
    homes = hass.data[DOMAIN]
    accesspoints = config.get(DOMAIN, [])

    def _update_event(events):
        """Handle incoming HomeMaticIP events."""
        for event in events:
            etype = event['eventType']
            edata = event['data']
            if etype == 'DEVICE_CHANGED':
                dispatcher_send(hass, EVENT_DEVICE_CHANGED, edata.id)
            elif etype == 'GROUP_CHANGED':
                dispatcher_send(hass, EVENT_GROUP_CHANGED, edata.id)
            elif etype == 'HOME_CHANGED':
                dispatcher_send(hass, EVENT_HOME_CHANGED, edata.id)
            elif etype == 'JOURNAL_CHANGED':
                dispatcher_send(hass, EVENT_SECURITY_CHANGED, edata.id)
        return True

    for device in accesspoints:
        name = device.get(CONF_NAME)
        accesspoint = device.get(CONF_ACCESSPOINT)
        authtoken = device.get(CONF_AUTHTOKEN)

        home = Home()
        if name.lower() == 'none':
            name = ''
        home.label = name
        try:
            home.set_auth_token(authtoken)
            home.init(accesspoint)
            if home.get_current_state():
                _LOGGER.info("Connection to HMIP established")
            else:
                _LOGGER.warning("Connection to HMIP could not be established")
                return False
        except timeout:
            _LOGGER.warning("Connection to HMIP could not be established")
            return False
        homes[home.id] = home
        home.onEvent += _update_event
        home.enable_events()
        _LOGGER.info('HUB name: %s, id: %s', home.label, home.id)

        for component in ['sensor']:
            load_platform(hass, component, DOMAIN, {'homeid': home.id}, config)

    return True


class HomematicipGenericDevice(Entity):
    """Representation of an HomematicIP generic device."""

    def __init__(self, home, device):
        """Initialize the generic device."""
        self._home = home
        self._device = device

    async def async_added_to_hass(self):
        """Register callbacks."""
        async_dispatcher_connect(
            self.hass, EVENT_DEVICE_CHANGED, self._device_changed)

    @callback
    def _device_changed(self, deviceid):
        """Handle device state changes."""
        if deviceid is None or deviceid == self._device.id:
            _LOGGER.debug('Event device %s', self._device.label)
            self.async_schedule_update_ha_state()

    def _name(self, addon=''):
        """Return the name of the device."""
        name = ''
        if self._home.label != '':
            name += self._home.label + ' '
        name += self._device.label
        if addon != '':
            name += ' ' + addon
        return name

    @property
    def name(self):
        """Return the name of the generic device."""
        return self._name()

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def available(self):
        """Device available."""
        return not self._device.unreach

    def _generic_state_attributes(self):
        """Return the state attributes of the generic device."""
        laststatus = ''
        if self._device.lastStatusUpdate is not None:
            laststatus = self._device.lastStatusUpdate.isoformat()
        return {
            ATTR_HOME_LABEL: self._home.label,
            ATTR_DEVICE_LABEL: self._device.label,
            ATTR_HOME_ID: self._device.homeId,
            ATTR_DEVICE_ID: self._device.id.lower(),
            ATTR_STATUS_UPDATE: laststatus,
            ATTR_FIRMWARE_STATE: self._device.updateState.lower(),
            ATTR_LOW_BATTERY: self._device.lowBat,
            ATTR_RSSI: self._device.rssiDeviceValue,
            ATTR_TYPE: self._device.modelType
        }

    @property
    def device_state_attributes(self):
        """Return the state attributes of the generic device."""
        return self._generic_state_attributes()
