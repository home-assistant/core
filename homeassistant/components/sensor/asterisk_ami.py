# -*- coding: utf-8 -*-
"""Asterisk Sensors."""
import logging

from homeassistant.components import asterisk_ami as ami_platform
from homeassistant.const import STATE_UNKNOWN
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Sensor setup.

    Loads configuration and creates devices for extensions and mailboxes.
    """
    add_devices([AsteriskSensor(hass)])
    for mailbox in hass.data[ami_platform.DATA_MAILBOX]:
        add_devices([AsteriskMailbox(hass, mailbox)])


class AsteriskSensor(Entity):
    """Asterisk Server connection status sensor."""

    def __init__(self, hass):
        """Initialize the sensor."""
        self._hass = hass
        self._state = STATE_UNKNOWN

    @property
    def name(self):
        """Return the name of the sensor."""
        return 'Asterisk Connection'

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def should_poll(self):
        """Return the polling mode of teh sensor."""
        return True

    def update(self):
        """Check the connection status and update the internal state."""
        if self._hass.data[ami_platform.DATA_ASTERISK].connected():
            self._state = 'connected'
        else:
            self._state = 'disconnected'

            ami_platform.setup(self._hass, self._hass.config)


class AsteriskMailbox(Entity):
    """Voicemail Mailbox Sensor."""

    def __init__(self, hass, mailbox):
        """Sensor Setup."""
        self._hass = hass
        self._mailbox = mailbox
        self._state = STATE_UNKNOWN

    @property
    def name(self):
        """Return the name of the sensor."""
        return "Asterisk Mailbox " + self._mailbox

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def should_poll(self):
        """Return the polling mode of the sensor."""
        return True

    def update(self):
        """Check the mailbox status and update the state."""
        cdict = {'Action': 'MailboxStatus'}
        cdict['Peer'] = self._mailbox
        response = self._hass.data[ami_platform.DATA_ASTERISK] \
                             .send_action(cdict)
        _LOGGER.info(response)
        _LOGGER.info(response.headers)
        if response.get_header('Response') == 'Error':
            raise Exception(response.get_header('Message'))
        self._state = response.get_header('Waiting', STATE_UNKNOWN)
