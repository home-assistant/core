"""
Sensor for Asterisk Voicemail box.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.mailbox/
"""
import asyncio
import logging


from homeassistant.helpers.entity import Entity
from homeassistant.core import callback
from homeassistant.helpers.event import async_track_state_change
from homeassistant.components.mailbox import DOMAIN

_LOGGER = logging.getLogger(__name__)


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up sensor for the Mailbox platform."""
    async_add_devices([MailboxSensor(hass, discovery_info['mailbox_id'])])


class MailboxSensor(Entity):
    """Mailbox Sensor."""

    def __init__(self, hass, mailbox_id):
        """Initialize the sensor."""
        self._name = None
        self._attributes = None
        self._state = 0
        self._mailbox_id = mailbox_id

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Register callbacks."""
        state = self.hass.states.get(self._mailbox_id)
        if state:
            self._state = state.state

        @callback
        def update_callback(entity, old_state, new_state):
            """Update the message count in HA, if needed."""
            self._state = new_state.state
            self.hass.async_add_job(self.async_update_ha_state(True))

        async_track_state_change(self.hass,
                                 [self._mailbox_id], update_callback)

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{}'.format(self._name or DOMAIN)

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state
