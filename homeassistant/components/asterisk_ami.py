# -*- coding: utf-8 -*-
"""Asterisk Phone System"""
import logging

from homeassistant.const import (
    CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import load_platform
import voluptuous as vol

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5038
DEFAULT_USERNAME = "manager"
DEFAULT_PASSWORD = "manager"
CONF_MONITOR = "monitor"

DOMAIN = "asterisk_ami"
REQUIREMENTS = ['pyst2==0.5.0']
DATA_ASTERISK = 'asterisk'
DATA_MONITOR = 'asterisk-monitor'
CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT): cv.port,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_MONITOR): cv.ensure_list,
    })
}, extra=vol.ALLOW_EXTRA)

_LOGGER = logging.getLogger(__name__)


def setup(hass, config):
    """Your controller/hub specific code."""

    import asterisk.manager
    manager = asterisk.manager.Manager()

    host = config[DOMAIN].get(CONF_HOST, DEFAULT_HOST)
    port = config[DOMAIN].get(CONF_PORT, DEFAULT_PORT)
    username = config[DOMAIN].get(CONF_USERNAME, DEFAULT_USERNAME)
    password = config[DOMAIN].get(CONF_PASSWORD, DEFAULT_PASSWORD)

    try:
        manager.connect(host, port)
        login_status = manager.login(username=username, secret=password) \
                              .get_header("Response")
    except asterisk.manager.ManagerException as e:
        _LOGGER.error("Error connecting to Asterisk: %s", e.args[1])
        return False

    if "Success" not in login_status:
        _LOGGER.error("Could not authenticate: %s", login_status)

    hass.data[DATA_ASTERISK] = manager
    hass.data[DATA_MONITOR] = config[DOMAIN].get(CONF_MONITOR, [])

    def handle_peer_status_message(event, manager):
        """Handle PeerStatus events from Asterisk"""
        hass.states.set(DOMAIN+'.PeerStatus_'+event['Peer'],
                        event['PeerStatus'])

    def handle_extension_status_message(event, manager):
        """Handle ExtensionStatus events from Asterisk"""
        hass.states.set(DOMAIN + '.ExtensionStatus_' + event['Exten'],
                        event['StatusText'])

    def handle_device_state_change_message(event, manager):
        """Handle DeviceState events from Asterisk"""
        hass.states.set(DOMAIN + '.DeviceStateChange_' + event['Device'],
                        event['State'])

    def handle_newstate_message(event, manager):
        """Handle NewState events from Asterisk"""
        hass.bus.fire('asterisk.new_call_state', event)

    def handle_hangup_message(event, manager):
        """Handle Hangup events from Asterisk"""
        hass.bus.fire('asterisk.hangup', event)

    manager.register_event('PeerStatus', handle_peer_status_message)
    manager.register_event('ExtensionStatus', handle_extension_status_message)
    manager.register_event('DeviceStateChange',
                           handle_device_state_change_message)

    manager.register_event('Newstate', handle_newstate_message)
    manager.register_event('Hangup', handle_hangup_message)

    load_platform(hass, 'sensor', DOMAIN)

    return True
