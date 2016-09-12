"""
Interfaces with Verisure alarm control panel.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/alarm_control_panel.verisure/
"""
import logging

import homeassistant.components.alarm_control_panel as alarm
from homeassistant.components.verisure import HUB as hub
from homeassistant.components.verisure import (CONF_ALARM, CONF_CODE_DIGITS)
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY, STATE_ALARM_ARMED_HOME, STATE_ALARM_DISARMED,
    STATE_UNKNOWN)

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Verisure platform."""
    alarms = []
    if int(hub.config.get(CONF_ALARM, 1)):
        hub.update_alarms()
        alarms.extend([
            VerisureAlarm(value.id)
            for value in hub.alarm_status.values()
            ])
    add_devices(alarms)


# pylint: disable=abstract-method
class VerisureAlarm(alarm.AlarmControlPanel):
    """Represent a Verisure alarm status."""

    def __init__(self, device_id):
        """Initalize the Verisure alarm panel."""
        self._id = device_id
        self._state = STATE_UNKNOWN
        self._digits = hub.config.get(CONF_CODE_DIGITS)
        self._changed_by = None

    @property
    def name(self):
        """Return the name of the device."""
        return 'Alarm {}'.format(self._id)

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def available(self):
        """Return True if entity is available."""
        return hub.available

    @property
    def code_format(self):
        """The code format as regex."""
        return '^\\d{%s}$' % self._digits

    @property
    def changed_by(self):
        """Last change triggered by."""
        return self._changed_by

    def update(self):
        """Update alarm status."""
        hub.update_alarms()

        if hub.alarm_status[self._id].status == 'unarmed':
            self._state = STATE_ALARM_DISARMED
        elif hub.alarm_status[self._id].status == 'armedhome':
            self._state = STATE_ALARM_ARMED_HOME
        elif hub.alarm_status[self._id].status == 'armed':
            self._state = STATE_ALARM_ARMED_AWAY
        elif hub.alarm_status[self._id].status != 'pending':
            _LOGGER.error(
                'Unknown alarm state %s',
                hub.alarm_status[self._id].status)
        self._changed_by = hub.alarm_status[self._id].name

    def alarm_disarm(self, code=None):
        """Send disarm command."""
        hub.my_pages.alarm.set(code, 'DISARMED')
        _LOGGER.info('verisure alarm disarming')
        hub.my_pages.alarm.wait_while_pending()
        self.update()

    def alarm_arm_home(self, code=None):
        """Send arm home command."""
        hub.my_pages.alarm.set(code, 'ARMED_HOME')
        _LOGGER.info('verisure alarm arming home')
        hub.my_pages.alarm.wait_while_pending()
        self.update()

    def alarm_arm_away(self, code=None):
        """Send arm away command."""
        hub.my_pages.alarm.set(code, 'ARMED_AWAY')
        _LOGGER.info('verisure alarm arming away')
        hub.my_pages.alarm.wait_while_pending()
        self.update()
