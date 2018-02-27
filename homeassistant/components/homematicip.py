"""
Support for HomematicIP components.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/homematicip/
"""

import logging
from datetime import timedelta
from socket import timeout

import voluptuous as vol
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import load_platform

from homematicip.home import Home

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['homematicip==0.8']

DOMAIN = 'homematicip'

CONF_NAME = 'name'
CONF_ACCESSPOINT = 'accesspoint'
CONF_AUTHTOKEN = 'authtoken'
CONF_TIMEOUT = 'timeout'
CONF_RECONNECT = 'reconnect'
CONF_DISCOVERY = 'discovery'

CONFIG_SCHEMA = vol.Schema({
    vol.Optional(DOMAIN): [vol.Schema({
        vol.Optional(CONF_NAME, default=''): cv.string,
        vol.Required(CONF_ACCESSPOINT): cv.string,
        vol.Required(CONF_AUTHTOKEN): cv.string,
        vol.Optional(CONF_TIMEOUT, default=timedelta(seconds=20)): (
            vol.All(cv.time_period, cv.positive_timedelta)),
        vol.Optional(CONF_RECONNECT, default=timedelta(minutes=10)): (
            vol.All(cv.time_period, cv.positive_timedelta)),
        vol.Optional(CONF_DISCOVERY, default=True): cv.boolean,
    })],
}, extra=vol.ALLOW_EXTRA)

EVENT_HOME_CHANGED = 'homematicip_home_changed'
EVENT_DEVICE_CHANGED = 'homematicip_device_changed'
EVENT_GROUP_CHANGED = 'homematicip_group_changed'
EVENT_SECURITY_CHANGED = 'homematicip_security_changed'
EVENT_JOURNAL_CHANGED = 'homematicip_journal_changed'


def setup(hass, config):
    """Set up the HomematicIP component."""
    hass.data.setdefault(DOMAIN, {})
    homes = hass.data[DOMAIN]
    accesspoints = config.get(DOMAIN, [])

    @callback
    def event_handle(events):
        """Handle incoming HomeMaticIP events."""
        for event in events:
            etype = event['eventType']
            edata = event['data']
            _LOGGER.debug("Event: %s", event)
            if etype == 'DEVICE_CHANGED':
                hass.bus.fire(EVENT_DEVICE_CHANGED, edata.id)
            elif etype == 'GROUP_CHANGED':
                hass.bus.fire(EVENT_GROUP_CHANGED, edata.id)
            elif etype == 'HOME_CHANGED':
                hass.bus.fire(EVENT_HOME_CHANGED, edata.id)
            elif etype == 'JOURNAL_CHANGED':
                hass.bus.fire(EVENT_SECURITY_CHANGED, edata.id)
        return True

    for device in accesspoints:
        name = device.get(CONF_NAME)
        accesspoint = device.get(CONF_ACCESSPOINT)
        authtoken = device.get(CONF_AUTHTOKEN)
        # timeout = device.get(CONF_TIMEOUT)
        # reconnect = device.get(CONF_RECONNECT)

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
        except timeout:
            _LOGGER.warning("Connection to HMIP could not be established")
        homes[home.id] = home
        home.onEvent += event_handle
        home.enable_events()
        _LOGGER.info('HUB name: %s, id: %s', home.label, home.id)

        for component in ['sensor']:
            load_platform(hass, component, DOMAIN,
                          {'homeid': home.id}, config)
    return True
