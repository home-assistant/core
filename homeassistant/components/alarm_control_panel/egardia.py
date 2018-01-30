"""
Interfaces with Egardia/Woonveilig alarm control panel.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/alarm_control_panel.egardia/
"""
import logging

import requests

import homeassistant.components.alarm_control_panel as alarm
from homeassistant.const import (
    STATE_UNKNOWN, STATE_ALARM_DISARMED, STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_AWAY, STATE_ALARM_TRIGGERED)

REQUIREMENTS = ['pythonegardia==1.0.36']

_LOGGER = logging.getLogger(__name__)

STATES = {
    'ARM': STATE_ALARM_ARMED_AWAY,
    'DAY HOME': STATE_ALARM_ARMED_HOME,
    'DISARM': STATE_ALARM_DISARMED,
    'HOME': STATE_ALARM_ARMED_HOME,
    'TRIGGERED': STATE_ALARM_TRIGGERED,
    'UNKNOWN': STATE_UNKNOWN,
}

D_EGARDIASYS = 'egardiadevice'
D_EGARDIADEV = 'egardia_dev'
D_EGARDIASRV = 'egardiaserver'
CONF_REPORT_SERVER_CODES_IGNORE = 'ignore'
CONF_REPORT_SERVER_CODES = 'report_server_codes'
CONF_REPORT_SERVER_ENABLED = 'report_server_enabled'
CONF_REPORT_SERVER_PORT = 'report_server_port'


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Egardia platform."""
    device = EgardiaAlarm(
        hass,
        discovery_info['name'],
        hass.data[D_EGARDIASYS],
        discovery_info[CONF_REPORT_SERVER_ENABLED],
        discovery_info[CONF_REPORT_SERVER_CODES] if CONF_REPORT_SERVER_CODES
        in discovery_info else None,
        discovery_info[CONF_REPORT_SERVER_PORT])
    hass.data[D_EGARDIADEV] = device
    # add egardia alarm device
    add_devices([device], True)


class EgardiaAlarm(alarm.AlarmControlPanel):
    """Representation of a Egardia alarm."""

    def __init__(self, hass, name, egardiasystem,
                 rs_enabled=False, rs_codes=None, rs_port=52010):
        """Initialize the Egardia alarm."""
        from pythonegardia import egardiaserver
        self._name = name
        self._egardiasystem = egardiasystem
        self._status = None
        self._rs_enabled = rs_enabled
        if rs_codes is not None:
            self._rs_codes = rs_codes[0]
        else:
            self._rs_codes = rs_codes
        self._rs_port = rs_port

        # configure egardia server, including callback
        if self._rs_enabled:
            # Set up the egardia server
            _LOGGER.info("Setting up EgardiaServer")
            try:
                if D_EGARDIASRV not in hass.data:
                    server = egardiaserver.EgardiaServer('', rs_port)
                    bound = server.bind()
                    if not bound:
                        raise IOError("Binding error occurred while " +
                                      "starting EgardiaServer")
                    hass.data[D_EGARDIASRV] = server
                    server.start()
            except IOError:
                return
            hass.data[D_EGARDIASRV].register_callback(
                self.handle_status_event)

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._status

    @property
    def should_poll(self):
        """Poll if no report server is enabled."""
        if not self._rs_enabled:
            return True
        return False

    def handle_status_event(self, event):
        """Handle the Egardia system status event."""
        statuscode = event.get('status')
        if statuscode is not None:
            status = self.lookupstatusfromcode(statuscode)
            self.parsestatus(status)
            self.schedule_update_ha_state()

    def lookupstatusfromcode(self, statuscode):
        """Look at the rs_codes and returns the status from the code."""
        status = 'UNKNOWN'
        if self._rs_codes is not None:
            statuscode = str(statuscode).strip()
            for i in self._rs_codes:
                val = str(self._rs_codes[i]).strip()
                if ',' in val:
                    splitted = val.split(',')
                    for code in splitted:
                        code = str(code).strip()
                        if statuscode == code:
                            status = i.upper()
                            break
                elif statuscode == val:
                    status = i.upper()
                    break
        return status

    def parsestatus(self, status):
        """Parse the status."""
        _LOGGER.debug("Parsing status %s", status)
        # Ignore the statuscode if it is IGNORE
        if status.lower().strip() != CONF_REPORT_SERVER_CODES_IGNORE:
            _LOGGER.debug("Not ignoring status")
            newstatus = ([v for k, v in STATES.items()
                          if status.upper() == k][0])
            self._status = newstatus
        else:
            _LOGGER.error("Ignoring status")

    def update(self):
        """Update the alarm status."""
        status = self._egardiasystem.getstate()
        self.parsestatus(status)

    def alarm_disarm(self, code=None):
        """Send disarm command."""
        try:
            self._egardiasystem.alarm_disarm()
        except requests.exceptions.RequestException as err:
            _LOGGER.error("Egardia device exception occurred when "
                          "sending disarm command: %s", err)

    def alarm_arm_home(self, code=None):
        """Send arm home command."""
        try:
            self._egardiasystem.alarm_arm_home()
        except requests.exceptions.RequestException as err:
            _LOGGER.error("Egardia device exception occurred when "
                          "sending arm home command: %s", err)

    def alarm_arm_away(self, code=None):
        """Send arm away command."""
        try:
            self._egardiasystem.alarm_arm_away()
        except requests.exceptions.RequestException as err:
            _LOGGER.error("Egardia device exception occurred when "
                          "sending arm away command: %s", err)
