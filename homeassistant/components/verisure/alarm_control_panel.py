"""Support for Verisure alarm control panels."""
import logging
from time import sleep

import homeassistant.components.alarm_control_panel as alarm
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY, STATE_ALARM_ARMED_HOME, STATE_ALARM_DISARMED)

from . import CONF_ALARM, CONF_CODE_DIGITS, HUB as hub

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Verisure platform."""
    alarms = []
    if int(hub.config.get(CONF_ALARM, 1)):
        hub.update_overview()
        alarms.append(VerisureAlarm())
    add_entities(alarms)


def set_arm_state(state, code=None):
    """Send set arm state command."""
    transaction_id = hub.session.set_arm_state(code, state)[
        'armStateChangeTransactionId']
    _LOGGER.info('verisure set arm state %s', state)
    transaction = {}
    while 'result' not in transaction:
        sleep(0.5)
        transaction = hub.session.get_arm_state_transaction(transaction_id)
    # pylint: disable=unexpected-keyword-arg
    hub.update_overview(no_throttle=True)


class VerisureAlarm(alarm.AlarmControlPanel):
    """Representation of a Verisure alarm status."""

    def __init__(self):
        """Initialize the Verisure alarm panel."""
        self._state = None
        self._digits = hub.config.get(CONF_CODE_DIGITS)
        self._changed_by = None

    @property
    def name(self):
        """Return the name of the device."""
        return '{} alarm'.format(hub.session.installations[0]['alias'])

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def code_format(self):
        """Return one or more digits/characters."""
        return alarm.FORMAT_NUMBER

    @property
    def changed_by(self):
        """Return the last change triggered by."""
        return self._changed_by

    def update(self):
        """Update alarm status."""
        hub.update_overview()
        status = hub.get_first("$.armState.statusType")
        if status == 'DISARMED':
            self._state = STATE_ALARM_DISARMED
        elif status == 'ARMED_HOME':
            self._state = STATE_ALARM_ARMED_HOME
        elif status == 'ARMED_AWAY':
            self._state = STATE_ALARM_ARMED_AWAY
        elif status != 'PENDING':
            _LOGGER.error('Unknown alarm state %s', status)
        self._changed_by = hub.get_first("$.armState.name")

    def alarm_disarm(self, code=None):
        """Send disarm command."""
        set_arm_state('DISARMED', code)

    def alarm_arm_home(self, code=None):
        """Send arm home command."""
        set_arm_state('ARMED_HOME', code)

    def alarm_arm_away(self, code=None):
        """Send arm away command."""
        set_arm_state('ARMED_AWAY', code)
