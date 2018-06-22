"""
Support for Arlo Alarm Control Panels.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/alarm_control_panel.arlo/
"""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.components.alarm_control_panel import (
    AlarmControlPanel, PLATFORM_SCHEMA)
from homeassistant.components.arlo import (
    DATA_ARLO, CONF_ATTRIBUTION, SIGNAL_UPDATE_ARLO)
from homeassistant.const import (
    ATTR_ATTRIBUTION, STATE_ALARM_ARMED_AWAY, STATE_ALARM_ARMED_HOME,
    STATE_ALARM_DISARMED)

_LOGGER = logging.getLogger(__name__)

ARMED = 'armed'

CONF_HOME_MODE_NAME = 'home_mode_name'
CONF_AWAY_MODE_NAME = 'away_mode_name'

DEPENDENCIES = ['arlo']

DISARMED = 'disarmed'

ICON = 'mdi:security'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_HOME_MODE_NAME, default=ARMED): cv.string,
    vol.Optional(CONF_AWAY_MODE_NAME, default=ARMED): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Arlo Alarm Control Panels."""
    arlo = hass.data[DATA_ARLO]

    if not arlo.base_stations:
        return

    home_mode_name = config.get(CONF_HOME_MODE_NAME)
    away_mode_name = config.get(CONF_AWAY_MODE_NAME)
    base_stations = []
    for base_station in arlo.base_stations:
        base_stations.append(ArloBaseStation(base_station, home_mode_name,
                                             away_mode_name))
    add_devices(base_stations, True)


class ArloBaseStation(AlarmControlPanel):
    """Representation of an Arlo Alarm Control Panel."""

    def __init__(self, data, home_mode_name, away_mode_name):
        """Initialize the alarm control panel."""
        self._base_station = data
        self._home_mode_name = home_mode_name
        self._away_mode_name = away_mode_name
        self._state = None

    @property
    def icon(self):
        """Return icon."""
        return ICON

    async def async_added_to_hass(self):
        """Register callbacks."""
        async_dispatcher_connect(
            self.hass, SIGNAL_UPDATE_ARLO, self._update_callback)

    @callback
    def _update_callback(self):
        """Call update method."""
        self.async_schedule_update_ha_state(True)

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    def update(self):
        """Update the state of the device."""
        _LOGGER.debug("Updating Arlo Alarm Control Panel %s", self.name)
        mode = self._base_station.mode
        if mode:
            self._state = self._get_state_from_mode(mode)
        else:
            self._state = None

    async def async_alarm_disarm(self, code=None):
        """Send disarm command."""
        self._base_station.mode = DISARMED

    async def async_alarm_arm_away(self, code=None):
        """Send arm away command. Uses custom mode."""
        self._base_station.mode = self._away_mode_name

    async def async_alarm_arm_home(self, code=None):
        """Send arm home command. Uses custom mode."""
        self._base_station.mode = self._home_mode_name

    @property
    def name(self):
        """Return the name of the base station."""
        return self._base_station.name

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_ATTRIBUTION: CONF_ATTRIBUTION,
            'device_id': self._base_station.device_id
        }

    def _get_state_from_mode(self, mode):
        """Convert Arlo mode to Home Assistant state."""
        if mode == ARMED:
            return STATE_ALARM_ARMED_AWAY
        elif mode == DISARMED:
            return STATE_ALARM_DISARMED
        elif mode == self._home_mode_name:
            return STATE_ALARM_ARMED_HOME
        elif mode == self._away_mode_name:
            return STATE_ALARM_ARMED_AWAY
        return mode
